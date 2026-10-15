"""Bootstrap do runtime embebido do Ampliagro Desktop.

Este processo é filho do Electron. Ele, por sua vez:

1. resolve o `SECRET_KEY` por instalação;
2. escolhe uma porta livre em loopback;
3. corre as migrações e cria a tabela de cache;
4. arranca o **Daphne** (ASGI — HTTP e WebSocket);
5. espera `/healthz` responder antes de dizer ao Electron "pode abrir";
6. fica à espera e, quando o Electron morre, mata o Daphne.

O Electron **não** fala com o Django directamente. Fala com este processo
e lê a porta de uma linha no stdout.

--------------------------------------------------------------------------
A ORDEM DOS PASSOS 1 e 4 NÃO É ESTILÍSTICA — É O QUE EVITA UM BUG
SILENCIOSO
--------------------------------------------------------------------------

`config/asgi.py:6` tem:

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.prod")

`setdefault` só escreve se a variável **ainda não existir**. Por isso este
ficheiro atribui `DJANGO_SETTINGS_MODULE` no topo, ANTES de qualquer
`import django`.

Se a ordem se invertesse, o desktop arrancava com **`config.settings.prod`**:
PostgreSQL, `django_redis` e `SECURE_SSL_REDIRECT=True`. Em loopback HTTP o
redirect TLS dá um 301↔301 infinito (é o loop descrito em
`config/settings/prod.py:20-28`, que ali não acontece porque o Caddy absorve
o TLS e aqui não há Caddy). O sintoma seria uma janela branca que nunca
carrega, e a causa — os settings errados — não apareceria em lado nenhum.

Da mesma ordem depende o `SECRET_KEY`: `config/settings/base.py:26-32` levanta
`ValueError` se a chave faltar e `DEBUG` for falso.
"""

from __future__ import annotations

import argparse
import atexit
import json
import os
import secrets
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

# ---------------------------------------------------------------------------
# CAMINHOS — resolvidos ANTES de tocar em `os.environ`
# ---------------------------------------------------------------------------
# `AMPLIAGRO_CODE_ROOT` é a raiz do repositório: onde vivem `app/`,
# `config/` e `staticfiles/`. O Electron passa-o por ambiente porque, num
# pacote empacotado, o código não está onde o repositório estava.
#
# Sem a variável, procuramos **subindo** a árvore em vez de contar níveis
# com `.parent.parent`. A contagem é um número que mente assim que a pasta
# ganha um nível — e mente em SILÊNCIO, porque o caminho errado só falha
# quando o Django não está onde se espera. O marcador `manage.py` + os
# settings é o que confirma que é a raiz certa, não a contagem.

AQUI = Path(__file__).resolve().parent


def _procurar_raiz() -> Path:
    """Sobe a árvore à procura da raiz do repositório.

    O teste é duplo de propósito: `manage.py` sozinho encontraria o
    `manage.py` de outro projecto num directório acima, e `config/`
    sozinho não diz nada. Os dois juntos, mais os settings de desktop, são
    o que torna o match fiável.
    """
    for candidato in (AQUI, *AQUI.parents):
        if (candidato / "manage.py").is_file() and (
            candidato / "config" / "settings" / "desktop.py"
        ).is_file():
            return candidato

    # Não encontrado: dá a dica mais útil possível, que é aonde se
    # procurou e o que lá havia — não um "erro de configuração".
    raise SystemExit(
        f"[bootstrap] Não encontrei a raiz do Ampliagro a partir de {AQUI}.\n"
        f"[bootstrap] Esperava um directório com manage.py E config/settings/desktop.py.\n"
        f"[bootstrap] Defina AMPLIAGRO_CODE_ROOT para apontar para essa raiz."
    )


CODE_ROOT = Path(os.environ.get("AMPLIAGRO_CODE_ROOT") or _procurar_raiz()).resolve()

if str(CODE_ROOT) not in sys.path:
    sys.path.insert(0, str(CODE_ROOT))

DATA_DIR = Path(
    os.environ.get("AMPLIAGRO_DESKTOP_DATA_DIR") or (CODE_ROOT / ".desktop-data")
).resolve()
DATA_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# AMBIENTE — antes de QUALQUER import do Django. Ver o aviso no topo.
# ---------------------------------------------------------------------------

os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings.desktop"
# `setdefault` deliberado: quem chamou (o Electron, em testes) pode ter
# vindo com um valor explícito.
os.environ.setdefault("AMPLIAGRO_DESKTOP_DATA_DIR", str(DATA_DIR))
os.environ.setdefault("AMPLIAGRO_DESKTOP_CODE_ROOT", str(CODE_ROOT))
# O `.env` do projecto tem `REDIS_URL` e `DATABASE_URL` a apontar para a
# cloud. `config/settings/desktop.py` já os ignora, mas limpamos aqui
# para que qualquer biblioteca de terceiros que os leia directamente não
# tente ligar-se a um Redis que não existe.
os.environ.pop("REDIS_URL", None)
os.environ.pop("DATABASE_URL", None)


def log(mensagem: str) -> None:
    """Vai para stderr, nunca para stdout.

    stdout é o **canal de comando** entre o Electron e este processo: a
    linha `AMPLIAGRO_DESKTOP_READY ...` é lida pelo pai. Um log em stdout
    sujava esse protocolo.
    """
    print(f"[bootstrap] {mensagem}", file=sys.stderr, flush=True)


def resolver_secret_key() -> str:
    """Devolve a chave desta instalação, criando-a na primeira vez.

    Porquê não a do `.env`: duas instalações na mesma máquina (ou um
    checkout de desenvolvimento ao lado) passariam a partilhar sessão, e
    uma cookie válida numa serviria na outra. A chave é por instalação.

    Guardada em `secret.key` com permissão 600 (POSIX). No Windows o modo
    é herdado do directório do utilizador, que já é protegido — por isso
    o `chmod` está dentro de um `try` que engole o `OSError`, e não numa
    excepção que impediria o arranque numa máquina legível.
    """
    caminho = DATA_DIR / "secret.key"

    if caminho.is_file():
        chave = caminho.read_text(encoding="utf-8").strip()
        if chave:
            return chave
        log("secret.key vazio — a gerar um novo.")
    else:
        log("Primeiro arranque: a gerar SECRET_KEY.")

    chave = secrets.token_urlsafe(64)
    caminho.write_text(chave, encoding="utf-8")
    try:
        caminho.chmod(0o600)
    except OSError:
        pass  # Windows; a ACL do perfil do utilizador cobre isto.

    return chave


def escolher_porta() -> int:
    """Porta livre em 127.0.0.1, escolhida pelo próprio sistema operativo.

    A janela entre fechar o socket de sondagem e o Daphne abrir é pequena
    mas não é zero — é a razão de `arrancar_daphne` ter um retry. Pedir
    uma porta fixa (8765) seria pior: dois desktops abertos no mesmo
    momento, ou um atacante local a ocupar a porta, e o segundo desktop
    não arrancava com uma mensagem que não diria a causa.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        # Sem SO_REUSEADDR: queremos que o bind falhe se já houver alguém.
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def esperar_health(porta: int, timeout_s: float = 45.0) -> dict:
    """Esquece o `OK` do processo: espera o `/healthz` responder de facto.

    `/healthz` (`app/views/health_dashboard.py`) não exige autenticação e
    devolve JSON com quatro verificações — base de dados, cache, disco e
    migrações. É o único ponto do sistema que diz "o pedido chegou e o
    Django está a responder", que é o que o Electron precisa saber.

    Insuficiente não é "não respondeu ainda": se o status vier `fail`, o
    bootstrap não arranca. Um painel que abre sobre uma base sem migrações
    mostra erros em cada página, e a causa fica atrás de três camadas de UI.

    `warn` NÃO trava o arranque — MEDIDO 2026-10-13, e era um bug que fechava
    o produto inteiro sem o produtor poder fazer nada:

        [bootstrap] /healthz não ficou OK em 45.0s. Último: healthz
        status=warn checks={'db': {'status': 'ok', 'latency_ms': 16.0},
        'cache': {'status': 'ok', ...}, 'disk': {'status': 'warn',
        'used_pct': 90.4, 'free_gb': 89.05}, 'migrations': {'status': 'ok',
        'pending': 0}}

    O disco do utilizador estava a 90,4% ocupado — com 89 GB LIVRES. O
    `_check_disk` responde `warn` a partir de 90% (`app/views/
    health_dashboard.py:51`), o agregado sobe a `warn`, e este `== "ok"`
    tratava `warn` como morte. Resultado: o desktop não arrancava, o Electron
    abria um `dialog.showErrorBox` a dizer "o runtime terminou (código 1)", e
    a causa real — um disco quase cheio num portátil — ficava a três camadas
    de distância, sem nada no ecrã que a dissesse.

    `warn` é, pela definição do endpoint, "responde e funciona, mas há um
    aviso". O `warn` é registado e mostrado, e o arranque continua: é
    exactamente o que o docstring desta função promete desde o início.
    """
    url = f"http://127.0.0.1:{porta}/healthz"
    limite = time.monotonic() + timeout_s
    ultimo_erro = "sem tentativa"

    while time.monotonic() < limite:
        try:
            with urllib.request.urlopen(url, timeout=3) as resposta:
                corpo = json.loads(resposta.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            ultimo_erro = f"HTTP {e.code} — o servidor respondeu, mas não OK"
            time.sleep(0.5)
            continue
        except (urllib.error.URLError, OSError, json.JSONDecodeError) as e:
            ultimo_erro = repr(e)
            time.sleep(0.35)
            continue

        estado = corpo.get("status")
        if estado == "ok":
            return corpo

        if estado == "warn":
            # Arranca, mas não em silêncio. Um `warn` que ninguém lê é um
            # `fail` só que mais lento: o disco enche-se todo e ninguém foi
            # avisado. Vai para stderr, que é o log, e o Electron mostra-o.
            avisos = {
                nome: check
                for nome, check in (corpo.get("checks") or {}).items()
                if check.get("status") == "warn"
            }
            log(f"/healthz em warn — a arrancar na mesma. Verificações: {avisos}")
            return corpo

        ultimo_erro = f"healthz status={estado} checks={corpo.get('checks')}"
        time.sleep(0.5)

    raise TimeoutError(f"/healthz não ficou OK em {timeout_s}s. Último: {ultimo_erro}")


def fazer_backup(db: Path) -> Path | None:
    """Cópia de segurança da base ANTES de `migrate`, se existir uma.

         ---------------------------------------------------------------------------
         PORQUÊ ISTO É OBRIGATÓRIO E NÃO UM DETALHE
         ---------------------------------------------------------------------------
         Uma migração do Django que dá errado a meio deixa a base num estado
         intermédio. No desktop isso é pior do que na web: aqui a base é a
         **única** cópia. A nuvem tem réplicas; um produtor com o desktop não
         tem nada para onde ir se a migração partir.

         E "se a migração partir" não é-books: há mais de 300 migrações
         (`app/migrations/`), e a atualização de uma app que sai a cada poucas
         semanas vai cruzar o caminho de uma delas.

         Três decisões que este código toma e o porquê:

         **1. Só copia se a base já existir.** Num primeiro arranque não há nada
         para preservar, e criar uma cópia vazia de um ficheiro inexistente só
         confunde quem vai limpar a pasta.

         **2. Usa a API do SQLite, não `shutil.copy`.** Copiar o ficheiro a
         meio de uma escrita dá um `.sqlite3` truncado que o SQLite recusa a
         abrir — e o producer fica sem base E sem cópia boa. A
         `Connection.backup()` tira uma cópia consistente mesmo com WAL activo
         (que é o caso: `base.py:209` liga `journal_mode=WAL`).

    **3. Apaga o backup depois de `migrate` correr bem.** Deixá-lo no
        sítio seria mentir sobre o estado: o produtor vê o backup e pensa que
        é o estado actual, quando é o anterior. O backup é para o caso de
        correr mal, não para clutter permanente. Falha a migração? O backup
        fica, e o bootstrap aborta sem abrir a janela.
    """
    if not db.is_file():
        return None

    destino_dir = DATA_DIR / "backups"
    destino_dir.mkdir(parents=True, exist_ok=True)
    destino = destino_dir / f"{db.stem}-antes-da-migracao.sqlite3"

    import sqlite3

    origem = sqlite3.connect(db)
    try:
        alvo = sqlite3.connect(destino)
        try:
            origem.backup(alvo)
        finally:
            alvo.close()
    except sqlite3.Error as e:
        origem.close()
        raise RuntimeError(
            f"não consegui fazer backup da base antes de migrar: {e}\n"
            f"Recuso-me a migrar sem cópia de segurança — na cloud há "
            f"réplica, no desktop não há."
        ) from e
    finally:
        origem.close()

    tamanho = destino.stat().st_size
    log(f"Backup da base antes de migrar: {destino.name} ({tamanho / 1024:.0f} KB)")
    return destino


def preparar_banco() -> None:
    """Backup, migrações e tabela de cache — antes de o Daphne aceitar tráfego.

    `CACHES` é `DatabaseCache` (herdado de `base.py:644`) e a tabela não é
    criada por `migrate` — é `createcachetable`, à parte. Sem ela, o
    primeiro acesso ao cache levanta `ProgrammingError` e a página morre
    com um erro que não menciona cache.
    """
    from django.core.management import call_command

    from django.conf import settings

    caminho_db = Path(settings.DATABASES["default"]["NAME"])

    backup = None
    verbosity = 0

    try:
        backup = fazer_backup(caminho_db)
    except RuntimeError:
        # O backup falhou. Deixar correr `migrate` na mesma seria continuar
        # sem rede debaixo de uma ponte que ardeu. Abortar aqui dá ao
        # produtor a base intacta e uma mensagem que diz o que fazer.
        raise

    log("A aplicar migrações…")
    call_command("migrate", interactive=False, verbosity=verbosity)

    # Só depois de `migrate` ter corrido bem é que o backup deixa de
    # servir. Ver o ponto 3 do docstring de `fazer_backup`.
    if backup is not None and backup.exists():
        backup.unlink()
        log("Migrações aplicadas — backup pré-migração removido.")

    log("A garantir a tabela de cache…")
    call_command("createcachetable", verbosity=verbosity)


def _pr_set_pdeathsig() -> None:  # pragma: no cover — executado no filho
    """`preexec_fn` para Linux: o pai morreu? Então leva SIGTERM.

    Corre dentro do filho, logo depois do `fork`. É o único sítio onde isto
    pode ser pedido — depois do `exec` já não há Python.

    A corrida conhecida (o pai morre entre o `fork` e esta chamada) fica
    tapada pela verificação de `getppid()` em `arranque_daphne`: se o pai
    já tiver morrido, o ppid é 1 (init) e o filho sai antes de servir.
    """
    import ctypes
    import signal as _signal

    libc = ctypes.CDLL("libc.so.6", use_errno=True)
    PR_SET_PDEATHSIG = 1
    if libc.prctl(PR_SET_PDEATHSIG, _signal.SIGTERM, 0, 0, 0) != 0:
        errno = ctypes.get_errno()
        raise OSError(errno, f"prctl(PR_SET_PDEATHSIG) falhou: {os.strerror(errno)}")


#: Handle do Job Object do Windows.
#:
#: Vive no escopo do módulo **de propósito**. Se este objeto for
#: colectado pelo garbage collector, o CPython fecha a handle, o job
#: esgota a última referência e — por `KILL_ON_JOB_CLOSE` — mata o Daphne
#: a meio do arranque. Referência a mais é inofensiva; a menos não é.
_HANDLE_JOB: int | None = None


def _proteger_filho_windows(processo: subprocess.Popen) -> None:
    """Põe o filho num Job Object que morre com este processo.

    Só `ctypes` e `kernel32` — sem `pywin32`, sem nova dependência.

    `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE` diz ao núcleo: "quando a última
    handle deste job fechar, mata tudo o que lá estiver dentro". Como a
    handle vive neste processo, e este processo morreu, o núcleo mata o
    Daphne — sem depender de este código correr seja o que for.
    """
    global _HANDLE_JOB  # noqa: PLW0603 — é um handle de SO, por definição global

    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    JobObjectExtendedLimitInformation = 9
    JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
    PROCESS_SET_QUOTA = 0x0100
    PROCESS_TERMINATE = 0x0001

    class _BASIC_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.c_int64),
            ("PerJobUserTimeLimit", ctypes.c_int64),
            ("LimitFlags", wintypes.DWORD),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", wintypes.DWORD),
            ("Affinity", ctypes.c_size_t),
            ("PriorityClass", wintypes.DWORD),
            ("SchedulingClass", wintypes.DWORD),
        ]

    class _IO_COUNTERS(ctypes.Structure):
        _fields_ = [
            ("ReadOperationCount", ctypes.c_uint64),
            ("WriteOperationCount", ctypes.c_uint64),
            ("OtherOperationCount", ctypes.c_uint64),
            ("ReadTransferCount", ctypes.c_uint64),
            ("WriteTransferCount", ctypes.c_uint64),
            ("OtherTransferCount", ctypes.c_uint64),
        ]

    class _EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", _BASIC_LIMIT_INFORMATION),
            ("IoInfo", _IO_COUNTERS),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]

    # A handle do job vive neste processo; se for fechada, mata o job.
    job = kernel32.CreateJobObjectW(None, None)
    if not job:
        raise ctypes.WinError(ctypes.get_last_error())

    info = _EXTENDED_LIMIT_INFORMATION()
    info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE

    if not kernel32.SetInformationJobObject(
        job, JobObjectExtendedLimitInformation, ctypes.byref(info), ctypes.sizeof(info)
    ):
        err = ctypes.get_last_error()
        kernel32.CloseHandle(job)
        raise ctypes.WinError(err)

    processo = kernel32.OpenProcess(
        PROCESS_SET_QUOTA | PROCESS_TERMINATE, False, processo.pid
    )
    if not processo:
        err = ctypes.get_last_error()
        kernel32.CloseHandle(job)
        raise ctypes.WinError(err)

    try:
        if not kernel32.AssignProcessToJobObject(job, processo):
            raise ctypes.WinError(ctypes.get_last_error())
    finally:
        kernel32.CloseHandle(processo)  # a do job é que tem de ficar de pé

    _HANDLE_JOB = job
    log(f"Job Object {job}: o Daphne morre com este processo, mesmo em kill forçado.")


def proteger_filho(processo: subprocess.Popen) -> None:
    """Garante que o filho não sobrevive a este processo. Ver o docstring."""
    if sys.platform == "win32":
        _proteger_filho_windows(processo)
    elif sys.platform.startswith("linux"):
        # A protecção já foi pedida no preexec_fn; aqui só se confirma que
        # o pai ainda estava vivo quando o filho nasceu.
        if os.getppid() == 1:
            processo.terminate()
            raise RuntimeError(
                "o pai morreu antes de o filho instalar PR_SET_PDEATHSIG"
            )
        log(
            "PR_SET_PDEATHSIG instalado: o Daphne leva SIGTERM se este processo morrer."
        )
    else:
        # macOS: sem suporte no núcleo. Registado como limitação, não
        # escondido — ver o docstring de `arranque_daphne`.
        log(
            "AVISO: macOS não tem PR_SET_PDEATHSIG nem Job Object. "
            "O encerramento depende de o Electron matar explicitamente o "
            "processo filho. Registado como limitação conhecida."
        )


def arranque_daphne(porta: int, tentativas: int = 3) -> subprocess.Popen:
    """Arranca o Daphne como processo FILHO.

    Daphne e não `runserver`: `runserver` recarrega ao alterar ficheiros
    (inútil aqui, e em produção é desaconselhado), e — o que decide — é o
    único caminho que serve **WebSocket**. `config/asgi.py` expõe
    `ws/dashboard/` → `DashboardConsumer` (`app/consumers.py`), que alimenta
    os alertas de sensor em tempo real. Um servidor WSGI serviria a página
    e deixaria os alertas mudos, sem dar sinal.

    Ser um processo separado (e não um `Server` em thread) é o que permite
    matar o Daphne a sério quando o Electron fecha: `terminate()` numa
    thread dentro do mesmo processo não liberta o socket de listening.

    ------------------------------------------------------------------
    PORQUÊ O FILHO PRECISA DE PROtecÇÃO E NÃO DE `atexit`
    ------------------------------------------------------------------
    A primeira versão deste ficheiro confiava no `atexit` para matar o
    Daphne. **Medido que isso não funciona no Windows** — e o Windows é o
    SO principal do projecto.

    Prova (medida nesta máquina, `diag_atexit.py`):

        pai vivo, PID 42336
        terminate() devolveu exit=1
        o atexit do filho CORREU?   False
        -> terminate() NAO executa atexit

    `subprocess.terminate()` no Windows chama `TerminateProcess`, que mata
    o processo a sério e a sério: sem cadeia de excepções, sem `finally`,
    sem `atexit`. E o Electron fecha a janela exactamente assim.

    Consequência se ficar assim: fechar o desktop deixa um Daphne vivo a
    segurar uma porta e a servir os dados da fazenda, invisível. A
    segunda abertura escolhe outra porta e o primeiro servidor fica para
    sempre. **Foi exactamente isto que o teste de encerramento apanhou.**

    A correcção é pedir ao **núcleo** que faça o trabalho, porque o núcleo
    é a única coisa que sobrevive a um processo que já não pode executar
    código:

    - **Windows** — Job Object com `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`.
      Quando a última handle do job fecha (isto é, quando este processo
      morre, de qualquer maneira), o SO mata os membros do job.
    - **Linux** — `PR_SET_PDEATHSIG(SIGTERM)` no filho.
    - **macOS** — não existe equivalente no núcleo. Fica a garantia
      explícita do Electron (`taskkill`/kill do grupo) e está escrito como
      limitação conhecida, não como sucesso.

    Em Windows o handle do job é guardado numa variável de módulo de
    propósito: se o objeto Python fosse colectado, o handle fechava e o
    job mataria o Daphne **imediatamente**, com o servidor ainda a
    arrancar.
    """
    # ---------------------------------------------------------------------------
    # O COMANDO DEPENDE DE ESTAR CONGELADO
    # ---------------------------------------------------------------------------
    # Descongelado: `python -m daphne ...`. `sys.executable` é o Python.
    #
    # **Congelado: `sys.executable` é o `ampliagro-runtime.exe`.** Passar
    # `-m daphne` ao próprio executável não serve de nada: o
    # `entrypoint.py` não entende desses argumentos, o filho não é um
    # servidor, e o bootstrap fica à espera de um `/healthz` que nunca vem.
    # Medido:
    #
    #     [bootstrap] A arrancar Daphne em http://127.0.0.1:63829 .
    #     [bootstrap] /healthz não ficou OK em 45.0s. Último:
    #       URLError(ConnectionRefusedError(10061, ...))
    #
    # Congelado, o mesmo executável é relançado com `--daphne`, que o
    # `entrypoint.py` reconhece e transforma numa chamada ao CLI do daphne.
    # A separação de processos mantém-se — e com ela o Job Object, que é o
    # que garante que o servidor morre quando o Electron fecha.
    if getattr(sys, "frozen", False):
        comando = [
            sys.executable,
            "--daphne",
            "--bind",
            "127.0.0.1",
            "--port",
            str(porta),
            "config.asgi:application",
        ]
    else:
        # `sys.executable -m daphne` em vez do executável `daphne`: o primeiro
        # usa o interpretador deste processo, o que garante a mesma versão
        # de Python e as mesmas dependências. O segundo pode não estar no
        # PATH de quem lançou a app (é o caso normal no macOS).
        comando = [
            sys.executable,
            "-m",
            "daphne",
            "--bind",
            "127.0.0.1",
            "--port",
            str(porta),
            "config.asgi:application",
        ]

    ultimo: Exception | None = None
    for tentativa in range(1, tentativas + 1):
        processo = subprocess.Popen(  # noqa: S603 — lista fixa, sem shell
            comando,
            cwd=str(CODE_ROOT),
            stdout=sys.stderr,
            stderr=sys.stderr,
            env=os.environ.copy(),
            # `preexec_fn` corre no filho entre o fork e o exec, e é o
            # único sítio onde `PR_SET_PDEATHSIG` pode ser pedido: depois
            # do exec já não há Python para o pedir. Só no Linux — no
            # Windows `preexec_fn` não é seguro com o CreateProcess e
            # seria silenciosamente ignorado.
            preexec_fn=_pr_set_pdeathsig if sys.platform.startswith("linux") else None,
        )
        proteger_filho(processo)
        # Espera breve: se a porta foi roubada, o processo morre de
        # imediato e não vale a pena esperar o health-check inteiro.
        time.sleep(1.0)
        if processo.poll() is None:
            return processo

        ultimo = RuntimeError(f"daphne saiu com código {processo.returncode}")
        log(f"daphne morreu logo a seguir (tentativa {tentativa}/{tentativas}).")
        time.sleep(1.0)

    raise RuntimeError(f"não foi possível arrancar o daphne: {ultimo}")


def preparar_build() -> int:
    """Passo de BUILD: `collectstatic`. Não corre em cada arranque.

    ---------------------------------------------------------------------------
    PORQUÊ ISTO É OBRIGATÓRIO E NÃO OPCIONAL
    ---------------------------------------------------------------------------
    MEDIDO na Fase 0. Com o `staticfiles/` desatualizado, a janela do
    Electron abria com a **navbar completa e o meio da página vazio** — a
    barra de "0 ALERTAS", os KPIs e o painel Amplia não apareciam.

    Quatro ficheiros davam 404:
        /static/css/auto-contraste.css
        /static/css/ia-rail.css
        /static/css/paginas/widgets-polish.css
        /static/js/auto-contraste.js
    Todos existem em `app/static/`. Nenhum existia em `staticfiles/`.

    A causa não é um bug do desktop: é que `STATICFILES_STORAGE` é
    `CompressedManifestStaticFilesStorage` (`base.py:253`), que serve a
    partir do que foi colectado e **não** de `app/static/`. A web não sofre
    disto porque o `Dockerfile:58` corre `collectstatic --clear` na build.
    O desktop, que não passa pelo Dockerfile, precisa do mesmo passo — ou
    equivalente a um pacote com a página meio morta.

    Repara no sintoma: um 404 destes **não dá erro**. A navbar é servida de
    ficheiros que existem, aparece; o conteúdo depende de ficheiros que
    faltam, desaparece. A janela abre, o título está certo, e o produtor
    vê uma página em branco. Sem uma prova que tire uma captura e leia o
    ecrã, isto passa por "funciona".

    Porque não no arranque: `collectstatic` reescreve `staticfiles/` e
    processa 321 ficheiros. Num pacote instalado, `staticfiles/` é
    read-only — e correr isso em cada abertura seria lento e falharia.
    """
    os.environ["SECRET_KEY"] = resolver_secret_key()

    import django

    django.setup()
    from django.core.management import call_command

    log("A colectar os ficheiros estáticos (collectstatic)…")
    call_command("collectstatic", interactive=False, verbosity=0)
    log("collectstatic concluído.")
    return 0


def correr_check() -> int:
    """`manage.py check` com os settings de desktop. Usado pelo CI."""
    os.environ["SECRET_KEY"] = os.environ.get("SECRET_KEY") or resolver_secret_key()
    import django

    django.setup()
    from django.core.management import call_command

    try:
        call_command("check")
    except SystemExit as e:
        return int(e.code or 0)
    return 0


def servir() -> int:
    """O caminho normal: migura, arranca, anuncia, espera."""
    os.environ["SECRET_KEY"] = resolver_secret_key()

    import django

    django.setup()

    preparar_banco()

    porta = escolher_porta()
    log(f"A arrancar Daphne em http://127.0.0.1:{porta} …")

    processo = arranque_daphne(porta)

    def ao_sair(*_args) -> None:
        log("A encerrar o Daphne…")
        if processo.poll() is None:
            processo.terminate()
            try:
                processo.wait(timeout=10)
            except subprocess.TimeoutExpired:
                log("O Daphne não saiu em 10s — a matar.")
                processo.kill()

    atexit.register(ao_sair)
    signal.signal(signal.SIGINT, lambda *a: (ao_sair(), sys.exit(0)))
    if hasattr(signal, "SIGTERM"):  # pragma: no branch — POSIX
        signal.signal(signal.SIGTERM, lambda *a: (ao_sair(), sys.exit(0)))

    try:
        saude = esperar_health(porta)
    except TimeoutError as e:
        log(str(e))
        ao_sair()
        return 1

    log("Pronto.")

    # ---- PROTOCOLO COM O ELECTRON ----
    # Uma linha, no stdout, que o pai lê. Se esta linha mudar de forma, o
    # `main.js` tem de mudar com ela — é o único contrato entre os dois.
    print(
        f"AMPLIAGRO_DESKTOP_READY port={porta} "
        f"pid={processo.pid} status={saude.get('status')}",
        flush=True,
    )

    # Mantém o processo vivo. Se o Daphne morrer sozinho, o Electron tem de
    # saber — daí este `wait()` em vez de um `while True`.
    codigo = processo.wait()
    log(f"O Daphne terminou com código {codigo}.")
    return codigo


def principal_ponto_de_entrada() -> int:
    """Arranque do runtime **congelado** (ver `entrypoint.py`).

    Igual a `main()`, menos o `argparse`. A diferença é deliberada: o
    Electron não passa argumentos, e um `argparse` que falha por isso
    impede o arranque com uma mensagem sobre flags — a pessoa que vê
    aquilo não tem nenhum contexto para perceber o que fez de errado.

    As sub-comandos que interessam ao build (`--check`, `--preparar`) são
    continuação de linha de comandos e continuam a existir; é só o caminho
    normal que deixa de passar por elas.
    """
    return servir()


def main() -> int:
    ap = argparse.ArgumentParser(description="Runtime embebido do Ampliagro")
    ap.add_argument(
        "--check",
        action="store_true",
        help="Corre `manage.py check` e sai (usado pelo CI).",
    )
    ap.add_argument(
        "--preparar",
        action="store_true",
        help="Passo de BUILD: collectstatic. Correr ao empacotar, não a cada arranque.",
    )
    args = ap.parse_args()
    if args.check:
        return correr_check()
    if args.preparar:
        return preparar_build()
    return servir()


if __name__ == "__main__":
    raise SystemExit(main())
