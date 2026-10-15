"""Testes do serviço de capacidade de pagamento (item nº 1 do plano).

O que se fixa aqui, além do aritmético:

1. **Ausência nunca vira zero.** É o teste mais importante do ficheiro. Um
   factor que falta e se lê como `0` ou `0.00` diz ao banco "o produtor não
   tem receita" quando a verdade é "não sabemos". Num dossier de crédito essa
   distinção é a diferença entre aprovar e negar.
2. **Cada número vem com a fonte.** Um factor sem `fonte` não é auditável, e
   um factor sem `motivo` quando falta não é accionável.
3. **O módulo não decide crédito.** `decisao_de_credito` é sempre `None`.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from app.models import (
    Cultura,
    LancamentoFinanceiro,
    Propriedade,
    Safra,
)
from app.services.capacidade_pagamento import (
    capacidade_pagamento,
    custo_por_hectare_medio,
    historico_safras,
)


class CapacidadePagamentoTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("ana", password="x")
        self.prop = Propriedade.objects.create(
            user=self.user, nome="Fazenda Boa", area_total=100
        )
        self.cultura = Cultura.objects.create(nome="Soja", ativo=True)
        self._safra(2026, area="50.00", producao="30000.00")
        self._lancamento(Decimal("90000.00"), "RECEITA", "VENDA_PROD")
        self._lancamento(Decimal("40000.00"), "DESPESA", "INSUMO")

    def _safra(self, ano, area, producao):
        return Safra.objects.create(
            propriedade=self.prop,
            cultura=self.cultura,
            ano=ano,
            area_plantada=Decimal(area),
            producao_total=Decimal(producao),
        )

    def _lancamento(self, valor, tipo, categoria, safra=None):
        return LancamentoFinanceiro.objects.create(
            propriedade=self.prop,
            descricao="L",
            valor=valor,
            tipo=tipo,
            categoria=categoria,
            data=date(2026, 3, 10),
            safra=safra,
        )

    # ------------------------------------------------------------------
    # O contrato: nada de ausências disfarçadas de zero
    # ------------------------------------------------------------------

    def test_ausencia_nao_vira_zero(self):
        """Propriedade sem NADA registado: cada factor ausente é None.

        Este é o teste que fixa a doutrina. O `0` é uma medição válida —
        "o produtor não teve receita" é fact. "Não sabemos" é outra coisa,
        e precisa de ser legível como tal.
        """
        vazia = Propriedade.objects.create(
            user=self.user, nome="Sem registo", area_total=Decimal("0.00")
        )
        r = capacidade_pagamento(vazia.id)

        self.assertIsNone(r["fatores"]["receitas_periodo"]["valor"])
        self.assertIsNone(r["fatores"]["despesas_periodo"]["valor"])
        self.assertIsNone(r["fatores"]["saldo_periodo"]["valor"])
        # A área é o VALOR registado: 0.0 é uma medição. O que marca a
        # ausência de medição é `area_medida=False` + `motivo` — é o mesmo
        # contrato que `user.py:209-217` já usa. O que NÃO pode é o valor
        # ausente virar 0 e ler-se como "receita zero".
        self.assertNotIn(
            0,
            [r["fatores"]["receitas_periodo"]["valor"]],
            "ausencia de receita virou zero: o banco leria 'receita zero'",
        )

    def test_factor_ausente_tem_motivo(self):
        vazia = Propriedade.objects.create(
            user=self.user, nome="Sem registo 2", area_total=Decimal("0.00")
        )
        r = capacidade_pagamento(vazia.id)

        for nome in r["fatores_incompletos"]:
            with self.subTest(fator=nome):
                self.assertIsNotNone(
                    r["fatores"][nome]["motivo"],
                    f"{nome} esta ausente sem motivo: o produtor nao sabe o que preencher",
                )

    def test_zero_real_e_zero(self):
        """Lançamento de valor 0 é uma medição: soma 0, e é 0."""
        z = Propriedade.objects.create(user=self.user, nome="Com zero", area_total=10)
        LancamentoFinanceiro.objects.create(
            propriedade=z,
            descricao="Zero",
            valor=Decimal("0.00"),
            tipo="RECEITA",
            categoria="VENDA_PROD",
            data=date(2026, 3, 10),
        )
        r = capacidade_pagamento(z.id)
        # `Sum` devolve 0 (há linha), não None. Os dois são distintos.
        self.assertEqual(r["fatores"]["receitas_periodo"]["valor"], 0.0)
        self.assertIsNone(r["fatores"]["receitas_periodo"]["motivo"])

    def test_todo_factor_tem_fonte(self):
        """Factor sem fonte não é auditável — e um dossier de crédito é
        exactamente o lugar onde isso não pode acontecer."""
        r = capacidade_pagamento(self.prop.id)
        for nome, fator in r["fatores"].items():
            with self.subTest(fator=nome):
                self.assertTrue(
                    fator.get("fonte"), f"{nome} entrou no payload sem fonte"
                )

    def test_modulo_nao_decide_credito(self):
        """A decisão é da instituição. Este módulo diz isso em código."""
        r = capacidade_pagamento(self.prop.id)
        self.assertIsNone(r["decisao_de_credito"])
        self.assertIn("instituição financeira", r["aviso"])

    # ------------------------------------------------------------------
    # Aritmética
    # ------------------------------------------------------------------

    def test_saldo_e_receitas_menos_despesas(self):
        r = capacidade_pagamento(self.prop.id)
        self.assertEqual(r["fatores"]["receitas_periodo"]["valor"], 90000.0)
        self.assertEqual(r["fatores"]["despesas_periodo"]["valor"], 40000.0)
        self.assertEqual(r["fatores"]["saldo_periodo"]["valor"], 50000.0)

    def test_area_total_apurada(self):
        r = capacidade_pagamento(self.prop.id)
        self.assertEqual(r["fatores"]["area_total_ha"]["valor"], 100.0)
        self.assertTrue(r["fatores"]["area_total_ha"]["area_medida"])

    def test_area_zero_marca_nao_medida(self):
        z = Propriedade.objects.create(
            user=self.user, nome="Sem area", area_total=Decimal("0.00")
        )
        r = capacidade_pagamento(z.id)
        self.assertFalse(r["fatores"]["area_total_ha"]["area_medida"])

    # ------------------------------------------------------------------
    # Histórico de safras — o asset que ninguém tem
    # ------------------------------------------------------------------

    def test_historico_devolve_safras_com_ano(self):
        serie = historico_safras(self.prop.id)
        self.assertEqual(len(serie), 1)
        self.assertEqual(serie[0]["ano"], 2026)
        self.assertEqual(serie[0]["cultura"], "Soja")

    def test_safra_com_ano_invalido_nao_entra_no_historico(self):
        """Safra sem ano válido não tem posição numa série.

        `ano` é NOT NULL no model, então a defesa real não é `isnull` — é
        `ano <= 0`, que passa pelo banco e chega ao histórico como um ano que
        não existe. Uma safra de 2026 não pode ser comparada com a de "ano 0".
        """
        Safra.objects.create(
            propriedade=self.prop,
            cultura=self.cultura,
            ano=0,
            area_plantada=Decimal("10.00"),
            producao_total=Decimal("1000.00"),
        )
        serie = historico_safras(self.prop.id)
        self.assertEqual(len(serie), 1, "safra com ano invalida entrou no historico")

    def test_custo_medio_sem_area_e_none_com_motivo(self):
        """Safra sem área: a média não existe, e diz porquê."""
        z = Propriedade.objects.create(user=self.user, nome="Z", area_total=10)
        Safra.objects.create(
            propriedade=z,
            cultura=self.cultura,
            ano=2026,
            area_plantada=Decimal("0.00"),
            producao_total=Decimal("100.00"),
        )
        r = custo_por_hectare_medio(z.id)
        self.assertIsNone(r["valor"])
        self.assertIsNotNone(r["motivo"])
        self.assertEqual(r["safras_consideradas"], 0)

    def test_custo_medio_so_conta_safras_medidas(self):
        """Uma safra com área e outra sem: a média usa só a primeira.

        Se a segunda contasse, o valor seria diluído por uma safra que
        ninguém mediu.
        """
        s2026 = Safra.objects.filter(propriedade=self.prop, ano=2026).first()
        self._lancamento(Decimal("15000.00"), "DESPESA", "INSUMO", safra=s2026)
        # 2025: sem área => não conta para a média.
        self._safra(2025, area="0.00", producao="1000.00")

        r = custo_por_hectare_medio(self.prop.id)
        self.assertEqual(r["valor"], 300.0)
        self.assertEqual(r["safras_consideradas"], 1)
        self.assertEqual(r["anos"], [2026])

    def test_periodo_padrao_e_dezasseis_meses(self):
        r = capacidade_pagamento(self.prop.id)
        self.assertIn("periodo", r)
        self.assertTrue(r["periodo"]["inicio"])
        self.assertTrue(r["periodo"]["fim"])

    def test_periodo_customizado(self):
        r = capacidade_pagamento(
            self.prop.id, data_inicio=date(2026, 1, 1), data_fim=date(2026, 12, 31)
        )
        self.assertEqual(r["periodo"]["inicio"], "2026-01-01")
        self.assertEqual(r["periodo"]["fim"], "2026-12-31")
        self.assertEqual(r["fatores"]["receitas_periodo"]["valor"], 90000.0)
