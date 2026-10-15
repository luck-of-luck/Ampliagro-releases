"""Sonda MCP real: arranca o servidor como subprocesso e fala com ele como
um cliente MCP a sério, para não confundir 'o servidor não respondeu' com
'a sonda fechou o stdin demasiado cedo'.

Existe porque duas sondas por linha de comando deram resultados diferentes
para o mesmo servidor: com o `echo` a terminar logo, as últimas respostas
m iam-se ao ar com o EOF. Este script espera por cada resposta.

Uso:  python scripts/amplia_mcp_sonda.py [--usuario NOME]
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import threading
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
SERVIDOR = RAIZ / "app" / "amplia_mcp" / "servidor.py"


def _env() -> dict[str, str]:
    e = dict(os.environ)
    # Um cliente MCP não tem CWD do projecto. É de propósito que o teste corra
    # de outro sítio: é a situação real, e a que reproduziu o bug do banco.
    e["PYTHONPATH"] = str(RAIZ)
    return e


def pedir(proc: subprocess.Popen, req: dict) -> None:
    proc.stdin.write(json.dumps(req) + "\n")
    proc.stdin.flush()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--usuario", default="demo")
    ap.add_argument("--cwd", default=str(Path(os.environ.get("TEMP", "."))))
    a = ap.parse_args()

    linhas: list[str] = []
    proc = subprocess.Popen(
        [sys.executable, str(SERVIDOR), "--usuario", a.usuario],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        cwd=a.cwd,
        env=_env(),
        text=True,
        encoding="utf-8",
    )

    def leitor():
        for linha in proc.stdout:
            linhas.append(linha)

    t = threading.Thread(target=leitor, daemon=True)
    t.start()

    pedir(
        proc,
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "sonda", "version": "1"},
            },
        },
    )
    proc.stdin.write(
        json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n"
    )
    proc.stdin.flush()

    pedidos = [
        (2, "tools/list", {}),
        (3, "resources/list", {}),
        (4, "prompts/list", {}),
        (5, "resources/read", {"uri": "amplia://capacidades"}),
    ]
    for rid, metodo, params in pedidos:
        pedir(proc, {"jsonrpc": "2.0", "id": rid, "method": metodo, "params": params})

    # Esperar as respostas em vez de confiar no EOF.
    try:
        proc.wait(timeout=60)
    except subprocess.TimeoutExpired:
        proc.kill()

    recebidas: dict[int, dict] = {}
    for l in linhas:
        l = l.strip()
        if not l.startswith("{"):
            continue
        try:
            d = json.loads(l)
        except ValueError:
            continue
        if isinstance(d.get("id"), int):
            recebidas[d["id"]] = d

    print(f"cwd do processo : {a.cwd}")
    print(f"respostas lidas : {sorted(recebidas)}\n")

    ok = True
    if 1 not in recebidas:
        print("  initialize   SEM RESPOSTA")
        ok = False
    else:
        print("  initialize   ok")

    for rid, metodo, _ in pedidos:
        d = recebidas.get(rid)
        if d is None:
            print(f"  {metodo:<16} SEM RESPOSTA")
            ok = False
        elif "error" in d:
            print(f"  {metodo:<16} ERRO: {d['error'].get('message')}")
            ok = False
        else:
            res = d.get("result") or {}
            if rid == 2:
                print(f"  {metodo:<16} ok — {len(res.get('tools', []))} tools")
            elif rid == 3:
                print(f"  {metodo:<16} ok — {len(res.get('resources', []))} resources")
            elif rid == 4:
                print(f"  {metodo:<16} ok — {len(res.get('prompts', []))} prompts")
            else:
                cont = res.get("contents") or []
                n = len(json.dumps(cont))
                print(f"  {metodo:<16} ok — {len(cont)} conteudo(s), {n} chars")

    print()
    print("RESULTADO:", "todas as superficies respondem" if ok else "houve falhas")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
