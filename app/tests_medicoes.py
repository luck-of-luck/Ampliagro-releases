# -*- coding: utf-8 -*-
"""Testes de regressao para as corrigicoes que affirmavam numero sem medir.

Estes testes existem porque cada uma das falhas que corrigi ja tinha passado
por `manage.py check`, por `py_compile` e por revisao visual do diff:

  - `setor-estoque.html` tinha "R$ 487.320,00" LITERAL no HTML, com a view a
    passar `itens` do banco e o template a nao o ler. `check` nao vê numeros
    inventados num template; so uma execucao da view com dados reais ve.
  - `custos.py` tinha `sinal = (1 if tipo == "RECEITA" else 1)`, que compila,
    nao levanta, e nao muda o resultado.
  - `seguro_chuva_param`, `voz_assistente` e `copilot_hedge` devolviam numeros e
    booleanos inventados como se fossem medidos.
"""

from decimal import Decimal

from django.contrib.auth.models import User
from django.db.models import F, Sum
from django.test import Client, TestCase

from app.models import EstoqueItem, Propriedade


class SetorEstoqueMedeTest(TestCase):
    """A tela do setor/estoque tem de medir, nao recitar."""

    def setUp(self):
        self.user = User.objects.create_user("t_setor", password="x")
        self.prop = Propriedade.objects.create(
            user=self.user, nome="Fazenda", area_total=100
        )
        # 10 x 25,00 + 4 x 50,00 + 7 x 0,00 + 1 x 10,00 = 460,00
        EstoqueItem.objects.create(
            propriedade=self.prop,
            nome="Adubo A",
            categoria="INSUMO",
            quantidade=10,
            valor_unitario=Decimal("25.00"),
        )
        EstoqueItem.objects.create(
            propriedade=self.prop,
            nome="Adubo B",
            categoria="DEFENSIVO",
            quantidade=4,
            valor_unitario=Decimal("50.00"),
        )
        # valor_unitario = 0: existe item, nao existe medicao de valor.
        EstoqueItem.objects.create(
            propriedade=self.prop,
            nome="Sem preco",
            categoria="INSUMO",
            quantidade=7,
            valor_unitario=Decimal("0.00"),
        )
        # ruptura real: 1 < minimo 5
        EstoqueItem.objects.create(
            propriedade=self.prop,
            nome="Em ruptura",
            categoria="INSTRUMENTO",
            quantidade=1,
            valor_unitario=Decimal("10.00"),
            quantidade_minima=Decimal("5"),
        )
        self.client.force_login(self.user)

    def test_estatisticas_batem_com_a_base_de_dados(self):
        r = self.client.get("/setor/estoque/")
        self.assertEqual(r.status_code, 200)
        base = EstoqueItem.objects.filter(propriedade=self.prop)
        self.assertEqual(r.context["total_itens"], base.count())
        self.assertEqual(r.context["total_categorias"], 3)
        self.assertEqual(r.context["alertas"], 1)
        # O total vem do banco, nao de um numero escrito a mao aqui. Foi
        # precisamente esse numero fixo que me deu 470 quando a soma dava 460:
        # o teste falhava por causa de mim, nao da view.
        #
        # MEDIDO 2026-10-05: este `esperado` estava errado de outra maneira, e
        # a falha seguinte era `460 != 85`. Somava `valor_unitario` sozinho,
        # dando 25 + 50 + 0 + 10 = 85 — que e' a soma dos PRECOS UNITARIOS,
        # nao o valor do estoque. A view soma `quantidade * valor_unitario`,
        # que e' o que o comentario da linha 33 ja anunciava (460,00).
        #
        # A view estava certa e o teste errado. Um teste que "corrige" uma
        # view boa para a fazer bater com a propria conta e' como um numero
        # inventado entra no sistema: pela porta do teste.
        esperado = base.aggregate(soma=Sum(F("quantidade") * F("valor_unitario")))[
            "soma"
        ]
        self.assertIsNotNone(
            esperado, "o agregado devolveu None — ha itens com valor nulo"
        )
        self.assertEqual(Decimal("460"), esperado, "10x25 + 4x50 + 7x0 + 1x10")
        self.assertEqual(Decimal(r.context["valor_total"]), esperado)
        self.assertTrue(r.context["valor_medido"])

    def test_html_nao_tem_numeros_inventados(self):
        """O R$ 487.320,00 era LITERAL. Este teste e' o que nao o apanhou."""
        html = self.client.get("/setor/estoque/").content.decode("utf-8", "replace")
        for proibido in ("R$ 487.320,00", ">156<", ">8<"):
            self.assertNotIn(
                proibido,
                html,
                "O template voltou a ter um numero literal: %s" % proibido,
            )

    def test_valor_zero_diz_sem_dado(self):
        """`valor_unitario` nao e' gravavel pela API. R$ 0,00 diria que o
        estoque vale nada — que e' uma afirmacao. `sem dado` diz o que sabemos."""
        EstoqueItem.objects.filter(propriedade=self.prop).update(
            valor_unitario=Decimal("0.00")
        )
        r = self.client.get("/setor/estoque/")
        self.assertFalse(r.context["valor_medido"])
        html = r.content.decode("utf-8", "replace")
        self.assertIn("sem dado", html)

    def test_ruptura_so_conta_onde_o_limite_foi_preenchido(self):
        """Onde `quantidade_minima` e' 0 nao ha nada a comparar. Contar um
        alerta ali seria inventar."""
        base = EstoqueItem.objects.filter(propriedade=self.prop)
        alertas = (
            base.filter(quantidade_minima__gt=0)
            .filter(
                quantidade__lt=__import__("django").db.models.F("quantidade_minima")
            )
            .count()
        )
        self.assertEqual(alertas, 1)
        base.update(quantidade_minima=Decimal("0"))
        alertas0 = base.filter(quantidade_minima__gt=0).count()
        self.assertEqual(alertas0, 0)


class WidgetsHonestosTest(TestCase):
    """Widgets que afirmavam capacidade sem a ter."""

    def test_seguro_chuva_nao_afirma_que_nao_houve_perda(self):
        from app.services.top_globais import seguro_chuva_param

        d = seguro_chuva_param(-15, -47)
        self.assertIsNone(
            d["paga"], "'paga: False' afirma que nao ha perda a indenizar"
        )
        self.assertIsNone(d["chuva_60d"])
        self.assertIsNone(
            d["limite"], "'limite: 200' era politica de subscricao inventada"
        )
        self.assertIsNone(d["valor"])
        self.assertTrue(d["motivo"])
        self.assertEqual(d["_evidencia"], "")

    def test_voz_nao_afirma_motor_de_voz(self):
        from app.services.top_globais import voz_assistente

        d = voz_assistente("quanto choveu")
        self.assertFalse(d["tts"], "'tts: True' afirmava um motor que nao existe")
        self.assertFalse(d["stt"])
        self.assertIsNone(d["voz"])
        self.assertTrue(d["motivo"])

    def test_copilot_nao_emite_prosa_inventada(self):
        from app.services.top_globais import copilot_hedge

        d = copilot_hedge("simula hedge 65sc se Chicago -5%")
        self.assertFalse(d["copilot"], "'copilot: True' affirmava um LLM")
        self.assertIsNone(d["resposta"], "a resposta era um dict stringificado")
        self.assertTrue(d["motivo"])

    def test_as_chaves_que_o_frontend_usa_continuam_a_existir(self):
        """Mudar a forma do payload parte o renderizador. As chAVES ficam."""
        from app.services.top_globais import (
            copilot_hedge,
            seguro_chuva_param,
            voz_assistente,
        )

        for d, chaves in (
            (seguro_chuva_param(-15, -47), ["chuva_60d", "limite", "paga", "valor"]),
            (voz_assistente("x"), ["texto", "tts", "stt", "voz"]),
            (copilot_hedge("x"), ["copilot", "resposta"]),
        ):
            for c in chaves:
                self.assertIn(c, d)


class CustosSinalTest(TestCase):
    """`sinal = (1 if RECEITA else 1)` nao mudava nada. Agora diz o que faz."""

    def test_valores_sao_acumulados_em_positivo(self):
        """A despesa e' somada como positiva e classificada depois, por prefixo.
        A soma tem de ser insensivel ao signe guardado no lancamento."""
        import inspect

        from app.api.views import custos

        src = inspect.getsource(custos)
        self.assertNotIn(
            'if lanc.tipo == "RECEITA" else 1',
            src,
            "o ternario sem efeito voltou a estar no codigo",
        )
        self.assertIn("abs(float(lanc.valor))", src)
