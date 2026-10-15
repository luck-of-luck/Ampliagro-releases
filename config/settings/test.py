"""
Test settings for Ampliagro.
Optimized for fast test execution.

MEDIDO 2026-10-06: a base ja nao e' `:memory:` para os comandos de gestao.
Ver o comentario em `DATABASES` abaixo, e o porque de `pytest` e de
`manage.py` precisarem de alvos diferentes.
"""

import os
import tempfile  # para o ficheiro SQLite de teste sobreviver entre comandos

# O `SECRET_KEY` tem de existir ANTES de `from .base import *`.
#
# MEDIDO 2026-10-05. O CI estava a falhar em 20 execucoes seguidas (todas desde
# 2026-09-03, commit `aea8a7c`) com:
#
#     ValueError: SECRET_KEY must be set in .env for production
#
# A causa e' a ORDEM, nao a ausencia do valor. `base.py` faz, na linha 26:
#
#     SECRET_KEY = os.environ.get("SECRET_KEY")
#     if not SECRET_KEY:
#         if DEBUG: ...
#         else: raise ValueError(...)      # <-- aborta AQUI
#
# E o `SECRET_KEY` do teste estava DEFINIDO NA LINHA 9, depois do
# `from .base import *` da linha 6. O import corre primeiro, o `raise` dispara
# dentro dele, e a linha 9 nunca chega a executar. O valor estava escrito -- e
# era inerte.
#
# Isto e' a razao pela qual `settings/test.py` nao resolvia o problema: o CI nao
# define `SECRET_KEY` (ao contrario do `cd.yml`, que define `SECRET_KEY: ci`), e
# `DEBUG` nao e' `true` no GitHub Actions, entao `base.py` vai pelo ramo do
# `raise`.
#
# `os.environ.setdefault` em vez de atribuicao directa: se o CI ou o
# ventilador缀 DEFINIR `SECRET_KEY`, esse valor ganha. Nao e' um default
# inseguro como o de `base.py` -- e' uma chave de teste, num ficheiro que so o
# CI e o `pytest` local carregam, e nunca em producao. `base.py` continua a
# recusar arrancar sem chave em `DEBUG=False`, que e' o que se quer.
os.environ.setdefault(
    "SECRET_KEY", "test-secret-key-for-testing-only-not-for-production"
)

from .base import *  # noqa: E402  tem de vir depois do setdefault acima

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ["SECRET_KEY"]

# --- O dev-server do Vite NUNCA num teste ------------------------------------
#
# MEDIDO 2026-10-04, ao escrever `tests/test_csp.py::OBundleServidoTest`.
#
# `base.py:33` le `DEBUG` do ambiente, e o `.env` da maquina de
# desenvolvimento tem `DEBUG=True`. Logo, sob `pytest`, `DEBUG` era True e
# `DJANGO_VITE["default"]["dev_mode"]` (base.py:762) era True — e o
# `{% vite_asset %}` emitia `http://localhost:5173/...` em vez do bundle
# construido. O guard que escrevi para apanhar um bundle em falta ficava
# VERDE com a pagina a servir o dev-server: media o `.env` de quem corre.
#
# E nao se resolve com `override_settings` dentro do teste: o
# `DjangoViteAssetLoader` e' um SINGLETON (`asset_loader.py`, `cls._instance`)
# que le `dev_mode` uma vez e nunca se reconstroi. Um `override_settings`
# chega tarde. E o mesmo singleton e' a razao de `DEBUG` ter de estar
# aqui, e nao dentro do teste.
#
# Um teste que depende do `.env` da maquina nao e' um teste: e' uma
# fotografia do ambiente de quem o corre. Este bloco e' o sitio estavel
# para o impedir — e nao um `if DEBUG` no import, que e' o que a CSP
# precisou de um sinal `setting_changed` para nao ser (ver `base.py:465`).
#
# MEDIDO 2026-10-04: `DEBUG=False` tem um efeito de segundo ordem que vale a
# pena saber. `auth.py:495` liga a conta demo a `settings.DEBUG or
# AMPLIAGRO_DEMO_ENABLED`, portanto este bloco DESLIGA o login demo. E'
# o correcto — e os quatro testes que dependem dele
# (`tests_auth.py:489,507` e `tests_operario_kanban.py:84`) usam
# `@override_settings(DEBUG=..., AMPLIAGRO_DEMO_ENABLED=...)` explicito, que
# e' o que torna o DEBUG=True anterior inofensivo e este DEBUG=False
# seguro. Se algum dia um teste precisar do demo sem overridar, o sitio
# certo e' o override, nao ligar DEBUG=True aqui em geral.
DEBUG = False
DJANGO_VITE = {
    **DJANGO_VITE,
    "default": {**DJANGO_VITE["default"], "dev_mode": False},
}

# Chave Fernet fixa p/ testes de criptografia (nunca produção)
AMPLIAGRO_DATA_KEY = "P9BO46kX9OJ46V3LRADIHqiGN_lP_ElHOT9u9nZdWdM="

# Test database
#
# MEDIDO 2026-10-06: isto era `NAME: ":memory:"`, e era a causa da falha do
# job `js` no CI — `no such table: auth_user`, com a migracao a passar.
#
# Por que o `:memory:` parte o CI
# -------------------------------
#
# `:memory:` vive DENTRO do processo. A base existe enquanto o processo
# existir, e desaparece com ele. O CI corre, em comandos separados:
#
#     python manage.py migrate --noinput --settings=config.settings.test
#     python manage.py criar_conta_demo --settings=config.settings.test
#
# O primeiro cria 73 tabelas numa base que morre quando acaba. O segundo abre
# um processo novo, recebe uma base nova e vazia, e falha em `auth_user`.
# Nao ha migracao nenhuma errada: e' a base que nao atravessou a fronteira
# entre os dois comandos.
#
# Por que um FICHEIRO e nao `:memory:`
# ------------------------------------
#
# O `pytest` cria a sua propria base de teste a partir de `NAME` (o Django
# acrescenta `test_` ao nome), portanto o `pytest` continua a correr em
# memoria ou em ficheiro, conforme o `TEST` abaixo. O que muda e' o comando
# de gestao: `migrate` e `criar_conta_demo` passam a ver a MESMA base, porque
# ela esta num ficheiro que sobrevive ao processo.
#
# `TEST["NAME"]` mantem `:memory:` de proposito: o `pytest` cria e destroi
# essa base a cada corrida, e um ficheiro em disco aqui ia deixar dados de uma
# corrida na seguinte. Sao dois ciclos de vida diferentes e por isso dois
# alvos diferentes.
#
# O ficheiro vai para `/tmp`, que no runner do CI e' o mesmo `$RUNNER_TEMP`.
# Nao entra no repositorio: `.gitignore` cobre `*.sqlite3`.
_TEST_DB = os.path.join(tempfile.gettempdir(), "ampliagro_test.sqlite3")

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": _TEST_DB,
        # O pytest continua a usar memoria: criado e destruido a cada corrida.
        "TEST": {"NAME": ":memory:"},
    }
}


# Disable migrations for faster tests
class DisableMigrations:
    def __contains__(self, item):
        return True

    def __getitem__(self, item):
        return None


MIGRATION_MODULES = DisableMigrations()

# Password hashers - use fast hasher for tests
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

# Email backend for tests
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

# Cache - use local memory
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "test-cache",
    }
}

# Celery - eager mode for tests
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# Celery broker for tests
CELERY_BROKER_URL = "memory://"
CELERY_RESULT_BACKEND = "cache"

# Media files
MEDIA_ROOT = "/tmp/test_media/"
MEDIA_URL = "/media/"

# Static files
STATIC_ROOT = "/tmp/test_static/"
STATIC_URL = "/static/"

# Logging - minimal for tests
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "WARNING",
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
    },
}

# Disable external services
WEATHER_API_KEY = "test"
OPENWEATHER_API_KEY = "test"
AGRODOC_API_KEY = "test"
SENTRY_DSN = ""

# Celery eager for tests
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_BROKER_URL = "memory://"
CELERY_RESULT_BACKEND = "cache"

# File storage
DEFAULT_FILE_STORAGE = "django.core.files.storage.FileSystemStorage"

# Disable PWA for tests
PWA_SERVICE_WORKER_PATH = None

# Rate limiting disabled for tests
REST_FRAMEWORK = {
    **REST_FRAMEWORK,
    "DEFAULT_THROTTLE_RATES": {
        "anon": "10000/minute",
        "user": "100000/minute",
    },
}

# Disable rate limiting middleware
MIDDLEWARE = [m for m in MIDDLEWARE if "axes" not in m.lower()]

# Email
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

# Logging minimal
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "null": {
            "class": "logging.NullHandler",
        },
    },
    "root": {
        "handlers": ["null"],
        "level": "CRITICAL",
    },
}
