"""Os invariantes que quebraram nesta sessao, virados em verificacoes.

PORQUE ISTO EXISTE
==================
O painel dizia "sem dado" em tudo, durante semanas, e NADIZEM via:
o dashboard nao carregava dados. Um agente MCP que perguntasse "os widgets
estao a mostrar os dados?" nao tinha onde olhar — o catalogo diz o que a
IA sabe FAZER, nao o que o sistema esta A DAR.

Estes cinco invariantes sao os que quebraram, todos medidos:

  1. Mojibake nos `.js` — o rotulo do KPI chegou a tela como
     `ÃƒÂrea Total` (codepoints U+00C3 U+0192 U+00C2 U+0081), e media
     **0 px de altura**: um rotulo invisivel.
  2. `hasWidgetSession()` lia o cookie `sessionid`, que e' HTTP-only e
     invisivel a `document.cookie`. A guarda era `false` para TODOS os
     utilizadores autenticados, sempre — e os dados nunca eram buscados.
  3. `AUTHENTICATION_BACKENDS` com um backend sem `get_user`: se alguma
     sessao apontasse para ele, 500 em todas as paginas.
  4. Um handler de skill que nao existe no registo: o modelo ia chamar
     uma ferramenta inexistente e levar `tool_fora_do_catalogo`.
  5. Migracoes por aplicar: o codigo pedia uma coluna que a base nao
     tinha, e o middleware de tenancy desativava-se a si proprio.

O QUE ESTE MODULO NAO E'
========================
Nao e' um painel. Nao adivinha. Cada item e' lido do ficheiro ou da base
no momento da chamada e vem com `ok`, `valor` e `onde`. Um item que nao
consegue ser medido vem `null` com o motivo — nunca `true` por omissao.

Isto segue a regra que ja existe no repo: `fonte_dado: sem_dado` quando
nao ha medicao, e nunca um numero gerado a apresentar como medido. Um
verificador que devolvesse `ok: true` sem ter lido nada seria o mesmo
bug do "IoT: 4" com 8 dispositivos, outra vez e ao contrario.
"""

import pathlib
import re

RAIZ = pathlib.Path(__file__).resolve().parents[2]  # app/amplia_mcp/estado.py -> repo

# MEDIDO: `parents[3]` sobe um nivel a mais e as duas verificacoes de
# ficheiro devolviam `null` — "a pasta nao existe neste checkout". Vale a
# pena deixar escrito porque o sintoma era silencioso: o verificador nao
# rebentava, dizia que nao sabia. E `null` e' o comportamento certo para
# quem nao mediu; `True` teria sido a mentira que este modulo existe para
# nao contar.


def _item(ok, valor, onde, o_que, porquê=""):
    return {
        "ok": ok,
        "valor": valor,
        "onde": onde,
        "o_que": o_que,
        "nota": porquê or None,
    }


def _inviavel(onde, o_que, porque):
    """O que nao deu para medir. `null`, nunca `True`."""
    return {
        "ok": None,
        "valor": None,
        "onde": onde,
        "o_que": o_que,
        "nota": porque,
    }


# ----------------------------------------------------------------------
# 1) MOJIBAKE NOS FICHEIROS JS
# ----------------------------------------------------------------------
# Um controlo C1 (U+0080-U+009F) nao existe em texto nenhum, em nenhuma
# lingua. E' a assinatura de um byte lido como latin-1.
#
# O detector NAO pode procurar `Ã` ou `Â` isolados: sao letras portuguesas
# legitimas (`avô`, `irmã`, `João`). Um detector que as acuse da 4069
# falsos positivos num unico ficheiro — foi o que aconteceu na primeira
# versao deste. Por isso: controlo C1 e o par `Ãƒ`.
_C1 = re.compile("[\u0080-\u009f]")
_AE_F = re.compile("\u00c3\u0192")


def verificar_mojibake_js():
    pasta = RAIZ / "app" / "static" / "js"
    if not pasta.exists():
        return _inviavel(
            "app/static/js",
            "mojibake nos ficheiros JS",
            "a pasta nao existe neste checkout",
        )
    maus = {}
    total_c1 = 0
    for f in sorted(pasta.rglob("*.js")):
        if any(x in f.as_posix() for x in ("node_modules", ".venv", "staticfiles")):
            continue
        try:
            t = f.read_text(encoding="utf-8")
        except Exception:
            continue
        c1 = len(_C1.findall(t))
        af = len(_AE_F.findall(t))
        if c1 or af:
            maus[f.relative_to(RAIZ).as_posix()] = {"C1": c1, "A_f": af}
            total_c1 += c1 + af
    return _item(
        not maus,
        {"ficheiros_com_mojibake": len(maus), "ocorrencias": total_c1, "detalhe": maus},
        "app/static/js/**/*.js",
        "texto com codificacao partida",
        "MEDIDO 2026-10-05 em pagina-index.js: 1658 controlos C1 e 892 pares "
        "Ãƒ. O rotulo do KPI chegou a tela como 'ÃƒÂrea Total'. `Ã` e "
        "`Â` sao letras portuguesas — o detector usa controlo C1 e o par "
        "`Ãƒ` para nao acusar `avô`.",
    )


# ----------------------------------------------------------------------
# 2) A GUARDA DE SESSAO
# ----------------------------------------------------------------------
def _cookie_http_only():
    """O `SESSION_COOKIE_HTTPONLY` esta a True? Le-o dos settings."""
    try:
        for nome in (
            "config/settings/base.py",
            "config/settings/dev.py",
            "config/settings/test.py",
        ):
            p = RAIZ / nome
            if not p.exists():
                continue
            t = p.read_text(encoding="utf-8", errors="replace")
            m = re.search(r"SESSION_COOKIE_HTTPONLY\s*=\s*(\w+)", t)
            if m:
                return m.group(1) == "True", nome
    except Exception:
        return None, None
    return None, None


def verificar_guarda_sessao():
    """`hasWidgetSession()` pode ler a sessao?"""
    js = RAIZ / "app" / "static" / "js" / "pagina-index.js"
    if not js.exists():
        return _inviavel(
            "app/static/js/pagina-index.js",
            "a guarda de sessao",
            "o ficheiro nao existe",
        )
    txt = js.read_text(encoding="utf-8", errors="replace")
    m = re.search(
        r"window\.hasWidgetSession\s*=\s*function\s*\(\)\s*\{(.*?)\n\};", txt, re.S
    )
    if not m:
        return _inviavel(
            "app/static/js/pagina-index.js",
            "a guarda de sessao",
            "nao encontrei window.hasWidgetSession",
        )
    corpo = m.group(1)
    sem_comentarios = re.sub(r"/\*.*?\*/", "", corpo, flags=re.S)
    sem_comentarios = re.sub(r"^\s*//.*$", "", sem_comentarios, flags=re.M)

    http_only, onde_settings = _cookie_http_only()
    usa_flag = "data-authenticated" in sem_comentarios
    pos_flag = sem_comentarios.find("data-authenticated")
    pos_cookie = sem_comentarios.find("getCookie(")

    # O problema so existe se: o cookie e' http-only E a guarda depende
    # dele. Se `http_only` for None, nao se pode afirmar nada.
    if http_only is None:
        return _inviavel(
            "config/settings",
            "se o cookie de sessao e' legivel por JS",
            "SESSION_COOKIE_HTTPONLY nao esta declarado; o Django usa True "
            "por omissao, mas nao o li",
        )

    if usa_flag and (pos_cookie == -1 or pos_flag < pos_cookie):
        return _item(
            True,
            {"fonte": "data-authenticated do servidor", "cookie_http_only": http_only},
            "app/static/js/pagina-index.js",
            "a guarda de sessao ve a autenticacao",
            "MEDIDO: antes lia `getCookie('sessionid')`, que e' HTTP-only e "
            "devolve sempre null — a guarda era `false` para todos os "
            "utilizadores autenticados e o painel mostrava 'sem dado'.",
        )

    return _item(
        False,
        {
            "fonte": "cookie http-only",
            "cookie_http_only": http_only,
            "le_data_authenticated": usa_flag,
        },
        "app/static/js/pagina-index.js",
        "a guarda de sessao ve a autenticacao",
        "A guarda depende de `getCookie('sessionid')` e o cookie e' "
        f"HTTP-only (config/settings: SESSION_COOKIE_HTTPONLY={http_only} "
        f"em {onde_settings}): "
        "`document.cookie` nao o ve. O resultado e' `false` para todos os "
        "utilizadores autenticados, e os dados nunca sao buscados.",
    )


# ----------------------------------------------------------------------
# 3) BACKENDS DE AUTENTICACAO
# ----------------------------------------------------------------------
def verificar_backends():
    try:
        from django.conf import settings
        from django.utils.module_loading import import_string
    except Exception as e:
        return _inviavel(
            "AUTHENTICATION_BACKENDS",
            "os backends tem get_user",
            f"Django nao carregou: {e}",
        )
    sem = []
    for caminho in getattr(settings, "AUTHENTICATION_BACKENDS", []) or []:
        try:
            cls = import_string(caminho)
        except Exception as e:
            sem.append({"backend": caminho, "erro": str(e)[:60]})
            continue
        if not hasattr(cls, "get_user"):
            sem.append({"backend": caminho, "erro": "sem get_user"})
    return _item(
        not sem,
        {
            "total": len(getattr(settings, "AUTHENTICATION_BACKENDS", []) or []),
            "problemas": sem,
        },
        "config/settings/base.py :: AUTHENTICATION_BACKENDS",
        "todo o backend tem get_user",
        "MEDIDO: `AxesStandaloneBackend` tem MRO `[object]` e nao tem "
        "`get_user`. O Django grava na sessao o PRIMEIRO backend que "
        "autenticou; se for esse, `backend.get_user(user_id)` levanta "
        "AttributeError e toda a pagina da 500.",
    )


# ----------------------------------------------------------------------
# 4) HANDLERS DE SKILL QUE NAO EXISTEM
# ----------------------------------------------------------------------
def verificar_skills():
    try:
        from app.amplia_mcp.skills import catalogo_skis
    except Exception as e:
        return _inviavel(
            "app/ia/skills",
            "os handlers das skills existem",
            f"catalogo_skis() falhou: {e}",
        )
    try:
        cat = catalogo_skis()
    except Exception as e:
        return _inviavel(
            "app/ia/skills",
            "os handlers das skills existem",
            f"catalogo_skis() levantou: {e}",
        )
    fantasmas = cat.get("handlers_fantasmas")
    lista = {}
    for s in cat.get("skills", []):
        ci = s.get("cobre_inexistente") or []
        if ci:
            lista[s.get("nome")] = ci
    # o contador e a lista tem de concordar: um que discorda do outro e'
    # um numero que nao acompanha o estado que ele proprio publica
    batem = (not fantasmas) or bool(lista)
    return _item(
        (not fantasmas) and batem,
        {
            "skills": cat.get("total"),
            "handlers_fantasmas": fantasmas,
            "promessas_sem_botao": cat.get("promessas_sem_botao"),
            "detalhe": lista,
            "contador_e_lista_concordam": batem,
        },
        "app/ia/skills/*.md",
        "os handlers declarados existem no registo",
        "Um handler que nao existe e' uma tool que o modelo chama e leva "
        "`tool_fora_do_catalogo`. `prometido_sem_botao` nomeia logica que "
        "existe mas ainda nao e' chamavel — e' honesto, nao e' falha.",
    )


# ----------------------------------------------------------------------
# 5) MIGRACOES POR APLICAR
# ----------------------------------------------------------------------
def verificar_migracoes():
    try:
        from django.db import connection
        from django.db.migrations.executor import MigrationExecutor
    except Exception as e:
        return _inviavel(
            "django.db.migrations",
            "as migracoes estao aplicadas",
            f"Django nao carregou: {e}",
        )
    try:
        ex = MigrationExecutor(connection)
        alvos = ex.loader.graph.leaf_nodes()
        plan = ex.migration_plan(alvos)
    except Exception as e:
        return _inviavel(
            "django.db.migrations",
            "as migracoes estao aplicadas",
            f"o MigrationExecutor falhou: {e}",
        )
    pendentes = [{"app": m.app_label, "nome": m.name} for m, _ in plan]
    return _item(
        not pendentes,
        {"pendentes": len(pendentes), "detalhe": pendentes[:20]},
        "django.db.migrations",
        "nao ha migracoes por aplicar",
        "MEDIDO: 5 migracoes por aplicar fizeram o codigo pedir "
        "`app_propriedade.cod_municipio` a uma base sem a coluna, e o "
        "`TenantIsolationMiddleware` desativou-se a si proprio a cada "
        "pedido — um guard de tenancy que falha ABERTO.",
    )


VERIFICACOES = {
    "mojibake_js": verificar_mojibake_js,
    "guarda_sessao": verificar_guarda_sessao,
    "backends": verificar_backends,
    "skills": verificar_skills,
    "migracoes": verificar_migracoes,
}


def estado_do_sistema(so_falhas: bool = False) -> dict:
    """Corre TODAS as verificacoes e devolve o estado medido.

    Cada item traz `ok`, `valor`, `onde` e `o_que`. Um item que nao deu para
    medir vem com `ok: null` — nunca `true`. `so_falhas` devolve so o que
    esta a falhar, que e' o que um agente quer primeiro.
    """
    itens = {}
    for nome, fn in VERIFICACOES.items():
        try:
            itens[nome] = fn()
        except Exception as e:  # noqa: BLE001
            itens[nome] = _inviavel(
                "desconhecido",
                f"verificacao {nome}",
                f"levantou {type(e).__name__}: {str(e)[:80]}",
            )

    falhas = [n for n, v in itens.items() if v.get("ok") is False]
    indef = [n for n, v in itens.items() if v.get("ok") is None]

    return {
        "ok": not falhas,
        "medido_em": "servidor, no momento da chamada",
        "verificacoes": falhas + indef if so_falhas else itens,
        "falhas": falhas,
        "nao_medidos": indef,
        "aviso": (
            f"{len(falhas)} verificacao(oes) a falhar."
            if falhas
            else (
                f"{len(indef)} verificacao(oes) nao mediram — isto NAO e' 'tudo bem'."
                if indef
                else "Todas as verificacoes medidas passam."
            )
        ),
        "por_que_importa": (
            "Estes sao os invariantes que ja partiram. O dashboard pode "
            "mostrar 'sem dado' sem dar erro nenhum quando a guarda de "
            "sessao falha — e foi o que aconteceu. Um 'sem dado' nao e' "
            "ausencia de dado: e' ausencia de fetch."
        ),
    }
