import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent

try:
    from dotenv import load_dotenv

    load_dotenv(BASE_DIR / ".env")
except Exception:
    env_path = BASE_DIR / ".env"
    if env_path.is_file():
        with open(env_path, encoding="utf-8-sig") as _f:
            for _line in _f:
                _line = _line.strip()
                if not _line or _line.startswith("#"):
                    continue
                if "=" not in _line:
                    continue
                _key, _value = _line.split("=", 1)
                os.environ.setdefault(
                    _key.strip(), _value.strip().strip('"').strip("'")
                )

# SECRET_KEY must be set in .env for production - no insecure default
SECRET_KEY = os.environ.get("SECRET_KEY")
if not SECRET_KEY:
    if os.environ.get("DEBUG", "False").lower() in ("true", "1", "t"):
        # Only allow insecure default in development
        SECRET_KEY = "django-insecure-dev-key-change-in-production"
    else:
        raise ValueError("SECRET_KEY must be set in .env for production")
DEBUG = os.environ.get("DEBUG", "False").lower() in ("true", "1", "t")
ALLOWED_HOSTS = os.environ.get("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")

# Security settings (can be overridden in prod.py)
SECURE_HSTS_SECONDS = int(os.environ.get("SECURE_HSTS_SECONDS", "0"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = os.environ.get(
    "SECURE_HSTS_INCLUDE_SUBDOMAINS", "False"
).lower() in ("true", "1", "t")
SECURE_HSTS_PRELOAD = os.environ.get("SECURE_HSTS_PRELOAD", "False").lower() in (
    "true",
    "1",
    "t",
)
SECURE_SSL_REDIRECT = os.environ.get("SECURE_SSL_REDIRECT", "False").lower() in (
    "true",
    "1",
    "t",
)
SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "False").lower() in (
    "true",
    "1",
    "t",
)
CSRF_COOKIE_SECURE = os.environ.get("CSRF_COOKIE_SECURE", "False").lower() in (
    "true",
    "1",
    "t",
)
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = False
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

INSTALLED_APPS = [
    "daphne",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",
    "rest_framework",
    "django_filters",
    "drf_spectacular",
    "corsheaders",
    "channels",
    "app.apps.AmpliagroConfig",
    "django_celery_results",
    "auditlog",
    "axes",
    "health_check",
    "health_check.db",
    "django_vite",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
]

SITE_ID = 1
# Backends únicos (definição única — ordem: axes primeiro para lockout de brute-force)
#
# MEDIDO 2026-10-05: isto era `AxesStandaloneBackend`, que NÃO tem
# `get_user`. O MRO dele é só `object`; o do `AxesBackend` é
#
#     AxesBackend → AxesStandaloneBackend → ModelBackend → BaseBackend
#
# O Django, ao carregar uma sessão, faz
#
#     backend = load_backend(request.session[BACKEND_SESSION_KEY])
#     user = backend.get_user(user_id)
#
# e o `BACKEND_SESSION_KEY` e' gravado no login como o PRIMEIRO backend
# que devolveu um utilizador. Se for o Standalone, o `get_user` não
# existe e toda a página dá 500:
#
#     AttributeError: 'AxesStandaloneBackend' object has no attribute 'get_user'
#
# Hoje não acontece porque o Standalone devolve `None` de
# `authenticate()` e quem ganha é o `ModelBackend` — mas é uma
# bomba-relógio numa lista de configuração: o dia em que o axes passar
# a autenticar alguém, o utilizador fica com 500 em tudo e sem forma
# de se desenrascar.
#
# `AxesBackend` é o que a documentação do django-axes manda usar, e é
# o que mantém o lockout de brute-force: herda o `authenticate` do
# Standalone e ganha o `get_user` do ModelBackend. A protecção de
# ataques de força bruta é a mesma — o que muda é que a sessão passa a
# carregar.
AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesBackend",
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]
# P9.2 SSO - allauth (Google OAuth). Configure SOCIALACCOUNT_PROVIDERS via .env
ACCOUNT_EMAIL_VERIFICATION = "none"
ACCOUNT_LOGIN_METHODS = {"username", "email"}
ACCOUNT_SIGNUP_FIELDS = ["email", "username*", "password1*", "password2*"]
SOCIALACCOUNT_PROVIDERS = {
    "google": {
        "SCOPE": ["profile", "email"],
        "AUTH_PARAMS": {"access_type": "online"},
    }
}

MIDDLEWARE = [
    "app.middleware.RequestIDMiddleware",
    "app.middleware.QueryCountMiddleware",
    "django.middleware.gzip.GZipMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "csp.middleware.CSPMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    # O detector vai AQUI, e nao no topo, por uma razao que so se descobre
    # quando o codigo corre: `request.user` so existe depois da
    # autenticacao. Antes, o detector nao tem como distinguir "um produtor com
    # login" de "um raspador" — e sem essa distincao, um falso positivo
    # fecha-lhe o painel. Ver `app.bot.BotDeteccaoMiddleware`.
    "app.bot.BotDeteccaoMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    # REVOGACAO antes da tenancy: e' a recusa mais barata (um flag) e a mais
    # absoluta. Depende de `request.user`, portanto depois de
    # `AuthenticationMiddleware`. Ver `app.middleware.ServidorRevogadoMiddleware`.
    "app.middleware.ServidorRevogadoMiddleware",
    "app.middleware.TenantIsolationMiddleware",
    "app.middleware.ServidorRevogadoMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "axes.middleware.AxesMiddleware",
    "auditlog.middleware.AuditlogMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "app" / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "app.context_processors.base_template",
                "app.context_processors.ampliagro_globals",
                "app.context_processors.ampliagro_build",
            ],
        },
    },
]

import environ

env = environ.Env()
# Assume .env is already loaded near the top of the file

DATABASES = {
    "default": env.db("DATABASE_URL", default=f"sqlite:///{BASE_DIR}/db.sqlite3")
}

if DATABASES["default"]["ENGINE"] == "django.db.backends.sqlite3":
    DATABASES["default"].setdefault("OPTIONS", {})
    DATABASES["default"]["OPTIONS"]["timeout"] = 20
    DATABASES["default"]["OPTIONS"]["transaction_mode"] = "IMMEDIATE"
    DATABASES["default"]["OPTIONS"]["init_command"] = (
        "PRAGMA journal_mode=WAL;PRAGMA synchronous=NORMAL;PRAGMA mmap_size=3000000000;"
    )

# IA local sandbox: chave só de serviços locais (NUNCA vai para o JS).
# Gerar com: python manage.py ia_chave
IA_LOCAL_KEY = env.str("IA_LOCAL_KEY", default="")
# FRONTEIRA DE CONFIANÇA: a chave só pode agir pelos user IDs listados aqui.
# Vazio = auth por chave DESLIGADA (fail-closed). Serviço NUNCA informa user
# arbitrário: sem vínculo explícito, a chave não age por ninguém.
IA_KEY_USERS = [
    int(x)
    for x in env.str("IA_KEY_USERS", default="").split(",")
    if x.strip().isdigit()
]

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 12},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Password hashers - SHA-512 based (PBKDF2 with SHA-512, 600k iterations)
PASSWORD_HASHERS = [
    "app.security.hashers.PBKDF2SHA512PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.BCryptSHA256PasswordHasher",
    "django.contrib.auth.hashers.ScryptPasswordHasher",
]

LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "app" / "static"]
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# Capture de clima em cache (`app/services/clima.py`). Fica **fora** de
# `MEDIA_ROOT` de propósito: um ficheiro em `MEDIA_ROOT` é servido pelo
# WhiteNoise e pelo Django, e o `clima.json` diz a latitude e longitude
# da fazenda de quem o produziu.
CLIMA_CACHE_DIR = BASE_DIR / ".cache-clima"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/login/"


REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 50,
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "1000/hour",
        "user": "10000/hour",
    },
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Ampliagro API",
    "DESCRIPTION": "Sistema de gestao agricola e pecuaria",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

# CHANNEL_LAYERS: InMemoryChannelLayer é por processo — com mais de um
# worker (daphne/gunicorn), group_send não chega aos outros processos.
# Se channels_redis estiver instalado e REDIS_URL definido, usa Redis.
# Senão, cai para InMemory (dev com 1 processo).
try:
    import channels_redis  # noqa: F401

    _REDIS_URL = os.environ.get("REDIS_URL", "")
    if _REDIS_URL:
        CHANNEL_LAYERS = {
            "default": {
                "BACKEND": "channels_redis.core.RedisChannelLayer",
                "CONFIG": {"hosts": [_REDIS_URL]},
            },
        }
    else:
        CHANNEL_LAYERS = {
            "default": {"BACKEND": "channels.layers.InMemoryChannelLayer"},
        }
except ImportError:
    CHANNEL_LAYERS = {
        "default": {"BACKEND": "channels.layers.InMemoryChannelLayer"},
    }

OPENWEATHER_API_KEY = os.environ.get("OPENWEATHER_API_KEY", "")

from datetime import timedelta

AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = timedelta(minutes=15)
AXES_LOCKOUT_TEMPLATE = "globais/lockout.html"
# Disable brute-force protection during tests / playwright to avoid flaky lockouts
import sys as _sys

if (
    (
        _sys.argv
        and any(x in " ".join(_sys.argv) for x in ["test", "pytest", "playwright"])
    )
    or os.environ.get("PLAYWRIGHT_TEST") == "1"
    or os.environ.get("PYTEST_CURRENT_TEST")
):
    AXES_ENABLED = False
    AXES_FAILURE_LIMIT = 1000

CSRF_COOKIE_HTTPONLY = False

# A CSP fica aqui em CONTENT_SECURITY_POLICY, e nao em CSP_DEFAULT_SRC /
# CSP_SCRIPT_SRC. A diferenca nao e' de estilo: o django-csp INSTALADO e' o
# 4.x, e o 4.x le `getattr(settings, "CONTENT_SECURITY_POLICY", {})`
# (csp/utils.py:81). A sintaxe antiga era lida como {} e o middleware devolvia
# uma politica vazia — a resposta NAO trazia Content-Security-Policy. MEDIDO:
# antes desta mudanca, `client.get("/")` devolveva X-Frame-Options,
# X-Content-Type-Options, Referrer-Policy e Cross-Origin-Opener-Policy (todos
# do Django) e mais nada. A politica estava escrita, a middleware estava
# ligada, e nao havia proteccao nenhuma.
#
# `tests/test_csp.py` e' o guarda: verifica o cabecalho na resposta E que
# nenhuma origin carregada por um template fica de fora. Sem ele, voltar a
# sintaxe antiga ou acrescentar um `<script src=...>` sem actualizar a
# .directiva nao da sinal a ninguem — foi assim que este passou.
CONTENT_SECURITY_POLICY = {
    "DIRECTIVES": {
        "default-src": ["'self'"],
        # unpkg.com entra aqui com um nome: e' de onde sao o Leaflet (o mapa),
        # o leaflet-draw, o htmx e o html5-qrcode, em 6 templates. Estava
        # ausente, o que significaria mapa e QR recusados em silencio.
        "script-src": [
            "'self'",
            "cdn.jsdelivr.net",
            "cdnjs.cloudflare.com",
            "unpkg.com",
            # Sentry: so e' carregado quando ha SENTRY_DSN, mas quando ha,
            # e' um <script src> a serio.
            "browser.sentry-cdn.com",
            # WebLLM (SmolLM2 no celular) e transformers.js (Whisper) sao
            # importados dinamicamente de esm.run. Sem isto, o import e'
            # recusado em silencio e a IA cai para o modo deterministico.
            "esm.run",
            # WebLLM compila WASM; sem 'wasm-unsafe-eval' o
            # WebAssembly.instantiate e' bloqueado e o motor nao arranca.
            "'wasm-unsafe-eval'",
            # `'unsafe-inline'` ESTA AQUI POR CAUSA DOS onCLICK, E E' UMA
            # CONCESSAO. MEDIDO: 606 handlers `on*=` em todos os templates —
            # 132 so em index.html, mais dashboard_appbar (47),
            # guia-ferramentas (22), kanban (19), navbar (18)...
            #
            # A CSP e' a unica defesa contra XSS injectado, e isto desliga essa
            # defesa para SCRIPT. Nao e' uma opcao que se escolha: e' o preco de
            # um frontend que e' um `<script>` inline de 13.000 linhas.
            #
            # O caminho estrito e' NONCE, e funciona para o `<script>` inline —
            # mas NAO para os handlers `on*=` (ver abaixo). E as duas coisas nao
            # podem viver na mesma directiva: pela spec, quando ha nonce, o
            # `'unsafe-inline'` e' IGNORADO. Ponha os dois e os handlers deixam
            # de funcionar — que e' exactamente o bug que a tentativa de
            # endurecer a politica criou.
            #
            # Para fechar isto a serio sao precisos os dois passos:
            #   1. `nonce="{{ CSP_NONCE }}"` + `csp.constants.NONCE` em vez
            #      deste `'unsafe-inline'`;
            #   2. reescrever os 132 `on*=` de index.html como addEventListener.
            # O passo 2 e' o caro. Sem ele, o nonce sozinho deixa a barra e os
            # botoes mortos.
            "'unsafe-inline'",
        ],
        # unpkg tambem serve as folhas de estilo do Leaflet e do leaflet-draw.
        "style-src": [
            "'self'",
            "cdn.jsdelivr.net",
            "fonts.googleapis.com",
            "unpkg.com",
            # 1.268 atributos `style="..."` nos templates (109 em index.html).
            # MEDIDO, e' a razao de ser necessario.
            #
            # Aqui `'unsafe-inline'` e' MENOS GRAVE do que em script-src: um
            # nonce NAO se aplica a atributos `style=` (so a tags <style> e a
            # <script>), e CSS injectado nao executa JavaScript num browser
            # moderno. E' a concessao padrao da industria para uma app com
            # estilos inline.
            "'unsafe-inline'",
        ],
        # fonts.gstatic.com NAO entra em style-src: so aparece em
        # `rel="preconnect"`, que nao descarrega nada. As fontes sao servidas
        # de gstatic, e para isso e' font-src.
        "font-src": ["'self'", "fonts.gstatic.com", "cdn.jsdelivr.net"],
        # unpkg.com serve os icones do Leaflet (marker-icon.png, marker-shadow.png)
        # MEDIDO 2026-10-11: sem isto, o mapa nao carrega os marcadores no onboarding.
        "img-src": [
            "'self'",
            "data:",
            "blob:",
            "*.tile.openstreetmap.org",
            "unpkg.com",
        ],
        "connect-src": [
            "'self'",
            "api.open-meteo.com",
            "servicodados.ibge.gov.br",
            # Geocodificacao REVERSA (coordenada -> cidade/UF) do onboarding.
            # A API de busca do Open-Meteo NAO faz reversa: /search?name=LAT,LON
            # volta sem `results` — testado. Quem resolve e' o Nominatim
            # (OpenStreetMap).
            "nominatim.openstreetmap.org",
            # Tiles do OpenStreetMap para o mapa interativo
            "*.tile.openstreetmap.org",
            # O bundle do Sentry faz telemetria para a sua propria API.
            "*.ingest.sentry.io",
            # WebLLM baixa os pesos do modelo de HuggingFace em runtime.
            "huggingface.co",
            "*.huggingface.co",
            # esm.run tambem serve os sub-recursos do WebLLM (WASM, config).
            "esm.run",
            # Cotacao de commodities (agrodoc-adapter.js).
            "agrodocai.com.br",
            # --- OS MESMOS CDNS DE `script-src` E `style-src` ---
            #
            # MEDIDO, 2026-10-04: o Service Worker (`app/static/js/pwa/sw.js`)
            # faz `fetch()` cross-origin no `cacheFirst` (linha 300) para
            # Google Fonts, bootstrap-icons, chart.js e leaflet — as MESMAS
            # origens que `script-src` e `style-src` ja listavam. `fetch()` e'
            # `connect-src`, nao `script-src`: sao directivas diferentes para a
            # mesma origem. Sem estas tres, o precache (sw.js:98-100) e' recusado
            # em SILENCIO e o mapa, os icones e as fontes nao carregam — que e'
            # exactamente o sintoma que o comentario de `script-src` sobre o
            # `unpkg.com` descreve e que nao se repetiu aqui.
            #
            # `fonts.gstatic.com` entra preventivamente: `font-src` ja o aceita,
            # e se o SW passar a pre-cachear os ficheiros de fonte (e nao so o
            # CSS), o mesmo bloqueio volta sem nenhuma mensagem.
            "cdn.jsdelivr.net",
            "unpkg.com",
            "fonts.googleapis.com",
            "fonts.gstatic.com",
        ],
        # O worker do Whisper (whisper-worker.js) e' same-origin; blob:
        # cobre workers criados a partir de Blob URLs.
        "worker-src": ["'self'", "blob:"],
        # Sem isto, a aplicacao pode ser posta dentro de um iframe noutro
        # sitio e controlada com clickjacking.
        "frame-ancestors": ["'none'"],
        "base-uri": ["'self'"],
        "form-action": ["'self'"],
    },
}

# --- O dev-server do Vite, so em desenvolvimento ---------------------------
#
# MEDIDO 2026-10-04 (agente 4). Em desenvolvimento, `dev_mode` e' True
# (base.py:689, `"dev_mode": DEBUG`), logo `{% vite_asset %}` emite
# `http://localhost:5173/static/app/static/js/main.js` e o
# `{% vite_hmr_client %}` abre um WebSocket para a mesma origem. Sem esta
# entrada, a CSP recusa **os dois** em silencio — era a unica violacao CSP
# que sobrava depois de a politica passar a ser aplicada de facto.
#
# `connect-src` tambem precisa dela, e pela razao que ja esta escrita mais
# acima no bloco: `WebSocket` e `fetch()` sao `connect-src`, nao `script-src`.
#
# **Porque fica sob `if DEBUG:`** e nao sempre: `localhost:5173` em
# producao seria uma origins de desenvolvimento dentro da politica de
# producao. Nao e' um risco teorico — e uma porta que nao devia existir.
# `tests/test_csp.py::test_o_dev_server_so_entra_em_debug` e' o guarda.
#
# Os valores sao literais e nao `DJANGO_VITE[...]` porque a `DJANGO_VITE` e'
# definida mais abaixo neste ficheiro (linha ~687). O teste referido acima
# compara estas duas strings com as de `DJANGO_VITE`, para que nao possam
# divergir em silencio.
# **Porque e' um sinal, e nao um `if DEBUG:` no import.** MEDIDO
# 2026-10-04 (agente 4). A primeira versao desta correccao fazia a conta no
# import de `base.py`, e o guarda imediatamente a apanhou a errar: sob
# `pytest`, `base.DEBUG` era `True` (do `.env`) mas `settings.DEBUG` era
# `False` — porque o `pytest-django` poe `DEBUG = False` em RUNTIME, depois
# do import. A politica ficava com a origin de dev e o `DEBUG` ja nao a
# justificava.
#
# Isto nao e' um artefacto do pytest: `settings.DEBUG` pode ser mudado por
# qualquer codigo, em qualquer momento. Um guarda de seguranca que le um
# valor de import-time nao e' um guarda — e uma fotografia. O sinal
# `setting_changed` e' o que mantem a verdade correcta depois de qqem
# mexer no interruptor.
_DEV_SERVER_ORIGIN = "http://localhost:5173"
_DEV_SERVER_DIRECTIVES = ("script-src", "connect-src")


def _aplicar_origem_dev_server():
    """Poe, ou tira, a origin do dev-server conforme o `DEBUG` actual."""
    import django.conf

    directivas = CONTENT_SECURITY_POLICY["DIRECTIVES"]
    em_debug = bool(django.conf.settings.DEBUG)

    for _directiva in _DEV_SERVER_DIRECTIVES:
        valores = directivas.get(_directiva)
        if valores is None:
            continue
        if em_debug and _DEV_SERVER_ORIGIN not in valores:
            valores.append(_DEV_SERVER_ORIGIN)
        elif not em_debug and _DEV_SERVER_ORIGIN in valores:
            valores.remove(_DEV_SERVER_ORIGIN)


def _csp_devserver_ao_mudar_setting(sender, setting, **kwargs):
    if setting == "DEBUG":
        _aplicar_origem_dev_server()


# Aplica uma vez (o `DEBUG` do import pode ja ser o final), e liga-se ao
# sinal para o futuro. `django.core.signals.setting_changed` e' o sitio
# canonico — `django.test.signals` reexporta-o.
try:
    from django.core.signals import setting_changed
except ImportError:  # pragma: no cover - Django antigo
    from django.test.signals import setting_changed  # type: ignore

_aplicar_origem_dev_server()
setting_changed.connect(
    _csp_devserver_ao_mudar_setting, dispatch_uid="ampliagro.csp.devserver"
)

# --- Deteccao de bots -------------------------------------------------------
# Ver `app/bot.py` para o porque de tudo isto ser server-side e nao JS.
#
# OS DOIS INTERRUPTORES COMECAM DESLIGADOS, e por ordem. O primeiro liga a
# observacao; o segundo, a accao. So se activa o segundo depois de ler os
# registos do primeiro e de confirmar que nenhum produtor real caiu do lado
# errado. Um falso positivo nao custa um log: custa a um produtor ser
# fechado fora da propria fazenda.
BOT_DETECTOR_LIGADO = False
BOT_BLOQUEAR = False

#: Pontos a partir dos quais o pedido e' considerado bot. O limiar e' de 8
#: porque nenhum sinal isolado o atinge: curl chega a 7 (ferramenta 3 +
#: sem Accept-Language 2 + sem Accept-Encoding 2, menos 1 por se dizer
#: Chrome). Um scraper tem de juntar comportamento — cadencia e dispersao —
#: para passar. Com 6, so um curl com User-Agent honesto passava.
BOT_LIMIAR = 8

#: Pedidos por minuto por cliente, acima do qual a cadencia conta.
#: 90 e' generoso de proposito: um produtor num link lento, com uma tela que
#: recarrega dados a cada 2 segundos, fica abaixo.
BOT_PEDIDOS_POR_MINUTO = 90

#: `X-Forwarded-For` so e' lido com isto ligado. Sem o proxy a reescrever o
#: cabecalho, o cliente escolhe o seu proprio identificador — e escolher o
#: proprio identificador e' precisamente o que um scraper faz.
BOT_CONFIA_XFF = False

#: `CF-Connecting-IP` e' o IP real que o CLOUDFLARE poe, por o hostname do
#: cliente. E' o unico cabecalho que nao e' falsificavel pelo cliente — mas so
#: se o ORIGIN nao for directamente acessivel pela internet.
#:
#: >>> PERIGO, E LEIA ANTES DE LIGAR <<<
#: Se o origin estiver aberto (o IP do servidor e' respondavel), alguem chega
#: ao origin sem passar pelo Cloudflare e inventa o cabecalho. Nesse dia, quem
#: quiser escapar ao limite so' precisa de mandar
#: `CF-Connecting-IP: <outro>` e fica com a cota de outra pessoa.
#:
#: Como saber se o origin esta fechado: testar de fora, a partir de uma rede
#: que nao passe pelo Cloudflare, se o origin ainda responde. Se responde,
#: este interruptor tem de ficar em False ate estar fechado.
#:
#: Como fechar: no firewall do servidor, so' aceitar ligacoes vindas dos
#: prefixos do Cloudflare. Os prefixos mudam — a lista esta em
#: https://www.cloudflare.com/ips-v4 e ips-v6. Nao esta no codigo de proposito:
#: uma lista de IP codificada envelhece e ninguem a actualiza.
BOT_USAR_CF_IP = False

#: Segundos da janela de contagem. 60 e' o que os limites medem; mudar isto
#: muda o significado de `BOT_PEDIDOS_POR_MINUTO` e tem de ser feito junto.
BOT_JANELA_SEGUNDOS = 60

#: Rotas que o detector nunca toca. Sao as que nao tem opiniao a dar: quem
#: pede um ficheiro estatico ou um health check nao esta a tentar ler o ERP.
#: `/api/` NAO esta aqui de proposito — e' o que vale a pena proteger, e a IA
#: local chega-lhe pelo browser, que traz os cabecalhos que um browser traz.
BOT_ISENTOS = (
    "/static/",
    "/media/",
    "/healthz",
    "/health/",
    "/robots.txt",
    "/favicon.ico",
)

SESSION_COOKIE_AGE = 86400  # 24 horas

# Uploads: teto global anti-DoS (validators por campo refinam por tipo)
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024
SESSION_EXPIRE_AT_BROWSER_CLOSE = False
SESSION_SAVE_EVERY_REQUEST = True

# Cache partilhado entre processos.
#
# O `LocMemCache` guardava o payload do painel em memória de cada processo. Com
# um só processo de dev isso ninguém notava; com o autoreload do Django, ou com
# Daphne, cada processo tinha a sua cópia — e a invalidação feita num deles
# (app/cache_painel.py) não chegava aos outros. O sintoma é um painel que
# "volta ao número antigo" sem que ninguém tenha escrito nada, e só de vez em
# quando.
#
# `DatabaseCache` resolve-o sem introduzir uma dependência nova: é backend do
# Django, usa a base de dados que já existe, e é partilhado por construção.
# Em produção continua a ser Redis (ver config/settings/prod.py) — aí também é
# partilhado, e é o que lá faz sentido.
#
# `createcachetable` é preciso uma vez (já está nas migrações do projeto).
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.db.DatabaseCache",
        "LOCATION": "cache_tabela_painel",
        # O payload do painel é um dicionário Python serializado; sem isto o
        # timeout não respeitaria a data de expiração.
        "OPTIONS": {"MAX_ENTRIES": 500, "CULL_FREQUENCY": 4},
    }
}

CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/1")
CELERY_RESULT_BACKEND = "django-db"
CELERY_CACHE_BACKEND = "django-cache"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_TIMEZONE = "America/Sao_Paulo"

# P4 Health alerts (Slack/Telegram) — configure via .env
HEALTH_ALERT_SLACK_WEBHOOK = os.environ.get("HEALTH_ALERT_SLACK_WEBHOOK", "")
HEALTH_ALERT_TELEGRAM_BOT_TOKEN = os.environ.get("HEALTH_ALERT_TELEGRAM_BOT_TOKEN", "")
HEALTH_ALERT_TELEGRAM_CHAT_ID = os.environ.get("HEALTH_ALERT_TELEGRAM_CHAT_ID", "")

# P8 LGPD / Backup criptografado
BACKUP_ENCRYPTION_KEY = os.environ.get(
    "BACKUP_ENCRYPTION_KEY", ""
)  # Fernet key: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

import structlog


def _rodar_testes() -> bool:
    """Este processo e' uma suite de testes?

    `manage.py test` e `pytest` correm ambos com `config.settings.dev`
    (`manage.py` faz `setdefault`, e o `pytest.ini` aponta para `dev`), por isso
    os testes heredavam o `LOGGING` de `base` — e o handler de ficheiro
    escrevia em `logs/ampliagro.log`, que e' o log de PRODUCAO.

    O preco foi concreto: um `manage.py test app.ia.tests` fez o ficheiro
    crescer de 4.328.735 para 4.453.879 bytes, e as ultimas linhas passaram a
    ser `Forbidden: /api/ia/executar/` — ruido de teste. Num log com 1.045
    tracebacks, 446 deles vinham de `tests_proativo.py:517-521 explode()`, e nao
    havia como distingui-los dos verdadeiros. Quem lesse o log achava que a
    aplicacao estava em chamas.

    Um log que nao distingue "a app falhou" de "o teste injectou uma falha" nao
    e' um log: e' um ruido com occasionally util. Por isso a suite tem ficheiro
    proprio, e `logs/ampliagro.log` fica com o que aconteceu a quem o leu.

    Nao ha settings "de teste" activo por omissao — `config.settings.test`
    existe, mas so quando alguem passa `--settings`. E um diagnostico que so
    funciona numa das duas portas nao e' um diagnostico.

    O QUE ESTA DETECCAO NAO FAZIA (medido, nao suposto)
    ====================================================
    As duas portas que existiam falhavam as DUAS ao mesmo tempo:

        argv[0] stem        = "__main__"
        PYTEST_CURRENT_TEST = existe, mas so' durante o item de teste
        ARQUIVO_LOG         = "ampliagro.log"   -> logs/ampliagro.log

    `python -m pytest` mete `sys.argv[0]` no `__main__.py` DO PACOTE pytest,
    e o stem disso e' "__main__" — nao "pytest". A comparacao por stem nunca
    reconhecia a porta que o `pytest.ini` e o CI usam.

    E a outra nao podia salvar: `PYTEST_CURRENT_TEST` so' existe a partir do
    primeiro item de teste. Os settings sao importados ANTES disso — e' o
    `conftest.py` que chama `django.setup()`. Ao momento de `ARQUIVO_LOG` ser
    avaliado, a variavel ainda nao existe.

    Resultado: a suite escrevia no log de PRODUCAO. Nao era teoria: e' o
    ficheiro que se abre quando alguem pergunta o que aconteceu a quem esta a
    usar a aplicacao.

    A CORRECAO
    ==========
    `_pytest` tambem nao esta em `sys.modules` a tempo. O que existe e'
    fiavel ao IMPORT e' o caminho de `argv[0]`, que contem "pytest" nas duas
    portas (`Scripts\\pytest.exe` e `...\\pytest\\__main__.py`).

    A leitura por stem fica como fallback para o caso em que o nome do
    executavel seja pytest mas o caminho nao o contenha — que e' o que
    acontece com um launcher que reescreve `argv[0]`.
    """
    if "PYTEST_CURRENT_TEST" in os.environ or "PYTEST_ADDOPTS" in os.environ:
        return True
    argv0 = str(_sys.argv[0]) if _sys.argv else ""
    # Caminho inteiro, nao o stem: `python -m pytest` põe argv[0] no
    # `__main__.py` do pacote, e o stem e' "__main__".
    if "pytest" in argv0 or "py.test" in argv0:
        return True
    executavel = Path(argv0).stem if argv0 else ""
    if executavel in ("pytest", "py.test"):
        return True
    return any(arg == "test" or arg.startswith("test_") for arg in _sys.argv[1:])


# `sys` foi importado acima como `_sys` (linha 264) para o resto deste ficheiro.
ARQUIVO_LOG = "test-run.log" if _rodar_testes() else "ampliagro.log"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "()": structlog.stdlib.ProcessorFormatter,
            "processor": structlog.dev.ConsoleRenderer()
            if DEBUG
            else structlog.processors.JSONRenderer(),
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json",
        },
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": BASE_DIR / "logs" / ARQUIVO_LOG,
            "formatter": "json",
            "maxBytes": 10 * 1024 * 1024,  # 10MB
            "backupCount": 5,  # mantém 5 arquivos (50MB total) + rotação
            "encoding": "utf-8",
        },
    },
    "root": {
        "handlers": ["console", "file"],
        "level": "INFO",
    },
    "loggers": {
        "django": {"level": "WARNING"},
        "app": {"level": "DEBUG"},
        "app.iot": {"level": "DEBUG"},
    },
}

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
        structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
    ],
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

CORS_ALLOWED_ORIGINS = env.list(
    "CORS_ALLOWED_ORIGINS",
    default=[
        "http://localhost:8000",
        "http://localhost:3000",
        "http://127.0.0.1:8000",
    ],
)
CORS_ALLOW_CREDENTIALS = True

DJANGO_VITE = {
    "default": {
        "dev_mode": DEBUG,
        "dev_server_host": "localhost",
        "dev_server_port": 5173,
        "manifest_path": BASE_DIR / "staticfiles" / "dist" / ".vite" / "manifest.json",
    }
}

# P7 Sentry (opcional via .env SENTRY_DSN)
import os as _os_sentry

SENTRY_DSN = _os_sentry.environ.get("SENTRY_DSN", "")
SENTRY_ENVIRONMENT = _os_sentry.environ.get(
    "SENTRY_ENVIRONMENT", "development" if DEBUG else "production"
)
if SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        environment=SENTRY_ENVIRONMENT,
        integrations=[DjangoIntegration()],
        traces_sample_rate=0.1,
        send_default_pii=False,
    )
