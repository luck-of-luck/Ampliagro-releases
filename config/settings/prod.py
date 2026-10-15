from .base import *

# Override default for prod
DEBUG = False

# Ensure these are provided in .env
# ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', '').split(',')

# Configurações de segurança avançadas para prod
#
# `SECURE_PROXY_SSL_HEADER` é o que faz o Django enxergar o TLS.
#
# O Caddy é a borda e termina o TLS; a ligação Caddy -> app é HTTPWithin a
# rede do compose. O WSGI server põe `wsgi.url_scheme = "http"` e, sem esta
# linha, `request.is_secure()` é SEMPRE False — o header que o Caddy manda
# (Caddyfile, `header_up X-Forwarded-Proto {scheme}`) chega em
# HTTP_X_FORWARDED_PROTO e ninguém o lê.
#
# Sem isto, `SECURE_SSL_REDIRECT=True` devolve 301 para https, o browser
# pede, o Caddy repassa como http, o Django volta a pedir https: loop. Foi
# exatamente isso que obrigou a desligar o redirect em produção — e desligar
# o redirect significa perder também o HSTS, que só é emitido em resposta
# segura.
#
# IMPORTANTE — isto só é seguro porque o app NÃO está exposto directamente:
# `docker-compose.prod.yml` publica 8000 em 127.0.0.1, não em 0.0.0.0. Se
# alguém publicar a porta 8000, um cliente passa a mandar este header à mão
# e a enganar o Django sobre o próprio transporte.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

SECURE_SSL_REDIRECT = os.environ.get("SECURE_SSL_REDIRECT", "True").lower() in (
    "true",
    "1",
    "t",
)
SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "True").lower() in (
    "true",
    "1",
    "t",
)
CSRF_COOKIE_SECURE = os.environ.get("CSRF_COOKIE_SECURE", "True").lower() in (
    "true",
    "1",
    "t",
)
SECURE_HSTS_SECONDS = int(os.environ.get("SECURE_HSTS_SECONDS", "31536000"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = os.environ.get(
    "SECURE_HSTS_INCLUDE_SUBDOMAINS", "True"
).lower() in ("true", "1", "t")
SECURE_HSTS_PRELOAD = os.environ.get("SECURE_HSTS_PRELOAD", "True").lower() in (
    "true",
    "1",
    "t",
)


# ─────────────────────────────────────────────────────────────────────────────
# PORQUE ESTE GUARDA EXISTE
#
# MEDIDO 2026-10-05: `manage.py check --deploy --settings=config.settings.prod`
# acusou security.W004/W008/W012/W016 — e `prod.py` declara os quatro como
# `True` nas linhas acima. Os valores EFECTIVOS eram `False`.
#
# A razao e' uma assimetria, nao um erro de escrita:
#
#   * `SECRET_KEY` (base.py:27-32) falha FECHADO — levanta se faltar em prod.
#     Esse e' o padrao do projecto, e ja' estava escrito.
#   * `DEBUG` esta' protegido por um LITERAL (linha 4), que vem depois do
#     `from .base import *` e por isso ganha do `.env`. E' por isso que
#     security.W018 NAO disparou: so o DEBUG sobreviveu.
#   * Estes cinco sao lidos de `os.environ`. Um default seguro so protege
#     enquanto a variavel nao existir — e `base.py:9` faz
#     `load_dotenv(BASE_DIR / ".env")` SEM condicao. O `.env` de
#     DESENVOLVIMENTO define os cinco como `False`.
#
# Logo: se o `.env` de desenvolvimento entrar na imagem ou no volume, o
# arranque em producao fica com cookies sem `Secure`, sem redireccionamento
# para HTTPS e sem HSTS — sem erro, sem aviso, sem teste vermelho.
#
# Nao e' um exploit. E' pior: e' uma falha que se apresenta como
# funcionamento normal. O produtor manda as credenciais em claro e o site
# aceita-as, e nada avisa.
#
# O QUE FAZ: o arranque falha, e a mensagem diz QUAL ficheiro esta' a
# poisoning. Recusar e' mais barato do que servir em claro.
# ─────────────────────────────────────────────────────────────────────────────

if not DEBUG:
    _inseguras = [
        nome
        for nome, valor in (
            ("SECURE_SSL_REDIRECT", SECURE_SSL_REDIRECT),
            ("SESSION_COOKIE_SECURE", SESSION_COOKIE_SECURE),
            ("CSRF_COOKIE_SECURE", CSRF_COOKIE_SECURE),
        )
        if not valor
    ]
    if SECURE_HSTS_SECONDS <= 0:
        _inseguras.append("SECURE_HSTS_SECONDS=0 (HSTS desactivado)")
    if not SECURE_HSTS_PRELOAD:
        _inseguras.append("SECURE_HSTS_PRELOAD=False")

    if _inseguras and os.environ.get("AMPLIAGRO_ALLOW_INSECURE_PROD", "") != "1":
        from django.core.exceptions import ImproperlyConfigured

        raise ImproperlyConfigured(
            "Arranque em producao com transport inseguro. Nao e' um aviso: "
            "e' a condicao que faria o producer enviar a sessao em claro.\n\n"
            "Inseguras:\n  - "
            + "\n  - ".join(_inseguras)
            + "\n\nCausa provavel: o `.env` de DESENVOLVIMENTO foi copiado para "
            "a maquina de producao. `config/settings/base.py:9` faz "
            "`load_dotenv(BASE_DIR / '.env')` sem condicao, e esse ficheiro "
            "define estes cinco como `False`.\n\n"
            "Corrige o `.env` de producao (ver `.env.prod.example`), ou "
            "declara no compose:\n"
            "  SESSION_COOKIE_SECURE=True\n"
            "  CSRF_COOKIE_SECURE=True\n"
            "  SECURE_SSL_REDIRECT=True\n"
            "  SECURE_HSTS_SECONDS=31536000\n"
            "  SECURE_HSTS_PRELOAD=True\n\n"
            "Para um smoke test LOCAL e so local, "
            "AMPLIAGRO_ALLOW_INSECURE_PROD=1. Em producao isso e' o mesmo "
            "defeito com um nome mais comprido."
        )

# Banco de dados PostgreSQL
import environ

env = environ.Env()

DATABASES = {"default": env.db("DATABASE_URL")}

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": env("REDIS_URL", default="redis://localhost:6379/0"),
        "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
    }
}
SESSION_ENGINE = "django.contrib.sessions.backends.cache"
SESSION_CACHE_ALIAS = "default"
