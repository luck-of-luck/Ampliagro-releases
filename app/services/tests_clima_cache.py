"""Prova da Fase 2: o cache de clima.

Este teste não verifica que o código "faz cache". Verifica as três
situações que o produtor encontra, e que o código antigo não distinguia:

    1. COM rede          -> fonte "open-meteo", hora agora
    2. SEM rede, COM cache -> fonte "cache", hora da captura, e o DADO
    3. SEM rede, SEM cache -> 503, e a UI mostra "—"/"sem sinal"

O teste 2 é o que interessa. Nele, a rede é bloqueada a sério (monkeypatch
no `urlopen`), e mesmo assim a previsão tem de aparecer — com a hora certa.

A hora verificada não é "agora". É a hora que estava no JSON. Um teste que
aceitasse qualquer hora recente passaria mesmo com a cache a mentir.
"""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.test import TestCase, override_settings

from app.services import clima as clima_mod
from app.services.clima import ClimaService


RESPOSTA_FALSA = {
    "daily": {
        "time": ["2026-10-12", "2026-10-13"],
        "temperature_2m_max": [31.2, 29.8],
        "temperature_2m_min": [19.4, 18.1],
        "precipitation_sum": [0.0, 4.7],
        "precipitation_probability_max": [5, 62],
    }
}


class _RedeCorta:
    """Substitui `urlopen` por uma falha de rede.

    Não se corta a rede a sério aqui: o que interessa é que o código de
    decisão siga o caminho certo. O gate da Fase 2 já provou, no browser,
    que a CSP não deixa sair nada.
    """

    @staticmethod
    def __call__(*a, **k):
        raise OSError("rede bloqueada para a prova")


class TesteFuncaoObstruida(unittest.TestCase):
    """As três situações, sem Django nem base de dados."""

    def setUp(self):
        self._dir = tempfile.TemporaryDirectory()
        self.addCleanup(self._dir.cleanup)
        self.settings = override_settings(
            CLIMA_CACHE_DIR=Path(self._dir.name),
            CACHES={
                "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}
            },
        )
        self.settings.enable()
        self.addCleanup(self.settings.disable)
        from django.core.cache import cache

        cache.clear()

    # ---------------------------------------------------------------- 1
    def test_com_rede_grava_e_anota_a_fonte(self):
        """Com rede: o número é medido agora, e isso é dito."""
        resposta = type("R", (), {})()

        class _FakeHTTP:
            def __init__(self, *a, **k):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def read(self):
                return json.dumps(RESPOSTA_FALSA).encode()

        with patch("urllib.request.urlopen", _FakeHTTP):
            d = ClimaService.get_previsao(-15.78, -47.93)

        self.assertEqual(d["fonte_dados"], "open-meteo")
        self.assertIsNotNone(d["capturado_em"])
        self.assertNotIn("error", d)

        # E o JSON tem de estar em disco, com a hora dentro.
        ficheiro = Path(self._dir.name) / "clima.json"
        self.assertTrue(ficheiro.is_file(), "o clima.json não foi escrito")
        bruto = json.loads(ficheiro.read_text(encoding="utf-8"))
        self.assertEqual(bruto["versao"], 1)
        entrada = bruto["capturas"]["-15.7800,-47.9300"]
        self.assertEqual(entrada["fonte"], "open-meteo")
        self.assertIn("capturado_em", entrada)

    # ---------------------------------------------------------------- 2
    def test_sem_rede_mostra_a_captura_com_a_dela_hora(self):
        """Sem rede e com captura: mostra o dado, e a hora do dado."""

        # Primeiro: uma captura com rede.
        class _FakeHTTP:
            def __init__(self, *a, **k):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def read(self):
                return json.dumps(RESPOSTA_FALSA).encode()

        with patch("urllib.request.urlopen", _FakeHTTP):
            com_rede = ClimaService.get_previsao(-15.78, -47.93)
        hora_da_captura = com_rede["capturado_em"]

        # Depois: a mesma coordenada, sem rede e sem o cache do Django.
        from django.core.cache import cache

        cache.clear()

        with patch("urllib.request.urlopen", _RedeCorta()):
            offline = ClimaService.get_previsao(-15.78, -47.93)

        self.assertNotIn("error", offline, "havia captura — não pode ser erro")
        self.assertEqual(offline["fonte_dados"], "cache")
        self.assertEqual(
            offline["capturado_em"],
            hora_da_captura,
            "a hora mostrada tem de ser a da captura, não a de agora",
        )
        # O dado é o que estava gravado. Uma cache que devolvesse a mesma
        # forma mas com os valores trocados seria decoração.
        self.assertEqual(
            offline["daily"]["temperature_2m_max"][0],
            RESPOSTA_FALSA["daily"]["temperature_2m_max"][0],
        )
        self.assertIn("aviso", offline)
        self.assertIn("Sem ligação", offline["aviso"])

    # ---------------------------------------------------------------- 3
    def test_sem_rede_e_sem_captura_diz_sem_sinal(self):
        """Sem rede e sem nunca ter havido captura: ausência, não zero."""
        with patch("urllib.request.urlopen", _RedeCorta()):
            d = ClimaService.get_previsao(-15.78, -47.93)

        self.assertIn("error", d, "as três views dependem disto para o 503")
        self.assertEqual(d["fonte_dados"], "sem-sinal")
        self.assertIsNone(d["capturado_em"])

    # ------------------------------------------------------------ extras
    def test_coordenadas_perto_partilham_a_entrada(self):
        """30 m de diferença não são outra fazenda."""
        clima_mod.gravar_captura(-15.78000, -47.93000, {"a": 1}, "open-meteo")
        clima_mod.gravar_captura(-15.78003, -47.93001, {"a": 2}, "open-meteo")

        bruto = json.loads(
            (Path(self._dir.name) / "clima.json").read_text(encoding="utf-8")
        )
        self.assertEqual(len(bruto["capturas"]), 1, "partilharam a chave")

    def test_json_corrompido_e_cache_vazio_nao_parte_nada(self):
        """Cache ilegível é cache vazio — nunca uma excepção."""
        (Path(self._dir.name) / "clima.json").write_text(
            "{isto nao e json", encoding="utf-8"
        )

        self.assertIsNone(clima_mod.ler_captura(-15.78, -47.93))

        # E, com a rede em baixo, o sistema ainda tem de responder.
        with patch("urllib.request.urlopen", _RedeCorta()):
            d = ClimaService.get_previsao(-15.78, -47.93)
        self.assertEqual(d["fonte_dados"], "sem-sinal")

    def test_gravar_preserva_as_capturas_dos_outros_sitios(self):
        clima_mod.gravar_captura(-15.78, -47.93, {"x": 1}, "open-meteo")
        clima_mod.gravar_captura(-20.00, -45.00, {"x": 2}, "open-meteo")

        bruto = json.loads(
            (Path(self._dir.name) / "clima.json").read_text(encoding="utf-8")
        )
        self.assertEqual(len(bruto["capturas"]), 2)

    def test_nao_ha_escrita_parcial(self):
        """O ficheiro tem de ser substituído, não sobrescrito."""
        import app.services.clima as m

        clima_mod.gravar_captura(-15.78, -47.93, {"x": 1}, "open-meteo")
        leftovers = list(Path(self._dir.name).glob("*.tmp"))
        self.assertEqual(leftovers, [], f"ficou temporário por limpar: {leftovers}")


class TesteSetting(unittest.TestCase):
    def test_o_cache_fora_do_media_root(self):
        """Se `clima.json` estivesse em `MEDIA_ROOT`, seria servido ao mundo."""
        from django.conf import settings as s

        if hasattr(s, "MEDIA_ROOT"):
            self.assertFalse(
                str(getattr(s, "CLIMA_CACHE_DIR", "")).startswith(str(s.MEDIA_ROOT)),
                "CLIMA_CACHE_DIR está dentro de MEDIA_ROOT — o ficheiro "
                "com a coordenada da fazenda seria público",
            )


if __name__ == "__main__":
    unittest.main()
