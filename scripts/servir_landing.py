"""Servidor de previa da landing page.

Serve a landing e o instalador Windows local por rotas explícitas. Nao expoe a raiz do repositorio:
servir o directorio inteiro publicaria `.env`, `CREDENCIAIS.txt` e
`db.sqlite3` por HTTP sem autenticacao nenhuma.

Uso:
    python scripts/servir_landing.py            # http://127.0.0.1:8088/
    python scripts/servir_landing.py --porta 9000
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import sys
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
LANDING = RAIZ / "landing.html"
INSTALADOR = RAIZ / "ampliagro-app/desktop/dist/Ampliagro-x64.exe"


class LandingHandler(SimpleHTTPRequestHandler):
    """Permite somente a página, metadados e o executável configurado."""

    def __init__(
        self, *args, ficheiro: Path, instalador: Path = INSTALADOR, **kwargs
    ) -> None:
        self._ficheiro = ficheiro
        self._instalador = instalador
        super().__init__(*args, directory=str(ficheiro.parent), **kwargs)

    def send_head(self):
        pedido = self.path.split("?")[0]
        if pedido in ("/", "/index.html", "/" + self._ficheiro.name):
            arquivo, tipo = self._ficheiro, "text/html; charset=utf-8"
        elif pedido == "/downloads/Ampliagro-Instalador-Novo-x64.exe":
            arquivo, tipo = self._instalador, "application/octet-stream"
        elif pedido == "/downloads/local.json":
            try:
                with self._instalador.open("rb") as executable:
                    digest = hashlib.file_digest(executable, "sha256").hexdigest()
                size = self._instalador.stat().st_size
            except OSError:
                self.send_error(404, "Gere o instalador Windows local primeiro")
                return None
            payload = json.dumps(
                {
                    "size": size,
                    "sha256": digest,
                    "url": "/downloads/Ampliagro-Instalador-Novo-x64.exe?sha256="
                    + digest,
                }
            ).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            return io.BytesIO(payload)
        else:
            self.send_error(404, "Rota indisponivel")
            return None
        try:
            stream = arquivo.open("rb")
        except OSError:
            self.send_error(404, "Arquivo indisponivel")
            return None
        self.send_response(200)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(arquivo.stat().st_size))
        self.send_header("Cache-Control", "no-store")
        if arquivo == self._instalador:
            self.send_header(
                "Content-Disposition",
                'attachment; filename="Ampliagro-Instalador-Novo-x64.exe"',
            )
        self.end_headers()
        return stream

    def log_message(self, format: str, *args) -> None:  # noqa: A002
        sys.stderr.write(f"{self.address_string()} - {format % args}\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Previa local da landing page")
    parser.add_argument("--porta", type=int, default=8088)
    parser.add_argument("--ficheiro", type=Path, default=LANDING)
    args = parser.parse_args()

    ficheiro = args.ficheiro.resolve()
    if not ficheiro.is_file():
        print(f"[ERRO] landing page nao encontrada: {ficheiro}", file=sys.stderr)
        return 1

    handler = partial(LandingHandler, ficheiro=ficheiro)
    with ThreadingHTTPServer(("127.0.0.1", args.porta), handler) as servidor:
        print(f"Landing page em http://127.0.0.1:{args.porta}/")
        print(f"Ficheiro: {ficheiro}")
        print("Ctrl+C para parar.", flush=True)
        try:
            servidor.serve_forever()
        except KeyboardInterrupt:
            print("\nServidor parado.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
