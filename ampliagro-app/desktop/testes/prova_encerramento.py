"""Prova de encerramento: matar o bootstrap tem de matar o Daphne.

Este é o teste que decide se o desktop deixa um servidor a correr depois
de o utilizador fechar a janela. Se o Daphne sobreviver, o utilizador fica
com um processo invisivel a segurar uma porta e a servir dados da fazenda —
e a segunda abertura do desktop escolhe outra porta, deixando o primeiro
para sempre.

O que se mede:
  1. o bootstrap anuncia READY;
  2. identify o PID do Daphne (vem na propria linha READY);
  3. termino o bootstrap (SIGTERM — o que o Electron faz ao fechar);
  4. o Daphne tem de desaparecer sozinho num prazo razoavel.

SIGTERM e nao SIGKILL de proposito: SIGKILL nao da ao Python para correr o
`atexit`, e o objectivo e exactamente provar que o `atexit` funciona.
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

RAIZ = Path(r"C:\Trabalho\Projetos\Ativos\Ampliagro2")
DATA = Path(tempfile.gettempdir()) / "ampliagro-encerramento-prova"
BOOTSTRAP = RAIZ / "ampliagro-app" / "desktop" / "backend" / "bootstrap.py"

ENV = os.environ.copy()
ENV["AMPLIAGRO_CODE_ROOT"] = str(RAIZ)
ENV["AMPLIAGRO_DESKTOP_DATA_DIR"] = str(DATA)
ENV.pop("REDIS_URL", None)
ENV.pop("DATABASE_URL", None)


def vivo(pid: int) -> bool:
    """Existe um processo com este PID?"""
    if os.name == "nt":
        r = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
            capture_output=True,
            text=True,
        )
        return str(pid) in r.stdout
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def porta_ouvinte(porta: int) -> int | None:
    """PID que segura a porta EM LISTEN, ou None.

    Só conta `LISTEN`. Um socket em `TIME_WAIT` aparece no netstat com
    `OwningProcess` 0 — não tem dono, não aceita ligações e expira sozinho.
    Contá-lo como "porta ocupada" dá um falso negativo que faz parecer que
    o servidor sobreviveu quando morreu bem. (Foi o que aconteceu na
    primeira medição: o Daphne já tinha morrido, mas dois sockets em
    TIME_WAIT do health-check faziam o teste dizer que não.)
    """
    if os.name == "nt":
        r = subprocess.run(
            ["netstat", "-ano", "-p", "TCP"], capture_output=True, text=True
        )
        for linha in r.stdout.splitlines():
            partes = linha.split()
            # TCP  127.0.0.1:56159  0.0.0.0:0  LISTENING  3260
            if len(partes) < 5:
                continue
            if partes[0] != "TCP" or partes[3] != "LISTENING":
                continue
            local = partes[1].rsplit(":", 1)[-1]
            if local == str(porta) and partes[-1].isdigit():
                return int(partes[-1])
    return None


def principal() -> int:
    print("=" * 72)
    print("PROVA DE ENCERRAMENTO — o Daphne morre com o pai?")
    print("=" * 72)

    flags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
    proc = subprocess.Popen(
        [sys.executable, str(BOOTSTRAP)],
        cwd=str(RAIZ),
        env=ENV,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=flags,
    )

    porta = pid_daphne = None
    limite = time.monotonic() + 120
    try:
        while time.monotonic() < limite and porta is None:
            if proc.poll() is not None:
                print(f"  [FALHA] bootstrap saiu cedo ({proc.returncode})")
                return 1
            linha = proc.stdout.readline() if proc.stdout else ""
            if linha.startswith("AMPLIAGRO_DESKTOP_READY"):
                for campo in linha.split():
                    if campo.startswith("port="):
                        porta = int(campo.split("=", 1)[1])
                    if campo.startswith("pid="):
                        pid_daphne = int(campo.split("=", 1)[1])
                print(f"  READY: port={porta} pid_daphne={pid_daphne}")

        if porta is None or pid_daphne is None:
            print("  [FALHA] sem READY")
            return 1

        dono = porta_ouvinte(porta)
        print(f"  porta {porta} detida pelo PID {dono} (esperado {pid_daphne})")
        if dono != pid_daphne:
            print(f"  [FALHA] a porta NÃO é do Daphne anunciado")
            return 1
        print("  [OK]    o PID anunciado é mesmo quem detém a porta")

        # ---- 3. SIGTERM ao bootstrap, como o Electron faz ao fechar ----
        print("\n  a enviar SIGTERM ao bootstrap (o que o Electron faz ao fechar)...")
        if os.name == "nt":
            proc.terminate()
        else:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)

        # ---- 4. o Daphne tem de ir embora sozinho ----
        print("  a ver se o Daphne se encerra (atexit)...")
        limite2 = time.monotonic() + 25
        while time.monotonic() < limite2:
            if not vivo(pid_daphne):
                print(f"  [OK]    Daphne {pid_daphne} encerrado em <25s")
                break
            time.sleep(0.4)
        else:
            print(f"  [FALHA] Daphne {pid_daphne} SOBREVIVEU ao pai")
            return 1

        # ---- 5. e a porta fica livre ----
        time.sleep(1.0)
        if os.name == "nt":
            dono2 = porta_ouvinte(porta)
            if dono2 is None:
                print(f"  [OK]    porta {porta} libertada")
            else:
                print(f"  [FALHA] porta {porta} ainda detida por {dono2}")
                return 1

        return 0

    finally:
        if proc.poll() is None:
            if os.name == "nt":
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                    capture_output=True,
                    timeout=30,
                )
            else:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        if pid_daphne and vivo(pid_daphne):
            print(f"  [limpeza] a matar Daphne {pid_daphne} que sobrou")
            if os.name == "nt":
                subprocess.run(
                    ["taskkill", "/F", "/PID", str(pid_daphne)],
                    capture_output=True,
                    timeout=30,
                )


if __name__ == "__main__":
    try:
        raise SystemExit(principal())
    finally:
        print("\n" + "=" * 72)
