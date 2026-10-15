"""O MRV visto pela porta do MCP e da IA.

Estes testes nao testam o `mrv.py` — isso e' `tests/test_mrv_carbono.py`.
Testam que a capacidade chega ao MCP e a IA, e o que acontece quando nao
deveria chegar.

A razao de existirem: uma capacidade correcta e inacessivel e' uma capacidade
que nao existe. O `mrv.py` pode estar perfeito e o produtor nunca ver o
numero, se a tool nao estiver no catalogo ou se a IA nao souber que existe.
"""

from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from app.amplia_mcp import TOOLS_CATALOGO, executar_catalogo
from app.models.core import Propriedade, Talhao
from app.models.safra import AplicacaoInsumo, Insumo


class TesteToolNoCatalogo(TestCase):
    """A tool tem de ESTAR no catalogo. Nao basta o servico existir."""

    def test_a_tool_esta_no_catalogo_do_mcp(self):
        nomes = [t["name"] for t in TOOLS_CATALOGO]
        self.assertIn("amplia_inventario_carbono", nomes)

    def test_o_schema_nao_pede_propriedade(self):
        """`propriedade_id` NAO pode ser um campo.

        Se o modelo pode passar `propriedade_id`, o produtor A pede o
        inventario da fazenda do produtor B. A propriedade vem do contexto
        autenticado e nao de um argumento.
        """
        tool = next(
            t for t in TOOLS_CATALOGO if t["name"] == "amplia_inventario_carbono"
        )
        props = tool["inputSchema"].get("properties", {})
        self.assertNotIn(
            "propriedade_id",
            props,
            "a tool aceita `propriedade_id`. Isso e' uma IDOR: o produtor A "
            "pede o inventario da fazenda do produtor B.",
        )

    def test_a_descricao_avisa_que_nao_verifica(self):
        """A descricao e' o que o modelo le ANTES de chamar.

        Se a descricao nao disser que nao emite credito, o modelo pode chamar a
        tool e anunciar o numero como credito de carbono ao produtor. O aviso
        tem de estar AQUI, nao so no retorno.
        """
        tool = next(
            t for t in TOOLS_CATALOGO if t["name"] == "amplia_inventario_carbono"
        )
        desc = tool["description"]
        self.assertIn("NÃO VERIFICA", desc)
        self.assertIn("crédito", desc.lower())
        # e tem de dizer o que nao e' medido, para o modelo nao preencher a
        # lacuna com um palpite
        self.assertIn("Escopo 2", desc)
        self.assertIn("Escopo 3", desc)
        self.assertIn("carbono_negativo", desc)


class TesteToolExecuta(TestCase):
    """A tool tem de funcionar pela porta do MCP, com um user de verdade."""

    def setUp(self):
        self.u = User.objects.create_user("mcp_carbono", password="x1234567")
        self.prop = Propriedade.objects.create(
            user=self.u, nome="Fazenda MCP", area_total=Decimal("200"), uf="MT"
        )

    def test_devolve_o_relatorio_com_o_ano_pedido(self):
        r = executar_catalogo(self.u, "amplia_inventario_carbono", {"ano": 2026})
        self.assertTrue(r["ok"])
        self.assertEqual(r["ano"], 2026)
        self.assertEqual(r["propriedade_id"], self.prop.id)

    def test_sem_propriedade_diz_que_nao_ha_o_que_inventariar(self):
        u_sem = User.objects.create_user("mcp_sem_prop", password="x1234567")
        r = executar_catalogo(u_sem, "amplia_inventario_carbono", {"ano": 2026})
        self.assertFalse(r["ok"])
        self.assertIn("propriedade", r["erro"].lower())

    def test_ano_invalido_diz_qual_o_erro(self):
        r = executar_catalogo(self.u, "amplia_inventario_carbono", {"ano": "dois"})
        self.assertFalse(r["ok"])
        self.assertIn("inteiro", r["erro"])

    def test_o_numero_que_sai_tem_a_fonte_ao_lado(self):
        """Um numero de emissao sem fonte nao e' auditavel.

        Este teste existe porque a tentacao, a primeira vez que isto rodar com
        dados, e' devolver so o total. O total sem fonte e' um numero que o
        produtor nao pode mostrar a ninguem.
        """
        diesel = Insumo.objects.create(
            propriedade=self.prop,
            categoria="COMBUSTIVEL",
            nome="Diesel",
            quantidade=Decimal("500"),
            unidade="L",
            valor_unitario=Decimal("6"),
        )
        talhao = Talhao.objects.create(
            propriedade=self.prop, nome="T", area_hectare=Decimal("50")
        )
        AplicacaoInsumo.objects.create(
            insumo=diesel, talhao=talhao, dose=Decimal("200"), data=date(2026, 4, 1)
        )

        r = executar_catalogo(self.u, "amplia_inventario_carbono", {"ano": 2026})
        linhas = r["escopo_1"]["linhas"]
        self.assertTrue(
            linhas, "ha uma aplicacao de diesel em 2026 e nao devolveu linha"
        )
        for linha in linhas:
            if linha.get("medido"):
                self.assertTrue(
                    linha.get("fator_fonte"),
                    f"a linha {linha.get('categoria')} devolveu numero medido sem "
                    "fator_fonte. Um numero sem fonte nao e' auditavel.",
                )

    def test_a_resposta_carrega_o_aviso_de_nao_verificacao(self):
        """A garantia final: o que a IA le diz que NAO e' credito."""
        r = executar_catalogo(self.u, "amplia_inventario_carbono", {"ano": 2026})
        self.assertFalse(r["pode_ser_verificado"])
        self.assertIn("NAO e' um credito", r["aviso"])
        self.assertIsNone(r["carbono_negativo"])


class TesteCoerenciaComOComparativo(TestCase):
    """O MRV mede alguma coisa que o `comparativo` nao diz que mede?

    O `comparativo` diz que o Ampliagro "nao passa" em G05 (carbono/MRV), e
    isso tem de continuar verdade. Implementar medicao NAO cumpre o G05 inteiro
    — falta verificacao, que e' externa. Se este teste passar, o MRV grew e o
    comparativo tem de ser actualizado; se falhar, alguem esta a anunciar mais
    do que existe.
    """

    def test_o_comparativo_aindiz_que_g05_esta_em_aberto(self):
        from app.amplia_mcp.comparativo import catalogo_comparativo

        cat = catalogo_comparativo()
        g05 = next(
            (c for c in cat.get("capacidades", []) if c.get("id") == "G05"), None
        )

        if g05 is None:
            self.skipTest(
                "o comparativo nao tem 'G05' em `capacidades`. Se a folha "
                "mudar de forma, este teste tem de mudar com ela — nao "
                "desaparecer."
            )

        # `G05` nao pode estar marcado como conforme. Isto nao impede a
        # actualizacao futura — impede que se anuncie MRV completo sem
        # verificador.
        self.assertNotEqual(
            str(g05.get("veredicto", "")).upper(),
            "C",
            "G05 (carbono/MRV) marcado como conforme. MRV exige Medicao, "
            "Relatorio E Verificacao. A verificacao e' externa e nao existe "
            "aqui. Se isto passou, o manifesto tem de ser corrigido primeiro.",
        )
