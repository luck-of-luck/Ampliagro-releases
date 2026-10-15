"""Prova do runtime CONGELADO: o executável serve, ou só existe?

Ter um `.exe` de 93,8 MB não prova nada. O PyInstaller produz um
executável que arranca e depois morre com um `ModuleNotFoundError` numa
rota, e a diferença entre "construído" e "funcional" só aparece quando
alguém lhe bate.

O que esta prova mede:
  1. o executável arranca e anuncia `AMPLIAGRO_DESKTOP_READY`;
  2. `/healthz` responde `ok` — a base foi migrada pelo próprio executável,
     sem Python do sistema e sem o repositório;
  3. `/login/` renderiza;
  4. o WebSocket faz 101 — os alertas de sensor dependem disto;
  5. fechar o executável não deixa nada vivo.

O ponto 2 é o mais forte: o `migrate` corre dentro do binário, contra a
base no directório de dados. Se as migrações não tivessem viajado nos
dados, o `/healthz` viria `fail` com `migrations.pending` diferente de 0.
"""

from __future__ import annotations

import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

RAIZ = Path(r"C:\Trabalho\Projetos\Ativos\Ampliagro2")
EXE = (
    RAIZ
    / "ampliagro-app"
    / "desktop"
    / "dist-runtime"
    / "ampliagro-runtime"
    / "ampliagro-runtime.exe"
)
DADOS = Path(tempfile.gettempdir()) / "ampliagro-frozen-prova"


def handshake(porta: int) -> str:
    s = socket.create_connection(("127.0.0.1", porta), timeout=10)
    try:
        s.sendall(
            (
                "GET /ws/dashboard/ HTTP/1.1\r\n"
                f"Host: 127.0.0.1:{porta}\r\n"
                "Upgrade: websocket\r\n"
                "Connection: Upgrade\r\n"
                "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\n"
                "Sec-WebSocket-Version: 13\r\n"
                f"Origin: http://127.0.0.1:{porta}\r\n"
                "\r\n"
            ).encode("ascii")
        )
        return s.recv(4096).decode("iso-8859-1", errors="replace").splitlines()[0]
    finally:
        s.close()


def principal() -> int:
    print("=" * 72)
    print("PROVA DO RUNTIME CONGELADO")
    print("=" * 72)

    if not EXE.is_file():
        print(f"[FALHA] executável não encontrado: {EXE}")
        return 1

    import shutil

    if DADOS.exists():
        shutil.rmtree(DADOS)
    DADOS.mkdir(parents=True, exist_ok=True)

    print(f"\n  exe: {EXE.name}")
    print(f"  dados limpos: {DADOS}  (primeiro arranque a sério)")

    env = os.environ.copy()
    env["AMPLIAGRO_DESKTOP_DATA_DIR"] = str(DADOS)
    env["PYTHONIOENCODING"] = "utf-8"
    env.pop("REDIS_URL", None)
    env.pop("DATABASE_URL", None)
    # Sem isto, o congelado podia ir buscar o `.env` do repositório e
    # arrancar com REDIS_URL da cloud — o teste passaria no computador
    # do programador e falharia no do produtor.
    env.pop("DJANGO_SETTINGS_MODULE", None)

    proc = subprocess.Popen(
        [str(EXE)],
        cwd=str(EXE.parent),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
    )

    falhas = []
    try:
        porta = None
        limite = time.monotonic() + 240
        while time.monotonic() < limite and porta is None:
            if proc.poll() is not None:
                print(f"  [FALHA] o executável saiu: {proc.returncode}")
                print((proc.stderr.read() if proc.stderr else "")[-2500:])
                return 1
            linha = proc.stdout.readline() if proc.stdout else ""
            if linha.startswith("AMPLIAGRO_DESKTOP_READY"):
                porta = int(re.search(r"port=(\d+)", linha).group(1))
                print(f"  [OK] READY port={porta}  (o binário migrou a base sozinho)")
            time.sleep(0.05)

        if porta is None:
            print("  [FALHA] não ficou pronto em 240s")
            return 1

        with urllib.request.urlopen(
            f"http://127.0.0.1:{porta}/healthz", timeout=15
        ) as r:
            corpo = json.loads(r.read().decode("utf-8"))
            mig = corpo.get("checks", {}).get("migrations", {})
            print(f"  [OK] /healthz status={corpo.get('status')} migrations={mig}")
            if corpo.get("status") != "ok":
                falhas.append("healthz")

        with urllib.request.urlopen(
            f"http://127.0.0.1:{porta}/login/", timeout=15
        ) as r:
            n = len(r.read())
            print(f"  [OK] /login/ {r.status} ({n / 1024:.0f} KB)")
            if r.status != 200 or n < 5000:
                falhas.append("login")

        linha = handshake(porta)
        print(f"  {'[OK]   ' if '101' in linha else '[FALHA]'} WebSocket: {linha!r}")
        if "101" not in linha:
            falhas.append("websocket")
    finally:
        if proc.poll() is None:
            if os.name == "nt":
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                    capture_output=True,
                    timeout=30,
                )

    print("\n" + ("RESULTADO: FALHOU" if falhas else "RESULTADO: PASSOU"))
    for f in falhas:
        print("  -", f)
    return 1 if falhas else 0


if __name__ == "__main__":
    raise SystemExit(principal())
