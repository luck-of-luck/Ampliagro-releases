"""Um custo por hectare tem de dizer QUAL custo e DE QUE PERÍODO.

O DEFEITO
=========
`kpi-custo` dividia a despesa de TODOS os anos pela área colhida de TODOS
os anos, e o `/api/dashboard` dividia a despesa total pela área total da
propriedade. Para a mesma fazenda, no mesmo dia:

    painel da IA   R$ 176,33/ha   = 420.000 / 2.381,94 ha (3 anos)
    /api/dashboard R$ 338,71/ha   = 420.000 / 1.240 ha (área total)

Dois números, uma tela, nenhum aviso. O produtor multiplica hectares pelo
que leu e contrata semente com isso.

Não é que um dos dois estivesse "errado": medem coisas diferentes. O que era
errado era não dizer qual. Um número sem período não pode ser conferido
contra nada, e o produtor não tem como descobrir que os dois cartões que
lhe mostram o mesmo conceito usam bases diferentes.

A REGRA QUE FICA
================
1. O numerador e o denominador são do MESMO período. Despesa de um ano sobre
   área desse ano.
2. Quando há duas medidas legítimas (área colhida e área plantada), as duas
   saem — com nome, não com o mesmo campo trocado de significado.
3. O período vai no cartão.

O QUE ESTE TESTE TRAVA
======================
1. Despesa de 2024 não é dividida por área de 2026.
2. As duas medidas (colhida, plantada) têm nomes distintos.
3. O cartão diz o ano.
4. Sem despesa nenhuma, não há custo por hectare inventado.
"""

from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from app.ia.palco import validar_estrutura
from app.ia.palco_dados import enriquece
from app.models import Cultura, LancamentoFinanceiro, Propriedade, Safra

User = get_user_model()


class CustoPorHectareDizQual(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("custo_t", "custo_t@t.com", "x")
        self.prop = Propriedade.objects.create(
            user=self.user,
            nome="Fazenda",
            cidade="Muzambinho",
            uf="MG",
            area_total=Decimal("1200.00"),
        )
        self.soja = Cultura.objects.create(nome="Soja")
        self.milho = Cultura.objects.create(nome="Milho")

    def _safra(self, cultura, ano, area, colhida=None):
        return Safra.objects.create(
            propriedade=self.prop,
            cultura=cultura,
            ano=ano,
            area_plantada=Decimal(str(area)),
            area_colhida=Decimal(str(colhida)) if colhida is not None else None,
        )

    def _despesa(self, dia, valor):
        LancamentoFinanceiro.objects.create(
            propriedade=self.prop,
            data=date.fromisoformat(dia),
            tipo="DESPESA",
            valor=Decimal(str(valor)),
        )

    def _kpi(self):
        ws = validar_estrutura([{"tipo": "kpi-custo"}])[0]
        out = enriquece(self.user, [dict(w) for w in ws])
        return out[0].get("config") or {}

    # ───────────────────────────────────────────────────────────────────
    # 1. Numerador e denominador são do mesmo período
    # ───────────────────────────────────────────────────────────────────
    def test_a_despesa_de_um_ano_nao_e_dividida_pela_area_de_outro(self):
        """O defeito exato: 2024 pagada, dividido pela área colhida de 3 anos.

        R$ 420.000 é a despesa de 2024. A área colhida de 2026 é 800 ha.
        A conta honesta é 420.000 / 800 = 525. A conta antiga dividia por
        2.000 ha (a soma de 2024+2025+2026) e dava 210.
        """
        self._safra(self.soja, 2024, 1000.0, colhida=1000.0)
        self._safra(self.milho, 2025, 1000.0, colhida=1000.0)
        self._safra(self.soja, 2026, 800.0, colhida=800.0)
        self._despesa("2024-10-05", "420000.00")

        cfg = self._kpi()

        self.assertEqual(cfg["ano"], 2026, "o cartão não diz de que ano é o custo")
        self.assertEqual(
            cfg["area_colhida"],
            800.0,
            "o denominador é a área de todos os anos. A despesa é de 2024 e a "
            "safra de referência é 2026 — a divisão é de dois períodos.",
        )
        self.assertEqual(cfg["custo_por_ha_colhida"], 525.0)

    def test_o_custo_do_ano_que_e_a_safra_de_referencia(self):
        """A despesa é a do ano da safra, não a soma de todos os anos."""
        self._safra(self.soja, 2024, 1000.0, colhida=1000.0)
        self._safra(self.milho, 2026, 500.0, colhida=500.0)
        self._despesa("2024-03-01", "100000.00")  # 2024
        self._despesa("2026-03-01", "50000.00")  # 2026

        cfg = self._kpi()

        self.assertEqual(cfg["custo_total"], 150000.0, "o total é de todos os anos")
        self.assertEqual(
            cfg["custo_do_ano"],
            50000.0,
            "a despesa do ano da safra tem de ser a de 2026, não a soma nem a de 2024.",
        )
        self.assertEqual(cfg["custo_por_ha_colhida"], 100.0)

    def test_o_periodo_vai_escrito_no_cartao(self):
        """Um custo por hectare sem o ano não pode ser conferido contra nada.

        O produtor que quiser verificar vai ao lançamento. Tem de conseguir
        ler a que período o cartão se refere.
        """
        self._safra(self.soja, 2026, 500.0, colhida=500.0)
        self._despesa("2026-03-01", "50000.00")

        cfg = self._kpi()
        self.assertIn("2026", str(cfg["periodo"]))

    # ───────────────────────────────────────────────────────────────────
    # 2. As duas medidas têm nomes distintos
    # ───────────────────────────────────────────────────────────────────
    def test_area_colhida_e_area_plantada_sao_campos_diferentes(self):
        """A safra plantada e ainda não colhida tem dois custos diferentes.

        Quem já colheu quer saber quanto custou o que colheu. Quem está a
        investir quer saber quanto custou o que plantou. São respostas
        diferentes, e partilhar um campo é como o produtor passa a ler o
        número errado sem perceber.
        """
        self._safra(self.soja, 2026, 500.0, colhida=400.0)
        self._despesa("2026-03-01", "100000.00")

        cfg = self._kpi()

        self.assertEqual(cfg["area_plantada"], 500.0)
        self.assertEqual(cfg["area_colhida"], 400.0)
        self.assertEqual(
            cfg["custo_por_ha_plantada"], 200.0, "100.000 / 500 ha plantadas"
        )
        self.assertEqual(
            cfg["custo_por_ha_colhida"], 250.0, "100.000 / 400 ha colhidas"
        )
        # E os dois são diferentes um do outro — que é o ponto.
        self.assertNotEqual(
            cfg["custo_por_ha_plantada"],
            cfg["custo_por_ha_colhida"],
            "os dois custos deram iguais. Ou a conta está errada, ou a "
            "safra foi toda colhida.",
        )

    # ───────────────────────────────────────────────────────────────────
    # 3. Ausência continua a ser ausência
    # ───────────────────────────────────────────────────────────────────
    def test_sem_despesa_nao_ha_custo_por_hectare(self):
        """Sem despesa não há custo. Um 0,00 afirma que a produção foi de graça."""
        self._safra(self.soja, 2026, 500.0, colhida=500.0)

        cfg = self._kpi()

        self.assertIsNone(
            cfg.get("custo_por_ha_colhida"),
            "sem despesa registada apareceu um custo por hectare. 'R$ 0,00/ha' "
            "e 'não sei' são frases diferentes para quem lê.",
        )

    def test_sem_area_colhida_o_custo_por_colhida_e_ausente(self):
        """Safra plantada e ainda por colher não tem "custo por hectare colhido".

        Dividir por uma área que ninguém colheu seria fabricar uma
        produtividade. O `custo_por_ha_plantada` continua a valer — essa é a
        pergunta de quem está a investir.
        """
        self._safra(self.soja, 2026, 500.0, colhida=None)
        self._despesa("2026-03-01", "100000.00")

        cfg = self._kpi()

        self.assertIsNone(cfg.get("custo_por_ha_colhida"))
        self.assertEqual(
            cfg["custo_por_ha_plantada"], 200.0, "o custo do que foi plantado existe"
        )

    def test_sem_safras_e_sem_despesas_o_cartao_diz_sem_dado(self):
        cfg = self._kpi()
        self.assertEqual(cfg.get("fonte_dado"), "sem_dado")
        self.assertNotIn("custo_por_ha", cfg)
