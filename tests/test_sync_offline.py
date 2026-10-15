"""
O caminho de ESCRITA offline tem de falar com endpoints que aceitam escrita.

O QUE ESTE TESTE PROTEGE
------------------------
O produtor esta no talhao, sem rede, e regista um lancamento. O `data-sync.js`
guarda-o em `localStorage` com `_pending = true` e tenta descarregar quando a
rede volta. Se o endpoint nao aceitar o metodo, o item fica `_pending` para
sempre e o produtor nunca sabe: o `.catch` so faz `console.warn`.

E o que acontece hoje com `financeiro`:

    app/static/js/data-sync.js   API.financeiro = '/api/financeiro/'
    app/api/views/financial.py:222   @api_view(["GET"])

Um POST para `/api/financeiro/` da **405 Method Not Allowed**. O `data-sync.js`
faz `if (!r.ok) throw`, o `catch` regista um warning e devolve `{ok: false}`.
O item continua `_pending`, volta a tentar no proximo sync, e nao ha nada no
ecra que diga ao produtor que o lancamento nao chegou ao servidor.

Isto e a mesma classe de bug que o `sw.js` ja documentou e corrigiu para o
`Background Sync` (ver o comentario em sw.js, "ERRADO SE FOSSE LIGADO"): os
mesmos tres endpoints `/api/caderno/*` que nao existiam. A correcao de la
tirou o flush do service worker mas deixou o `pwa/sync.js` a apontar para
eles — e esse continua no precache.

O QUE ESTE TESTE FAZ
--------------------
Para cada tipo do `DataStore.TYPES`, confere que o endpoint do `API[...]`
aceita POST (criar) e PUT (actualizar). Um GET-only falha aqui, no CI, em
segundos — em vez de no talhao, meses depois.
"""

import ast
import json
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DATA_SYNC = RAIZ / "app" / "static" / "js" / "data-sync.js"
DATA_STORE = RAIZ / "app" / "static" / "js" / "data-store.js"
# O `pwa/sync.js` — o sync do Caderno de Campo, distinto do `data-sync.js`.
SYNC = RAIZ / "app" / "static" / "js" / "pwa" / "sync.js"
API_URLS = RAIZ / "app" / "api" / "urls.py"

# Os metodos que o data-sync usa: POST quando nao ha id, PUT quando ha.
METODOS = ("POST", "PUT")


def _mapear_api() -> dict[str, str]:
    """Extrai o `var API = {...}` do data-sync.js."""
    m = re.search(
        r"var\s+API\s*=\s*\{(.*?)\};", DATA_SYNC.read_text(encoding="utf-8"), re.S
    )
    assert m, "API map nao encontrado em data-sync.js"
    return dict(re.findall(r"(\w+)\s*:\s*'([^']+)'", m.group(1)))


def _tipos_do_store() -> list[str]:
    m = re.search(
        r"var\s+TYPES\s*=\s*\[(.*?)\];", DATA_STORE.read_text(encoding="utf-8"), re.S
    )
    assert m, "TYPES nao encontrado em data-store.js"
    return re.findall(r"'([^']+)'", m.group(1))


def _router_registados() -> set[str]:
    """Os `router.register(r"x", ...)` — os que aceitam CRUD."""
    return set(
        re.findall(
            r'router\.register\(r?"([\w-]+)"', API_URLS.read_text(encoding="utf-8")
        )
    )


def _endpoints_de_funcao() -> dict[str, str | None]:
    """`path("financeiro/", financeiro_data)` -> {'financeiro': 'financeiro_data'}

    Precisamos do nome da view para ir ver o decorator `@api_view`.
    """
    txt = API_URLS.read_text(encoding="utf-8")
    out: dict[str, str | None] = {}
    for m in re.finditer(r'path\(\s*r?"([^"]+)"\s*,\s*([\w.]+)', txt):
        rota, view = m.group(1).rstrip("/").split("/")[-1], m.group(2)
        out[rota] = view.split(".")[-1]
    return out


def _metodos_de_view(nome: str) -> set[str] | None:
    """Le o `@api_view([...])` da view. `None` se nao encontrarmos."""
    for py in (RAIZ / "app" / "api" / "views").glob("*.py"):
        txt = py.read_text(encoding="utf-8", errors="replace")
        # Procura o decorator imediatamente antes de `def <nome>(`.
        m = re.search(
            r"@api_view\(\s*\[([^\]]*)\]\s*\)\s*(?:@[^\n]*\n\s*)*def\s+"
            + re.escape(nome)
            + r"\s*\(",
            txt,
        )
        if m:
            return set(re.findall(r'"([A-Z]+)"', m.group(1)))
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Os testes
# ─────────────────────────────────────────────────────────────────────────────


def test_o_mapa_api_nao_aponta_para_nada_que_nao_exista():
    """Endpoint typo'ado = 404 silencioso no sync."""
    api = _mapear_api()
    routers = _router_registados()
    funcoes = _endpoints_de_funcao()

    inexistentes = []
    for tipo, url in api.items():
        nome = url.rstrip("/").split("/")[-1]
        if nome not in routers and nome not in funcoes:
            inexistentes.append(f"{tipo} -> {url}")

    assert not inexistentes, (
        "O `API` do data-sync.js aponta para endpoints que nao existem:\n  "
        + "\n  ".join(inexistentes)
        + "\n\nUm 404 no sync nao mostra nada ao produtor: o `catch` faz "
        "`console.warn` e o item fica `_pending` para sempre."
    )


def test_todo_o_tipo_do_datastore_tem_endpoint():
    """Um tipo no TYPES sem entrada no API e um item que nunca sai do telemovel."""
    api = _mapear_api()
    sem_endpoint = [t for t in _tipos_do_store() if t not in api]
    assert not sem_endpoint, (
        "Estes tipos estao no `DataStore.TYPES` mas nao tem entrada no `API` "
        "do data-sync.js — nunca sao sincronizados:\n  " + "\n  ".join(sem_endpoint)
    )


def test_todo_o_endpoint_aceita_escrita():
    """A RAIZ do bug: `/api/financeiro/` e GET-only e o sync faz POST.

    Um item de financeiro guardado offline levaria 405 em cada tentativa, e o
    produtor nunca veria nada — o lancamento nao chegaria ao servidor.
    """
    api = _mapear_api()
    routers = _router_registados()
    funcoes = _endpoints_de_funcao()

    so_leitura = []
    sem_metodo_conhecido = []

    for tipo, url in sorted(api.items()):
        nome = url.rstrip("/").split("/")[-1]

        if nome in routers:
            # Um ViewSet do DRF aceita create/update por defeito. A excepcao
            # e um `http_method_names` restrito — que aqui nao ha.
            continue

        if nome in funcoes:
            metodos = _metodos_de_view(funcoes[nome])
            if metodos is None:
                sem_metodo_conhecido.append(f"{tipo} -> {url} (view `{funcoes[nome]}`)")
                continue
            em_falta = [m for m in METODOS if m not in metodos]
            if em_falta:
                so_leitura.append(
                    f"{tipo} -> {url} aceita {sorted(metodos)}, "
                    f"o sync usa {'/'.join(em_falta)}"
                )

    assert not so_leitura, (
        "Estes endpoints sao de LEITURA e o data-sync.js escreve neles. Cada "
        "item guardado offline levaria 4xx em TODAS as tentativas, e o produtor "
        "nunca veria nada (o `catch` so faz console.warn):\n  "
        + "\n  ".join(so_leitura)
        + "\n\nOu o endpoint passa a aceitar escrita, ou o tipo sai do "
        "`DataStore.TYPES` ate existir um endpoint de escrita."
    )

    # Nao falhar por ignorancia: se nao conseguimos ler o decorator, dizemos.
    assert not sem_metodo_conhecido, (
        "Nao consegui ler o `@api_view` destas views, portanto NAO CONSIGO "
        "afirmar que aceitam escrita. Vem verificar:\n  "
        + "\n  ".join(sem_metodo_conhecido)
    )


# Onde vive hoje o codigo que o produtor executa ao carregar a fila.
#
# MEDIDO 2026-10-05. Este `INDEX` apontava para `app/templates/index.html`.
# Era verdade ate o refactor: a logica da folha de calculo migrou para
# `app/static/js/pagina-index.js`, que `index.html:1714` carrega.
#
# Um teste que le um ficheiro morto passa a testar o vazio — e aqui falhava
# por razao errada: acusava `index.html` de prometer "salvos com sucesso"
# sem caminho para a falta de rede, quando essa frase esta agora em
# `pagina-index.js`, **depois** da correccao, dentro do ramo certo.
INDEX = RAIZ / "app" / "static" / "js" / "pagina-index.js"


def test_o_sync_js_morto_nao_esta_no_precache():
    """`pwa/sync.js` e `pwa/indexeddb.js` nao sao carregados por nenhum template.

         O `pwa/sync.js` faz POST para `/api/caderno/notas/`, `/api/caderno/fotos/` e
         `/api/caderno/voice/` — nenhum dos tres existe. E o `pwa/indexeddb.js`, que
         criaria o `window.OfflineDB` de que o `sync.js` depende, tambem nao e
         carregado. Sao 21 KB de precache a guardar codigo morto.

         O caminho de escrita offline real e o `app/static/js/data-sync.js`, com
         `localStorage` e endpoints que aceitam escrita.

    Nota sobre o alcance do teste: so se le o ARRAY do `STATIC_ASSETS`, nao o
        ficheiro todo. A primeira versao fazia `"pwa/sync.js" in sw` e falhava
        por causa do comentario que explica a remocao — o teste tinha de ler o
        array, como o `test_precache_pwa.py` faz.
    """
    sw = (RAIZ / "app" / "static" / "js" / "pwa" / "sw.js").read_text(encoding="utf-8")
    m = re.search(r"const\s+STATIC_ASSETS\s*=\s*\[(.*?)\];", sw, re.S)
    assert m, "STATIC_ASSETS nao encontrado em sw.js"
    entradas = re.findall(r"'([^']+)'", m.group(1))

    for morto in ("/static/js/pwa/sync.js", "/static/js/pwa/indexeddb.js"):
        assert morto not in entradas, (
            f"`{morto}` voltou ao precache. Confirma primeiro que passou a ter "
            "quem o carregue — hoje nao tem, e aponta para endpoints que nao "
            "existem."
        )


def test_o_toast_nao_promete_sucesso_ao_que_nao_sincroniza():
    """A parte que doi mais: o produtor via "salvos com sucesso" e perdia o dado.

    A cadeia toda:

      index.html  DataStore.save('financeiro', linha)   -> _pending = true
      index.html  showToast('salvos com sucesso!')     -> o produtor acredita
      data-sync   POST /api/financeiro/                -> 405, GET-only
      data-sync   .catch -> console.warn               -> invisivel
      ...         o item fica _pending para sempre

    Um toast verde sobre um registo que nunca chega ao servidor e pior que
    nenhuma mensagem: e o produtor a fazer as contas com um numero que so
    existe no telefone dele.
    """
    txt = INDEX.read_text(encoding="utf-8")

    # Nao pode haver um mapeamento de 'financeiro' para a fila offline.
    assert not re.search(r"financeiro\s*:\s*'financeiro'", txt), (
        "O index.html voltou a meter 'financeiro' na fila offline. "
        '`/api/financeiro/` e `@api_view(["GET"])` — o POST leva 405 em cada '
        "tentativa e o registo nunca chega ao servidor."
    )

    # E o caminho feliz nao pode ser a unica resposta: tem de haver uma rama
    # para quando o que foi salvo NAO vai sincronizar.
    m = re.search(
        r"(pessoas?_?financeir|guardados neste aparelho|precisam? de liga)", txt, re.I
    )
    assert m, (
        "O pagina-index.js diz 'salvos com sucesso' sem nenhum caminho para o "
        "caso de nao haver rede. Ou o produtor e avisado de que ficou no "
        "aparelho, ou o tipo sai da fila."
    )


# ─────────────────────────────────────────────────────────────────────────────
# O caminho do apagamento — MEDIDO, 2026-10-04
#
# Estes dois testes NAO leem texto: correm o `data-sync.js` e o
# `data-store.js` reais num `vm` do Node, com `fetch` e `localStorage`
# falsos, e observam o que sai pela rede e o que fica no armazenamento.
#
# Porque nao bastam os estruturais: o bug era invisible a leitura. O
# `deletedIds` era escrito em `data-store.js` e nao lido em lado nenhum —
# um `grep` mostrava o `write`, e nao mostrava a falta do `read`.
# ─────────────────────────────────────────────────────────────────────────────

JS_DIR = RAIZ / "tests" / "js"


def _node(*args: str) -> tuple[int, str]:
    """Corre um script Node e devolve (codigo, stdout+stderr)."""
    import subprocess

    p = subprocess.run(
        ["node", *[str(a) for a in args]],
        capture_output=True,
        text=True,
        cwd=str(RAIZ),
        timeout=120,
    )
    return p.returncode, p.stdout + p.stderr


def test_o_apagamento_offline_chega_ao_servidor():
    """O P0: o produtor apagava um registo e ele voltava sozinho.

    MEDIDO antes da correccao: `pedidos enviados: []`, `deletedIds: [3]`,
    `pendingChanges: 0` (o badge dizia "sincronizado") e, depois do
    `pullFromServer` que o `init()` corre sozinho, o registo de volta no
    aparelho. O DELETE nunca tinha saido: `DataStore.delete()` tirava o item
    de `store.data` e sobe o id para `deletedIds`, mas o push so percorria
    `store.data`.
    """
    rc, saida = _node(JS_DIR / "prova_delete_offline.cjs")
    assert rc == 0, saida
    assert "REPRODUZIDO" not in saida, saida
    assert "o talhao apagado ficou apagado" in saida, saida
    # O DELETE tem mesmo de sair, e nao basta que o script acabe bem.
    assert '"method":"DELETE"' in saida, saida


def test_o_sync_diz_a_verdade_quando_falha():
    """Um DELETE recusado tem de ficar para a proxima, e o badge tem de dizer que ha pendentes.

    Um sync que "acaba" e que apaga a lista de pendencias nao basta — o
    produtor passa a acreditar que o trabalho foi entregue. E o que torna o
    apagamento perdido sem possibilidade de recovery: o proximo pull repõe o
    registo.
    """
    rc, saida = _node(JS_DIR / "prova_sync_honesto.cjs")
    assert rc == 0, saida
    assert "FALHA" not in saida, saida
    assert saida.count("OK") >= 8, saida


def test_a_hora_do_produtor_sobrevive_ao_sync():
    """A nota de campo tem de ficar datada quando o produtor a escreveu.

    MEDIDO: `indexeddb.js:198` grava `created_at` (a hora da observacao) e o
    `sync.js` nao a mandava. O servidor assumia `now()` — a hora de
    recepcao. Uma observacao de pulgao escrita as 06:00 e sincronizada as
    18:00 ficava as 18:00, que e' a informacao que decide se a pulverizacao
    chegou a tempo.
    """
    txt = SYNC.read_text(encoding="utf-8")

    # O corpo do POST tem de levar a hora.
    m = re.search(
        r"fetch\(\s*'/api/caderno/notas/'.*?JSON\.stringify\(\{(.*?)\}\)", txt, re.S
    )
    assert m, "nao encontrei o payload de /api/caderno/notas/ no sync.js"
    assert "registada_em" in m.group(1), (
        "o payload da nota de campo nao manda `registada_em`. A hora do "
        "produtor existe no IndexedDB (`created_at`) e esta a ser deitada "
        "fora: o servidor assume a hora de recepcao e a observacao fica "
        "datada ao sync."
    )

    # E o valor tem de vir do registo, nao de um new Date() do sync.
    linha = [ln for ln in m.group(1).splitlines() if "registada_em" in ln]
    assert linha, "sem linha de registada_em"
    assert "new Date()" not in linha[0], (
        "`registada_em` esta a ser gerado no momento do sync. Tem de ser a "
        "hora que o produtor escreveu."
    )
