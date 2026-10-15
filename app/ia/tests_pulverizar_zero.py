"""Testa h_melhor_pulverizar com os valores que a Open-Meteo devolve.

O bug: `(v or 99) < 10 and (p or 99) < 30`. `or` testa verdade, e 0.0 e'
falso em Python. Vento 0 km/h e' o MELHOR caso para pulverizar (sem deriva);
chuva 0% tambem. Com o `or`, as DUAS melhores condicoes eram deitadas fora --
e a funcao diz "Melhores janelas p/ pulverizar".

Medido antes da correccao: 720 horas de previsao real (5 cidades, 6 dias),
60 delas com chuva 0%. Sao 60 horas perdidas.
"""

import os
import sys
import unittest
import pathlib
from unittest import mock

ROOT = str(pathlib.Path(__file__).resolve().parents[2])
os.chdir(ROOT)
sys.path.insert(0, ROOT)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

import django  # noqa: E402

django.setup()

from django.contrib.auth.models import User  # noqa: E402
from django.test import TestCase  # noqa: E402

from app.ia import intents  # noqa: E402
from app.models import Propriedade  # noqa: E402


class TesteJanelaDePulverizacao(TestCase):
    """h_melhor_pulverizar: 0 e' o melhor dado, nao ausencia de dado."""

    def _corre(self, ventos, chuvas):
        u, _created = User.objects.get_or_create(username="pulverizador_teste")
        Propriedade.objects.get_or_create(
            user=u,
            nome="Prop Pulverizacao",
            defaults={"area_total": 100.0},
        )
        previsao = {
            "hourly": {
                "time": [f"2026-10-02T{i:02d}:00" for i in range(len(ventos))],
                "wind_speed_10m": list(ventos),
                "precipitation_probability": list(chuvas),
            }
        }
        # `_fp` e' importada DENTRO da funcao, a partir de app.ia.fontes
        with (
            mock.patch(
                "app.ia.fontes.fetch_permitido", return_value=(previsao, "open-meteo")
            ),
            mock.patch.object(intents, "_coords", return_value=(-22.0, -47.0, "stub")),
        ):
            return intents.h_melhor_pulverizar(u, {}, {"fontes": []})

    def test_vento_zero_e_aceite(self):
        """0 km/h e' o melhor vento para pulverizar. Tem de entrar."""
        r = self._corre([0.0, 12.0, 3.0], [0, 0, 80])
        self.assertEqual(
            len(r["dados"]["janelas"]),
            1,
            "vento 0 km/h com chuva 0% foi descartado:\n" + r["resposta"],
        )

    def test_chuva_zero_e_aceite(self):
        """0% de chuva e' o melhor tempo. Com `or 99` virava 99 e saia fora."""
        r = self._corre([4.0, 4.0], [0, 40])
        self.assertEqual(
            len(r["dados"]["janelas"]),
            1,
            "chuva 0% foi tratada como 99%:\n" + r["resposta"],
        )

    def test_zero_em_ambos_e_a_melhor_hora(self):
        """O par ideal nao pode ser o pior."""
        r = self._corre([0.0, 25.0], [0, 10])
        self.assertIn("00h", r["resposta"])
        self.assertNotIn("01h", r["resposta"])

    def test_none_ainda_e_descartado(self):
        """A intencao original do autor: sem dado da API, nao recomendar."""
        self.assertEqual(
            len(self._corre([None], [10])["dados"]["janelas"]),
            0,
            "None foi aceite como vento",
        )
        self.assertEqual(
            len(self._corre([5.0], [None])["dados"]["janelas"]),
            0,
            "None foi aceite como chuva",
        )

    def test_fora_dos_limites_e_descartado(self):
        """O comportamento normal nao mudou: 15 km/h ou 60% nao entram."""
        r = self._corre([15.0, 3.0, 3.0], [10, 10, 60])
        self.assertEqual(
            len(r["dados"]["janelas"]),
            1,
            "15 km/h tem de sair; so' a hora de 3.0/10% entra. Saiu: "
            + str(r["dados"]["janelas"]),
        )
        self.assertIn("vento 3.0 km/h", r["resposta"])
