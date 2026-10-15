"""O rotulo do KPI nao pode voltar a ser invisivel nem a cortar o texto.

O QUE PARTIU, MEDIDO NO DOM
============================
Antes da correccao, em `http://127.0.0.1:8001/` (playwright):

    .amp-kpi__label
      texto            "ÃƒÂ<U+0081>rea Total"     <- mojibake, triplo
      altura            0 px                      <- INVISIVEL
      flexShrink        1
      whiteSpace        nowrap                    <- herdado
      scrollWidth       65 px
      clientWidth       48 px                    <- transborda

Tres defeitos independentes, e so um deles era o que se via:

1. **A altura zero.** Nao era "o texto era pequeno". O contentor do widget
   tem 62 px de altura util e o conteudo (rotulo 13 + valor 50 + legenda 23
   + gaps 8 = 94 px) nao cabe. Com `flex-shrink: 1` herdado de
   `.amp-kpi > *`, o flex encolhe os tres na proporcao e o rotulo — o mais
   pequeno — vai a zero. Um rotulo de zero altura nao e' um rotulo pequeno:
   e' um rotulo que nao existe.

2. **O `nowrap` herdado.** `white-space` e' propriedade HERDADA. MEDIDO na
   cadeia:

       .widget-content     nowrap     <- a origem
       .amp-kpi            nowrap     herdado
       .amp-kpi__label     nowrap     herdado

   Nenhuma regra do repo define `nowrap` no rotulo. O `.widget-content`
   poe-o para as tabelas e listas nao partirem as celulas — e essa e' a
   razao certa. Mas por isso `break-words` no JS **nao resolvia nada**:
   nao ha palavra para quebrar enquanto o espaco for `nowrap`. Este e' o
   ponto que custou mais tempo e que nao se adivinha: a peca que faltava
   nao era `overflow-wrap`, era `white-space`.

3. **O mojibake.** `app/static/js/pagina-index.js` tinha a codificacao
   TRIPLA em 690 linhas. Reparado; `tests/test_mojibake_js.py` trava.

O QUE ESTES TESTES FAZEM
========================
Nao medem o browser — medem o que produz o browser. Um teste de DOM
precisaria de um servidor a correr; estes verificam as tres causas, que sao
estaveis no ficheiro, e cada uma com o sintoma que produz.

O `white-space: normal` tem de ser declarado no PROPRIO rotulo. Nao
bastaria porem no `.widget-content`, porque ai partir-se-iam as celulas
das tabelas — que e' o que aquele `nowrap` resolve. A excecao e' local ao
KPI, e so porque um KPI e' texto corrido.
"""

import pathlib
import re
import unittest

RAIZ = pathlib.Path(__file__).resolve().parents[1]
CSS = RAIZ / "app" / "static" / "css" / "paginas" / "dashboard-index.css"
JS = RAIZ / "app" / "static" / "js" / "pagina-index.js"


def regra_do_rotulo():
    """O bloco CSS do `.amp-kpi__label` mais especifico."""
    t = CSS.read_text(encoding="utf-8")
    seletor = ".bento-block .widget-content .amp-kpi__label"
    i = t.find(seletor)
    if i == -1:
        return None
    j = t.find("}", i)
    return t[i : j + 1]


class RotuloKpiTest(unittest.TestCase):
    def test_a_regra_do_rotulo_existe(self):
        bloco = regra_do_rotulo()
        self.assertIsNotNone(
            bloco,
            "nao encontrei a regra `.bento-block .widget-content "
            ".amp-kpi__label` em %s" % CSS.name,
        )

    def test_o_rotulo_declara_white_space_normal(self):
        """A peca que faltava. `nowrap` e' HERDADO do `.widget-content`.

        Sem isto, qualquer classe de quebra de palavra no JS e' inerte:
        nao ha palavra para quebrar num espaco `nowrap`.
        """
        bloco = regra_do_rotulo()
        self.assertIn(
            "white-space: normal",
            bloco,
            "o rotulo do KPI nao declara `white-space: normal`.\n\n"
            "MEDIDO antes da correccao: a cadeia de herencia era\n"
            "    .widget-content  nowrap   <- a origem\n"
            "    .amp-kpi         nowrap   herdado\n"
            "    .amp-kpi__label  nowrap   herdado\n"
            "e `scrollWidth` era 65 px contra `clientWidth` de 48 px.\n\n"
            "Nao vale a pena po-lo no `.widget-content`: e' ai que o `nowrap` "
            "existe para as tabelas e listas nao partirem as celulas. A "
            "excepcao e' local ao KPI.",
        )

    def test_o_rotulo_nao_encolhe_a_zero(self):
        """`flex-shrink: 0` — sem isto o rotulo fica com ALTURA ZERO.

        MEDIDO: conteudo 94 px dentro de 62 px uteis, com `flex-shrink: 1`
        herdado. O flex encolhe os tres filhos na proporcao e o rotulo, o
        mais pequeno, vai a zero. Um rotulo de zero altura nao se le.
        """
        bloco = regra_do_rotulo()
        self.assertIn(
            "flex-shrink: 0",
            bloco,
            "o rotulo do KPI nao declara `flex-shrink: 0`. Sem isto volta a "
            "ter 0 px de altura quando o conteudo nao cabe no widget, e o "
            "produtor ve um numero sem saber de que e'.",
        )

    def test_o_rotulo_quebra(self):
        """`overflow-wrap: anywhere` — o texto quebra em vez de transbordar."""
        bloco = regra_do_rotulo()
        self.assertIn(
            "overflow-wrap: anywhere",
            bloco,
            "o rotulo do KPI nao declara `overflow-wrap: anywhere`, ou seja "
            "o texto transborda em vez de quebrar. MEDIDO antes: 65 px de "
            "conteudo numa caixa de 48 px.",
        )

    def test_o_js_nao_poe_truncate_no_rotulo(self):
        """`truncate` no JS era `white-space:nowrap` + `overflow:hidden`.

        Numa cadeia de flex-column com `overflow:hidden` no contentor, um
        `nowrap` dava largura correcta e altura colapsada. Tirar `truncate`
        do markup e' metade da correccao; a outra metade e' o `white-space`
        no CSS, que o teste anterior mede.
        """
        t = JS.read_text(encoding="utf-8")
        i = t.find("amp-kpi__label")
        self.assertNotEqual(i, -1, "nao encontrei amp-kpi__label no JS")
        linha = t[i : t.find("\n", i)]
        self.assertNotIn(
            "truncate",
            linha,
            "o markup do rotulo do KPI voltou a levar `truncate`. Era o que "
            "dava `white-space: nowrap` ao rotulo e altura zero.",
        )
        self.assertIn(
            "break-words",
            linha,
            "o markup do rotulo do KPI devia ter `break-words` para o texto "
            "quebrar no JS tambem. O CSS e' a garantia; esta e' a intencao.",
        )


if __name__ == "__main__":
    unittest.main()
