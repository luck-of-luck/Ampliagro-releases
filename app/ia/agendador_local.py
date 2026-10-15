"""Varredura proativa no processo local; sem Redis, Celery ou modelo remoto."""

import logging
import os
import threading
from contextlib import ExitStack
from pathlib import Path

from django.conf import settings
from django.db import close_old_connections
from django.utils import timezone

logger = logging.getLogger(__name__)
_thread = None
_mutex = threading.Lock()
_parar = threading.Event()
_estado = {"ativo": False, "ultima_execucao": None, "ultimo_erro": None}


def estado():
    return dict(_estado)


def _adquirir_lock(caminho, stack):
    """Lock do SO é libertado mesmo quando o servidor termina abruptamente."""
    arquivo = stack.enter_context(open(caminho, "a+b"))
    try:
        arquivo.seek(0, 2)
        if not arquivo.tell():
            arquivo.write(b"0")
            arquivo.flush()
        arquivo.seek(0)
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(arquivo.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(arquivo.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        return arquivo
    except OSError:
        arquivo.close()
        return None


def _loop_com_lock(caminho, intervalo, stack):
    try:
        lock = _adquirir_lock(caminho, stack)
    except OSError:
        logger.exception("Não foi possível abrir o lock do copiloto local")
        _estado["ultimo_erro"] = (
            "Não foi possível iniciar a varredura local. Consulte o log."
        )
        return
    if lock is None:
        _estado["ultimo_erro"] = "Outro processo já executa a varredura local."
        return
    _estado["ativo"] = True
    try:
        while not _parar.wait(10 if _estado["ultima_execucao"] is None else intervalo):
            close_old_connections()
            try:
                from app.ia.proativo_tasks import varrer

                resumo = varrer()
                _estado.update(
                    ultima_execucao=timezone.now().isoformat(),
                    ultimo_erro=None,
                    resumo=resumo,
                )
            except Exception:
                logger.exception("Falha na varredura do copiloto local")
                _estado.update(
                    ultima_execucao=timezone.now().isoformat(),
                    ultimo_erro="Falha na varredura. Consulte o log local.",
                )
            finally:
                close_old_connections()
    finally:
        _estado["ativo"] = False
        lock.close()


def _loop(caminho, intervalo):
    with ExitStack() as stack:
        _loop_com_lock(caminho, intervalo, stack)


def iniciar():
    """Chamado só pelo servidor HTTP, nunca por migrate ou pelos imports de modelos."""
    global _thread
    if (
        not getattr(settings, "AMPLIA_LOCAL_COPILOTO", False)
        or os.environ.get("AMPLIA_CELERY_BEAT") == "1"
    ):
        return False
    banco = settings.DATABASES["default"]
    if banco.get("ENGINE") != "django.db.backends.sqlite3" or banco.get("NAME") in (
        None,
        "",
        ":memory:",
    ):
        return False
    caminho = Path(banco["NAME"]).resolve().parent / ".copiloto-local.lock"
    with _mutex:
        if _thread and _thread.is_alive():
            return True
        _parar.clear()
        _thread = threading.Thread(
            target=_loop, args=(caminho, 300), name="amplia-copiloto", daemon=True
        )
        _thread.start()
    return True
