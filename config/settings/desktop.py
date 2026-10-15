"""Settings do runtime EMBEBIDO do Ampliagro Desktop.

Este módulo herda de `config.settings.base` — **não** de `prod.py`, e a
distinção não é um detalhe de estilo.

`prod.py` força três coisas que são **erradas** num desktop:

- `DATABASES` = PostgreSQL (linha 61). O desktop é uma máquina só.
- `CACHES` = `django_redis` (linha 63). Não há Redis no desktop.
- `SESSION_ENGINE = cache` (linha 70). E `SECURE_SSL_REDIRECT = True`
  (linha 31), que num loopback HTTP dá um **loop de redirect** — é
  exactamente o que o comentário de `prod.py:13-28` descreve a acontecer
  entre o Caddy e o Django, e aqui não há Caddy para o absorver.

`base.py` já tem, sem alterações, tudo o que o desktop precisa:

- SQLite por omissão (linha 201), já com WAL e `transaction_mode=IMMEDIATE`.
- `DatabaseCache` (linha 644) — partilhado sem Redis.
- `InMemoryChannelLayer` sem `REDIS_URL` (linhas 301-319).

O que esta folha faz é **fixar** essas escolhas, porque não se pode
confiar no ambiente: o `.env` do projecto tem `REDIS_URL` e `DATABASE_URL`
a apontar para a cloud, e um desktop que arrancasse com eles ia tentar
ligar-se a um Redis que não existe — e a falha aparece como "o painel não
actualiza", não como "Redis em falta".

O `SECRET_KEY` **também não vem de `.env`**: é gerado por instalação e
persistido no directório de dados. Duas instalações na mesma máquina não
partilham sessão, e o `.env` de desenvolvimento nunca é lido em produção.
"""

import os
from pathlib import Path

from .base import *  # noqa: F401,F403

# ---------------------------------------------------------------------------
# ONDE VIVE O ESTADO
# ---------------------------------------------------------------------------
# NUNCA dentro do directório de instalação. Em macOS a app vive em
# `/Applications`, que é read-only para quem não tem admin; em Linux o
# pacote vive em `/usr/lib`. Escrever aí é falhar no arranque, ou pior,
# correr com privilégios que o desktop não precisa.

AMPLIAGRO_DESKTOP_DATA_DIR = Path(
    os.environ.get("AMPLIAGRO_DESKTOP_DATA_DIR") or (BASE_DIR / ".desktop-data")
).resolve()

AMPLIAGRO_DESKTOP_DATA_DIR.mkdir(parents=True, exist_ok=True)

#: Raiz do código. `BASE_DIR` vem de `base.py` e aponta para a raiz do
#: repositório — onde vivem `app/`, `config/` e `staticfiles/`. O Electron
#: passa isto ao bootstrap por variável de ambiente.
AMPLIAGRO_CODE_ROOT = BASE_DIR

# ---------------------------------------------------------------------------
# MODO DE EXECUÇÃO
# ---------------------------------------------------------------------------

# DEBUG=False. Não é uma escolha de gusto: `DJANGO_VITE["dev_mode"]` é
# `DEBUG` (`base.py:809`), e com DEBUG=True o Django passa a emitir
# `http://localhost:5173/static/...` para o dev-server do Vite
# (`vite.config.ts`, `server.port: 5173`). Não há Vite no desktop, a CSP
# recusa a origem, e o painel fica sem JS nenhum.
DEBUG = False

# O Bootstrap é responsável por pôr isto no ambiente ANTES de importar o
# Django. Ver `config/asgi.py:6`: faz
# `os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.prod")`,
# e `setdefault` só aplica se a variável não existir. Importar o ASGI
# primeiro arrancava o desktop com os settings de PRODUÇÃO.
DJANGO_SETTINGS_MODULE = "config.settings.desktop"

# ---------------------------------------------------------------------------
# IDENTIDADE E ACESSO
# ---------------------------------------------------------------------------
# `SECRET_KEY` tem de existir ANTES de `base.py` — lá em cima ele levanta
# `ValueError` se não houver chave e `DEBUG` for falso (linhas 26-32). É o
# bootstrap que a gera e a persiste; aqui só se confirma que chegou.
#
# A NÃO VERIFICAÇÃO é deliberada: um `assert` aqui transformava uma
# configuração mal posta numa falha com mensagem de settings, e a causa
# real (o bootstrap não passou a chave) ficava escondida.

ALLOWED_HOSTS = ["127.0.0.1", "localhost"]

#: O servidor de loopback. Electron carrega `http://127.0.0.1:<porta>`, e
#: é este header que o Django usa para decidir se o pedido é do desktop.
AMPLIAGRO_DESKTOP_BIND = "127.0.0.1"

# ---------------------------------------------------------------------------
# PERSISTÊNCIA
# ---------------------------------------------------------------------------
# SQLite **no directório de dados**, não em `BASE_DIR/db.sqlite3`. A base
# de desenvolvimento é de outra vida: misturar as duas faz `migrate`
# escrever migrações de um esquema que o produtor nunca viu.

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": str(AMPLIAGRO_DESKTOP_DATA_DIR / "ampliagro-desktop.sqlite3"),
        "OPTIONS": {
            # Mesmos pragmas de `base.py:206-210`. Sem `transaction_mode`
            # a leitura e a escrita ficam a bloquear uma à outra, e o painel
            # do desktop — que lê muito — trava a escrever.
            "timeout": 20,
            "transaction_mode": "IMMEDIATE",
            "init_command": (
                "PRAGMA journal_mode=WAL;"
                "PRAGMA synchronous=NORMAL;"
                "PRAGMA mmap_size=3000000000;"
            ),
        },
    }
}

# Uploads e ficheiros do produtor: no directório de dados, pelo mesmo
# motivo de não-escrever-na-instalação. `MEDIA_ROOT` herdado aponta para
# `BASE_DIR/media` (`base.py:256`).
MEDIA_ROOT = AMPLIAGRO_DESKTOP_DATA_DIR / "media"
MEDIA_ROOT.mkdir(parents=True, exist_ok=True)

# Capturas de clima (`app/services/clima.py`). No directório de dados pelo
# mesmo motivo do SQLite e do `MEDIA_ROOT`: uma actualização do programa não
# pode apagar a última previsão que o produtor viu, e a directório de
# instalação no Windows é `Program Files`, onde não se escreve.
CLIMA_CACHE_DIR = AMPLIAGRO_DESKTOP_DATA_DIR / "cache-clima"
CLIMA_CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Cache em base de dados: herda de `base.py` (`DatabaseCache`). **Não**
# importar `prod.py` — lá isto é `django_redis`, que precisa do Redis.
# Criar a tabela é `createcachetable`, e o bootstrap corrige isso no
# primeiro arranque.

SESSION_ENGINE = "django.contrib.sessions.backends.db"

# ---------------------------------------------------------------------------
# WEBSOCKETS (canais em tempo real)
# ---------------------------------------------------------------------------
# `base.py` escolhe `InMemoryChannelLayer` **se não houver** `REDIS_URL`
# (linhas 303-319). O `.env` deste projecto TEM `REDIS_URL`. Portanto
# deixar herdar é deixar o desktop tentar ligar-se ao Redis de
# desenvolvimento, e a consequência é silenciosa: os WebSockets
# (`ws/dashboard/`, `app/consumers.py`) falham a subir e o painel fica
# sem actualizações de sensor — sem erro visível.
#
# InMemory é correcto **porque o desktop é um processo só**. É a mesma
# condição que o comentário de `base.py:297-300` descreve.

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    },
}

# ---------------------------------------------------------------------------
# TAREFAS
# ---------------------------------------------------------------------------
# Sem Celery: sem broker, sem worker, sem `CELERY_BROKER_URL` a resolver.
# `task_always_eager` corre a tarefa **na thread do pedido**, o que serve
# para o AlertTask do painel e para a recolha de telemetria.
#
# O custo é Known e escrito: uma tarefa que bloqueie (chamada a API
# externa lenta, PDF grande) atrasa o pedido HTTP que a disparou. Por
# isso o `thread_sensitive` fica desligado, e a verificação de "isto não
# é seguro correr na request" é da Fase 1.

CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_TASK_STORE_EAGER_RESULT = False

# `CELERY_TASK_STORE_EAGER_RESULT = False` acima ja e' a resposta: o desktop
# nao guarda resultado de tarefa em lado nenhum. Logo a app que os guarda nao
# serve para nada aqui.
#
# MEDIDO 14/10/2026, no CI: `base.py:84` põe `django_celery_results` em
# `INSTALLED_APPS`, e o `requirements-desktop.txt` exclui `django-celery-results`
# de proposito (esta escrito na razao da exclusao). O Django importa todas as
# apps do `INSTALLED_APPS` no arranque, portanto um desktop instalado numa
# maquina limpa morria com `ModuleNotFoundError: No module named
# 'django_celery_results'` — e nao na instalacao: no arranque da app.
#
# So nao rebentou local porque a venv de desenvolvimento tinha o pacote, e o
# PyInstaller empacotou-o por ela. O produto carregava uma dependencia que
# declara nao usar, por acaso.
INSTALLED_APPS = [app for app in INSTALLED_APPS if app != "django_celery_results"]

# ---------------------------------------------------------------------------
# SEGURANÇA
# ---------------------------------------------------------------------------
# O desktop serve HTTP em loopback. Todo o bloco TLS de `prod.py` é
# inaplicável e actively perigoso: `SECURE_SSL_REDIRECT=True` devolveria
# 301 para https, o Chromium seguiria, e o servidor não TLS devolveria
# outra vez 301 — o loop que `prod.py:20-28` descreve.

SECURE_SSL_REDIRECT = False
SECURE_HSTS_SECONDS = 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

# Loopback em HTTP não é a internet em HTTP: o processo escuta só em
# `127.0.0.1`, e nenhum outro host o alcança. `None` (o omisso) obriga o
# browser a não enviar cookies em contexto cross-site, o que é o que se
# quer num receptor com sessão.
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_TRUSTED_ORIGINS = [
    f"http://127.0.0.1:{os.environ.get('AMPLIAGRO_DESKTOP_PORT', '8765')}",
    "http://127.0.0.1",
    "http://localhost",
]

# ---------------------------------------------------------------------------
# FRONTEND
# ---------------------------------------------------------------------------
# `dev_mode=False` — com DEBUG=False já vem False de `base.py:809`, mas
# fica escrito porque é o ajuste que mais doeria perder em silêncio: com
# `dev_mode` ligado, o Vite não é encontrado e o painel não tem JS.
DJANGO_VITE = {
    "default": {
        "dev_mode": False,
        "dev_server_host": "127.0.0.1",
        "dev_server_port": 5173,
        "manifest_path": BASE_DIR / "staticfiles" / "dist" / ".vite" / "manifest.json",
    }
}

# ---------------------------------------------------------------------------
# CONTENT SECURITY POLICY
# ---------------------------------------------------------------------------
# A CSP de `base.py` (linhas 358-481) está feita para a web e é mantida
# tal e qual. Duas entradas acrescentadas, **aqui** e não em `base.py`:
#
# 1. `ws://127.0.0.1` em `connect-src`. O painel abre `ws://127.0.0.1:<p>/ws/dashboard/`
#    (`app/consumers.py`). `'self'` não é uniforme quanto a `ws:` — a
#    compatibilidade entre navegadores é irregular, e a falha é o
#    WebSocket recusado sem mensagem.
# 2. `'unsafe-inline'` já está em `script-src` (`base.py:401`) e continua
#    a ser preciso: são 606 handlers `on*=` nos templates. Não se mexe
#    aqui — mexer é a ADR de endurecer CSP, que é outro projecto.
#
# O objectivo desta fase é **não acrescentar** origens, e é por isso que
# a verificação da Fase 2 (rede bloqueada) passa a ser o gate real.

# ---------------------------------------------------------------------------
# LOG
# ---------------------------------------------------------------------------
# `base.py:762` põe o handler de ficheiro em `BASE_DIR / "logs"`. Numa app
# instalada isso é o directório de instalação — `/Applications` no macOS
# (read-only sem admin), `/usr/lib` numa distribuição Linux, `Program Files`
# no Windows. Escrever lá é o executável morrer no arranque com:
#
#     ValueError: Unable to configure handler 'file'
#
# e o producer vê uma janela que não abre, sem causa. Foi o que aconteceu
# na primeira construção congelada.
#
# O log vai para o directório de dados, que é do utilizador e é para isso
# que ele existe. Numa instalação em modo de leitura, isto não levanta
# excepção nenhuma.
_LOGS = AMPLIAGRO_DESKTOP_DATA_DIR / "logs"
_LOGS.mkdir(parents=True, exist_ok=True)

LOGGING = {
    **LOGGING,  # noqa: F405 — herdado de base
    "handlers": {
        **LOGGING["handlers"],  # noqa: F405
        "file": {
            **LOGGING["handlers"]["file"],  # noqa: F405
            "filename": str(_LOGS / "ampliagro-desktop.log"),
        },
    },
}

# ---------------------------------------------------------------------------
# CONTENT SECURITY POLICY — ESTA É A PROVA DE OFFLINE
# ---------------------------------------------------------------------------
# A CSP herdada de `base.py` (linhas 358-481) está feita para a web e lista
# explicitamente as origens externas que o browser pode contactar:
# unpkg, jsdelivr, fonts.gstatic, esm.run, huggingface, open-meteo, OSM.
#
# No desktop, **todas essas entradas saem**. Não por_updates de estilo —
# é a diferença entre uma aplicação que funciona sem rede e uma que só
# funciona porque alguém se lembra de não desligar a net.
#
# E o que faz isto ser uma PROVA, e não uma configuração: o browser não
# pede para depois recusar. Uma origem que não está na CSP **nunca chega a
# ser pedida**. Se a página abre com o gráfico, o mapa e os ícones todos no
# sítio, é porque tudo veio de `127.0.0.1` — não porque o pedido foi
# bloqueado e a página se houve bem na mesma.
#
# O que fica FORA de propósito, e porque:
#
#   `esm.run`, `huggingface.co` — o WebLLM (pack opcional, Fase 4). Sem
#     isto a IA local avisa em vez de tentar e falhar: ver o modo
#     determinístico. Preferimos um aviso honesto a um request recusado.
#
#   `api.open-meteo.com`, `nominatim.openstreetmap.org`, `*.tile.openstreetmap.org`,
#   `agrodocai.com.br` — serviços. Vendorizar um endpoint de API não é
#     vendorizar: não há ficheiro para guardar que o substitua. O desktop
#     guarda a última captura em cache e mostra a hora dela; sem captura,
#     mostra `—` com fonte `sem sinal`. Ver `previsao_clima` do plano.
#
# ⚠️ Se mexer nesta lista, `testes/gate-offline.cjs` é o que vai dizer se
#    a página ainda abre. Um bloco a mais e o mapa desaparece em silêncio.

_CSP_APENAS_LOCAL = {
    "default-src": ["'self'"],
    # `'unsafe-inline'` continua a ser preciso: são 606 handlers `on*=`
    # nos templates e um `<script>` inline de ~13.000 linhas. Endurecer
    # isto é a ADR de CSP, que é outro projecto.
    "script-src": ["'self'", "'unsafe-inline'", "'wasm-unsafe-eval'"],
    "style-src": ["'self'", "'unsafe-inline'"],
    "font-src": ["'self'", "data:"],
    # `blob:` porque o worker do Whisper é criado a partir de um Blob URL
    # (`app/static/js/ia-local/whisper-worker.js`).
    "img-src": ["'self'", "data:", "blob:"],
    "worker-src": ["'self'", "blob:"],
    # Só o WebSocket do próprio servidor.
    "connect-src": ["'self'", "ws://127.0.0.1", "http://127.0.0.1"],
    "frame-ancestors": ["'none'"],
    "base-uri": ["'self'"],
    "form-action": ["'self'"],
    "object-src": ["'none'"],
}

#: A política do desktop **substitui** a de `base.py` por inteiro, e não
#: a acrescenta. Acrescentar deixaria as origens externas da web a
#: continuar permitidas, que é exactamente o que se quer tirar.
CONTENT_SECURITY_POLICY = {"DIRECTIVES": _CSP_APENAS_LOCAL}

# ---------------------------------------------------------------------------
# DETECÇÃO DE BOTS
# ---------------------------------------------------------------------------
# `base.py` tem os dois desligados (linhas 564-565) e assim fica. Mas
# escrito de propósito: Electron envia um `User-Agent` **sem** a cadeia
# normal de browser em alguns canais, e o limiar de `BOT_LIMIAR` (8) é
# feito para detectores. Um desktop ligado a isto fecha o painel ao
# produtor. Desligado é o estado correcto, e não um esquecimento.

BOT_DETECTOR_LIGADO = False
BOT_BLOQUEAR = False

# Regras locais a cada cinco minutos enquanto o aplicativo estiver aberto.
# Apenas propriedades com proatividade ativada entram na varredura.
AMPLIA_LOCAL_COPILOTO = os.environ.get("AMPLIA_LOCAL_COPILOTO", "1") == "1"

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------
# O desktop não é uma origem CORS: a página é servida pelo **mesmo**
# processo que a serve, em `127.0.0.1:<porta>`. `CORS_ALLOW_ALL_ORIGINS`
# seria um buraco sem motivo. Lista mínima para o dev-server, que só
# existe em DEBUG e portanto nunca é alcançada a partir daqui.

CORS_ALLOWED_ORIGINS = ["http://127.0.0.1:8765", "http://localhost:8765"]
CORS_ALLOW_CREDENTIALS = True

# ---------------------------------------------------------------------------
# STATIC
# ---------------------------------------------------------------------------
# `base.py:253` usa `CompressedManifestStaticFilesStorage`, que é o que o
# WhiteNoise usa para servir ficheiros com nome hasheado. Os ficheiros já
# estão colectados em `staticfiles/` (medição: 169 `.js`). Se o bootstrap
# correr `collectstatic` antes de servir, isto continua a funcionar; é a
# operação que garante que não falta nada num checkout novo.
