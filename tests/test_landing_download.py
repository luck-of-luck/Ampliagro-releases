"""Downloads da prévia usam apenas o artefato local explicitamente permitido."""

import hashlib
import json
import threading
import unittest
from functools import partial
from http.server import ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from scripts.servir_landing import LandingHandler


class LandingDownloadTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        root = Path(self.temp.name)
        self.page = root / "landing.html"
        self.page.write_text("<h1>Ampliagro</h1>", encoding="utf-8")
        self.binary = root / "installer.exe"
        self.binary.write_bytes(b"new installer fixture")
        (root / ".env").write_text("private", encoding="utf-8")
        self.server = ThreadingHTTPServer(
            ("127.0.0.1", 0),
            partial(LandingHandler, ficheiro=self.page, instalador=self.binary),
        )
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.temp.cleanup()

    def test_download_matches_manifest_and_head_has_no_body(self):
        with urlopen(self.base + "/downloads/local.json", timeout=5) as response:
            manifest = json.load(response)
            self.assertEqual(response.headers["Cache-Control"], "no-store")
        with urlopen(self.base + manifest["url"], timeout=5) as response:
            body = response.read()
            self.assertIn(
                "Ampliagro-Instalador-Novo-x64.exe",
                response.headers["Content-Disposition"],
            )
        self.assertEqual(hashlib.sha256(body).hexdigest(), manifest["sha256"])
        self.assertEqual(len(body), manifest["size"])
        with urlopen(
            Request(self.base + manifest["url"], method="HEAD"), timeout=5
        ) as response:
            self.assertEqual(response.read(), b"")
            self.assertEqual(int(response.headers["Content-Length"]), len(body))

    def test_missing_installer_and_private_paths_are_not_served(self):
        self.binary.unlink()
        for route in [
            "/downloads/local.json",
            "/downloads/Ampliagro-Instalador-Novo-x64.exe",
            "/.env",
            "/../.env",
            "/%2eenv",
        ]:
            with self.assertRaises(HTTPError) as error:
                urlopen(self.base + route, timeout=5)
            self.assertEqual(error.exception.code, 404)


if __name__ == "__main__":
    unittest.main()
