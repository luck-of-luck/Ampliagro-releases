"""Testes do Resumo Gerencial — os 3 graficos e os 4 cards com dado real.

Por que este arquivo existe
---------------------------
A view entregava ``receita_total``/``despesa_total``/``lucro_liquido``, mas o
template lia ``despesas``, ``roi``, ``receitas_meses``, ``despesas_meses`` e
``meses_labels``. Nenhum desses quatro ultimos existia no contexto. Resultado:

* "Receitas vs Despesas" e "Evolucao Financeira": canvas em branco (default "[]")
* "Distribuicao de Custos": ``[30,25,15,10,20]`` hardcoded — grafico de mentira
* card "Despesas": R$ 0,00 para sempre (lia ``despesas``, nao ``despesa_total``)
* card "ROI": 0% para sempre (nunca calculado)

Os testes abaixo travam o comportamento correto E a regressao do grafico falso.
"""

import re
from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import Client, TestCase

from app.models import LancamentoFinanceiro, Propriedade

URL = "/dashboard/resumo/"


def _lancamento(prop, tipo, valor, quando, categoria="OUTRO"):
    return LancamentoFinanceiro.objects.create(
        propriedade=prop,
        tipo=tipo,
        valor=Decimal(str(valor)),
        data=quando,
        categoria=categoria,
        descricao=f"{tipo} teste",
    )


def _rotulo_do_mes(d):
    curtos = [
        "",
        "jan",
        "fev",
        "mar",
        "abr",
        "mai",
        "jun",
        "jul",
        "ago",
        "set",
        "out",
        "nov",
        "dez",
    ]
    return f"{curtos[d.month]}/{str(d.year)[2:]}"


class ResumoGerencialGraficosTest(TestCase):
    """A view precisa entregar as series que o template consome."""

    def setUp(self):
        self.user = User.objects.create_user("fin", password="x")
        self.prop = Propriedade.objects.create(
            user=self.user, nome="Faz Fin", area_total=50, uf="MT", cidade="X"
        )
        self.c = Client()
        self.c.force_login(self.user)

    def _contexto(self):
        r = self.c.get(URL)
        self.assertEqual(r.status_code, 200)
        return r.context

    def test_agora_o_contexto_tem_as_tres_series(self):
        _lancamento(self.prop, "DESPESA", 700, date.today(), "INSUMO")
        _lancamento(self.prop, "RECEITA", 900, date.today(), "VENDA_PROD")
        ctx = self._contexto()
        for chave in (
            "receitas_meses",
            "despesas_meses",
            "meses_labels",
            "custos_labels",
            "custos_valores",
        ):
            self.assertIn(chave, ctx, f"template le {chave} e a view nao passava")
            self.assertTrue(ctx[chave], f"{chave} veio vazio mesmo com lancamento")

    def test_sem_lancamento_a_serie_mantem_12_meses(self):
        """Sem dado a serie ainda tem 12 meses (o eixo existe) e o doughnut
        fica vazio — o template mostra o aviso em vez de um zero falso."""
        ctx = self._contexto()
        self.assertEqual(len(ctx["meses_labels"]), 12)
        self.assertEqual(len(ctx["receitas_meses"]), 12)
        self.assertEqual(ctx["custos_labels"], [])
        self.assertFalse(ctx["tem_serie"])
        self.assertFalse(ctx["tem_custos"])

    def test_serie_tem_12_meses_e_esta_alinhada(self):
        ctx = self._contexto()
        self.assertEqual(len(ctx["meses_labels"]), 12)
        self.assertEqual(len(ctx["receitas_meses"]), 12)
        self.assertEqual(len(ctx["despesas_meses"]), 12)

    def test_janela_termina_no_mes_corrente(self):
        """Regressao: a serie andava para tras a partir de (ano-1, mes+1) e
        gerava set/25..out/24 — invertia o periodo."""
        hoje = date.today()
        ctx = self._contexto()
        # ultimo mes = mes corrente
        self.assertEqual(ctx["meses_labels"][-1], _rotulo_do_mes(hoje))
        # primeiro mes = 11 meses antes. De out/25 ate set/26 sao 12 labels
        # distintos — incluir set/25 daria 13 meses.
        primeiro = date(hoje.year, hoje.month, 1)
        for _ in range(11):
            primeiro = (
                date(primeiro.year - 1, 12, 1)
                if primeiro.month == 1
                else date(primeiro.year, primeiro.month - 1, 1)
            )
        self.assertEqual(ctx["meses_labels"][0], _rotulo_do_mes(primeiro))
        # ordem cronologica crescente. A chave precisa ser (ano, mes): a janela
        # atravessa a virada do ano, e ordenar por (mes, ano) botaria jan/26 na
        # frente de out/25.
        ordem = [
            "jan",
            "fev",
            "mar",
            "abr",
            "mai",
            "jun",
            "jul",
            "ago",
            "set",
            "out",
            "nov",
            "dez",
        ]
        self.assertEqual(
            ctx["meses_labels"],
            sorted(
                ctx["meses_labels"],
                key=lambda s: (int(s.split("/")[1]), ordem.index(s.split("/")[0])),
            ),
        )

    def test_lancamento_do_mes_corrente_cai_no_mes_certo(self):
        hoje = date.today()
        _lancamento(self.prop, "RECEITA", 1000, hoje, "VENDA_PROD")
        ctx = self._contexto()
        rotulo = _rotulo_do_mes(hoje)
        self.assertIn(rotulo, ctx["meses_labels"])
        i = ctx["meses_labels"].index(rotulo)
        self.assertEqual(ctx["receitas_meses"][i], 1000.0)
        self.assertEqual(ctx["despesas_meses"][i], 0.0)

    def test_mes_sem_lancamento_vira_zero_e_nao_pula_mes(self):
        """Bug classico: sem preenchimento o grafico desalinha do label."""
        _lancamento(self.prop, "RECEITA", 500, date.today(), "VENDA_PROD")
        ctx = self._contexto()
        self.assertEqual(len(ctx["receitas_meses"]), 12)
        self.assertEqual(sum(1 for v in ctx["receitas_meses"] if v), 1)
        self.assertEqual(ctx["receitas_meses"].count(0.0), 11)

    def test_receita_e_despesa_no_mesmo_label(self):
        hoje = date.today()
        _lancamento(self.prop, "RECEITA", 800, hoje, "VENDA_PROD")
        _lancamento(self.prop, "DESPESA", 300, hoje, "INSUMO")
        ctx = self._contexto()
        i = ctx["receitas_meses"].index(800.0)
        self.assertEqual(ctx["despesas_meses"][i], 300.0)

    def test_fora_da_janela_fica_de_fora(self):
        _lancamento(self.prop, "RECEITA", 9999, date(2020, 1, 15), "VENDA_PROD")
        ctx = self._contexto()
        self.assertNotIn(9999.0, ctx["receitas_meses"])
        self.assertEqual(ctx["receita_total"], 0.0)

    def test_doughnut_de_custos_e_real(self):
        """Regressao do [30,25,15,10,20] hardcoded."""
        hoje = date.today()
        _lancamento(self.prop, "DESPESA", 400, hoje, "INSUMO")
        _lancamento(self.prop, "DESPESA", 150, hoje, "FOLHA")
        _lancamento(self.prop, "RECEITA", 900, hoje, "VENDA_PROD")
        ctx = self._contexto()
        self.assertIn("Compra de Insumo", ctx["custos_labels"])
        self.assertIn("Folha de Pagamento", ctx["custos_labels"])
        self.assertEqual(ctx["custos_valores"][0], 400.0)  # ordenado por total
        # receita NAO pode entrar na distribuicao de custos
        self.assertNotIn(900.0, ctx["custos_valores"])
        self.assertEqual(sum(ctx["custos_valores"]), 550.0)

    def test_template_nao_tem_dados_fake_hardcoded(self):
        html = self.c.get(URL).content.decode("utf-8")
        # Remove comentarios HTML antes: a propria documentacao do conserto cita
        # o dado falso antigo, e testar no HTML cru daria falso positivo.
        sem_comentarios = re.sub(r"<!--[\s\S]*?-->", "", html)
        self.assertNotIn("[30,25,15,10,20]", sem_comentarios.replace(" ", ""))
        self.assertNotIn("'Insumos','Folha','Manutencao'", sem_comentarios)
        # O padrao antigo (|safe direto na variavel) nao pode voltar
        self.assertNotIn("|safe", sem_comentarios, "grafico nao deve usar mais |safe")
        for marcador in ("g-receitas", "g-despesas", "g-labels", "g-custos-valores"):
            self.assertIn(marcador, html, f"falta o bloco {marcador}")


class ResumoGerencialCardsTest(TestCase):
    """Os 4 cards superiores: chave certa e ROI com regra de nao-dividir."""

    def setUp(self):
        self.user = User.objects.create_user("cards", password="x")
        self.prop = Propriedade.objects.create(
            user=self.user, nome="Faz Cards", area_total=50, uf="MT", cidade="X"
        )
        self.c = Client()
        self.c.force_login(self.user)
        self.hoje = date.today()

    def test_card_despesas_usa_despesa_total(self):
        """O card lia `despesas`; a view passa `despesa_total`."""
        _lancamento(self.prop, "DESPESA", 250, self.hoje, "INSUMO")
        ctx = self.c.get(URL).context
        self.assertEqual(ctx["despesa_total"], 250.0)
        self.assertNotIn(
            "despesas", ctx, "template lia `despesas`, que nao existe mais"
        )

    def test_roi_calculado(self):
        _lancamento(self.prop, "RECEITA", 1000, self.hoje, "VENDA_PROD")
        _lancamento(self.prop, "DESPESA", 250, self.hoje, "INSUMO")
        ctx = self.c.get(URL).context
        self.assertEqual(ctx["roi"], 75.0)

    def test_roi_negativo(self):
        _lancamento(self.prop, "RECEITA", 100, self.hoje, "VENDA_PROD")
        _lancamento(self.prop, "DESPESA", 250, self.hoje, "INSUMO")
        ctx = self.c.get(URL).context
        self.assertEqual(ctx["roi"], -150.0)

    def test_roi_none_sem_receita_e_template_mostra_traco(self):
        """Sem receita a razao nao existe. Antes mostrava 0% (mentira)."""
        _lancamento(self.prop, "DESPESA", 250, self.hoje, "INSUMO")
        ctx = self.c.get(URL).context
        self.assertIsNone(ctx["roi"])
        html = self.c.get(URL).content.decode("utf-8")
        self.assertNotIn(">0%<", html)

    def test_totais_ignoram_fazenda_de_outro_usuario(self):
        outro = User.objects.create_user("outro_fin", password="x")
        p2 = Propriedade.objects.create(
            user=outro, nome="Faz Alheia", area_total=10, uf="MT", cidade="X"
        )
        _lancamento(self.prop, "RECEITA", 100, self.hoje, "VENDA_PROD")
        _lancamento(p2, "RECEITA", 999999, self.hoje, "VENDA_PROD")
        ctx = self.c.get(URL).context
        self.assertEqual(ctx["receita_total"], 100.0)
        self.assertNotIn(999999.0, ctx["receitas_meses"])


class ResumoGerencialVazioTest(TestCase):
    """Fazenda sem lancamento: pagina abre, sem grafico de mentira."""

    def setUp(self):
        self.user = User.objects.create_user("vazio", password="x")
        Propriedade.objects.create(
            user=self.user, nome="Faz Vazia", area_total=10, uf="MT", cidade="X"
        )
        self.c = Client()
        self.c.force_login(self.user)

    def test_pagina_abre_e_avisa_que_nao_ha_dado(self):
        r = self.c.get(URL)
        self.assertEqual(r.status_code, 200)
        ctx = r.context
        self.assertFalse(ctx["tem_serie"])
        self.assertFalse(ctx["tem_custos"])
        self.assertIsNone(ctx["roi"])
        html = r.content.decode("utf-8")
        self.assertIn("Sem lancamentos nos ultimos 12 meses", html)
        self.assertIn("Nenhuma despesa registrada no periodo", html)

    def test_anonimo_redireciona(self):
        self.assertEqual(Client().get(URL).status_code, 302)
