"""Verificação de que o servidor MCP stdio funciona a sério.

Um teste que arranca o módulo e diz "não rebentou" não prova que um cliente
MCP consegue falar com ele. Isto faz o handshake pelo protocolo: escreve um
`initialize` em JSON-RPC, pede `tools/list`, pede `prompts/list`, e lê o que
volta. Se responder a três, o servidor está de pé.

Corre de fora do repositório de propósito — um cliente MCP arranca com o CWD
do utilizador, e um teste que corre na raiz não prova o caso que falha.
"""

import json
import os
import pathlib
import subprocess
import sys

RAIZ = pathlib.Path(__file__).resolve().parents[1]


def _python_do_venv():
    """O interpretador do `.venv`, em qualquer sistema operativo.

    MEDIDO 2026-10-06, no CI:
        FileNotFoundError: [Errno 2] No such file or directory:
        '/home/runner/work/Ampliagro/Ampliagro/.venv/Scripts/python.exe'

    Este script era um caminho Windows escrito a mao — `.venv/Scripts/
    python.exe` — e foi corrido no runner do Linux, onde o venv vive em
    `.venv/bin/python`. A razao de a escolha ser silenciosa e' que o ficheiro
    LE e o runner TEM — o erro so aparece quando o `subprocess` tenta
    arrancar o filho, e ai ja e' tarde.

    Tres casos, pela ordem de preferencia:

      1. `AMPLIAGRO_PYTHON` — o CI pode dizer explicitamente qual e'. E' o
         unico que ganha sobre os outros, e existe para quando o venv nao
         esta onde este script espera.
      2. O `sys.executable` que esta a correr este script. Na maioria dos
         casos ja e' o do venv, porque quem o chamou estava nele.
      3. Os dois caminhos `.venv`, para quando `sys.executable` for o Python
         do sistema.

    O `2` vem primeiro de proposito: em vez de adivinhar um caminho e falhar
    com `FileNotFoundError`, usa-se o interpretador que ja provou que funciona.
    """
    escolhido = os.environ.get("AMPLIAGRO_PYTHON") or sys.executable
    if pathlib.Path(escolhido).exists():
        return escolhido
    for relativo in (("bin", "python"), ("Scripts", "python.exe")):
        cand = RAIZ / ".venv" / relativo[0] / relativo[1]
        if cand.exists():
            return str(cand)
    return escolhido


VENV_PY = _python_do_venv()
SERVIDOR = RAIZ / "app" / "amplia_mcp" / "servidor.py"
USUARIO = sys.argv[1] if len(sys.argv) > 1 else "demo"


def pedir(proc, method, params, req_id):
    """Um pedido JSON-RPC e a leitura da resposta correspondente."""
    msg = {"jsonrpc": "2.0", "id": req_id, "method": method, "params": params}
    proc.stdin.write(json.dumps(msg) + "\n")
    proc.stdin.flush()
    while True:
        linha = proc.stdout.readline()
        if not linha:
            # O stdout fechou. A causa quase nunca é do stdout — é o servidor
            # ter-Morri do com traceback no stderr. Sem isto, o sintoma e
            # "fechou o stdout" e a causa fica a governed-se ao acaso.
            erro = ""
            try:
                if proc.stderr is not None:
                    proc.stdin.close()
                    erro = proc.stderr.read() or ""
            except Exception:
                pass
            raise SystemExit(
                f"[falhou] {method}: o servidor fechou o stdout.\n"
                f"--- stderr do servidor ---\n{erro[-2500:]}"
            )
        linha = linha.strip()
        if not linha:
            continue
        try:
            r = json.loads(linha)
        except ValueError:
            continue  # log do servidor, não resposta
        if r.get("id") == req_id:
            return r


def main():
    # O CAMINHO DO FICHEIRO, e nao `-m app.amplia_mcp.servidor`.
    #
    # Medido: `python -m app.amplia_mcp.servidor` de fora do repositorio da
    #     ModuleNotFoundError: No module named 'app.amplia_mcp'
    #
    # `-m` resolve o nome do modulo no `sys.path` ANTES de correr uma linha
    # do ficheiro — e o `RAIZ_REPO` que o servidor faz para se arranjar sem
    # CWD vive dentro do ficheiro, que nunca chega a ser lido. `-m` só
    # funciona de dentro da raiz, o que um cliente MCP nunca está.
    #
    # Invocar pelo caminho do ficheiro deixa o Python executar aquilo, e o
    # `RAIZ_REPO` faz o resto. Foi medido a funcionar assim.
    cmd = [
        str(VENV_PY),
        str(SERVIDOR),
        "--usuario",
        USUARIO,
    ]
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    # CWD de fora do repositório: e' o que um cliente MCP faz.
    proc = subprocess.Popen(
        cmd,
        cwd=str(RAIZ.parent),
        env=env,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        bufsize=1,
    )
    try:
        r = pedir(
            proc,
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "verificador", "version": "1"},
            },
            1,
        )
        info = r.get("result", {}).get("serverInfo", {})
        print(
            f"OK  initialize -> servidor={info.get('name')} "
            f"versao={info.get('version')}"
        )

        r = pedir(proc, "tools/list", {}, 2)
        tools = r.get("result", {}).get("tools", [])
        print(f"OK  tools/list  -> {len(tools)} ferramentas")
        nomes = {t["name"] for t in tools}
        for MUST in (
            "amplia_clima_agora",
            "amplia_catalogos",
            "amplia_desenhar_pagina",
        ):
            print(f"    {'presente' if MUST in nomes else 'AUSENTE '}: {MUST}")

        r = pedir(proc, "prompts/list", {}, 3)
        prompts = r.get("result", {}).get("prompts", [])
        print(
            f"OK  prompts/list -> {len(prompts)} prompts: "
            f"{[p['name'] for p in prompts]}"
        )

        r = pedir(proc, "resources/list", {}, 4)
        recursos = r.get("result", {}).get("resources", [])
        print(
            f"OK  resources/list -> {len(recursos)} recursos: "
            f"{[x['uri'] for x in recursos]}"
        )

        # A leitura de um prompt tem de devolver texto util.
        r = pedir(proc, "prompts/get", {"name": "amplia_seguranca"}, 5)
        texto = (
            r.get("result", {})
            .get("messages", [{}])[0]
            .get("content", {})
            .get("text", "")
        )
        print(f"OK  prompts/get  -> {len(texto)} chars de orientacao")

        # E uma tool de leitura tem de responder a sério.
        r = pedir(
            proc,
            "tools/call",
            {"name": "amplia_catalogos", "arguments": {}},
            6,
        )
        conteudo = r.get("result", {}).get("content", [{}])[0].get("text", "")
        print(f"OK  tools/call   -> {len(conteudo)} chars de catalogo")

        print("\nTUDO VERIFICADO: o servidor MCP do AmplIA responde ao protocolo.")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    main()
