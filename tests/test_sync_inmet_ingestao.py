"""O clima ingerido tem de ser a MEDICAO DA FONTE — nunca um numero de catalogo.

O DEFEITO QUE ESTE CAMINHO JA TEVE
==================================
`app/management/commands/sync_inmet.py` corre em duas sementeiras:

    seed_telemetry.py:253   call_command("sync_inmet", propriedade=..., horas=24)
    seed_mvp_demo.py:351    call_command("sync_inmet", propriedade=...)

ou seja, o `sync_inmet` decide o clima de todo o ambiente de demonstracao.
E nao tinha NENHUM teste. `tests/test_clima_fonte_real.py` cobre o caminho
do PAINEL (`_get_real_weather`); nada cobria a INGESTAO.

Tres formas de o dado ser falso, todas nesta funcao:

1. **Fonte que responde vazia vira "sincronizada".** O `except Exception` em
   volta do `requests.get` (linha ~169) escreve em `stderr` e segue — ate ai,
   bom. O perigo e' o caminho do meio: a resposta foi 200, `hourly` veio sem
   `time`, `objs` fica vazio, e a Fonte e' escrita na mesma com
   `ultimo_sync` fresco e `ativo=True`. A IA e' consulta essa Fonte e recebe
   "sincronizada, sem dados" — que e' diferente de "nunca perguntou".

2. **Coordenadas erradas em silencio.** Sem estacao e sem gateway, o comando
   cai no fallback fixo de Brasilia (linha ~69). Uma fazenda no Acre recebe
   a temperatura de Brasilia com a certeza de quem mediu.

3. **`None` da fonte virando zero.** `hourly` usa `None` para "sem medicao".
   O mapeamento Open-Meteo -> metricas internas (linhas ~118-126) tem de dar
   MENOS telemetria quando falta, nunca telemetria inventada.

O QUE ESTE TESTE TRAVA
======================
1. Fonte que responde -> telemetria ingerida, com a metrica interna certa e o
   `raw_payload` a dizer de que chave veio.
2. Resposta sem leituras -> **zero** telemetria, e a Fonte NAO fica marcada
   como sincronizada (o ponto 1 acima).
3. `None` / linha curta -> nenhuma leitura inventada (o ponto 3 acima).
4. Sem estacao e sem gateway -> o fallback de Brasilia e' usado, e o comando
   DIZ isso em voz alta (o ponto 2 acima).
5. Estacao ou gateway com coordenadas reais ganha ao fallback: o dado da
   fazenda tem de vencer o default do Brasilia.
6. Sem propriedade -> o comando nao faz HTTP nenhum e nao ingere nada.

NADA aqui fala de rede real: `requests.get` e' substituido em todos os testes.
Estes testes correm offline e nao dependem do Open-Meteo estar de pe.
"""

from __future__ import annotations

from decimal import Decimal
from io import StringIO
from unittest import mock

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command

from app.models import Device, EstacaoMeteo, FonteDadosExterna, Gateway, TelemetryData

User = get_user_model()

#: O fallback que o comando usa quando nao ha coordenada nenhuma. Este valor
#: esta escrito no codigo (linha ~69): se mudar la, este teste tem de mudar
#: aqui — e o teste avisa que mudou.
FALLBACK_BRASILIA = (-15.7939, -47.8828)

#: Resposta Open-Meteo minima: 2 instantes x 2 metricas.
RESPOSTA_OPEN_METEO = {
    "hourly": {
        "time": ["2026-10-01T00:00", "2026-10-01T01:00"],
        "temperature_2m": [21.5, 20.0],
        "precipitation": [0.0, 3.25],
    }
}


@pytest.fixture
def propriedade(db):
    user = User.objects.create_user("sync_inmet_t", "sync_inmet_t@t.com", "x")
    from app.models import Propriedade

    return Propriedade.objects.create(
        user=user,
        nome="Fazenda do Sync",
        area_total=Decimal("500"),
        uf="MT",
        cidade="Primavera do Leste",
    )


def _rodar(*args, **opts):
    """Corre o comando e devolve (stdout, stderr) sem levantar."""
    out, err = StringIO(), StringIO()
    call_command("sync_inmet", *args, stdout=out, stderr=err, **opts)
    return out.getvalue(), err.getvalue()


def _fonte_que_responde(payload=None):
    """`requests.get` mockado a responder `payload` com HTTP 200."""
    req = mock.MagicMock()
    req.return_value.json.return_value = payload or RESPOSTA_OPEN_METEO
    req.return_value.raise_for_status.return_value = None
    return req


# ───────────────────────────────────────────────────────────────────────
# 1. A fonte responde -> a medicao entra, com a proveniencia
# ───────────────────────────────────────────────────────────────────────
def test_fonte_que_responde_ingere_a_medicao_da_fonte(propriedade):
    with mock.patch("requests.get", _fonte_que_responde()):
        _rodar(propriedade=propriedade.id, horas=24, source="open-meteo")

    telemetrias = TelemetryData.objects.filter(propriedade=propriedade)
    # 2 instantes x 2 metricas mapeadas.
    assert telemetrias.count() == 4

    # A metrica interna tem o nome que o resto do sistema usa
    # (TELEMETRY_METRIC_CHOICES), e nao o nome cru da Open-Meteo.
    metricas = set(telemetrias.values_list("metric", flat=True))
    assert metricas == {"temperatura", "chuva"}

    # O valor e' o da fonte, com a casa decimal do model.
    temp = telemetrias.get(metric="temperatura", timestamp__hour=1)
    assert temp.value == Decimal("20.0000")

    # A proveniencia viaja com o numero. Um valor sem origem nao e' auditavel.
    assert temp.raw_payload["source"] == "open-meteo"
    assert temp.raw_payload["open_meteo_key"] == "temperature_2m"


def test_a_ingestao_cria_o_device_virtual_e_a_fonte_externa(propriedade):
    """O device virtual e' o que torna a leitura consultavel mais tarde."""
    with mock.patch("requests.get", _fonte_que_responde()):
        _rodar(propriedade=propriedade.id, horas=24, source="open-meteo")

    device = Device.objects.get(device_eui=f"VIRT-METEO-{propriedade.id:04d}")
    assert device.tipo == "METEO"
    assert device.propriedade_id == propriedade.id
    # Telemetria sem device nao se sabe de onde veio.
    assert TelemetryData.objects.filter(device=device).count() == 4

    fonte = FonteDadosExterna.objects.get(propriedade=propriedade, tipo="OPEN_METEO")
    assert fonte.ativo is True
    assert fonte.ultimo_sync is not None


# ───────────────────────────────────────────────────────────────────────
# 2. Fonte que nao entregou nada -> nada, e sem carimbo de sincronizada
# ───────────────────────────────────────────────────────────────────────
def test_resposta_vazia_nao_marca_a_fonte_como_sincronizada(propriedade):
    """A fonte que nao entregou nada nao pode ficar marcada como entregue.

    Este e' o ponto que o `except` nao cobre: a resposta HTTP foi 200,
    `raise_for_status` nao disparou, e `hourly` veio sem `time`. Uma Fonte
    marcada como sincronizada com `ultimo_sync` fresco e' uma mentira que a
    IA vai ler como "ja consultei, nao ha nada".
    """
    with mock.patch("requests.get", _fonte_que_responde({"hourly": {}})):
        _rodar(propriedade=propriedade.id, horas=24, source="open-meteo")

    assert TelemetryData.objects.count() == 0
    assert not FonteDadosExterna.objects.filter(
        propriedade=propriedade, tipo="OPEN_METEO"
    ).exists()


def test_erro_da_fonte_nao_ingere_e_nao_marca_a_fonte(propriedade):
    """Rede fora -> stderr diz, e o banco fica como estava."""
    with mock.patch("requests.get", side_effect=Exception("sem rede")):
        _, err = _rodar(propriedade=propriedade.id, horas=24, source="open-meteo")

    assert "sem rede" in err
    assert TelemetryData.objects.count() == 0
    assert not FonteDadosExterna.objects.filter(
        propriedade=propriedade, tipo="OPEN_METEO"
    ).exists()


# ───────────────────────────────────────────────────────────────────────
# 3. `None` e linha curta nao viram leitura inventada
# ───────────────────────────────────────────────────────────────────────
def test_linhas_desiguais_nao_produzem_telemetria_inventada(propriedade):
    """`time` com 2 instantes e `temperature_2m` com 1: uma leitura, nao duas.

    O `None` que a fonte usa para "sem medicao" nao pode virar 0.
    """
    resposta = {
        "hourly": {
            "time": ["2026-10-01T00:00", "2026-10-01T01:00"],
            "temperature_2m": [21.5],
            "precipitation": [0.0, None],
        }
    }
    with mock.patch("requests.get", _fonte_que_responde(resposta)):
        _rodar(propriedade=propriedade.id, horas=24, source="open-meteo")

    temps = TelemetryData.objects.filter(metric="temperatura")
    # So a primeira hora tinha leitura.
    assert temps.count() == 1
    assert temps.get().value == Decimal("21.5000")

    # A chuva nunca foi medida na segunda hora: zero ali seria invencao.
    chuva_2a = TelemetryData.objects.filter(metric="chuva", timestamp__hour=1).exists()
    assert not chuva_2a, "a fonte disse None na 2a hora; 0 seria invencao"


# ───────────────────────────────────────────────────────────────────────
# 4. e 5. As coordenadas: o default nao pode vencer a fazenda
# ───────────────────────────────────────────────────────────────────────
def test_a_estacao_meteo_vence_o_fallback_de_brasilia(propriedade):
    EstacaoMeteo.objects.create(
        propriedade=propriedade,
        nome="Estacao da fazenda",
        latitude=Decimal("-54.240000"),
        longitude=Decimal("-54.240000"),
    )
    req = _fonte_que_responde()
    with mock.patch("requests.get", req):
        out, _ = _rodar(propriedade=propriedade.id, horas=24, source="open-meteo")

    enviados = req.call_args.kwargs["params"]
    assert enviados["latitude"] == -54.24
    assert enviados["longitude"] == -54.24
    # Com estacao, o fallback nao foi usado — e o comando nao o anuncia.
    assert "fallback" not in out.lower()


def test_sem_coordenada_o_comando_diz_que_esta_a_usar_brasilia(propriedade):
    """O default precisa de ser audivel.

    Sem estacao e sem gateway o comando mede Brasilia. Nao e' errado — e' melhor
    do que nao medir — mas quem le o dado tem de saber de onde ele veio, e o
    proprio comando tem de deixar isso escrito.
    """
    req = _fonte_que_responde()
    with mock.patch("requests.get", req):
        out, _ = _rodar(propriedade=propriedade.id, horas=24, source="open-meteo")

    enviados = req.call_args.kwargs["params"]
    assert enviados["latitude"] == FALLBACK_BRASILIA[0]
    assert enviados["longitude"] == FALLBACK_BRASILIA[1]
    # E diz. Uma medida sem origem declarada nao e' uma medida.
    assert "fallback" in out.lower()
    assert propriedade.nome in out


def test_o_gateway_tambem_fornece_coordenada(propriedade):
    Gateway.objects.create(
        propriedade=propriedade,
        nome="Gateway da fazenda",
        gateway_eui="AABBCCDD11223344",
        latitude=Decimal("-51.000000"),
        longitude=Decimal("-51.000000"),
    )
    req = _fonte_que_responde()
    with mock.patch("requests.get", req):
        out, _ = _rodar(propriedade=propriedade.id, horas=24, source="open-meteo")

    enviados = req.call_args.kwargs["params"]
    assert enviados["latitude"] == -51.0
    assert "fallback" not in out.lower()


# ───────────────────────────────────────────────────────────────────────
# 6. Sem propriedade nao ha nada a sincronizar
# ───────────────────────────────────────────────────────────────────────
def test_sem_nenhuma_propriedade_o_comando_nao_faz_nada(propriedade):
    """Sem `--propriedade` e sem `--all`: nao e' erro, mas nao ha HTTP nem dados."""
    with mock.patch("requests.get") as req:
        _, err = _rodar(source="open-meteo")
        # Aborta antes de qualquer chamada de rede.
        req.assert_not_called()

    assert "--propriedade" in err
    assert TelemetryData.objects.count() == 0
    assert Device.objects.count() == 0


def test_all_vazio_nao_levanta_e_nao_ingere(db):
    with mock.patch("requests.get") as req:
        out, _ = _rodar(all=True, horas=24, source="open-meteo")
        req.assert_not_called()

    assert TelemetryData.objects.count() == 0
    assert "concluído" in out
