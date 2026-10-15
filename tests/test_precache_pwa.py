"""
O precache do PWA tem de bater certo com o que os templates pedem.

O QUE ESTE TESTE PROTEGE
------------------------
O Cache API guarda por URL INTEIRA. `/static/js/spa.js?v=A` e
`/static/js/spa.js?v=B` sao duas entradas diferentes. Se o `STATIC_ASSETS` do
`sw.js` levar um `?v=` e o `base.html` pedir outro, o precache guarda uma
entrada que NINGUEM vai buscar e o pedido real vai a rede. Offline, o SPA
router nao arranca e o produtor ve um ecra em branco.

Aconteceu. Estas entradas estavam no precache e nenhuma era servida do cache:

    /static/js/spa.js?v=20250910e          (o base.html pede ?v=20250912a)
    /static/js/guide.js?v=20250910f        (o guia-vegetal pede ?v=20260917a)
    /static/css/navbar-premium.css         (o base.html pede com ?v=)
    /static/css/soft-ui.css                (o base.html pede com ?v=)

O comentario do proprio `sw.js` sobre subir a `CACHE_VERSION` nao resolvia
isto, porque o problema nao era a versao do cache — era o endereco.

Este teste e o que fecha essa porta: se alguem acrescentar um ?v= num template
e nao propagar ao precache (ou o contrario), a suite falha em vez de o
produtor ver um ecra branco no meio do talhao.

O QUE NAO E FALHA
-----------------
- Um ficheiro do precache que nenhum template pede. Alguns sao legítimos:
  `manifest.json` entra por `<link rel="manifest">`, e nao por `{% static %}`.
- Um `?v=` diferente em dois templates. Cada combinacao e uma URL legitima
  e as duas tem de estar no precache (o `soft-ui.css` tem dois, de facto).
- Uma URL de CDN. Nao e servida pelo Django e o Cache API trata-a aparte.
"""

import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SW = RAIZ / "app" / "static" / "js" / "pwa" / "sw.js"
TEMPLATES = RAIZ / "app" / "templates"

# `{% static 'js/x.js' %}?v=123` — o `?v=` pode vir depois, com ou sem aspas.
_RE_STATIC = re.compile(r"\{%\s*static\s*'([^']+)'\s*%\}([^<>\"']*)")
# `/static/js/x.js?v=123` dentro do array do sw.js
_RE_QUOTED = re.compile(r"'([^']+)'")


def _entradas_precache() -> list[str]:
    m = re.search(
        r"const\s+STATIC_ASSETS\s*=\s*\[(.*?)\];", SW.read_text(encoding="utf-8"), re.S
    )
    assert m, "STATIC_ASSETS nao encontrado em sw.js — o teste esta desatualizado"
    return _RE_QUOTED.findall(m.group(1))


def _entradas_estaticas() -> list[str]:
    """So as entradas servidas pelo Django. `/`, `/guias/vegetal/` e as CDN
    ficam de fora: as duas primeiras sao paginas, e as CDN nao passam por
    `{% static %}`."""
    return [u for u in _entradas_precache() if u.startswith("/static/")]


# Entradas sem nenhum template que as peca, por desulto. Cada uma tem de ter
# uma razao escrita aqui — uma lista sem justificacao e uma lista que se
# enche sem ninguem olhar.
ORFAOS_CONHECIDOS = {
    # A `onupgradeneeded` do sw.js e a de `indexeddb.js` correm para o MESMO
    # banco. A versao do sw.js e a copia; a de `indexeddb.js` e a fonte de
    # verdade dos indices. O comentario do sw.js (linhas 343-355) manda que as
    # DUAS listas mudem juntas. Ocommentario manda o oposto de apagar.
    "/static/js/pwa/indexeddb.js",
    # O `sync.js` e o caminho de sincronizacao que o proprio sw.js diz ser o
    # real (evento `online` + temporizador). Nao encontrei quem o carrega — e
    # 10 KB, que e o preco da aposta.
    "/static/js/pwa/sync.js",
}


def _urls_pedidas() -> set[str]:
    pedidas: set[str] = set()
    for html in TEMPLATES.rglob("*.html"):
        texto = html.read_text(encoding="utf-8", errors="replace")
        for caminho, sufixo in _RE_STATIC.findall(texto):
            pedidas.add("/static/" + caminho + (sufixo or "").strip())
    return pedidas


def urls_do_shell() -> list[str]:
    """Os estaticos que o shell da SPA precisa para arrancar offline.

    Nao e tudo o que o `base.html` pede: um template de uma pagina isolada
    (o cadastro de animal, por exemplo) traz o seu proprio JS e nao faz parte
    do arranque. O que esta aqui e o que o produtor ve no ecra principal.
    """
    return [
        u
        for u in _entradas_estaticas()
        if re.search(
            r"/(spa|guide|theme|soft-ui|navbar-premium|widgetbar|"
            r"tailwind-compiled|ampliagro-global|ia-|ia-local/|"
            r"cultures-loader|data-provider|dashboard_appbar|"
            r"adapters/|pwa/)",
            u,
        )
    ]


def _caminho_no_disco(url: str) -> Path:
    """`/static/js/x.js?v=1` -> `<RAIZ>/app/static/js/x.js`.

    O `lstrip` nao e cosmetico: em Python, `Path("/a") / "/b"` da `/b` — o
    componente absoluto descarta tudo o que estava a esquerda. Sem isto, o
    teste media `/static/...` na raiz do disco e acusava as 27 entradas.
    """
    return RAIZ / "app" / url.split("?")[0].lstrip("/")


def test_toda_a_url_estatica_do_precache_existe_no_disco():
    """Uma entrada que aponta para um ficheiro apagado e cache lixo."""
    inexistentes = [
        u for u in _entradas_estaticas() if not _caminho_no_disco(u).exists()
    ]
    assert not inexistentes, (
        "URL no precache sem ficheiro correspondente: "
        + ", ".join(inexistentes)
        + "\nO que acontece: o `install` tenta o fetch, recebe 404, e o `catch` "
        "faz `console.warn` e segue. A entrada fica como cache lixo e o "
        "produtor nunca tem essa pagina."
    )


def test_nenhuma_url_do_shell_esta_orfa_no_precache():
    """O bug dos `?v=` divergentes.

    Uma entrada que nenhum template pede e dinheiro gasto e um bug escondido:
    o precache enche-se, e o pedido que o produtor faz nao encontra nada.
    """
    pedidas = _urls_pedidas()
    orfas = [
        u for u in urls_do_shell() if u not in pedidas and u not in ORFAOS_CONHECIDOS
    ]
    assert not orfas, (
        "Estas entradas do precache nao sao pedidas por nenhum template "
        "(comprovavelmente nunca foram servidas do cache):\n  "
        + "\n  ".join(orfas)
        + "\n\nCausa provavel: o `?v=` aqui e diferente do `?v=` no template. "
        "O Cache API distingue `?v=A` de `?v=B`. Acerta o `?v=` nos dois "
        "lados e sobe a CACHE_VERSION.\n"
        "Se for legitimo, acrescenta a `ORFAOS_CONHECIDOS` COM A RAZAO — uma "
        "lista sem justificacao e uma lista que se enche sem ninguem olhar."
    )


def test_o_manifest_e_a_ampia_estao_no_precache():
    """A promessa do produto e abrir sem sinal. O que nao esta, nao abre.

    `ia-local.js` e o chat. `alerta-feed` e o aviso proativo. Sem os dois no
    precache, a PRIMERA visita sem sinal mostra um chat morto — o `cacheFirst`
    so os guardaria depois de uma visita com rede, que e exactamente o
    cenário que o produto promete cobrir.
    """
    entradas = set(_entradas_precache())
    orfaos = {
        "chat da AmplIA": "/static/js/ia-local/ia-local.js",
        "ponte para o sandbox": "/static/js/ia-sandbox.js?v=1",
        "leitor de alertas": "/static/js/ia-local/alerta-feed.js?v=1",
        "motor proativo na aba": "/static/js/ia-local/proativo-local.js?v=1",
    }
    em_falta = [
        f"{nome} ({url})" for nome, url in orfaos.items() if url not in entradas
    ]
    assert not em_falta, "Falta no precache: " + "; ".join(em_falta)


def test_a_raiz_esta_no_precache():
    """`/` e o dashboard. `start_url` do manifest aponta para la."""
    assert "/" in _entradas_precache(), (
        "A raiz `/` saiu do precache. O `start_url` do manifest.json aponta "
        "para `/`, e sem esta entrada o produtor abre a PWA instalada e cai "
        "no `503 Offline` do `networkFirst`."
    )


def test_a_versao_do_cache_nao_baixou():
    """Guarda contra uma regressão silenciosa.

    O `cacheFirst` so actualiza em segundo plano. Se um estatico do precache
    muda e a `CACHE_VERSION` nao sobe, quem ja visitou continua a ver a versao
    antiga — e nao ha forma de sair sem limpar a cache a mao.

    Este teste NAO fixa a versao exacta. Uma versao fixa e um contador que
    falha a cada bump e obriga a editar o teste junto — o que faz as pessoas
    editarem o numero para o verde em vez de pensarem. `app/ia/registro.py` tem
    o mesmo aviso escrito, e a razao e a mesma.

    O que interessa e a direcao: nunca descer. `v21` e o piso, desde que a
    correcao dos `?v=` e a remocao do `pwa/sync.js` morto.
    """
    m = re.search(
        r"const\s+CACHE_VERSION\s*=\s*'v(\d+)'", SW.read_text(encoding="utf-8")
    )
    assert m, "CACHE_VERSION nao encontrada ou sem a forma 'vN'"
    n = int(m.group(1))
    assert n >= 21, (
        f"CACHE_VERSION desceu para v{n}. O piso e v21 (a correcao dos `?v=` "
        "divergentes e a remocao do `pwa/sync.js` morto). Se baixaste de "
        "proposito, explica aqui porque — e nao no `git log`."
    )
