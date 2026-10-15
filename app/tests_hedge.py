from django.test import TestCase

from app.services.hedge import hedge_recomendado, simular_com_hedge


class HedgeTest(TestCase):
    def test_ganho_50pct(self):
        h = hedge_recomendado(80, 85, 1000, 65, 0.5)
        # sc_total 65*1000=65000, sc_travado 32500, ganho = 32500*(85-80)=162500
        self.assertEqual(h["ganho_hedge"], 162500)
        self.assertEqual(h["queda_pct"], 5.88)

    def test_simular_com_hedge(self):
        s = simular_com_hedge(
            {
                "area_ha": 1000,
                "produtividade_sc_ha": 65,
                "preco_sc": 80,
                "custo_ha": 4200,
            },
            85,
            0.5,
        )
        # preco_efetivo 50%*85+50%*80=82.5, lucro sem 1000000, com 1162500, ganho 162500
        self.assertEqual(s["preco_efetivo"], 82.5)
        self.assertEqual(s["ganho_lucro"], 162500)

    def test_sem_queda_nao_recomenda(self):
        h = hedge_recomendado(90, 85, 1000, 65, 0.5)
        self.assertTrue(h["ganho_hedge"] < 0)
