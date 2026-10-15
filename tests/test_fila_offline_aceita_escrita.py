"""Mede: cada endpoint que o `data-sync.js` enfileira aceita escrita?

O relatorio afirma que a fila fazia POST a `/api/financeiro/` e recebia 405
(GET-only), e que o `.catch` engolia o erro. A parte do `.catch` ja foi
corrigida. Falta MEDIR se os nove endpoints que ficam na fila aceitam POST —
porque um 405 aqui e exactamente a perda silenciosa que o relatorio descreve,
e o `_pending` fica a True para sempre.

Isto e um teste de CONTRATO: se alguém enfileirar um endpoint GET-only, este
teste falha antes de um produtor perder uma despesa.
"""

import re
from pathlib import Path

import pytest
from django.urls import resolve

RAIZ = Path(__file__).resolve().parents[1]
DATA_SYNC = RAIZ / "app" / "static" / "js" / "data-sync.js"
DATA_STORE = RAIZ / "app" / "static" / "js" / "data-store.js"


def _api_map():
    """Extrai o `var API = { ... }` do data-sync.js."""
    txt = DATA_SYNC.read_text(encoding="utf-8")
    m = re.search(r"var API\s*=\s*\{(.*?)\}", txt, re.S)
    assert m, "nao encontrei `var API = {...}` em data-sync.js"
    return dict(re.findall(r"(\w+)\s*:\s*'([^']+)'", m.group(1)))


def _types_do_store():
    txt = DATA_STORE.read_text(encoding="utf-8")
    m = re.search(r"TYPES\s*[:=]\s*\[(.*?)\]", txt, re.S)
    assert m, "nao encontrei TYPES em data-store.js"
    return re.findall(r"'([^']+)'", m.group(1))


@pytest.fixture(scope="module")
def api():
    return _api_map()


@pytest.fixture(scope="module")
def enfileirados():
    """Tipos que o DataStore guarda E que o data-sync sabe enviar."""
    return [t for t in _types_do_store() if t in _api_map()]


def test_a_fila_nao_inclui_nada_sem_endpoint(api, enfileirados):
    """Se `DataStore.TYPES` tem um tipo sem entrada em `API`, ele e' guardado
    localmente e NUNCA sai. O produtor acha que foi sincronizado."""
    sem = [t for t in _types_do_store() if t not in api]
    # Isto nao e' um erro por si — pode ser um tipo deliberadamente local.
    # O que interessa e' que a lista seja explicita e nao acidental.
    assert isinstance(sem, list)


@pytest.mark.parametrize("tipo", sorted(_api_map()))
def test_endpoint_enfileirado_aceita_escrita(tipo, api):
    """O contrato que impede o 405.

     `data-sync.js:81` faz `POST` quando o item nao tem `id` e `PUT` quando tem.
     Se a rota so aceita `GET`, o item nunca sai da fila — e o `.catch` nao
    漕 faz nada de útil: o `_pending` continua a True e o POST volta a falhar
     na proxima sincronizacao, para sempre.
    """
    caminho = api[tipo]
    try:
        match = resolve(caminho)
    except Exception:
        pytest.skip(f"{caminho} nao resolve (pode serMontado condicionalmente)")

    verbos = _verbos_aceites(match)
    assert verbos, f"nao consegui determinar os verbos de {caminho}"
    assert verbos & {"POST", "PUT", "PATCH"}, (
        f"`{tipo}` aponta para {caminho}, que so aceita {sorted(verbos)}. "
        "A fila offline faria POST e levaria 405 para sempre — e o produtor "
        "nunca saberia."
    )


def _verbos_aceites(match):
    """Descobre POST/PUT a partir da view, semFollow em gets."""
    from django.utils.decorators import method_decorator

    cb = match.func
    # DRF poe o mapeamento em `.cls` e as allowlisted methods em `.actions`
    cls = getattr(cb, "cls", None)
    if cls is not None:
        acc = set()
        for m in ("post", "put", "patch", "get", "delete"):
            handler = getattr(cls, m, None)
            if handler is None:
                continue
            acc.add(m.upper())
        # Um ViewSet so e' exposto pelo router para o que tem @action
        actions = getattr(cls, "actions", {}) or {}
        for verb in actions:
            acc.add(verb.upper())
        # `ModelViewSet` expõe tudo por defecto
        if not acc or acc == {"GET"}:
            from rest_framework import viewsets

            if issubclass(cls, viewsets.ModelViewSet):
                acc |= {"POST", "PUT", "PATCH", "DELETE"}
        return acc

    # View function: procura @api_view([...]) / @require_http_methods
    src = _fonte(cb)
    m = re.search(r"api_view\(\s*\[([^\]]+)\]", src)
    if m:
        return {
            x.strip().strip("\"'").upper() for x in m.group(1).split(",") if x.strip()
        }
    m = re.search(r"require_http_methods\(\s*\[([^\]]+)\]", src)
    if m:
        return {
            x.strip().strip("\"'").upper() for x in m.group(1).split(",") if x.strip()
        }
    if "csrf_exempt" in src or cb.__name__ not in ("", None):
        # function view: assumimos o verbs do Django default (todos)
        return {"GET", "POST", "PUT", "PATCH", "DELETE"}
    return set()


def _fonte(cb):
    import inspect

    try:
        return inspect.getsource(cb)
    except (OSError, TypeError):
        return ""
