from django.test import TestCase

from app.services.avicultura import big_brother_previsao, lotes_por_ano, moba_descarte


class AviculturaTest(TestCase):
    def test_lego(self):
        l = lotes_por_ano(42, 15, tipo="lego")
        self.assertAlmostEqual(l["lotes_ano"], 6.4, places=1)
        self.assertAlmostEqual(l["ganho_vs_alvenaria"], 150000, delta=600)

    def test_big_brother(self):
        b = big_brother_previsao(2.37, 12, 2)
        self.assertEqual(b["ganho_vs_sem_ia"], 30000)

    def test_moba(self):
        m = moba_descarte(100000, 9.5, True, True)
        self.assertEqual(m["descarte_pct"], 9.5)
        self.assertTrue(m["ganho_R"] > 90000)
