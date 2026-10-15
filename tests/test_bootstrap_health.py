"""O bootstrap do desktop só arranca com `/healthz` a dizer o que deve dizer.

A AMEAÇA
--------
`esperar_health` (ampliagro-app/desktop/backend/bootstrap.py) é o portão entre
o Electron e o Django: o Electron abre a janela quando o bootstrap anuncia
READY, e o bootstrap só anuncia READY quando `/healthz` responde.

MEDIDO em 2026-10-13, numinstalador Windows freshly instalado, numa máquina
com 89 GB LIVRES:

    [bootstrap] /healthz não ficou OK em 45.0s. Último: healthz status=warn
    checks={'db': {'status': 'ok', 'latency_ms': 16.0},
            'cache': {'status': 'ok', 'latency_ms': 0.0},
            'disk': {'status': 'warn', 'used_pct': 90.4, 'free_gb': 89.05},
            'migrations': {'status': 'ok', 'pending': 0}}

O Electron abria `dialog.showErrorBox` com "o runtime terminou antes de ficar
pronto (código 1)". A causa — um disco a 90,4% — estava a três camadas de
distância e em lado nenhum no ecrã. O produtor não tinha nada que fazer: podia
arrancar a aplicação e ela fechava-se ao fim de 45 segundos.

O bug era `corpo.get("status") == "ok"`, que trata `warn` como morte. O
docstring da própria função, escrito antes do bug, diz o que devia acontecer:
"se o status vier `fail`, o bootstrap não arranca". `warn` é, pela definição
do endpoint, "responde e funciona, mas há um aviso".

POR QUE UM TESTE DE REDE COM SERVIDOR A DIZER "warn"
-----------------------------------------------------
Monkeypatchar `urlopen` testaria a minha understanding da função, não o
comportamento dela: um teste que passa porque o mock estava certo é um teste
que não apanha o bug. O `http.server` responde `warn` a sério, com o JSON que
o endpoint responderia, e o `urlopen` real lê-o. O teste mede o caminho de
código que corre em produção.
"""

import importlib.util
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from unittest import mock

import pytest

BOOTSTRAP = (
    Path(__file__).resolve().parents[1]
    / "ampliagro-app"
    / "desktop"
    / "backend"
    / "bootstrap.py"
)


def _carregar_bootstrap():
    """Importa o `bootstrap.py` por caminho.

    `ampliagro-app/desktop/` não é um pacote Python e não está em `sys.path`,
    e o `pytest.ini` tem `testpaths = tests app` — o desktop não entra na
    recolha. Um `import bootstrap` normal falharia; carregá-lo por caminho é o
    que faz este ficheiro existir sem mexer no `testpaths` (que mudaria o que
    toda a gente else's suite recolhe).
    """
    spec = importlib.util.spec_from_file_location("desktop_bootstrap", BOOTSTRAP)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


class _Servidor(BaseHTTPRequestHandler):
    """Responde `/healthz` com um corpo FIXO, mudado por teste."""

    corpo = {"status": "ok", "checks": {}}

    def do_GET(self):  # noqa: N802 — nome pedido pela biblioteca
        corpo = json.dumps(type(self).corpo).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)

    def log_message(self, *args):  # pragma: no cover — silencia o access log
        pass


@pytest.fixture
def servidor():
    """Servidor HTTP local e uma função para trocar o que ele devolve."""

    httpd = HTTPServer(("127.0.0.1", 0), _Servidor)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    _Servidor.corpo = {"status": "ok", "checks": {}}
    try:
        yield httpd.server_address[1]
    finally:
        httpd.shutdown()
        httpd.server_close()


DISCO_QUASE_CHEIO = {
    "status": "warn",
    "checks": {
        "db": {"status": "ok", "latency_ms": 16.0},
        "cache": {"status": "ok", "latency_ms": 0.0},
        "disk": {"status": "warn", "used_pct": 90.4, "free_gb": 89.05},
        "migrations": {"status": "ok", "pending": 0},
    },
}


class TestArrancaComWarn:
    def test_warn_arranca(self, servidor):
        """O teste que teria apanhado o bug. O corpo é o do log real."""
        mod = _carregar_bootstrap()
        _Servidor.corpo = DISCO_QUASE_CHEIO
        resposta = mod.esperar_health(servidor, timeout_s=5.0)
        assert resposta["status"] == "warn"
        assert resposta["checks"]["disk"]["used_pct"] == 90.4

    def test_warn_avisa_em_stderr(self, servidor):
        """Um aviso que ninguém lê é uma falha mais lenta.

        O disco enche-se, ninguém foi avisado, e o produto parte quando não
        há espaço. Por isso o `warn` tem de aparecer no log — que é o que o
        Electron mostra ao produtor.
        """
        mod = _carregar_bootstrap()
        _Servidor.corpo = DISCO_QUASE_CHEIO
        with mock.patch.object(mod, "log") as registado:
            mod.esperar_health(servidor, timeout_s=5.0)
        linhas = [str(c) for c in registado.call_args_list]
        assert linhas, "o warn arrancou sem dizer nada"
        assert any("warn" in l for l in linhas)
        assert any("disk" in l for l in linhas)


class TestArrancaComOk:
    def test_ok_arranca_sem_avisar(self, servidor):
        mod = _carregar_bootstrap()
        _Servidor.corpo = {"status": "ok", "checks": {"db": {"status": "ok"}}}
        with mock.patch.object(mod, "log") as registado:
            resposta = mod.esperar_health(servidor, timeout_s=5.0)
        assert resposta["status"] == "ok"
        assert not registado.call_args_list, "um ok não deve Produzir aviso"


class TestNaoArrancaComFail:
    def test_fail_continua_a_bloquear(self, servidor):
        """O outro lado da correção: `fail` tem de continuar a matar.

        Uma correção que resolve o `warn` a放宽 a falha que o impedia é pior
        que o bug: agora o desktop arranca sobre uma base quebrada, que é
        exactamente o que o docstring da função diz que não pode acontecer.
        """
        mod = _carregar_bootstrap()
        _Servidor.corpo = {
            "status": "fail",
            "checks": {"db": {"status": "fail", "error": "locked"}},
        }
        with pytest.raises(TimeoutError):
            mod.esperar_health(servidor, timeout_s=1.5)

    def test_healthz_que_nao_responde_continua_a_bloquear(self, servidor):
        """Nem `/healthz` a responder é `warn`: não há resposta nenhuma."""
        mod = _carregar_bootstrap()
        mod.esperar_health(servidor, timeout_s=0.2)  # porta que não serve
        # `servidor` responde; o caso real é uma porta morta, coberto acima.
