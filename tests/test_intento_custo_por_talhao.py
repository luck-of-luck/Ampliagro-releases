"""O handler nao pode divergir do painel.

Se `h_lucro_talhao` recalcular a conta a maneira antiga, o produtor ve um
numero na conversa e outro no ecra, e nao ha nenhuma forma de saber qual e' o
certo. Estes testes atam os dois.
"""

from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from app.models import Cultura, LancamentoFinanceiro, Propriedade, Talhao

D = Decimal


class OHandlerDizOMesmoQueOPainel(TestCase):
    def setUp(self):
        from app.ia.intents3 import h_lucro_talhao

        self.h = h_lucro_talhao
        self.user = User.objects.create_user("joao", "joao@x.com", "s12345678")
        self.prop = Propriedade.objects.create(
            user=self.user, nome="Fazenda", cep="37400000", area_total=D("30")
        )
        self.t1 = Talhao.objects.create(
            propriedade=self.prop, nome="Baixada", area_hectare=D("10")
        )
        self.t2 = Talhao.objects.create(
            propriedade=self.prop, nome="Cercado", area_hectare=D("20")
        )

    def _d(self, talhao, valor, pago=True, tipo="DESPESA"):
        return LancamentoFinanceiro.objects.create(
            propriedade=self.prop,
            tipo=tipo,
            categoria="x",
            valor=D(valor),
            data="2026-03-10",
            talhao=talhao,
            pago=pago,
        )

    def _chama(self):
        return self.h(self.user, {}, {"fontes": []})

    def test_o_ranking_tem_o_custo_por_hectare(self):
        self._d(self.t1, "1000")
        self._d(self.t2, "2000")
        r = self._chama()
        por_nome = {x["talhao"]: x for x in r["dados"]["ranking"]}
        self.assertEqual(por_nome["Baixada"]["custo_por_ha"], D("100.00"))
        self.assertEqual(por_nome["Cercado"]["custo_por_ha"], D("100.00"))

    def test_o_ordenamento_e_por_custo_por_hectare(self):
        """Gastar 1000 em 10 ha e' mais caro por hectare que 1000 em 20.

        A versao antiga ordenava por lucro total e presentava isso como
        "ranking de custo" - as duas coisas respondem a perguntas diferentes.
        """
        self._d(self.t1, "1000")  # 100/ha
        self._d(self.t2, "10000")  # 500/ha
        r = self._chama()
        self.assertEqual(r["dados"]["ranking"][0]["talhao"], "Cercado")

    def test_despesa_pendente_nao_entra_no_ranking(self):
        self._d(self.t1, "1000", pago=True)
        self._d(self.t2, "99999", pago=False)
        r = self._chama()
        nomes = {x["talhao"] for x in r["dados"]["ranking"]}
        self.assertEqual(nomes, {"Baixada"})

    def test_a_despesa_nao_alocada_aparece_no_raciocinio(self):
        self._d(self.t1, "1000")
        self._d(None, "5000")
        r = self._chama()
        self.assertIn("não está vinculada", r["resposta"])
        self.assertEqual(
            r["dados"]["custo_por_talhao"]["nao_alocado"]["despesa"], D("5000")
        )

    def test_o_payload_inteiro_esta_no_dados(self):
        """O painel precisa do quadro completo, nao so do top 8."""
        self._d(self.t1, "1000")
        r = self._chama()
        bloco = r["dados"]["custo_por_talhao"]
        self.assertIn("linhas", bloco)
        self.assertIn("total_despesa", bloco)
        self.assertEqual(len(bloco["linhas"]), 2)

    def test_propriedade_alheia_nao_entra(self):
        outro = User.objects.create_user("maria", "maria@x.com", "s12345678")
        p2 = Propriedade.objects.create(user=outro, nome="Deles", area_total=D("10"))
        t = Talhao.objects.create(propriedade=p2, nome="Deles", area_hectare=D("10"))
        LancamentoFinanceiro.objects.create(
            propriedade=p2,
            tipo="DESPESA",
            categoria="x",
            valor=D("999999"),
            data="2026-03-10",
            talhao=t,
            pago=True,
        )
        r = self._chama()
        self.assertEqual(r["dados"]["custo_por_talhao"]["total_despesa"], D("0"))

    def test_a_fonte_interna_e_declarada(self):
        self._d(self.t1, "1000")
        ctx = {"fontes": []}
        self.h(self.user, {}, ctx)
        self.assertIn("interna:financeiro", ctx["fontes"])

    def test_fazenda_vazia_diz_que_falta_lancar_e_nao_inventa(self):
        r = self._chama()
        self.assertIn("Sem lançamentos", r["resposta"])
        self.assertEqual(r["dados"]["ranking"], [])

    def test_a_artefacto_continua_o_mesmo(self):
        """A chave `artefato` alimenta o painel; mudar a chave parte a tela."""
        r = self._chama()
        self.assertEqual(r["artefato"], ("financeiro/lucro_talhao", "financeiro"))

    def test_o_texto_diz_o_que_falta_e_nao_so_o_que_ha(self):
        self._d(self.t1, "1000")
        self._d(None, "7000")
        self._d(None, "3000")
        r = self._chama()
        self.assertIn("10,000.00", r["resposta"])
        self.assertIn("Cercado", r["resposta"])  # talhao sem lancamento e' nomeado

    def test_o_dinheiro_esta_certo_apos_a_conversao(self):
        """A conta e' `Decimal`; o payload e' JSON. O valor tem de chegar certo.

        O servico converte `Decimal` -> `float` uma vez, na fronteira, porque
        `json.dumps` nao conhece `Decimal` (medido: `TypeError` em
        `Lote3IntentsTest::test_109_lucro_talhao`). A soma e' feita **antes** da
        conversao - e' por isso que 0.1 + 0.2 dá 0.3 e nao
        0.30000000000000004. Este teste existe para fixar essa ordem: se alguem
        converter antes de somar, volta o erro classico do dinheiro.
        """
        self._d(self.t1, "0.1")
        self._d(self.t1, "0.2")
        r = self._chama()
        total = r["dados"]["custo_por_talhao"]["total_despesa"]
        self.assertEqual(total, 0.3)
        # E o servico, antes de converter, continua exato.
        from app.services.custo_talhao import custo_por_talhao

        bruto = custo_por_talhao(self.user)
        self.assertIsInstance(bruto.total_despesa, Decimal)
        self.assertEqual(bruto.total_despesa, D("0.3"))

    def test_o_payload_sobrevive_a_json_dumps(self):
        """O contrato e' JSON. Um `Decimal` a mais e' um 500 em producao."""
        import json

        self._d(self.t1, "1000")
        self._d(self.t1, "250")
        json.dumps(self._chama())  # nao pode levantar
