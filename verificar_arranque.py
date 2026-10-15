"""Reproduz o arranque do Ampliagro Desktop e mede o resultado.

Nao e' um teste — e' a MEDICAO que os testes nao podem fazer. Sobe o
runtime com `config.settings.desktop` num data dir temporario (o mesmo
que `bootstrap.py` faz num desktop novo), aplica as migracoes e arranca o
servidor em loopback. O browser entra a seguir.

Deixa o servidor vivo: escreve a porta em `.verificacao/porta.txt` e o
PID em `.verificacao/pid.txt`.
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
SAIDA = RAIZ / ".verificacao"
DADOS = SAIDA / "dados"
SAIDA.mkdir(exist_ok=True)
DADOS.mkdir(exist_ok=True)

# Liberta a porta anterior, se sobrou alguma.
pid_txt = SAIDA / "pid.txt"
if pid_txt.is_file():
    try:
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", pid_txt.read_text().strip()],
            capture_output=True,
            windowsHide=True,
        )
    except OSError:
        pass
    pid_txt.unlink(missing_ok=True)

AMBIENTE = {
    **os.environ,
    "DJANGO_SETTINGS_MODULE": "config.settings.desktop",
    "AMPLIAGRO_DESKTOP_DATA_DIR": str(DADOS),
    "SECRET_KEY": "verificacao-local-nao-e-segredo",
    "AMPLIAGRO_SETUP_TOKEN": "token-de-verificacao",
    "AMPLIAGRO_TERMS_HASH": "termos-v1",
}
for chave in ("DATABASE_URL", "REDIS_URL"):
    AMBIENTE.pop(chave, None)

base = [sys.executable, "manage.py"]
print("1/3 migrate…")
r = subprocess.run(
    base + ["migrate", "--noinput", "-v", "0"],
    cwd=RAIZ,
    env=AMBIENTE,
    capture_output=True,
    text=True,
)
if r.returncode != 0:
    print(r.stdout[-2000:])
    print(r.stderr[-2000:])
    raise SystemExit(1)

import sqlite3

db = DADOS / "ampliagro-desktop.sqlite3"
c = sqlite3.connect(db)
total = c.execute("select count(*) from app_cultura where ativo=1").fetchone()[0]
grupos = c.execute(
    "select count(distinct grupo) from app_cultura where ativo=1"
).fetchone()[0]
users = c.execute("select count(*) from auth_user").fetchone()[0]
c.close()
print(f"   migrate OK — {total} culturas ativas em {grupos} grupos, {users} contas")

print("2/3 a escolher porta…")
import socket

with socket.socket() as s:
    s.bind(("127.0.0.1", 0))
    porta = s.getsockname()[1]

print(f"3/3 runserver em 127.0.0.1:{porta}…")
log = open(SAIDA / "server.log", "w", encoding="utf-8")
proc = subprocess.Popen(
    base + ["runserver", f"127.0.0.1:{porta}", "--noreload"],
    cwd=str(RAIZ),
    env=AMBIENTE,
    stdout=log,
    stderr=subprocess.STDOUT,
    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
)

import urllib.error
import urllib.request

url = f"http://127.0.0.1:{porta}/healthz"
limite = time.monotonic() + 90
pronto = False
while time.monotonic() < limite:
    if proc.poll() is not None:
        print("o servidor morreu:")
        print(open(SAIDA / "server.log", encoding="utf-8").read()[-3000:])
        raise SystemExit(1)
    try:
        with urllib.request.urlopen(url, timeout=3) as resp:
            corpo = json.loads(resp.read().decode("utf-8"))
        if corpo.get("status") in ("ok", "warn"):
            pronto = True
            break
    except (urllib.error.URLError, OSError, json.JSONDecodeError):
        time.sleep(0.5)

if not pronto:
    proc.terminate()
    raise SystemExit("healthz nao ficou ok")

pid_txt.write_text(str(proc.pid), encoding="utf-8")
print(f"PRONTO http://127.0.0.1:{porta} (pid {proc.pid})")
