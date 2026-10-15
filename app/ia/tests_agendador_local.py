"""Execução local serializada, com encerramento e recuperação de falhas."""

from contextlib import ExitStack
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from app.ia import agendador_local as ag


class AgendadorLocalTest(SimpleTestCase):
    def test_lock_exclusivo_e_liberado_ao_fechar(self):
        with TemporaryDirectory() as pasta:
            caminho = Path(pasta) / "lock"
            with ExitStack() as primeiro, ExitStack() as segundo:
                self.assertIsNotNone(ag._adquirir_lock(caminho, primeiro))
                self.assertIsNone(ag._adquirir_lock(caminho, segundo))
            with ExitStack() as terceiro:
                self.assertIsNotNone(ag._adquirir_lock(caminho, terceiro))

    @override_settings(AMPLIA_LOCAL_COPILOTO=False)
    def test_desligado_nao_inicia_thread(self):
        with patch.object(ag.threading, "Thread") as thread:
            self.assertFalse(ag.iniciar())
            thread.assert_not_called()

    def test_loop_executa_nucleo_e_fecha_conexoes(self):
        with (
            TemporaryDirectory() as pasta,
            patch.object(ag._parar, "wait", side_effect=[False, True]),
            patch.object(ag, "close_old_connections") as fechar,
            patch(
                "app.ia.proativo_tasks.varrer", return_value={"alertas": 1}
            ) as varrer,
        ):
            ag._loop(Path(pasta) / "lock", 300)
        varrer.assert_called_once()
        self.assertEqual(fechar.call_count, 2)
        self.assertFalse(ag.estado()["ativo"])
        self.assertIsNone(ag.estado()["ultimo_erro"])

    def test_falha_nao_deixa_loop_sem_status(self):
        with (
            TemporaryDirectory() as pasta,
            patch.object(ag._parar, "wait", side_effect=[False, True]),
            patch.object(ag, "close_old_connections"),
            patch("app.ia.proativo_tasks.varrer", side_effect=RuntimeError("teste")),
            self.assertLogs(ag.logger, level="ERROR"),
        ):
            ag._loop(Path(pasta) / "lock", 300)
        self.assertIn("Falha", ag.estado()["ultimo_erro"])
