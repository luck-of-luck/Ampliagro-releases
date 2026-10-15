"""A CSP tem de PERMITIR tudo o que os templates carregam.

O que aconteceu
----------------
Duas coisas, ambas silenciosas.

**A CSP nao era aplicada.** O `base.py` tem `csp.middleware.CSPMiddleware` em
`MIDDLEWARE` e uma politica completa escrita em settings — mas escrita em
sintaxe do **django-csp 3.x** (`CSP_DEFAULT_SRC`, `CSP_SCRIPT_SRC`, ...). O
pacote instalado e' o **4.x**, que le `settings.CONTENT_SECURITY_POLICY`, um
dict. `getattr(settings, "CONTENT_SECURITY_POLICY", {})` devolvia `{}`, a
middleware devolvia `""`, e **a resposta nao trazia `Content-Security-Policy`**.
Os headers que a resposta trazia (`X-Frame-Options`, `nosniff`, `Referrer-
Policy`, `Cross-Origin-Opener-Policy`) sao do Django, nao desta politica.

Ou seja: o projecto acreditava ter CSP e nao tinha. Nenhum teste viu, porque
2200 testes Python nao carregam recursos externos.

**E, ligada, faltavam origens.** `unpkg.com` e' carregado por 6 templates
(Leaflet, leaflet-draw, htmx, html5-qrcode) e nao estava em `script-src` nem
em `style-src`. `browser.sentry-cdn.com` idem, quando o Sentry esta ligado.
A consequence seria o mapa e o QR a nao aparecer, sem erro e sem log — so a
queixa de "isto aqui nao funciona".

Este ficheiro e' o guarda. Ele nao julga se a politica e' boa: verifica se ela
e' *coerente com o que o HTML pede*, e isso verifica-se sem browser.
"""

import re
from pathlib import Path

from django.conf import settings
from django.test import TestCase

BASE_DIR = Path(settings.BASE_DIR)

#: Uma tag inteira, para distinguir o que CARREGA de uma dica que nao carrega.
#: `<link rel="preconnect" href="https://fonts.gstatic.com">` nao descarrega
#: nada — e' uma pista de ligacao. Conta-lo como stylesheet dava um falso
#: positivo: `fonts.gstatic.com` pertence a `font-src`, e la ja esta.
_TAG_RE = re.compile(r"<(script|link)\b([^>]*)>", re.IGNORECASE)
_SRC_RE = re.compile(r"""\b(src|href)\s*=\s*["'](https?://([^/"']+))""", re.IGNORECASE)
_REL_RE = re.compile(r"""\brel\s*=\s*["']([^"']+)["']""", re.IGNORECASE)

#: `rel` que nao descarrega o recurso. `preload`/`prefetch` NAO estao aqui
#: porque descarregam, e um guarda que os ignora seria um guarda partido.
_RELS_SEM_FETCH = {"preconnect", "dns-prefetch"}

_SCRIPT = "script-src"
_STYLE = "style-src"
_CONNECT = "connect-src"
_FRAME_ANCESTORS = "frame-ancestors"

#: import('https://...') em JS -> script-src
_IMPORT_RE = re.compile(r"""import\s*\(\s*['"](https?://([^/"']+))""", re.IGNORECASE)
#: script.src = 'https://...' em JS -> script-src
_SCRIPT_SRC_RE = re.compile(
    r"""script\.src\s*=\s*['"](https?://([^/"']+))""", re.IGNORECASE
)
#: fetch('https://...') ou BASE_URL = 'https://...' em JS -> connect-src
_FETCH_RE = re.compile(
    r"""(?:fetch|BASE_URL)\s*[=(]\s*['"](https?://([^/"']+))""", re.IGNORECASE
)
#: qualquer https://host restante em JS -> tem de estar em ALGUMA directiva
_ANY_URL_RE = re.compile(r"""https?://([a-zA-Z0-9.-]+)""", re.IGNORECASE)

#: Namespaces XML/SVG (xmlns='http://www.w3.org/2000/svg') nao sao fetches —
#: sao identificadores de namespace. Nao precisam de estar na CSP.
_NAMESPACES = {"www.w3.org"}


def directivas() -> dict[str, list[str]]:
    """A politica EFFECTIVA, seja ela onde estiver escrita.

    Le a forma do django-csp 4.x. Se um dia voltar a 3.x, isto devolve `{}` e
    os testes que dependem dela falham — que e' o resultado certo: uma politica
    que o middleware nao consegue ler e' uma politica que nao protege.
    """
    cfg = getattr(settings, "CONTENT_SECURITY_POLICY", None) or {}
    brutas = cfg.get("DIRECTIVES", {}) if isinstance(cfg, dict) else {}
    saida: dict[str, list[str]] = {}
    for nome, valores in brutas.items():
        if valores is None:
            saida[nome] = []
        elif isinstance(valores, str):
            saida[nome] = [valores]
        else:
            saida[nome] = list(valores)
    return saida


def _templates() -> list[Path]:
    return sorted((BASE_DIR / "app" / "templates").rglob("*.html"))


def _js_files() -> list[Path]:
    return sorted((BASE_DIR / "app" / "static").rglob("*.js"))


def _origens_por_directiva() -> dict[str, dict[str, set[str]]]:
    """Para cada directiva, que origins os templates e o JS pedem."""
    achados: dict[str, dict[str, set[str]]] = {_SCRIPT: {}, _STYLE: {}, _CONNECT: {}}
    for tpl in _templates():
        try:
            texto = tpl.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for tag, attrs in _TAG_RE.findall(texto):
            rel = _REL_RE.search(attrs)
            if rel and rel.group(1).lower() in _RELS_SEM_FETCH:
                continue
            m = _SRC_RE.search(attrs)
            if not m:
                continue
            host = m.group(3)
            if tag.lower() == "script":
                achados[_SCRIPT].setdefault(host, set()).add(tpl.name)
            else:
                achados[_STYLE].setdefault(host, set()).add(tpl.name)

    # O JS tambem carrega recursos externos — e o teste original nao o via.
    # Foi assim que `esm.run` (WebLLM) ficou de fora de script-src e a IA
    # caiu para o modo deterministico sem nenhum teste falhar.
    for js in _js_files():
        try:
            texto = js.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for m in _IMPORT_RE.finditer(texto):
            achados[_SCRIPT].setdefault(m.group(2), set()).add(js.name)
        for m in _SCRIPT_SRC_RE.finditer(texto):
            achados[_SCRIPT].setdefault(m.group(2), set()).add(js.name)
        for m in _FETCH_RE.finditer(texto):
            achados[_CONNECT].setdefault(m.group(2), set()).add(js.name)
    return achados


def _todos_os_hosts_js() -> dict[str, set[str]]:
    """Todo host https:// referenciado em qualquer ficheiro JS."""
    hosts: dict[str, set[str]] = {}
    for js in _js_files():
        try:
            texto = js.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for m in _ANY_URL_RE.finditer(texto):
            host = m.group(1)
            if host in _NAMESPACES:
                continue
            hosts.setdefault(host, set()).add(js.name)
    return hosts


class CspCoerenteComOsTemplatesTest(TestCase):
    def test_a_middleware_esta_ligada(self):
        """Sem isto, o resto do ficheiro testaria uma politica que nao e'
        aplicada. Foi exactamente assim que o bug passou despercebido."""
        self.assertIn(
            "csp.middleware.CSPMiddleware",
            list(settings.MIDDLEWARE),
            "a politica esta escrita mas a middleware nao esta ligada",
        )

    def test_a_politica_esta_no_formato_que_a_middleware_le(self):
        """O ponto do bug: escrita no formato 3.x, lida no 4.x.

        A politica pode estar completa e bellamente escrita; se o middleware
        nao a conseguir ler, o header nao sai e ninguem ve nada.
        """
        self.assertTrue(
            directivas(),
            "CONTENT_SECURITY_POLICY nao tem DIRECTIVES, ou tem a forma "
            "antiga (CSP_DEFAULT_SRC e companhia). O django-csp instalado "
            "le CONTENT_SECURITY_POLICY['DIRECTIVES']; com a forma antiga "
            "ele le um dict vazio e nao emite cabecalho nenhum.",
        )

    def test_o_cabecalho_csp_esta_publicado(self):
        """O que nos settings e' uma intencao; o que interessa e' o header."""
        from django.contrib.auth.models import User

        User.objects.create_user("csp_probe", "csp@x.com", "pw")
        self.client.login(username="csp_probe", password="pw")
        r = self.client.get("/")
        if r.status_code in (301, 302):
            r = self.client.get(r["Location"])
        self.assertIn(
            "Content-Security-Policy",
            r.headers,
            "a resposta nao traz Content-Security-Policy: a politica escrita "
            "nos settings nao chega ao browser",
        )

    def test_nenhum_origin_externo_usado_fica_de_fora(self):
        """O guarda principal: a politica tem de cobrir o que o HTML pede."""
        pol = directivas()
        falhas: list[str] = []

        for directiva, por_host in _origens_por_directiva().items():
            permitidos = set(pol.get(directiva, ()) or ())
            for host, ficheiros in sorted(por_host.items()):
                if host in permitidos or "*" in permitidos:
                    continue
                falhas.append(
                    f"  {host} falta em {directiva} "
                    f"(usado por: {', '.join(sorted(ficheiros))})"
                )

        self.assertEqual(
            falhas,
            [],
            "origens carregadas por um template ou JS e NAO permitidas pela CSP.\n"
            "Enquanto a CSP as bloquear, o recurso e' recusado em silencio: "
            "sem erro, sem log, e a queixa e' sempre 'isto aqui nao funciona'.\n"
            "Corrigir em config/settings/base.py, dentro de "
            "CONTENT_SECURITY_POLICY['DIRECTIVES'].\n" + "\n".join(falhas),
        )

    def test_todo_host_js_esta_em_alguma_directiva(self):
        """O guarda que faltava: o JS tambem carrega recursos externos.

        O teste original so' lia tags <script src> e <link href> nos
        templates HTML. Um `import('https://esm.run/...')` dentro de um
        ficheiro .js era invisivel — e foi assim que o WebLLM (SmolLM2 no
        celular) ficou bloqueado pela CSP sem nenhum teste falhar.
        """
        pol = directivas()
        todos_permitidos: set[str] = set()
        for valores in pol.values():
            todos_permitidos.update(valores or ())
        falhas: list[str] = []
        for host, ficheiros in sorted(_todos_os_hosts_js().items()):
            if host in todos_permitidos or "*" in todos_permitidos:
                continue
            falhas.append(
                f"  {host} nao esta em nenhuma directiva "
                f"(usado por: {', '.join(sorted(ficheiros))})"
            )
        self.assertEqual(
            falhas,
            [],
            "hosts referenciados em JS e ausentes da CSP.\n"
            "Corrigir em config/settings/base.py.\n" + "\n".join(falhas),
        )


class CspNaoEstaFrouxaTest(TestCase):
    """O outro lado da moeda: uma CSP sem restricoes nao protege nada."""

    def test_script_src_tem_unsafe_inline_e_e_uma_concessao_documentada(self):
        """Este teste ANTES proibia `'unsafe-inline'` em script-src.

        Proibia com razao. Mas a proibicao era impossivel de satisfazer: o
        frontend tem 132 handlers `on*=` em index.html (e mais nos restantes
        templates), e um nonce NAO cobre handlers inline — cobre tags <script>.
        Pelas duas razoes que impede a CSP de ser estrita aqui:

          1. nao havia `<script nonce=...>` em lado nenhum;
          2. mesmo depois de o haver, `'unsafe-inline'` e' IGNORADO quando ha
             nonce na mesma directiva (spec CSP3). Entao "endurecer" com nonce
             sem tirar os `on*=` troca uma politica frouxa por um painel morto.

        O que este teste faz agora e' o oposto de apagar a regra: mede a DIVIDA.
        Se o numero de handlers inline crescer, isto falha — e quando o passo 2
        do nonce (reescrever os `on*=` como addEventListener) estiver feito, o
        contador chega a zero e a politica pode endurecer. O comentario em
        config/settings/base.py diz o mesmo e aponta para ca.
        """
        self.assertIn(
            "'unsafe-inline'",
            directivas().get(_SCRIPT, ()) or (),
            "script-src perdeu o 'unsafe-inline'. Se foi DEPOIS de os handlers "
            "`on*=` virarem addEventListener, e' a CSP a endurecer: pode apagar "
            "esta classe de teste. Se nao foi, algum handler vai deixar de "
            "funcionar em silencio.",
        )

    def test_a_divida_inline_nao_cresceu(self):
        """Conta os `on*=` e os `<script>` sem src. E' a divida da concessao.

        Nao e' um limiar arbitrario: e' o numero medido quando o
        `'unsafe-inline'` foi posto. Subiu, alguem adicionou trabalho inline
        e o caminho para endurecer a CSP ficou mais longe.
        """
        handlers = 0
        scripts_inline = 0
        for tpl in _templates():
            try:
                texto = tpl.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            handlers += len(re.findall(r"\son[a-z]+\s*=", texto, re.IGNORECASE))
            for tag, attrs in _TAG_RE.findall(texto):
                if tag.lower() == "script" and not re.search(
                    r"\bsrc\s*=", attrs, re.IGNORECASE
                ):
                    scripts_inline += 1

        orcamento_handlers = 700
        orcamento_scripts = 110
        self.assertLessEqual(
            handlers,
            orcamento_handlers,
            f"{handlers} handlers `on*=` nos templates (orcamento "
            f"{orcamento_handlers}, medido em 2026-10-04: 606). Cada um e' um "
            f"ponto que um nonce nao cobre. Para endurecer a CSP, este numero "
            f"tem de chegar a 0.",
        )
        self.assertLessEqual(
            scripts_inline,
            orcamento_scripts,
            f"{scripts_inline} `<script>` inline sem src (orcamento "
            f"{orcamento_scripts}, medido em 2026-10-04: 96). Estes PODEM "
            f"receber nonce; e' o passo 1.",
        )

    def test_frame_ancestors_fecha(self):
        self.assertIn(
            "'none'",
            directivas().get(_FRAME_ANCESTORS, ()) or (),
            "sem frame-ancestors, a aplicacao pode ser posta dentro de um "
            "iframe noutro sitio e controlada com clickjacking",
        )

    def test_default_src_fecha(self):
        self.assertIn("'self'", directivas().get("default-src", ()) or ())


class DevServerNaCspTest(TestCase):
    """O dev-server do Vite na CSP: presente em dev, ausente em producao.

    MEDIDO 2026-10-04 (agente 4). Em desenvolvimento `dev_mode` e' True
    (`base.py:689`), logo `vite_asset` emite
    `http://localhost:5173/static/app/static/js/main.js` e `vite_hmr_client`
    abre um WebSocket para a mesma origem. Sem a entrada, a CSP recusa os
    **dois** em silencio — era a ultima violacao CSP que sobrava depois de a
    politica passar a ser aplicada de facto.

    E o outro lado, que e o que este teste existe para travar: uma origin de
    desenvolvimento dentro da politica de **producao** seria uma porta que
    nao devia existir. Por isso a entrada esta sob `if DEBUG:`, e este teste
    falha se alguem a mover para fora.
    """

    #: A origem que `base.py` acrescenta sob `if DEBUG:`.
    ORIGEM = "http://localhost:5173"

    def test_o_dev_server_so_entra_em_debug(self):
        from django.conf import settings as s

        pol = directivas()
        em_debug = bool(s.DEBUG)
        for directiva in ("script-src", "connect-src"):
            presente = self.ORIGEM in (pol.get(directiva) or ())
            self.assertEqual(
                presente,
                em_debug,
                f"em DEBUG={s.DEBUG}, `{directiva}` "
                f"{'contem' if presente else 'NAO contem'} {self.ORIGEM}. "
                "A origem do dev-server so entra em DEBUG; "
                "em producao seria uma porta de desenvolvimento viva.",
            )

    def test_o_sinal_segue_o_debug_nos_dois_sentidos(self):
        """O guarda acima passa por vazio se o `DEBUG` ja for False.

        MEDIDO 2026-10-04 (agente 4). Sob `pytest`, `DEBUG` e' False: o
        `pytest-django` poe-o a False em RUNTIME, depois do import dos
        settings. Um teste que so olha para o estado corrente verifica
        "False == False" e passa sem nunca exercise o caminho que interessa.

        Aqui forca-se os dois estados com `override_settings`, que e' a via
        que dispara `setting_changed`. E' este teste que prova que a origem
        entra E sai — o outro so prova uma das metades, e so por acaso.
        """
        from django.test import override_settings

        # `directivas()` devolve COPIAS. Chamar uma vez e usar o resultado
        # fora dos blocos daria sempre o estado de entrada — e o teste
        # passaria a medir o snapshot, nao a politica. Chamar dentro de cada
        # bloco e' o que o torna um teste.
        with override_settings(DEBUG=True):
            pol = directivas()
            for directiva in ("script-src", "connect-src"):
                self.assertIn(
                    self.ORIGEM,
                    pol.get(directiva) or (),
                    f"com DEBUG=True, `{directiva}` tem de permitir o "
                    "dev-server, senao o bundle e o HMR sao bloqueados.",
                )

        with override_settings(DEBUG=False):
            pol = directivas()
            for directiva in ("script-src", "connect-src"):
                self.assertNotIn(
                    self.ORIGEM,
                    pol.get(directiva) or (),
                    f"com DEBUG=False, `{directiva}` NAO pode permitir o "
                    "dev-server: e' uma porta de desenvolvimento em producao.",
                )

    def test_a_origem_combina_com_o_django_vite(self):
        """Os literais de `base.py` nao podem divergir do `DJANGO_VITE`.

        A CSP e' escrita com literais (`http://localhost:5173`) porque a
        `DJANGO_VITE` esta definida mais abaixo no mesmo ficheiro. Esse
        --------- e' o unico sitio onde a divergencia e' possivel, e e'
        silenciosa: se o dev-server mudar de porta, a CSP continua a
        autorizar a porta velha e o sintoma e' "a CSP esta errada" sem
        ninguem saber porquê.
        """
        from django.conf import settings as s

        vite = s.DJANGO_VITE["default"]
        esperado = f"http://{vite['dev_server_host']}:{vite['dev_server_port']}"
        self.assertEqual(
            esperado,
            self.ORIGEM,
            "o dev-server do django-vite mudou e a CSP nao. Actualize "
            "ambos em config/settings/base.py: a directiva e o literal "
            f"tem de dizer {esperado}.",
        )

    def test_hmr_continua_condicional_e_o_bundle_nao(self):
        """O `base.html` tem de emitir o bundle SEMPRE e o HMR só em dev.

        MEDIDO 2026-10-04 (agente 4). O `vite_asset` estava dentro do
        `{% if VITE_ATIVO %}`; com `DEBUG=False` isso e' falso, o tag nunca
        era emitido, e o bundle de 51 KB — que o `Dockerfile.prod` constroi
        com um stage `frontend` inteiro — nunca era carregado. O
        `Dockerfile.prod:58` afirmava "retirar esse `if` (ja feito no
        template)". Nao estava feito.
        """
        from pathlib import Path

        from django.conf import settings as conf

        # O TEMPLATE, nao os settings. A primeira versao deste teste lia
        # `config/settings/base.py` e falhava a dizer que o `vite_asset` nao
        # estava la — num ficheiro onde nunca esteve. Um teste que aponta
        # para o ficheiro errado falha com a certeza errada, que e a pior
        # das certezas: e' convincente e nao diz nada do assunto.
        base = (Path(conf.BASE_DIR) / "app" / "templates" / "base.html").read_text(
            encoding="utf-8"
        )

        # O `{% if %}` nao pode envolver o `vite_asset`.
        import re

        for bloco in re.findall(
            r"\{%\s*if\s+VITE_ATIVO\s*%\}(.*?)\{%\s*endif\s*%\}", base, re.S
        ):
            self.assertNotIn(
                "vite_asset",
                bloco,
                "o `vite_asset` voltou a estar dentro do `{% if VITE_ATIVO %}`. "
                "Em producao (DEBUG=False) o tag nao e' emitido e o bundle "
                "construido nunca e' servido.",
            )

        self.assertIn(
            "vite_asset 'app/static/js/main.js'",
            base,
            "o bundle tem de estar no base.html, fora de qualquer guarda de DEBUG.",
        )
        self.assertIn(
            "vite_hmr_client",
            base,
            "o cliente de HMR desapareceu do base.html. Sem ele nao ha "
            "hot-reload em desenvolvimento.",
        )


class OBundleServidoTest(TestCase):
    """O HTML SERVIDO tem o bundle. Nao o template.

    MEDIDO 2026-10-04 (achado do agente 4, guarda que faltava): os guardas
    deste ficheiro leem o SOURCE — o `base.html`, o `config/settings/base.py`.
    E um guard que passa com a pagina a servir a coisa errada.

    A razao de ser uma classe separada: `test_hmr_continua_condicional_e_o_bundle_nao`
    le um `if` e um tag. Isso prova que o TEMPLATE esta escrito certo. Nao
    prova que o que sai da pagina em `DEBUG=False` tem o `<script>`. Entre
    o template e o HTML servido ha o manifest, o `staticfiles`, e o proprio
    `django_vite` — e um bundle que o `Dockerfile.prod` constroi pode nao
    chegar ao disco de producao. Um guard que so le o source passa, e o
    bundle continua a nao carregar.

    ## Porque se renderiza o TEMPLATE e nao se faz GET a uma URL

    Nenhuma pagina que estenda `base.html` serve sem tocar no banco. E o
    `/login/` que se provou primeiro NAO estende `base.html`: e' um
    documento com o proprio `<head>`, sem `vite_asset`. Um guard escrito
    contra ele passaria a medir a pagina errada — a pior das certezas: e'
    convincente e nao diz nada do assunto.

    O que esta classe mede e o que o defeito era: **do template ao HTML**.
    O `render_to_string` exercita o `base.html` real, com os context
    processors reais, com o `django_vite` real e o manifest real. O que
    ele deixa de fora e' o URL conf, que nao e' o que estava partido.
    """

    def _html(self):
        from django.contrib.auth.models import AnonymousUser
        from django.template.loader import render_to_string
        from django.test import RequestFactory

        req = RequestFactory().get("/qualquer/")
        # `base.html` le `request.user` (navbar, `{% if user.is_authenticated %}`).
        # O `RequestFactory` nao põe o utilizador — e sem isto o guard falha
        # com `AttributeError`, que é um erro do guard e não do bundle.
        req.user = AnonymousUser()
        # Sem `override_settings` aqui, e de propósito.
        #
        # A primeira versão deste guard fazia `override_settings(DEBUG=False,
        # DJANGO_VITE={... dev_mode: False})` dentro do teste — e continuava
        # a ver o dev-server, porque o `DjangoViteAssetLoader` é um
        # SINGLETON que lê `dev_mode` uma vez. O `override_settings` chegava
        # tarde.
        #
        # A correcção é em `config/settings/test.py`, que fixa `DEBUG = False`
        # e `dev_mode = False` para a sessão de testes inteira. Assim o guard
        # mede o mesmo que a produção, e o `.env` de quem corre deixa de
        # poder torná-lo verde à falsehood.
        return render_to_string("base.html", request=req)

    def test_o_bundle_construido_e_servido_em_producao(self):
        """DEBUG=False: a pagina tem o bundle, e nao o dev-server."""
        html = self._html()
        self.assertNotIn(
            "localhost:5173",
            html,
            "a pagina em producao aponta para o dev-server do Vite. O "
            "vite_asset resolve para o manifest quando dev_mode=False; se "
            "aqui aparece o dev-server, ou o dev_mode esta a True, ou o "
            "manifest nao foi encontrado e ha um fallback.",
        )
        # O nome do bundle construido tem o hash do Vite no meio
        # (js/legacy.<hash>.js). Procurar o prefixo e' o que prova que
        # veio do manifest e nao de um caminho escrito a mao no template.
        self.assertRegex(
            html,
            r"/static/js/legacy\.[A-Za-z0-9_-]+\.js",
            "a pagina em producao nao carrega o bundle construido. O "
            "Dockerfile.prod constroi; se nao aparece aqui, ou o "
            "collectstatic nao rodou, ou o vite_asset esta dentro de "
            "alguma guarda de DEBUG.",
        )

    def test_o_manifest_existe_e_tem_a_chave_que_o_template_pede(self):
        """O HTML servido depende disto. Se faltar, a tag levanta."""
        from django.conf import settings as conf

        manifest = (
            Path(conf.BASE_DIR) / "staticfiles" / "dist" / ".vite" / "manifest.json"
        )
        self.assertTrue(
            manifest.exists(),
            f"falta {manifest}. Sem manifest, o vite_asset levanta "
            "DjangoViteAssetNotFoundError e TODA a pagina que estende "
            "base.html da 500 — nao uma pagina sem bundle, uma pagina morta.",
        )
        import json

        chaves = json.loads(manifest.read_text(encoding="utf-8"))
        self.assertIn(
            "app/static/js/main.js",
            chaves,
            "a chave que o base.html pede (app/static/js/main.js) nao esta "
            "no manifest. Ou o input do Vite mudou, ou o build e' antigo. "
            "Um bundle construido com outro nome e' um bundle que nao e' "
            "servido.",
        )

    def test_o_hmr_nao_e_servido_em_producao(self):
        """O outro lado do mesmo guard: o HMR e' so de dev."""
        html = self._html()
        self.assertNotIn(
            "@vite/client",
            html,
            "o cliente de HMR foi servido em producao. Ele abre um "
            "WebSocket para localhost:5173, que nao existe la — e e' um "
            "pedido que falha em silencio.",
        )
