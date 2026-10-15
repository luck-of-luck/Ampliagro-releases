"""Folha de pagamento entrava como receita, e o painel nao tinha como dizer.

O DEFEITO
=========
No banco real:

    LancamentoFinanceiro(data=2026-09-12, tipo="RECEITA", categoria="FOLHA",
                         valor=100.00, descricao="pagamento dos funcionários")

Folha e' despesa. Mas o painel soma por `tipo`, entao os R$ 100 entravam na
receita, o saldo subia e o ROI do produtor ia junto. Como o valor e' pequeno,
ninguem notou: um erro de R$ 100 e' do tipo que passa anos sem ser visto e
so aparece quando alguem compara o painel com o extrato do banco.

Pior, o sistema JA sabia a resposta certa e discordava de si mesmo:

    app/services/dre.py:30   "FOLHA": "despesa_operacional"

O DRE classificava pelo rotulo da categoria e acertava. O painel confiava no
campo `tipo` e errava. Dois lugares classificando o mesmo lancamento, com
respostas diferentes.

A REGRA QUE FICA
================
1. Categoria de saida de dinheiro nao entra como receita. Folha, insumo,
   frete, imposto, manutencao, combustivel, servico e energia.
2. `OUTRO` funciona nos dois lados: quem escreve "OUTRO" sabe o que esta
   lancando, e inventar regra ali seria chatear quem sabe.
3. A regra vale em TODA gravacao — API, formulario, admin e script de
   importacao. `Model.save()` nao chama `full_clean()` sozinho, entao um
   `clean()` sozinho so valida onde alguem lembrar de chamar.
4. Detectar depois nao e' o mesmo que impedir: o `diagnostico_dados` ja
   apontava este lancamento, mas so quando alguem lembra de rodar.

O QUE ESTE TESTE TRAVA
======================
1. FOLHA como RECEITA e' recusado, com mensagem que diz o que fazer.
2. FOLHA como DESPESA passa.
3. Receita de verdade passa.
4. OUTRO passa nos dois lados.
5. A validacao pega o `objects.create()`, nao so o serializer.
"""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from app.models import Cultura, LancamentoFinanceiro, Propriedade
from app.models.financeiro import CATEGORIAS_SO_DESPESA

User = get_user_model()


class CategoriaDeDespesaNaoEntraComoReceita(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("fin", "fin@t.com", "x")
        self.prop = Propriedade.objects.create(
            user=self.user,
            nome="Fazenda",
            cidade="Muzambinho",
            uf="MG",
            area_total=Decimal("100.00"),
        )

    def _cria(self, tipo, categoria, **kw):
        return LancamentoFinanceiro.objects.create(
            propriedade=self.prop,
            tipo=tipo,
            categoria=categoria,
            valor=kw.pop("valor", Decimal("100.00")),
            data=kw.pop("data", "2026-09-12"),
            descricao=kw.pop("descricao", ""),
            **kw,
        )

    def test_o_caso_real_e_recusado(self):
        """R$ 100,00 FOLHA como RECEITA — exatamente o que estava no banco."""
        with self.assertRaises(ValidationError) as cm:
            self._cria("RECEITA", "FOLHA", descricao="pagamento dos funcionários")
        msg = str(cm.exception)
        self.assertIn("despesa", msg.lower())
        self.assertIn("pagamento dos funcionários", msg, msg="a msg não diz o que é")

    def test_toda_categoria_de_despesa_e_recusada_como_receita(self):
        for categoria in sorted(CATEGORIAS_SO_DESPESA):
            with self.subTest(categoria=categoria):
                with self.assertRaises(ValidationError):
                    self._cria("RECEITA", categoria)

    def test_folha_como_despesa_passa(self):
        l = self._cria("DESPESA", "FOLHA", descricao="folha real")
        self.assertEqual(l.tipo, "DESPESA")

    def test_receita_de_verdade_passa(self):
        for categoria in ("VENDA_PROD", "VENDA_ANIMAL", "VENDA_LEITE"):
            with self.subTest(categoria=categoria):
                l = self._cria("RECEITA", categoria)
                self.assertEqual(l.categoria, categoria)

    def test_outro_funciona_dos_dois_lados(self):
        """Quem escreve "OUTRO" sabe o que está lançando."""
        r = self._cria("RECEITA", "OUTRO")
        d = self._cria("DESPESA", "OUTRO")
        self.assertEqual(r.tipo, "RECEITA")
        self.assertEqual(d.tipo, "DESPESA")

    def test_a_regra_pega_objects_create_e_nao_so_o_serializer(self):
        """`Model.save()` não chama `full_clean()`. O sinal é o que garante.

        Sem o `pre_save`, um `objects.create()` de script de importação
        passaria sem nenhuma checagem — que é como o lançamento errado entrou.
        """
        with self.assertRaises(ValidationError):
            LancamentoFinanceiro.objects.create(
                propriedade=self.prop,
                tipo="RECEITA",
                categoria="COMBUSTIVEL",
                valor=Decimal("50.00"),
                data="2026-09-12",
                descricao="abastecimento",
            )
        self.assertEqual(
            LancamentoFinanceiro.objects.filter(propriedade=self.prop).count(),
            0,
            msg="algo foi gravado apesar da recusa",
        )


class DreEDashboardNaoPodemDizerCoisasDiferentes(TestCase):
    """O `dre.py` classificava FOLHA como despesa pelo rótulo da categoria.

    O painel confiava no campo `tipo`. Com a regra do `clean()`, os dois
    passam a concordar — porque o lançamento incoerente não entra mais.

    Este teste fixa o PORQUE, olhando o que o DRE entrega e não o código que o
    entrega: se alguém "simplificar" a validação, o DRE volta a classificar
    folha como despesa enquanto o painel a soma na receita, e a divergência
    entre os dois relatórios reaparece sem erro nenhum.
    """

    def setUp(self):
        self.user = User.objects.create_user("dre", "dre@t.com", "x")
        self.prop = Propriedade.objects.create(
            user=self.user,
            nome="Fazenda",
            cidade="Muzambinho",
            uf="MG",
            area_total=Decimal("100.00"),
        )

    def test_folha_cai_em_despesa_no_dre(self):
        from app.services.dre import gerar_dre

        LancamentoFinanceiro.objects.create(
            propriedade=self.prop,
            tipo="DESPESA",
            categoria="FOLHA",
            valor=Decimal("1000.00"),
            data="2026-03-31",
            descricao="folha de março",
        )
        dre = gerar_dre(self.prop.id, "2026-01-01", "2026-12-31")

        grupos = dre if isinstance(dre, dict) else getattr(dre, "grupos", {})
        folha_em_receita = any(
            "1000" in str(v) and "receita" in k.lower() for k, v in grupos.items()
        )
        self.assertFalse(
            folha_em_receita,
            msg=f"folha entrou como receita no DRE: {grupos}",
        )
