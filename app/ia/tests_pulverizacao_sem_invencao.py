"""Teste do h_melhor_pulverizar: o 0 e' o melhor caso, nao ausencia de dado.

O bug: `if (v or 99) < 10 and (p or 99) < 30`. O `or` testava verdade, e 0.0
e' falso em Python. Vento 0 km/h e' o MELHOR caso para pulverizar; chuva 0%
tambem. Com o `or 99`, as duas melhores horas eram deitadas fora.
Numa leitura de 720 horas de previsao real (5 cidades, 6 dias), 60 tinham
chuva 0% -- 60 horas perdidas.
"""

import io
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

from django.test import TestCase  # noqa: E402

# O que esta linha fazia, e porque partia a suite INTEIRA
# ==========================================================
# Era:
#     sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", ...)
#
# Trocava o objecto `sys.stdout` global no momento do IMPORT. O wrapper
# antigo ia para o lixo; ao ser recolhido, fechava o `buffer` — e o `buffer`
# ja nao era o do console, era o ficheiro temporario que o pytest usa para
# capturar a saida. Resultado, medido: `pytest app` e `pytest app/ia`
# terminavam com `ValueError: I/O operation on closed file` e "no tests ran".
# Uma suite que nao corre e' pior do que uma suite que falha: nao avisa
# ninguem, so nao responde.
#
# Um teste nao tem porquao mudar o stdout do processo que o corre. O que se
# queria era nao rebentar com acentos na consola do Windows, e isso resolve-se
# a serio com `reconfigure()`, que muda a codificacao do MESMO objecto sem
# fechar o buffer e sem substituir nada.
#
# `reconfigure()` existe desde o Python 3.7. Este projeto e' 3.11.
#
# E so' quando a codificacao actual nao e' UTF-8: se ja e', nao ha o que
# corrigir e mexer no stream seria trabalho a mais com o mesmo resultado.
try:
    _stdin_utf8 = (sys.stdout.encoding or "").lower().replace("-", "") == "utf8"
except Exception:
    _stdin_utf8 = True
if not _stdin_utf8:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError, OSError):
        # Terminal que nao aceita reconfigure. Melhor um `?` na saida do que
        # uma suite que nao arranca.
        pass


class TesteJanelaDePulverizacao(TestCase):
    """h_melhor_pulverizar, com a API devolvida a mao."""

    def _chamar(self, hourly):
        from django.contrib.auth.models import User

        from app.ia import intents
        from app.models import Propriedade

        u, _ = User.objects.get_or_create(username="pulverizador")
        p, _ = Propriedade.objects.get_or_create(
            user=u, nome="Fazenda Pulverizacao", defaults={"area_total": 100.0}
        )
        ctx = {"fontes": []}

        resposta_api = {"hourly": hourly}
        # `_fp` e' importada DENTRO de `h_melhor_pulverizar`
        # (`app/ia/intents.py:406`), e nao no topo do modulo. Patchar
        # `intents._fp` levanta AttributeError: nao existe atributo com esse
        # nome para substituir. E' a FONTE que se patcha --
        # `app.ia.fontes.fetch_permitido` -- porque o import acontece a cada
        # chamada. O mesmo que `tests_pulverizar_zero.py` faz, e que ja traz
        # este comentario.
        with (
            mock.patch.object(intents, "_prop", return_value=p),
            mock.patch.object(intents, "_coords", return_value=(-22.0, -47.0, "stub")),
            mock.patch(
                "app.ia.fontes.fetch_permitido",
                return_value=(resposta_api, "stub"),
            ),
        ):
            return intents.h_melhor_pulverizar(u, {}, ctx)

    def test_vento_zero_e_chuva_zero_sao_a_melhor_hora(self):
        """O zero e' o melhor caso. Este e' o teste que falha no codigo antigo."""
        r = self._chamar(
            {
                "time": ["2026-10-03T03:00", "2026-10-03T04:00", "2026-10-03T05:00"],
                "wind_speed_10m": [0.0, 2.0, 15.0],
                "precipitation_probability": [0, 5, 5],
            }
        )
        janelas = r["dados"]["janelas"]
        self.assertEqual(
            len(janelas),
            2,
            (
                "vento 0 km/h e chuva 0% sao a melhor janela e tem de entrar. "
                "O codigo antigo descartava-as por `v or 99`."
            ),
        )
        # a hora com vento 0 tem de estar la, e com o valor certo
        self.assertIn("vento 0.0 km/h", janelas[0])
        # e a hora de vento 15 tem de ficar de fora
        self.assertNotIn("vento 15.0 km/h", " ".join(janelas))

    def test_chuva_zero_com_vento_aceitavel_entra(self):
        """Chuva 0% e' o melhor tempo. Com vento de 4 km/h, tem de contar."""
        r = self._chamar(
            {
                "time": ["2026-10-03T06:00"],
                "wind_speed_10m": [4.0],
                "precipitation_probability": [0],
            }
        )
        self.assertEqual(
            len(r["dados"]["janelas"]),
            1,
            (
                "chuva 0% com vento de 4 km/h e' pulverizavel. "
                "`p or 99` transformava 0 em 99 e descartava-a."
            ),
        )

    def test_none_continua_a_nao_contar(self):
        """A intencao original do autor: sem dado da API, nao recomendar."""
        r = self._chamar(
            {
                "time": ["2026-10-03T07:00"],
                "wind_speed_10m": [None],
                "precipitation_probability": [0],
            }
        )
        self.assertEqual(
            r["dados"]["janelas"],
            [],
            (
                "None e' ausencia de dado, e tem de continuar a nao contar. "
                "A correccao foi distinguir None de 0, nunca aceitar os dois."
            ),
        )

    def test_vento_alto_e_chuva_alta_fora(self):
        """O inverso: 25 km/h ou 80% de chuva nao sao janela."""
        r = self._chamar(
            {
                "time": ["2026-10-03T08:00", "2026-10-03T09:00"],
                "wind_speed_10m": [25.0, 2.0],
                "precipitation_probability": [0, 80],
            }
        )
        self.assertEqual(
            r["dados"]["janelas"],
            [],
            ("25 km/h com deriva e 80% de chuva nao sao janela de pulverizacao."),
        )

    def test_zero_e_um_dado_nao_uma_ausencia(self):
        """O contrato, escrito para se ler sem saber o historia do bug."""
        for valor, deve_contar in (
            (0.0, True),
            (0.5, True),
            (1.0, True),
            (None, False),
        ):
            with self.subTest(vento=valor):
                r = self._chamar(
                    {
                        "time": ["2026-10-03T10:00"],
                        "wind_speed_10m": [valor],
                        "precipitation_probability": [0],
                    }
                )
                conta = len(r["dados"]["janelas"]) == 1
                self.assertEqual(
                    conta,
                    deve_contar,
                    "vento={!r}: {} contar. 0 e' um dado; so' None e' ausencia.".format(
                        valor, "tem de" if deve_contar else "nao tem de"
                    ),
                )
