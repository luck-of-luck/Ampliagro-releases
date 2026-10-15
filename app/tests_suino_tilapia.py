from django.test import TestCase

from app.services.suino_tilapia import suino_biodigestor, tilapia_pele


class SuinoTilapiaTest(TestCase):
    def test_tilapia_pele(self):
        t = tilapia_pele(10000, mormaco=False)
        self.assertEqual(t["ganho_pele_vs_carne_pct"], 566.7)

    def test_mormaco(self):
        t = tilapia_pele(10000, mormaco=True)
        self.assertTrue(t["perda_mormaco_R"] > 0)
