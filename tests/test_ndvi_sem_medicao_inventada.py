"""NDVI: sem fonte, sem numero. Medido, nao lido.

O verificador (scripts/verificar_regressoes.py) checava NDVI com
`"import hashlib" in codigo` e `"0.88" in codigo`. Responde a "esta escrito
assim?".

Estes testes respondem a "o produtor pode estar a ler um NDVI que nao existe?".

O QUE MUDOU (FILA #3, P1, fechado em b604f88)
=============================================
`ndvi_medio` era:

    max(0.4, min(0.88, 0.55 + sha256(talhao_id-semana) % 300 / 1000))

Ou seja: um numero entre 0.40 e 0.88 derivado de um hash do id do talhao e da
semana. Dois talhoes davam dois numeros diferentes, e a semana mudava o numero.
E o docstring chegou a dizer "NDVI real por talhao". Nao usava. Um produtor
decidia adubar por uma medida de satelite que nunca foi feita.

Agora, sem fonte Copernicus configurada, `ndvi_medio` e' None e o payload diz
porque.

O TESTE QUE APANHA O DEFEITO
============================
O hash tornava o resultado VARIAVEL por talhao. E' esse o sintoma observavel, e
e' o que `test_dois_talhoes_nao_dam_ndvi_diferentes` mede: com o defeito, dois
talhoes devolvem numeros diferentes; sem ele, devolvem a mesma coisa — `None`.
"""

import datetime

import pytest

from app.services.ndvi import NDVIService

pytestmark = pytest.mark.django_db


class TestSemFonteNaoHaNumero:
    """O caso normal. Sem credencial Copernicus nao ha NDVI, e diz-se."""

    def test_ndvi_medio_e_none(self):
        r = NDVIService.process_talhao_ndvi(1)
        assert r["ndvi_medio"] is None, (
            f"ndvi_medio {r['ndvi_medio']!r} sem fonte Copernicus. "
            f"NDVI e' uma medicao: sem imagem nao ha medida."
        )

    def test_fonte_dado_diz_indisponivel(self):
        """O valor None sozinho nao chega: o produtor precisa de saber porquê.

        E' a decisao D1 — numero sem fonte e' `None` COM o motivo. Um None
        mudo e' indistinguivel de um bug.
        """
        r = NDVIService.process_talhao_ndvi(1)
        assert r["fonte_dado"] == "indisponivel", (
            f"fonte_dado {r['fonte_dado']!r}: o valor ausente tem de se declarar"
        )
        assert r["motivo"], (
            "sem valor, tem de haver motivo. None mudo nao avisa ninguem"
        )

    def test_data_de_captura_e_none(self):
        """A data de captura de um dado que nao existe e' a mesma mentira.

        Um NDVI de 12 de marco com `data_captura` de marco deste ano faz o
        produtor acreditar que a imagem existe.
        """
        r = NDVIService.process_talhao_ndvi(1)
        assert r["data_captura"] is None, (
            f"data_captura {r['data_captura']!r} sem imagem de satelite"
        )


class TestNuncaUmNumeroInventado:
    """Nenhum campo pode ser um numero quando nao ha fonte."""

    @pytest.mark.parametrize(
        "campo",
        ["ndvi_medio", "cobertura_nuvens", "data_captura", "satelite", "sanidade"],
    )
    def test_campo_nao_e_numero(self, campo):
        v = NDVIService.process_talhao_ndvi(7)[campo]
        assert (
            not isinstance(v, (int, float))
            or isinstance(v, bool) is False
            and v is None
            or v is None
        ), f"{campo} devolveu {v!r} sem fonte. So pode ser None."

    def test_nenhum_valor_cai_no_intervalo_do_defeito(self):
        """O defeito antigo produzia sempre um valor entre 0.40 e 0.88.

        Varredura por todos os campos: se algum devolver um numero decimal
        dentro da janela antiga, ha um hash algures a limpo.
        """
        r = NDVIService.process_talhao_ndvi(3)
        for k, v in r.items():
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                assert not (0.40 <= float(v) <= 0.88), (
                    f"{k} = {v}: dentro da janela do NDVI inventado (0.40-0.88)"
                )


class TestNaoVariaPorTalhao:
    """O TESTE QUE APANHA O DEFEITO.

    O hash era `sha256(talhao_id-semana)`, por isso o resultado dependia do id.
    Este e' o sintoma observavel do P0, e o verificador nunca o podia ver porque
    procurava `import hashlib` e nao o resultado.
    """

    def test_dois_talhoes_dao_o_mesmo_valor(self):
        a = NDVIService.process_talhao_ndvi(1)
        b = NDVIService.process_talhao_ndvi(999)
        assert a["ndvi_medio"] == b["ndvi_medio"] is None, (
            f"talhoes diferentes deram NDVI diferente: {a['ndvi_medio']!r} vs "
            f"{b['ndvi_medio']!r}. Houve aleatoriedade no resultado."
        )

    def test_o_mesmo_talhao_da_o_mesmo_valor(self):
        """Sem fonte, repetir a chamada nao pode mudar nada."""
        v1 = NDVIService.process_talhao_ndvi(42)["ndvi_medio"]
        v2 = NDVIService.process_talhao_ndvi(42)["ndvi_medio"]
        assert v1 == v2 is None, f"duas chamadas, dois valores: {v1!r} e {v2!r}"

    def test_id_inexistente_nao_cria_numero(self):
        """Um talhao que nao existe nao pode devolver uma medida inventada."""
        r = NDVIService.process_talhao_ndvi(10**9)
        assert r["ndvi_medio"] is None, "talhao inexistente produziu NDVI"

    def test_nao_depende_da_semana(self):
        """O defeito tinha a semana dentro do hash.

        Este teste nao congela o relogio — so verifica que duas talhoes
        quaisquer, no mesmo instante, nao divergem. Se alguem voltar a meter
        a data dentro de um hash, este teste pega.
        """
        antes = datetime.datetime.now().isocalendar()[1]
        r = NDVIService.process_talhao_ndvi(5)
        depois = datetime.datetime.now().isocalendar()[1]
        assert r["ndvi_medio"] is None, (
            f"semana {antes}-{depois}: o valor dependeu da data"
        )


class TestPayloadCompleto:
    """O frontend le estas chaves todas. Uma em falta parte o painel."""

    def test_tem_todas_as_chaves_do_payload(self):
        r = NDVIService.process_talhao_ndvi(1)
        esperadas = {
            "talhao_id",
            "ndvi_medio",
            "cobertura_nuvens",
            "data_captura",
            "satelite",
            "sanidade",
            "heatmap_url",
            "fonte_dado",
            "motivo",
        }
        em_falta = esperadas - set(r)
        assert not em_falta, f"faltam chaves no payload: {sorted(em_falta)}"

    def test_talhao_id_volta_igual(self):
        """O frontend sabe que talhao esta a ver. Um id trocado e' um bug de ecrã."""
        assert NDVIService.process_talhao_ndvi(77)["talhao_id"] == 77

    def test_heatmap_url_e_none_sem_imagem(self):
        """Um URL de heatmap que aponta para nada e' pior que nenhum."""
        r = NDVIService.process_talhao_ndvi(1)
        assert r["heatmap_url"] is None, f"heatmap_url {r['heatmap_url']!r} sem imagem"


# ──────────────────────────────────────────────────────────────────────────
# MUTATION CHECK — o que foi injectado para confirmar que estes testes partem
# --------------------------------------------------------------------------
# Reintroduzi o defeito dentro de `_buscar_sentinel2`, devolvendo em vez de
# None. Quatro mutacoes, todas injectadas e todas correram estes testes:
#
#   1. o defeito exacto — max(0.4, min(0.88, 0.55 + sha256(talhao) % 300/1000))
#   2. valor FIXO — {"ndvi_medio": 0.72}
#   3. valor fixo + data_captura de hoje
#   4. SO a data_captura de hoje, com ndvi_medio a None
#
# Resultados: 1, 2 e 3 partiram 10 testes cada. A 4 partiu 3.
#
# A 4 e' a que importa. E' a mentira pequena — o numero honesto ao lado de uma
# data que nao existe — e so dois testes a apanham. Um teste so de "tem de ser
# None" passaria com ela la dentro.
#
# PORQUE O VERIFICADOR NAO APANHAVA NENHUMA DAS QUATRO
# Ele procurava `import hashlib` e `0.88` no texto. Na mutacao 1 estaria
# "correcto": encontraria as duas palavras e acusaria defeito. Nas mutacoes 2,
# 3 e 4 nao encontraria nada e diria "ok". Nos quatro casos estaria a responder
# a uma pergunta que ninguem fez.
#
# UM ERRO DESTE PROCESSO, PARA QUE NAO SE REPITA
# A primeira versao deste mutation check substituiu `return None` por codigo com
# 8 espacos, e a linha tem 12. Saiu IndentationError, o pytest nao conseguiu
# recolher o modulo, e o harness contou "PARTEU". Um ficheiro partido nao e' um
# teste a funcionar: e' o mesmo erro da #73 uma camada acima — dar confianca
# sem a medicao. A versao corrigida valida a sintaxe antes de contar.
# --------------------------------------------------------------------------
