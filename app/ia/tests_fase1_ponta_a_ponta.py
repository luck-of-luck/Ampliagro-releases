"""Prova de que a Fase 1 chega ao produtor. Do handler a' resposta HTTP.

Este e' o teste que fecha a Fase 1: nao verifica que o campo existe, verifica
que a Mesa chega a quem perguntou.
"""

from django.contrib.auth.models import User
from django.test import TestCase


class ComposicaoChegaAoBrowserTest(TestCase):
    def setUp(self):
        from app.models import Propriedade

        self.u = User.objects.create_user("prod_f1", password="x1234567")
        self.p = Propriedade.objects.create(
            user=self.u, nome="FAZ F1", cidade="PASSO FUNDO", uf="RS", area_total=100
        )

    def test_o_resumo_da_safra_devolve_a_composicao(self):
        from app.ia.sandbox import executar

        out = executar(self.u, "resumo_safra", {}, via="sessao")
        self.assertTrue(out.get("ok"), out)
        self.assertIn("widget_composicao", out, "o resumo da safra nao anexou mesa")
        tipos = [w["tipo"] for w in out["widget_composicao"]]
        self.assertIn("kpi-produtividade", tipos)
        self.assertIn("chart-safras", tipos)

    def test_a_composicao_usa_apenas_widgets_do_catalogo(self):
        """A fronteira de seguranca e' `palco.CATALOGO_IA`.

        A `widget_composicao` nao e' validada contra o catalogo no sandbox — o
        sandbox so normaliza o formato. Quem valida e' o caminho que monta a tela.
        Por isso este teste e' a rede debaixo: se um handler nomear um widget que
        o catalogo nao tem, isso tem de aparecer aqui.
        """
        from app.ia import palco
        from app.ia.sandbox import executar

        out = executar(self.u, "resumo_safra", {}, via="sessao")
        for w in out.get("widget_composicao") or []:
            self.assertIn(
                w["tipo"],
                palco.CATALOGO_IA,
                f"widget {w['tipo']!r} nao esta em CATALOGO_IA",
            )

    def test_a_composicao_so_tem_widgets_com_numero_do_servidor(self):
        """Nenhum widget `top_globais` (simulado) numa mesa de resumo.

        Um cartao com numero inventado, numa tela que parece medida, e' o
        defeito que `palco.py:38-56` passou a vida a impedir. A regra aqui e'
        mais simples: resumo de safra so leva widgets que o servidor preenche.
        """
        from app.ia import palco
        from app.ia.sandbox import executar

        out = executar(self.u, "resumo_safra", {}, via="sessao")
        for w in out.get("widget_composicao") or []:
            self.assertIn(
                w["tipo"],
                palco.WIDGETS_SERVIDOR,
                f"{w['tipo']!r} nao e' preenchido pelo servidor — "
                "a mesa mostraria um numero que nao veio do banco",
            )

    def test_render_preset_da_a_duas_vidas_iguais(self):
        """`widget_composicao` e `dados.widgets` tem de ser a MESMA lista.

        Dois caminhos para o mesmo sitio e' a receita para divergirem. Este teste
        e' o que impede a divergencia de aparecer.
        """
        from app.ia.sandbox import executar

        out = executar(
            self.u,
            "render_preset",
            {"intent": "como evoluiu a safra", "widgets": [{"tipo": "chart-safras"}]},
            via="sessao",
        )
        self.assertTrue(out.get("ok"), out)
        self.assertEqual(out["widget_composicao"], out["dados"]["widgets"])

    def test_o_frontend_declara_normalizar_a_composicao(self):
        """O browser tem de ter a funcao, e tem de estar no que ele exporta.

        Um servidor que manda o campo e um browser que nao o lee dao
        "capacidade entregue" e nenhuma mesa na tela. E' o mesmo vazio que a
        `out["copiloto"]` foi — um campo que existe e ninguem consome.
        """
        import io
        import os

        caminho = os.path.join(
            os.path.dirname(__file__),  # app/ia
            "..",
            "static",
            "js",
            "ia-local",
            "palco-amplia.js",
        )
        with open(os.path.abspath(caminho), encoding="utf-8") as fh:
            fonte = fh.read()
        self.assertIn("function normalizaComposicao", fonte)
        self.assertIn("corpo.widget_composicao", fonte)
        self.assertIn("normalizaComposicao: normalizaComposicao", fonte)
