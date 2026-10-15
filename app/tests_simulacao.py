"""Testes do motor de simulação + API + intent IA."""

import json

from django.contrib.auth.models import User
from django.test import Client, TestCase

from app.services import simulacao as sim


class MotorSimulacaoTest(TestCase):
    def test_lucro(self):
        r = sim.simular_lucro(10, 60, 150, 380)
        self.assertEqual(r["receita"], 90000)
        self.assertEqual(r["custo"], 3800)
        self.assertEqual(r["lucro"], 86200)
        self.assertEqual(r["lucro_ha"], 8620)
        self.assertGreater(r["margem_pct"], 90)

    def test_cenarios_ordem(self):
        base = {
            "area_ha": 10,
            "produtividade_sc_ha": 60,
            "preco_sc": 150,
            "custo_ha": 380,
        }
        c = sim.cenarios(base)
        self.assertLess(c["pessimista"]["lucro"], c["base"]["lucro"])
        self.assertLess(c["base"]["lucro"], c["otimista"]["lucro"])

    def test_equilibrio(self):
        eq = sim.ponto_equilibrio(380, 150)
        self.assertAlmostEqual(eq["produtividade_equilibrio_sc_ha"], 2.5)

    def test_sensibilidade_invalida(self):
        with self.assertRaises(ValueError):
            sim.sensibilidade({}, "chuva", [1, 2])

    def test_sensibilidade_linhas(self):
        base = {
            "area_ha": 10,
            "produtividade_sc_ha": 60,
            "preco_sc": 150,
            "custo_ha": 380,
        }
        linhas = sim.sensibilidade(base, "preco_sc", [100, 150, 200])
        self.assertEqual(len(linhas), 3)
        self.assertLess(linhas[0]["lucro"], linhas[2]["lucro"])

    def test_montecarlo_deterministico(self):
        base = {
            "area_ha": 10,
            "produtividade_sc_ha": 60,
            "preco_sc": 150,
            "custo_ha": 380,
        }
        a = sim.monte_carlo(base, n=200, seed=7)
        b = sim.monte_carlo(base, n=200, seed=7)
        self.assertEqual(a, b)
        self.assertLessEqual(a["p10"], a["p50"])
        self.assertLessEqual(a["p50"], a["p90"])
        self.assertGreaterEqual(a["prob_lucro_pct"], 0)

    def test_financiamento(self):
        p = sim.financiamento(10000, 2, 12, "price")
        self.assertGreater(p["total"], 10000)
        self.assertGreater(p["juros_total"], 0)
        s = sim.financiamento(10000, 2, 12, "sac")
        self.assertLess(s["ultima"], s["primeira"])

    def test_ranking(self):
        ops = [
            {
                "cultura": "milho",
                "produtividade_sc_ha": 100,
                "preco_sc": 80,
                "custo_ha": 3000,
            },
            {
                "cultura": "soja",
                "produtividade_sc_ha": 60,
                "preco_sc": 150,
                "custo_ha": 3800,
            },
        ]
        r = sim.ranking_culturas(10, ops)
        self.assertEqual(r[0]["cultura"], "soja")


class SimulacaoAPITest(TestCase):
    def setUp(self):
        self.u = User.objects.create_user(username="sim", password="x")
        self.c = Client()
        self.c.force_login(self.u)

    def post(self, tipo, params):
        return self.c.post(
            "/api/simulacao/",
            data=json.dumps({"tipo": tipo, "params": params}),
            content_type="application/json",
        )

    def test_tipos_ok(self):
        base = {
            "area_ha": 10,
            "produtividade_sc_ha": 60,
            "preco_sc": 150,
            "custo_ha": 380,
        }
        for tipo, params in [
            ("lucro", base),
            ("cenarios", base),
            ("equilibrio", {"custo_ha": 380, "preco_sc": 150}),
            (
                "sensibilidade",
                {"base": base, "variavel": "preco_sc", "valores": [100, 200]},
            ),
            ("montecarlo", {**base, "n": 100}),
            ("financiamento", {"valor": 10000, "taxa_mes_pct": 2, "meses": 12}),
            (
                "ranking",
                {
                    "area_ha": 10,
                    "opcoes": [
                        {
                            "cultura": "soja",
                            "produtividade_sc_ha": 60,
                            "preco_sc": 150,
                            "custo_ha": 3800,
                        }
                    ],
                },
            ),
        ]:
            r = self.post(tipo, params)
            self.assertEqual(r.status_code, 200, tipo)
            self.assertTrue(r.json()["ok"], tipo)

    def test_tipo_invalido_400(self):
        r = self.post("foguete", {})
        self.assertEqual(r.status_code, 400)

    def test_sem_auth(self):
        c = Client()
        r = c.post(
            "/api/simulacao/",
            data=json.dumps({"tipo": "lucro", "params": {}}),
            content_type="application/json",
        )
        self.assertIn(r.status_code, (401, 403))


class SimularCenarioIATest(TestCase):
    def test_intent_simula(self):
        from app.ia.sandbox import executar
        from app.models import Propriedade, Talhao

        u = User.objects.create_user(username="simia", password="x")
        prop = Propriedade.objects.create(
            user=u, nome="Faz Sim", area_total=10, uf="MT", cidade="X"
        )
        Talhao.objects.create(
            propriedade=prop, nome="Talhão Sim", area_hectare=20, ativo=True
        )
        out = executar(
            u,
            "simular_cenario",
            {"talhao": "Sim", "produtividade": 60, "preco": 150, "custo_ha": 380},
        )
        self.assertTrue(out["ok"])
        self.assertIn("Simulação 20 ha", out["resposta"])
        self.assertIn("equilibrio", out["dados"])

    def test_sem_area_erro(self):
        from app.ia.sandbox import executar

        u = User.objects.create_user(username="simia2", password="x")
        out = executar(u, "simular_cenario", {"produtividade": 60})
        self.assertFalse(out["ok"])
