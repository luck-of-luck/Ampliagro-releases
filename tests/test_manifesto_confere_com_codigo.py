"""O manifesto confere com o código?

MEDIDO, 2026-10-05: o documento de arquitectura descreve o sistema que este
projecto **quer** ser, com a confiança de quem descreveu o que **é**. Este
teste é a lista de trabalho: cada item que falha é uma promessa que o código
não cumpre.

O que este teste faz:
1. Para cada promessa do manifesto, verifica se o código a cumpre.
2. Se não cumpre, o teste falha — e a falha é a lista de trabalho.

O que este teste NÃO faz:
- Não corrige o manifesto. A decisão de corrigir o manifesto ou o código é
  do dono do projecto.
- Não mede qualidade. Mede presença/ausência.

A CORRECÇÃO DA POLARIDADE, 2026-10-05
=====================================
Este ficheiro **funcionava ao contrário**, e vale a pena registar porque é um
erro que se repete.

O que estava escrito, nos 10 testes de promessa nao cumprida:

    count = _grep(r"ota_update|firmware_upload|...")
    assert count == 0          # <-- passa porque a promessa NAO e' cumprida

Ou seja: **o teste passava exactamente no caso que descia ser sinal.** E a
consequencia nao era teorica — era esta:

    Alguem implementa OTA como deve ser.
    O teste passa. A suite fica verde. A lacuna FECHOU-SE.
    Nao haxmarcador, nao ha registo, nao ha nada que diga que o manifesto
    deixou de estar em divida. A mudanca passou em silencio.

O inverso e' verdade: o ficheiro original tinha `test_ota_nao_existe` a passar
com OTA ausente, e `test_mqtt_listener_existe` a passar com MQTT presente. A
primeira e' uma promessa em aberto; a segunda e' uma promessa cumprida. **As
duas nao podem ter a mesma polaridade**, e tinham.

A correccao
-----------
Cada promessa em aberto recebeu:

    @pytest.mark.xfail(strict=True, reason="PROPOSTA NAO CUMPRIDA: ...")
    ...
    assert count != 0, (...)    # a promessa tem de se cumprir

`strict=True` e' a parte que importa. Sem ele, o `xfail` mente: quando a
lacuna fecha, o teste passa e o marcador fica la para sempre, a dizer falsehoods.
Com ele:

    | estado da promessa        | pytest              | suite     |
    |---------------------------|---------------------|-----------|
    | em aberto (feature falta) | `x` XFAIL           | **verde** |
    | cumprida (feature feita)  | `F` XPASS(strict)   | **vermelha** |

Ou seja: **implementar a promessa deixa de ser silencioso.** O marcador obriga
a ser removido, e enquanto ele estiver la, `pytest -rxX` mostra a divida com a
sua razao — visivel em CI sem ser ruido.

PROVADO por mutacao, nao por opiniao: injectar `ota_update` em
`app/iot/views.py` e ver o teste ir de `x` a `F`. Restaurado a seguir.

As 2 promessas que ja estao cumpridas (`test_celery_nao_se_arma_sozinho`,
`test_mqtt_listener_existe` ficam sem marcador e com a assercao normal: passa
quando a promessa e' verdade, que e' a polaridade correcta.
"""

import os
import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
APP = RAIZ / "app"


def _grep(padrao: str, raiz: Path = APP) -> int:
    """Conta ocorrências de um padrão em ficheiros .py."""
    count = 0
    for py in raiz.rglob("*.py"):
        try:
            txt = py.read_text(encoding="utf-8", errors="replace")
            count += len(re.findall(padrao, txt))
        except (OSError, UnicodeDecodeError):
            continue
    return count


def _existe(caminho: str) -> bool:
    return (RAIZ / caminho).exists()


# ─────────────────────────────────────────────────────────────────────────────
# As promessas do manifesto, e o que o código diz
# ─────────────────────────────────────────────────────────────────────────────


def test_celery_nao_se_arma_sozinho():
    """O manifesto diz "Motor Proativo Determinístico (Celery + Redis)".

    Realidade: `BEAT_SCHEDULE` só é preenchido se `AMPLIA_CELERY_BEAT=1`.
    Sem essa variável, não há varredura proativa nenhuma.
    """
    txt = (APP / "ia" / "proativo_tasks.py").read_text(encoding="utf-8")
    assert "AMPLIA_CELERY_BEAT" in txt, (
        "O Celery não se arma sozinho. O manifesto diz que o motor proativo "
        "corre em segundo plano, mas sem AMPLIA_CELERY_BEAT=1 não corre."
    )


def test_mqtt_listener_existe():
    """O manifesto diz "MQTT". O listener existe."""
    assert _existe(
        "app/management/commands/mqtt_listener.py"
    ), "O manifesto promete MQTT, mas o listener não existe."


@pytest.mark.xfail(
    strict=True,
    reason="PROPOSTA NAO CUMPRIDA: o manifesto §VII promete OTA sem bootloader. Fecha quando existir upload de firmware OU quando o manifesto deixar de prometer.",
)
def test_ota_nao_existe():
    """O manifesto §VII promete OTA. O código não tem."""
    count = _grep(r"ota_update|firmware_upload|esptool|mpremote")
    assert (
        count != 0
    ), "PROMETIDO E NAO IMPLEMENTADO: o manifesto promete e o codigo nao tem."


@pytest.mark.xfail(
    strict=True,
    reason="PROPOSTA NAO CUMPRIDA: carbono/MRV. Fecha com implementacao OU com o manifesto corrigido. Ver PLANO-EXECUCAO N1.",
)
def test_carbono_nao_tem_implementacao():
    """O manifesto promete carbono/MRV. O código não tem."""
    count = _grep(r"\bMRV\b|GHG ?Protocol|emissoes|carbono_organico")
    assert (
        count != 0
    ), "PROMETIDO E NAO IMPLEMENTADO: o manifesto promete e o codigo nao tem."


# Sem `xfail`, ao contrário dos 10 acima: esta promessa **nao** esta em aberto.
# A leitura de NF-e existe, e a emissao nao existe **de proposito** e por
# documentado. Um `xfail` aqui diria "esta por fazer", e ela nao esta.
def test_a_leitura_de_nfe_existe_e_a_emissao_nao():
    r"""O eixo certo para o NF-e é **ler** vs **emitir** — não tem e não tem.

    MEDIDO 2026-10-05. Este teste era `test_nfe_nao_tem_implementacao` com
    `_grep(r"sefaz|NF-e.*autoriz|portal\.nfe|svrs") == 0`. Dois problemas, e
    ambos;\;\ sao do teste, nao do código:

    **1. Era um `grep`, e o `grep` conta menções.** `app/services/nfe.py` fala
    de SEFAZ em texto, e a partir de ontem conta como implementação. Era o
    mesmo erro que o `4.md` §20 cometido comigo: um padrão que casa numa
    *docstring* não é código.

    **2. O eixo estava errado.** "Tem NF-e" não é uma condição — há três, e
    cada uma tem uma resposta diferente:

    | capacidade | estado | porquê |
    |---|---|---|
    | ler o XML que o produtor traz | **FEITO** | `app/services/nfe.py` |
    | ir buscar à SEFAZ sozinho | **não, e de propósito** | exige certificado A1 |
    | emitir NF-e | **não, e de propósito** | exige PKI |

    E é o ficheiro dele que diz porquê, em prosa: *"Nao chama a SEFAZ. `ClienteDFe`
    fica com o `TODO` explicito... Um stub que devolvesse notas inventadas seria
    exactamente o defeito que o `erp_externo.py` foi corrigido por ter."*

    Emitir NF-e **não** deve ser uma promessa a cumprir por este teste. Exige
    certificado A1 por produtor — o que o `PLANO-EXECUCAO` C3 põe como decisão de
    negócio, não como engenharia.
    """
    from pathlib import Path

    raiz = Path(__file__).resolve().parents[1]

    # ler: tem de existir e de declarar o que faz
    leitura = raiz / "app" / "services" / "nfe.py"
    assert leitura.exists(), (
        "o leitor de NF-e desapareceu. Sem ele o produtor tem de digitar as "
        "notas a mao, uma por uma."
    )
    fonte = leitura.read_text(encoding="utf-8", errors="replace")
    assert "class NotaLida" in fonte, (
        "`app/services/nfe.py` deixou de declarar o que devolve. Um leitor de "
        "NF-e sem tipo de retorno e' um script, nao uma integracao."
    )

    # ir buscar a SEFAZ: tem de continuar NAO feito, e a dizer porquê
    assert "ClienteDFe" in fonte, (
        "O stub `ClienteDFe` desapareceu. Se foi por ter ganhou implementacao, "
        "a decisao de negocio C3 foi tomada e este teste tem de ser reescrito. "
        "Se foi por esquecimento, restaure o TODO: um stub que devolve notas "
        "inventadas e' pior do que a ausencia dele."
    )

    # o que este teste nunca vai exigir: emissao
    assert "TODO" in fonte or "Nao emite" in fonte, (
        "`app/services/nfe.py` deixou de declarar que NAO emite NF-e. "
        "Emitir exige certificado A1 e assinatura XML — se isso mudar, e' a "
        "decisao C3 a ser tomada, e nao um detalhe de codigo."
    )


@pytest.mark.xfail(
    strict=True,
    reason="PROPOSTA NAO CUMPRIDA: telemetria de maquina. Fecha com o importador de CSV (Onda 1.5), que e' CSV primeiro e API nunca.",
)
def test_john_deere_nao_tem_implementacao():
    """O manifesto promete integração com John Deere. O código não tem.

    Nota: "John Deere" aparece em comentários (top_globais.py:2), mas isso
    não é implementação — é menção. O teste verifica padrões de código real.
    """
    count = _grep(r"developer\.deere|api\.deere\.com|johndeere\.com|JDOperationsCenter")
    assert (
        count != 0
    ), "PROMETIDO E NAO IMPLEMENTADO: o manifesto promete e o codigo nao tem."


@pytest.mark.xfail(
    strict=True,
    reason="PROPOSTA NAO CUMPRIDA: GHG Protocol. PLANO-EXECUCAO N1 diz explicitamente NAO fazer — e' produto a inteiro.",
)
def test_ghg_protocol_nao_tem_implementacao():
    """O manifesto promete GHG Protocol. O código não tem."""
    count = _grep(r"GHG ?Protocol")
    assert (
        count != 0
    ), "PROMETIDO E NAO IMPLEMENTADO: o manifesto promete e o codigo nao tem."


@pytest.mark.xfail(
    strict=True,
    reason="PROPOSTA NAO CUMPRIDA: ISOBUS. Mesma familia do John Deere — CSV primeiro, API nunca (N5).",
)
def test_isobus_nao_tem_implementacao():
    """O manifesto promete ISOBUS. O código não tem.

    Nota: "ISO 11783" aparece em vra.py:9 como referência a um padrão de
    prescrição, não como consumo de telemetria ISOBUS. O teste verifica
    padrões de código real.
    """
    count = _grep(r"isobus_client|iso_bus_client|ISO11783.*client|isobus.*telemetria")
    assert (
        count != 0
    ), "PROMETIDO E NAO IMPLEMENTADO: o manifesto promete e o codigo nao tem."


@pytest.mark.xfail(
    strict=True,
    reason="PROPOSTA NAO CUMPRIDA: hora motora. Fecha com o importador de CSV; o receptor (Maquinario.horas_uso) ja existe.",
)
def test_hora_motora_nao_tem_implementacao():
    """O manifesto promete hora motora. O código não tem.

    Nota: "engine_hours" aparece em importar_csv_maquinario.py:108 como
    cabeçalho de CSV — isso é importação, não tracking. O teste verifica
    padrões de tracking real (modelo, view, relatório).
    """
    count = _grep(
        r"hora_motora\s*=|engine_hours\s*=\s*models|hora_motora.*DecimalField|engine_hours.*DecimalField"
    )
    assert (
        count != 0
    ), "PROMETIDO E NAO IMPLEMENTADO: o manifesto promete e o codigo nao tem."


@pytest.mark.xfail(
    strict=True,
    reason="PROPOSTA NAO CUMPRIDA: adicionalidade. Conceito de MRV; N1 diz que nao e' nosso.",
)
def test_adicionalidade_nao_tem_implementacao():
    """O manifesto promete adicionalidade. O código não tem."""
    count = _grep(r"adicionalidade")
    assert (
        count != 0
    ), "PROMETIDO E NAO IMPLEMENTADO: o manifesto promete e o codigo nao tem."


@pytest.mark.xfail(
    strict=True,
    reason="PROPOSTA NAO CUMPRIDA: praticas regenerativas. Conceito de MRV; N1.",
)
def test_regenerativo_nao_tem_implementacao():
    """O manifesto promete regenerativo. O código não tem."""
    count = _grep(r"regenerativ")
    assert (
        count != 0
    ), "PROMETIDO E NAO IMPLEMENTADO: o manifesto promete e o codigo nao tem."


@pytest.mark.xfail(
    strict=True, reason="PROPOSTA NAO CUMPRIDA: Escopo 3. Conceito de MRV; N1."
)
def test_escopo_3_nao_tem_implementacao():
    """O manifesto promete Escopo 3. O código não tem."""
    count = _grep(r"[Ee]scopo ?3")
    assert (
        count != 0
    ), "PROMETIDO E NAO IMPLEMENTADO: o manifesto promete e o codigo nao tem."
