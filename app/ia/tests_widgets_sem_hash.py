"""Os widgets que multiplicavam um hash, e o que inventavam a dizer.

Estes seis foram encontrados por **execução**, não por leitura. Cada teste
diz o número que aparecia, porque um teste que diz "não deve inventar" sem
dizer o que inventava é um teste que não impede nada.

Os números abaixo não são decorativos — foram medidos:

- `ai_detecta_cultura` dava `algodao` para (-23.5, -46.6), `eucalipto` para
  (-15.8, -47.9) e `arroz` para (10, 20). Nenhuma das três tem relação com
  a geografia do ponto. Um hash de coordenadas não sabe o que cresce lá.
- `praga_ai_foto('demo')` e `praga_ai_foto('outra_foto')` davam os dois
  `ferrugem` com `acao: "Pulverizar"`.
- `guidance_ab` punha `_evidencia` = nome do talhão, e `precisao_cm: 2.5`
  escrito à mão na fonte.
- `rota_70_colheitadeiras` punha `_evidencia` = nome da propriedade, e
  `km_total`/`economia_pct`/`tempo_h` a 0.
"""

import ast
import inspect
import pathlib
import unittest

# `EvidenciaSoComConsulta` consultava a base (guidance_ab abre Talhao, rota abre
# Fazenda) e nunca pode passar como `unittest.TestCase` puro: o pytest-django
# só dá acesso à base às classes que herdam de `django.test.TestCase`. Sem isto
# os cinco testes morriam em `RuntimeError: Database access not allowed` — e,
# pior do que vermelho, VERDES para quem não os corre: o ficheiro parecia
# coberto e a garantia de que um widget não inventa precisão nenhuma estava a
# ser testada por testes que não testam nada.
#
# `django.test.TestCase` continua a ser um `unittest.TestCase`, com rollback
# por transação. O `unittest.main()` do fim do ficheiro continua válido.
from django.test import TestCase as DjangoTestCase

from app.services import top_globais as tg
from app.services.erp_externo import webhook_jbs_abate
from app.services.recomendacao_solo import RecomendacaoSoloService

FICHEIRO = (
    pathlib.Path(__file__).resolve().parent.parent / "services" / "top_globais.py"
)


def sem_docstrings():
    arvore = ast.parse(FICHEIRO.read_text(encoding="utf-8"))
    for no in ast.walk(arvore):
        corpo = getattr(no, "body", None)
        if not isinstance(corpo, list) or not corpo:
            continue
        p = corpo[0]
        if (
            isinstance(p, ast.Expr)
            and isinstance(p.value, ast.Constant)
            and isinstance(p.value.value, str)
        ):
            corpo.pop(0)
    return ast.unparse(arvore)


class AiDetectaCulturaNaoAdivinha(DjangoTestCase):
    """#5 — cultura detectada por `sha256(lat,lon) % 7`."""

    def test_um_hash_de_coordenadas_nao_sabe_geografia(self):
        """Os três pontos que medimos, e as três respostas sem relação com
        o lugar. Se a detecção voltar a ser um hash, um destes três pontos
        volta a ter uma cultura inventada."""
        for lat, lon, inventado in (
            (-23.5, -46.6, "algodao"),
            (-15.8, -47.9, "eucalipto"),
            (10.0, 20.0, "arroz"),
        ):
            with self.subTest(lat=lat, lon=lon):
                r = tg.ai_detecta_cultura(lat, lon)
                self.assertNotEqual(
                    r["cultura"],
                    inventado,
                    f"voltou a devolver {inventado!r} por hash de ({lat},{lon})",
                )
                self.assertIsNone(r["cultura"])
                self.assertIsNone(r["confianca"])

    def test_nao_declara_sentinel_2(self):
        r = tg.ai_detecta_cultura(-23.5, -46.6)
        self.assertIsNone(
            r["fonte"],
            "voltou a declarar 'Sentinel-2 AI deterministico' sem haver imagem",
        )

    def test_diz_onde_a_cultura_real_esta(self):
        r = tg.ai_detecta_cultura(-23.5, -46.6)
        self.assertIn("Safra", r["motivo"], "Diz onde está a cultura de verdade")

    def test_modulo_nao_usa_hash_para_classificar(self):
        codigo = sem_docstrings()
        for frag in ("culturas = [", "Sentinel-2 AI deterministico"):
            self.assertNotIn(frag, codigo, f"voltou a {frag!r}")


class PragaAiFotoNaoRecomendaPulverizar(DjangoTestCase):
    """#6 — diagnóstico de praga e acção por `sha256(foto_hash) % 4`."""

    def test_nao_da_diagnostico(self):
        r = tg.praga_ai_foto("demo")
        self.assertIsNone(r["praga"], "voltou a diagnosticar praga por hash")

    def test_nao_da_acao_de_pulverizar(self):
        """Isto é o mais grave dos seis. "Pulverizar" não é um
        diagnóstico, é uma instrução de aplicação de produto — e custava
        sair de um hash de uma string."""
        for h in ("demo", "outra_foto", "foto_do_productor", ""):
            with self.subTest(hash=h):
                self.assertIsNone(
                    tg.praga_ai_foto(h)["acao"],
                    f"voltou a recomendar pulverizar a partir de {h!r}",
                )

    def test_nenhuma_praga_inventada(self):
        for h in ("demo", "outra_foto", "x", "y", "z"):
            r = tg.praga_ai_foto(h)
            self.assertNotIn(
                r["praga"], ("ferrugem", "lagarta", "percevejo", "saudavel")
            )

    def test_default_nao_e_demo(self):
        """O default era a string "demo" — que é o que um cliente que não
        envia nada mandava, e portanto recebia um diagnóstico."""
        sig = inspect.signature(tg.praga_ai_foto)
        self.assertEqual(
            sig.parameters["foto_hash"].default, "", "o default voltou a ser 'demo'"
        )


class EvidenciaSoComConsulta(DjangoTestCase):
    """#7 e #8 — `_evidencia` preenchida sem consultar nada."""

    def test_guidance_ab_nao_declara_ter_mediado(self):
        r = tg.guidance_ab(1)
        self.assertEqual(
            r["_evidencia"],
            "",
            f"evidencia {r['_evidencia']!r} sem sensor de aplicação ligado",
        )

    def test_guidance_ab_nao_inventa_precisao(self):
        r = tg.guidance_ab(1)
        self.assertIsNone(r["precisao_cm"], "voltou a precisão de 2,5 cm à mão")

    def test_rota_nao_declara_ter_calculado(self):
        r = tg.rota_70_colheitadeiras(1)
        self.assertEqual(r["_evidencia"], "", "evidencia sem rota calculada")

    def test_rota_nao_devolve_tres_zeros(self):
        """Três zeros com evidência ao lado é pior que None: o 0 parece
        uma medição e a evidência desliga a dúvida."""
        r = tg.rota_70_colheitadeiras(1)
        for campo in ("km_total", "economia_pct", "tempo_h"):
            self.assertIsNone(r[campo], f"{campo} voltou a 0 sem rota calculada")

    def test_o_que_se_sabe_ainda_e_dito(self):
        """A contagem de máquinas é real e continua a aparecer — só não
        como se fosse uma rota."""
        r = tg.rota_70_colheitadeiras(1)
        self.assertIn("colheitadeiras_ativas", r, "Perdeu-se a informação real")


class RecomendacaoSoloNaoAfirmaQueEstaBom(DjangoTestCase):
    """#13 — `estado_ph: "Bom"` sem análise de pH."""

    class Analise:
        # Nomes como no modelo. `ph` minúsculo: o teste com `pH` passa a
        # testar outra coisa, e falha com AttributeError em vez de dizer
        # o que se está a medir.
        ph = None
        ctc = 20.0
        saturacao_bases_v = 50.0
        calcio_ca = None
        aluminio_al = None

    def test_sem_ph_nao_diz_que_o_solo_esta_bom(self):
        """Dizer que o solo está bom sem ter medido o pH é inventar o que
        se devia estar a medir — e é o que impede o produtor de fazer uma
        calagem de que precisa."""
        r = RecomendacaoSoloService.analisar_solo(self.Analise())
        self.assertIsNone(r["estado_ph"], "voltou a dizer 'Bom' sem pH")

    def test_nomeia_o_que_falta_a_analise(self):
        r = RecomendacaoSoloService.analisar_solo(self.Analise())
        self.assertIn("pH", r["faltando_na_analise"])
        self.assertIn("motivo", r)

    def test_nao_recomenda_fertilizante_placeholder(self):
        r = RecomendacaoSoloService.analisar_solo(self.Analise())
        self.assertIsNone(
            r["recomendacao_npk"],
            "voltou a recomendar 300 kg/ha de 04-14-08 como placeholder",
        )


class ErpExternoNaoInventaRebanho(DjangoTestCase):
    """#14 — stub com 10 721 000 cabeças e `recorde: True` por omissão."""

    def test_stub_nao_devolve_numero_de_jornal(self):
        r = webhook_jbs_abate()
        self.assertIsNone(
            r["dados"]["cabecas"],
            "voltou a devolver cabeças de um artigo de jornal",
        )

    def test_stub_nao_afirma_um_recorde(self):
        self.assertIsNone(
            webhook_jbs_abate()["dados"]["recorde"],
            "um default não pode afirmar um facto sobre o mundo",
        )

    def test_stub_diz_que_nao_tem_origem(self):
        d = webhook_jbs_abate()["dados"]
        self.assertIsNone(d["fonte"], "voltou a citar um jornal como fonte")
        self.assertIn("stub", d["status"])


if __name__ == "__main__":
    unittest.main()
