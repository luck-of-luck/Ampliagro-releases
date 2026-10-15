"""`custo_producao.py` reescrito para obedecer à doutrina do próprio projeto.

Este ficheiro documenta **três defeitos** que encontrei ao implementar o item
nº 1 do plano (crédito rural / dados de capacidade de pagamento). Não são
opinião: são observáveis.

O QUE ESTE MÓDULO FAZIA (`custo_producao.py`, antes)

1. `area_total = sum(t.area_hectare for t in talhoes) or Decimal("1.0")`
   `or Decimal("1.0")` existe para evitar divisão por zero — e cumpre esse
   objetivo. Mas o `area_total` que ia para o JSON passava a ser esse 1,0, e o
   produtor via "1 ha" numa fazenda que ninguém mediu.

   Isto é **exactamente** o defeito que `user.py:190-208` já corrigiu com um
   comentário de duas páginas ("A ÁREA É A DA FAZENDA, OU NÃO É NADA") e que
   `proveniencia.py` transformou em tipo. O mesmo bug, noutro ficheiro, por
   não ter sido propagado.

2. `safra.talhoes` — **não existe**. O campo chama-se `talhoes` com
   `related_name="safras_m2m"` (`models/safra.py`), e a área plantada está em
   `area_plantada`, que é NOT NULL. A linha levanta `AttributeError`.

3. `safra.producao_estimada` — **não existe**. O campo é `producao_total`.

O QUE A DOUTRINA DIZ (o próprio repo, não eu)

- `proveniencia.py:98-120`: `SemDado` **recusa-se a ter `valor`**, porque
  "um número sem procedência é pior que a ausência dele".
- `user.py:190-208`: "A conta que o produtor vê e a conta que o sistema usa não
  podem ser coisas diferentes."
- `cotacoes.py:3-7`: "um preço só entra no payload se veio de uma fonte que
  realmente respondeu."

Um `or Decimal("1.0")` num `custo_por_hectare` é um número **sem procedência**
que entra no payload. Num sistema que vai alimentar um **crédito rural**, isso
não éDEVICE um bug de display: é uma capacidade de pagamento ao banco que
não existe.

O QUE MUDEI

`None` quando não há dado, com o motivo. `0,0` continua a ser `0,0` — a
diferença entre "custou zero" e "não há custo registado" é a mesma que a
doutrinaaxiomática exige.
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
    Talhao,
)
from app.services.custo_producao import calcular_custo_producao


class CustoProducaoDoutrinaTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("ana", password="x")
        self.prop = Propriedade.objects.create(
            user=self.user, nome="Fazenda Boa", area_total=100
        )
        self.cultura = Cultura.objects.create(nome="Soja", ativo=True)
        self.safra = Safra.objects.create(
            propriedade=self.prop,
            cultura=self.cultura,
            ano=2026,
            area_plantada=Decimal("50.00"),
            producao_total=Decimal("30000.00"),
        )

    def _despesa(self, valor, categoria="INSUMO"):
        return LancamentoFinanceiro.objects.create(
            propriedade=self.prop,
            descricao="Compra",
            valor=valor,
            tipo="DESPESA",
            categoria=categoria,
            data=date(2026, 1, 15),
            safra=self.safra,
        )

    # ------------------------------------------------------------------
    # Bug 2 e 3 — os campos não existem
    # ------------------------------------------------------------------

    def test_calcular_custo_nao_levanta(self):
        """`safra.talhoes` e `safra.producao_estimada` não existem.

        Antes disto a função levantava `AttributeError` em qualquer safra real
        — ou seja, o módulo nunca funcionou para ninguém.
        """
        r = calcular_custo_producao(self.safra.id)
        self.assertNotIn("error", r, r)
        self.assertEqual(r["safra_id"], self.safra.id)

    def test_usa_area_plantada_e_producao_total(self):
        self._despesa(Decimal("15000.00"))
        r = calcular_custo_producao(self.safra.id)
        # 15.000 em 50 ha = 300/ha. Com o bug do `or 1.0`, daria 15.000/ha.
        self.assertEqual(r["area_total_ha"], 50.0)
        self.assertEqual(r["custo_por_hectare"], 300.0)

    # ------------------------------------------------------------------
    # Bug 1 — o `or` mascarador
    # ------------------------------------------------------------------

    def test_area_zero_nao_vira_um(self):
        """Safra sem área registada: custo/ha é `None`, nunca `1.0`.

        Este é o teste que fixa a correcção. O valor antigo era 1.0 e produzia
        um custo por hectare absurdo sem qualquer aviso.

        Nota sobre o contrato, para não confundir: `area_total_ha` reporta
        `0.0` (o valor registado é mesmo zero) e é `custo_por_hectare` que é
        `None`. É exactamente o que `user.py:209-217` já faz — `area_medida =
        area_total > 0`, e o quociente é `None` quando não há área medida.
        Divisão por área ausente não tem resposta, e é `None` que diz isso.
        """
        self.safra.area_plantada = Decimal("0.00")
        self.safra.save()
        self._despesa(Decimal("1000.00"))

        r = calcular_custo_producao(self.safra.id)

        self.assertEqual(r["area_total_ha"], 0.0)
        self.assertIsNone(
            r["custo_por_hectare"],
            "custo por hectare calculado sobre area inexistente: o produtor "
            "veria um numero que ninguem mediu",
        )
        # E o custo total continua a ser o que é: 1.000. Zero ≠ ausência.
        self.assertEqual(r["custo_total"], 1000.0)
        self.assertIn("motivo", r, "ausencia de dado sem motivo nao ajuda ninguem")

    def test_producao_zero_nao_vira_um(self):
        """Produção zero é dado real. Ausência de produção é outro dado."""
        self.safra.producao_total = Decimal("0.00")
        self.safra.save()
        self._despesa(Decimal("500.00"))

        r = calcular_custo_producao(self.safra.id)

        self.assertEqual(
            r["producao_total"],
            0.0,
            "producao 0 foi tratada como ausente: sao coisas diferentes",
        )
        self.assertIsNone(r["custo_por_unidade"])
        self.assertIn("motivo", r)

    def test_custo_por_unidade_calculado_quando_ha_dado(self):
        self._despesa(Decimal("30000.00"))
        r = calcular_custo_producao(self.safra.id)
        # 30.000 em 30.000 unidades = 1,00/unidade
        self.assertEqual(r["custo_por_unidade"], 1.0)

    # ------------------------------------------------------------------
    # O contrato honesto
    # ------------------------------------------------------------------

    def test_zero_real_continua_zero(self):
        """Sem despesas, custo total é 0 — não None.

        A distinção que este módulo tem de fazer: `0` é uma medição válida
        (não gastou nada), `None` é ausência. Tratar `0` como ausência
        apagaria informação real do produtor.
        """
        r = calcular_custo_producao(self.safra.id)
        self.assertEqual(r["custo_total"], 0.0)
        self.assertIsNotNone(r["custo_total"])

    def test_safra_inexistente(self):
        r = calcular_custo_producao(999999)
        self.assertIn("error", r)

    def test_despesas_apenas_da_safra_conta(self):
        """Despesa de outra safra não entra. O custo é da safra."""
        outra = Safra.objects.create(
            propriedade=self.prop,
            cultura=self.cultura,
            ano=2025,
            area_plantada=Decimal("10.00"),
            producao_total=Decimal("1000.00"),
        )
        self._despesa(Decimal("5000.00"))
        LancamentoFinanceiro.objects.create(
            propriedade=self.prop,
            descricao="Outra safra",
            valor=Decimal("9999.00"),
            tipo="DESPESA",
            categoria="INSUMO",
            data=date(2025, 1, 15),
            safra=outra,
        )

        r = calcular_custo_producao(self.safra.id)
        self.assertEqual(r["custo_total"], 5000.0)

    def test_breakdown_por_categoria(self):
        self._despesa(Decimal("3000.00"), categoria="INSUMO")
        self._despesa(Decimal("2000.00"), categoria="SERVICO")

        r = calcular_custo_producao(self.safra.id)
        self.assertEqual(r["breakdown_categorias"]["INSUMO"], 3000.0)
        self.assertEqual(r["breakdown_categorias"]["SERVICO"], 2000.0)

    def test_talhao_geometrico_nao_altera_area_plantada(self):
        """A área plantada vem da safra, não da soma dos talhões.

        Um talhão pode existir sem estar na safra (área de reserva, APP). Somar
        talhões daria uma área que ninguém plantou.
        """
        Talhao.objects.create(
            propriedade=self.prop, nome="Reserva", area_hectare=Decimal("20.00")
        )
        r = calcular_custo_producao(self.safra.id)
        self.assertEqual(r["area_total_ha"], 50.0)
