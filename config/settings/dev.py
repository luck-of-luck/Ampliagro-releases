from .base import *

# Override default for dev - read from env, default to True for local development
DEBUG = os.environ.get("DEBUG", "True").lower() in ("true", "1", "t")
ALLOWED_HOSTS = ["*"]

# Dev nunca força HTTPS — evita redirect http→https que quebra em 127.0.0.1:8001 (ERR_SSL_PROTOCOL_ERROR)
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

# Print emails to console instead of sending
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Always disable AXES in dev to avoid flaky lockouts during manual testing
AXES_ENABLED = False
AXES_FAILURE_LIMIT = 100

# In DEBUG mode, use Django's built-in static file serving (no WhiteNoise needed)
# WhiteNoise can interfere with DEBUG mode static file serving
MIDDLEWARE = [m for m in MIDDLEWARE if "whitenoise" not in m.lower()]
STATICFILES_STORAGE = "django.contrib.staticfiles.storage.StaticFilesStorage"

if os.environ.get("PLAYWRIGHT_TEST") == "1":
    DJANGO_VITE["default"]["dev_mode"] = False
    # Speed up tests: disable throttling
    REST_FRAMEWORK["DEFAULT_THROTTLE_CLASSES"] = []
    REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] = {}

# MEDIDO 2026-10-07: com o dev-server Vite no ar, o template injecta o HMR
# client em `localhost:5173` e a CSP recusava porque o dev-server nao estava na
# politica. Console inundado com "script-src ... blocked".
#
# So' quando DEBUG=True: acrescenta o dev-server do Vite a `script-src`,
# `style-src` e `connect-src` (o HMR fala por WebSocket `ws://`). Posto em
# dev.py e nao no base.py, e protegido por DEBUG, para nunca produzir uma
# politica que abra uma porta de desenvolvimento com DEBUG=False.
if DEBUG:
    _VITE_HOSTS = ["localhost:5173", "127.0.0.1:5173"]
    for _directiva in ("script-src", "style-src", "connect-src"):
        _diretiva = CONTENT_SECURITY_POLICY["DIRECTIVES"][_directiva]
        for _h in _VITE_HOSTS:
            if not any(_h in str(x) for x in _diretiva):
                _diretiva.append(_h)
    CONTENT_SECURITY_POLICY["DIRECTIVES"]["connect-src"].append("ws://localhost:5173")
    CONTENT_SECURITY_POLICY["DIRECTIVES"]["connect-src"].append("ws://127.0.0.1:5173")
