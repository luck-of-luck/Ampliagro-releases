"""O dataset de rede de preços. E o que ele nao é.

## Os três testes que importam

**`test_amostra_pequena_nao_e_preco_de_referencia`** — 3 transações nao são um
preço de mercado. O serviço devolve o número na mesma (é um dado medido) mas
com `e_preco_de_referencia: False` e um aviso. Esconder o número seria
mentira; publicar sem o `n` também.

**`test_concentracao_mostra_ausencia_de_contrapeso`** — 100% é um mercado sem
negociação. É o número que a Aegro nao dá, e o que vale mais que a mediana.

**`test_lancamento_sem_quantidade_nao_entra`** — a mediana nao pode ser
calculada a partir de `valor/1`. Um item sem quantidade daria um "preço" que é
o valor total, e a mediana seria uma média de vendas de valores diferentes.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from app.models import LancamentoFinanceiro, Propriedade
from app.services.rede_precos import preco_referencia


class RedePrecosTest(TestCase):
    def setUp(self):
        self.u = User.objects.create_user("prod", password="x")

    def _fazenda(self, nome, uf="MT"):
        return Propriedade.objects.create(
            user=self.u,
            nome=nome,
            area_total=Decimal("100.00"),
            uf=uf,
            cidade="Sorriso",
        )

    def _venda(
        self,
        prop,
        qtd,
        preco,
        unidade="SC",
        data=date(2026, 3, 10),
        nome="SOJA EM GRAO",
        tipo="RECEITA",
    ):
        return LancamentoFinanceiro.objects.create(
            propriedade=prop,
            tipo=tipo,
            categoria="VENDA_PROD",
            descricao=f"NF-e {nome}",
            valor=Decimal(str(preco * qtd)).quantize(Decimal("0.01")),
            data=data,
            quantidade=Decimal(str(qtd)) if qtd is not None else None,
            unidade=unidade,
            cfop="5102",
        )

    # ------------------------------------------------------------------
    # A amostra pequena nao se veste de preço de mercado
    # ------------------------------------------------------------------

    def test_amostra_pequena_nao_e_preco_de_referencia(self):
        """3 transações é uma amostra. O serviço diz isso."""
        f = self._fazenda("F1")
        self._venda(f, 100, 150.00)
        self._venda(f, 120, 152.00)
        self._venda(f, 110, 148.00)

        r = preco_referencia(self.u, "SOJA")

        self.assertEqual(r["n_transacoes"], 3)
        self.assertFalse(
            r["e_preco_de_referencia"],
            "3 transacoes declaradas como preco de referencia",
        )
        self.assertIn("amostra", r["aviso"])
        self.assertIn("5", r["aviso"], "o aviso tem de dizer o limiar")

    def test_amostra_suficiente_e_preco_de_referencia(self):
        f = self._fazenda("F1")
        for q, p in (
            (100, 150.0),
            (120, 152.0),
            (110, 148.0),
            (90, 151.0),
            (130, 149.0),
        ):
            self._venda(f, q, p)

        r = preco_referencia(self.u, "SOJA")
        self.assertTrue(r["e_preco_de_referencia"])
        self.assertIsNone(r["aviso"])

    def test_sem_transacoes_nao_inventa_preco(self):
        r = preco_referencia(self.u, "SOJA")
        self.assertEqual(r["n_transacoes"], 0)
        self.assertIsNone(r["concentracao_top1"])
        self.assertFalse(r["e_preco_de_referencia"])
        self.assertIn("quantidade", r["aviso"])
        self.assertEqual(r["unidades"], {})

    # ------------------------------------------------------------------
    # Percentis
    # ------------------------------------------------------------------

    def test_percentis_sao_calculados(self):
        """P25 ≤ mediana ≤ P75, e a mediana está no meio."""
        f = self._fazenda("F1")
        for q, p in (
            (100, 100.0),
            (100, 110.0),
            (100, 120.0),
            (100, 130.0),
            (100, 140.0),
        ):
            self._venda(f, q, p)

        sc = preco_referencia(self.u, "SOJA")["unidades"]["SC"]
        self.assertLessEqual(sc["p25"], sc["mediana"])
        self.assertLessEqual(sc["mediana"], sc["p75"])
        self.assertEqual(sc["min"], 100.0)
        self.assertEqual(sc["max"], 140.0)
        self.assertAlmostEqual(sc["mediana"], 120.0, places=6)

    def test_preco_unitario_e_derivado_e_depende_da_quantidade(self):
        """Duas vendas, mesmo valor, quantidades diferentes, preços diferentes.

        Isto é a razão de a quantidade existir. Sem ela, as duas valeriam
        "preço = valor", e a mediana seria uma média de totais de venda.
        """
        f = self._fazenda("F1")
        a = self._venda(f, 10, 100.0)  # 1000 total -> 100/unidade
        b = self._venda(f, 100, 100.0)  # 10000 total -> 100/unidade
        self.assertEqual(a.preco_unitario, 100.0)
        self.assertEqual(b.preco_unitario, 100.0)

        c = self._venda(f, 10, 50.0)  # 500 total -> 50/unidade
        self.assertEqual(c.preco_unitario, 50.0)

    def test_preco_unitario_e_none_sem_quantidade(self):
        """Sem quantidade, `None` — nao o valor, e nao zero."""
        f = self._fazenda("F1")
        sem = LancamentoFinanceiro.objects.create(
            propriedade=f,
            tipo="RECEITA",
            categoria="VENDA_PROD",
            descricao="NF-e SOJA",
            valor=Decimal("1000.00"),
            data=date(2026, 3, 10),
            quantidade=None,
            unidade="SC",
        )
        self.assertIsNone(sem.preco_unitario)

        zero = self._venda(f, 0, 100.0)
        self.assertIsNone(zero.preco_unitario, "quantidade 0 nao e preco 0")

    # ------------------------------------------------------------------
    # A estrutura: o que a Aegro nao dá
    # ------------------------------------------------------------------

    def test_concentracao_mostra_ausencia_de_contrapeso(self):
        """100% de uma fazenda é um mercado sem negociação."""
        f1 = self._fazenda("F1")
        for _ in range(6):
            self._venda(f1, 100, 150.0)

        r = preco_referencia(self.u, "SOJA")
        self.assertEqual(r["n_fazendas"], 1)
        self.assertEqual(r["concentracao_top1"], 1.0)
        self.assertEqual(r["transacoes_por_fazenda"], {f1.id: 6})

    def test_concentracao_baixa_quando_o_mercado_e_dividido(self):
        f1 = self._fazenda("F1")
        f2 = self._fazenda("F2")
        f3 = self._fazenda("F3")
        for f, n in ((f1, 6), (f2, 3), (f3, 3)):
            for _ in range(n):
                self._venda(f, 100, 150.0)

        r = preco_referencia(self.u, "SOJA")
        self.assertEqual(r["n_fazendas"], 3)
        self.assertAlmostEqual(r["concentracao_top1"], 6 / 12)

    def test_filtro_por_uf(self):
        mt = self._fazenda("MT", uf="MT")
        go = self._fazenda("GO", uf="GO")
        self._venda(mt, 100, 150.0)
        self._venda(go, 100, 170.0)

        self.assertEqual(preco_referencia(self.u, "SOJA", uf="MT")["n_transacoes"], 1)
        self.assertEqual(preco_referencia(self.u, "SOJA")["n_transacoes"], 2)

    def test_despesa_nao_entra_no_preco(self):
        """Só RECEITA é preço. Compra de soja a R$ 90 nao baixa o preço de venda."""
        f = self._fazenda("F1")
        for _ in range(5):
            self._venda(f, 100, 150.0)
        self._venda(f, 100, 90.0, tipo="DESPESA", nome="SOJA compra")

        r = preco_referencia(self.u, "SOJA")
        self.assertEqual(r["n_transacoes"], 5)
        self.assertAlmostEqual(r["unidades"]["SC"]["mediana"], 150.0, places=6)

    # ------------------------------------------------------------------
    # O que nao é comparável
    # ------------------------------------------------------------------

    def test_lancamento_sem_quantidade_nao_entra(self):
        """Um lançamento escrito à mão nao é um preço por unidade."""
        f = self._fazenda("F1")
        for _ in range(6):
            self._venda(f, 100, 150.0)
        LancamentoFinanceiro.objects.create(
            propriedade=f,
            tipo="RECEITA",
            categoria="VENDA_PROD",
            descricao="NF-e SOJA",
            valor=Decimal("150000.00"),
            data=date(2026, 3, 10),
            quantidade=None,
            unidade="",
        )

        r = preco_referencia(self.u, "SOJA")
        self.assertEqual(r["n_transacoes"], 6)
        self.assertEqual(r["descartados_sem_unidade"], 1)

    def test_unidades_diferentes_nao_sao_somadas(self):
        """1 KG de soja e 1 sc de soja são distribuições distintas.

        Somá-las daria uma mediana que nao corresponde a nada que se possa
        vender — e o produtor compara o numero com a oferta de uma
        ele compara a unidade errada.
        """
        f = self._fazenda("F1")
        for _ in range(6):
            self._venda(f, 1000, 2.00, unidade="KG")
        for _ in range(6):
            self._venda(f, 1, 150.00, unidade="SC")

        r = preco_referencia(self.u, "SOJA")
        self.assertEqual(sorted(r["unidades"]), ["KG", "SC"])
        self.assertIn("unidades diferentes", r["aviso"])
        # A concentração conta transações, nao unidades somadas.
        self.assertEqual(r["n_transacoes"], 12)

    def test_produto_inexistente_nao_devolve_preco(self):
        r = preco_referencia(self.u, "GIRASSOL")
        self.assertEqual(r["n_transacoes"], 0)
        self.assertFalse(r["e_preco_de_referencia"])

    def test_fonte_declara_a_convencao_de_percentis(self):
        """Quem compara com outro número precisa de saber a convenção."""
        f = self._fazenda("F1")
        self._venda(f, 100, 150.0)
        self.assertIn("inclusiva", preco_referencia(self.u, "SOJA")["fonte"])
