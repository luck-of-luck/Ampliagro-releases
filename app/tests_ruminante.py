from django.test import TestCase

from app.services.ruminante import (
    ph_rumen,
    recomendar_dieta,
    risco_acidose,
    simular_ganho,
)


class RuminanteTest(TestCase):
    def test_ph_fibra_amido(self):
        # 35 fibra 30 amido → 6.2+0.7-0.9=6.0
        self.assertEqual(ph_rumen(35, 30), 6.0)
        # tamponante +0.3 → 6.3
        self.assertEqual(ph_rumen(35, 30, True), 6.3)

    def test_risco(self):
        self.assertEqual(risco_acidose(5.4)["nivel"], "ALTO")
        self.assertEqual(risco_acidose(5.7)["nivel"], "MÉDIO")
        self.assertEqual(risco_acidose(6.2)["nivel"], "OK")

    def test_ganho_acidose(self):
        s = simular_ganho(
            400, 60, 1.6, 20, 50, False
        )  # pouca fibra muito amido → pH baixo
        # 6.2+0.4-1.5=5.1 → ALTO perda 0.4 → ganho 1.2
        self.assertEqual(s["ph"], 5.1)
        self.assertEqual(s["ganho_kg_d_real"], 1.2)
        self.assertEqual(s["perda_kg_total"], 24.0)

    def test_recomendar(self):
        r = recomendar_dieta(5.7, 6.2)
        self.assertTrue(r["tamponante"])
