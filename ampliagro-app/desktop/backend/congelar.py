"""Congela o runtime Python num executavel, por SO.

Corre-se NA MAQUINA DE BUILD, nunca no computador do produtor. O
`requirements-build.txt` e o que entra aqui; o `requirements-desktop.txt` e
o que entra no produto.

Uso:
    python backend/congelar.py [--onefile] [--limpar]

Porquê `onedir` e nao `onefile` (que e o default aqui):
- **arranque**. `onefile` extrai tudo para uma pasta temporaria em cada
  abertura. Num produto que abre 5 vezes por dia, com ~94 MB, isso sao
  segundos.
- **assinatura**. `onefile` assina um executavel, mas os contents que ele
  extrai nao ficam assinados. `onedir` assina a pasta toda.
- **diagnostico**. Se o runtime falhar, a pessoa tem a pasta e le o log;
  com `onefile` o log desaparece quando a temporaria e limpa.

O custo e que a entrega sao varios ficheiros - o que o `electron-builder`
embala sem problema.

---------------------------------------------------------------------------
A CORRECCAO QUE CUSTOU UMA CONSTRUCAO INTEIRA
---------------------------------------------------------------------------
A primeira versao deste script passava `app/` e `config/` por
`--add-data`. Construiu. Deu 93,8 MB. E **nao arrancava**:

    File "...\_internal\config\__init__.py", line 1, in <module>
      from .celery import app as celery_app
    ModuleNotFoundError: No module named 'celery'

O ficheiro `config/celery.py` estava NA distribution. O seu
`from celery import Celery` estava dentro dele. E nao havia celery.

E' a diferenca entre os dois modos do PyInstaller:

- `--add-data` COPIA o `.py` como se fosse uma imagem. O PyInstaller nao o
  le, nao o analisa, nao segue o import.
- `collect_submodules` ANALISA o pacote, le os imports, e arrasta o que
  eles referenciam.

E' o modo de falha mais irritante que existe num build: o ficheiro esta la,
o caminho esta certo, e o que falta e uma coisa que ninguem consegue ver.
Da vem este script escrever um SPEC e nao uma linha de comando — porque
`collect_submodules` so existe dentro de um spec.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

AQUI = Path(__file__).resolve().parent


def raiz_do_codigo() -> Path:
    for candidato in (AQUI, *AQUI.parents):
        if (candidato / "manage.py").is_file() and (
            candidato / "config" / "settings" / "desktop.py"
        ).is_file():
            return candidato
    raise SystemExit("[congelar] nao encontrei a raiz do repositorio")


RAIZ = raiz_do_codigo()

# ---------------------------------------------------------------------------
# DADOS: tudo o que NAO e Python
# ---------------------------------------------------------------------------
DATAS: list[tuple[Path, str]] = [
    (RAIZ / "app" / "templates", "app/templates"),
    (RAIZ / "app" / "static", "app/static"),
    (RAIZ / "app" / "migrations", "app/migrations"),
    (RAIZ / "app" / "management", "app/management"),
]

# ---------------------------------------------------------------------------
# O OUTPUT DO `collectstatic` — o que o Django serve de facto
# ---------------------------------------------------------------------------
# `STATIC_ROOT` é `BASE_DIR/staticfiles` (`base.py:251`). Congelado,
# `BASE_DIR` é `sys._MEIPASS`, logo o Django procura os ficheiros em
# `_internal/staticfiles/`. Se essa pasta não estiver no bundle, nada é
# servido — e o sintoma é uma aplicação que abre sem CSS e sem JS, com um
# aviso discreto no stderr:
#
#     UserWarning: No directory at: .../_internal/staticfiles/
#
# `app/static` (acima) é a FONTE. `staticfiles/` é o produto do
# `collectstatic`, com os nomes hasheados e comprimidos que o
# `CompressedManifestStaticFilesStorage` referencia nos templates. Um não
# substitui o outro.
#
# `build:all` corre `collectstatic` antes do congelamento. Congelar sem
# esse passo produz uma app que arranca e não funciona.
_staticfiles = RAIZ / "staticfiles"
if _staticfiles.is_dir():
    DATAS.append((_staticfiles, "staticfiles"))
else:  # pragma: no cover — só num checkout sem build prévio
    print(
        "[congelar] AVISO: staticfiles/ nao encontrado — corra "
        "`npm run build:assets` antes de congelar. A app abriria sem CSS."
    )


def _dir_pacote(nome: str) -> Path | None:
    """Directório de um pacote instalado, seja qual for o instalador.

    `sys.prefix / "Lib" / "site-packages"` é o caminho do Python *oficial*
    do Windows. No Python da Microsoft Store os pacotes vivem em
    `%LOCALAPPDATA%\\Packages\\...\\LocalCache\\local-packages\\Python311\\site-packages`
    e o `sys.prefix` aponta para `C:\\Program Files\\WindowsApps\\...` — onde
    não há nada. O resultado é um DATAS a apontar para uma pasta inexistente,
    o PyInstaller a não copiar nada, e um `FileNotFoundError` em runtime que
    só aparece quando o executável congelado arranca.

    `find_spec` pergunta ao próprio Python onde o pacote está. Não adivinha.
    """
    try:
        import importlib.util

        spec = importlib.util.find_spec(nome)
    except (ImportError, ValueError):
        return None
    if spec is None:
        return None
    locais = list(spec.submodule_search_locations or [])
    if not locais:
        return None
    return Path(locais[0]).resolve()


# As traduções do Django vivem no pacote, não no `sys.prefix`. Ver
# `_dir_pacote` acima para o porquê de não se usar `sys.prefix/Lib/site-packages`.
_django = _dir_pacote("django")
if _django and (_django / "conf" / "locale").is_dir():
    DATAS.append((_django / "conf" / "locale", "django/conf/locale"))

# ---------------------------------------------------------------------------
# DADOS DE PACOTES DE TERCEIROS
# ---------------------------------------------------------------------------
# Um pacote pode precisar de ficheiros que não são `.py` e que não estão em
# nenhum `MANIFEST.in`. O `autobahn` é o caso, e é um caso que só aparece
# congelado:
#
#     File "autobahn\websocket\utf8validator.py", line 447, in <module>
#     File "autobahn\nvx\_utf8validator.py", line 81, in <module>
#     FileNotFoundError: [Errno 2] No such file or directory:
#       ...\_internal\autobahn\nvx\_utf8validator.c
#
# O validador de UTF-8 do autobahn tem três implementações e escolhe por
# ordem: `wsaccel` (extensão C), `nvx` (Python com uma fonte C que
# **compila em runtime**), e uma terceira em Python puro. Com o
# PyInstaller, o `nvx` ganha e tenta ler o `.c` — que não foi copiado.
#
# A solução é dar-lhe o ficheiro. A alternativa (excluir o `nvx` e ficar com
# o validador puro) é mais frágil: muda o caminho de execução do WebSocket
# por causa de um detalhe de empacotamento.
_autobahn = _dir_pacote("autobahn")
NVX = _autobahn / "nvx" if _autobahn else None
if NVX and NVX.is_dir():
    DATAS.append((NVX, "autobahn/nvx"))
else:  # pragma: no cover — o caminho muda entre SOs
    print("[congelar] AVISO: autobahn/nvx não encontrado — o WebSocket pode falhar")

#: Pacotes do projecto que o spec tem de ANALISAR.
PACOTES_PROJECTO = ["app", "config"]

# ---------------------------------------------------------------------------
# IMPORTS INVISIVEIS A QUALQUER ANALISE ESTATICA
# ---------------------------------------------------------------------------
# Os que interessam sao os que entram por NOME DE STRING: o Django le
# `DJANGO_SETTINGS_MODULE` do ambiente e faz `import_module`, e isso nao
# aparece em nenhum `import`. Cada um destes ja foi um
# `ModuleNotFoundError` numa versao anterior deste ficheiro.

HIDDEN_IMPORTS = [
    "bootstrap",
    "entrypoint",
    # -----------------------------------------------------------------------
    # TUDO O QUE ESTÁ EM `INSTALLED_APPS`
    # -----------------------------------------------------------------------
    # O Django resolve cada entrada de `INSTALLED_APPS` com um
    # `import_module` do nome que está no setting. Nenhum desses nomes
    # aparece num `import` que uma análise estática possa ler.
    #
    # A lista de `INSTALLED_APPS` está em `config/settings/base.py:69-94`.
    # Este bloco é uma transcrição dela. Se alguém acrescentar uma app lá e
    # não a acrescentar aqui, o executável congelado morre com
    # `ModuleNotFoundError` — em desenvolvimento nunca, porque o Python
    # tem tudo instalado. É o género de coisa que só aparece no build.
    #
    # Este foi o que custou a primeira volta: `django_filters` faltava e o
    # `django.setup()` morria em `apps/registry.py:91`.
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",
    "django.contrib.postgres",
    "rest_framework",
    "django_filters",
    "drf_spectacular",
    "corsheaders",
    "channels",
    # `django_celery_results` e `django_celery_beat` nao entram: em
    # 14/10/2026 `config/settings/desktop.py` deixou de os ter em
    # `INSTALLED_APPS` (o desktop nao guarda resultado de tarefa) e o
    # `requirements-desktop.txt` nunca os instalou. Pedi-los aqui dava
    # "Hidden import 'django_celery_results' not found" e o build morria nos
    # tres sistemas operacionais. A lista tem de descrever o desktop, nao o
    # servidor.
    "auditlog",
    "axes",
    "health_check",
    "health_check.db",
    "django_vite",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
    # -----------------------------------------------------------------------
    # MIDDLEWARE E SERVIDORES, todos resolvidos por string
    # -----------------------------------------------------------------------
    "daphne",
    "daphne.apps",
    "channels.layers",
    "channels.auth",
    "channels.routing",
    "csp",
    "csp.middleware",
    "whitenoise",
    "whitenoise.middleware",
    "whitenoise.storage",
    "axes.backends",
    "axes.middleware",
    "auditlog.middleware",
    "drf_spectacular.views",
    # -----------------------------------------------------------------------
    # MÓDULOS DO PROJECTO CHAMADOS POR STRING NOS SETTINGS
    # `base.py:143-189` (MIDDLEWARE) e `base.py:186-189` (context_processors)
    # -----------------------------------------------------------------------
    "app.bot",
    "app.context_processors",
    "app.middleware",
    "app.presets",
    "app.seguranca",
    "app.validators",
    "app.security.hashers",
    "app.consumers",
    "app.hierarquia",
    # O `DJANGO_SETTINGS_MODULE` é uma string no ambiente.
    "config",
    "config.settings.desktop",
    "config.asgi",
    "config.celery",
    "config.urls",
    "config.wsgi",
    # Providers do allauth: o `INSTALLED_APPS` dele carrega por string.
    "allauth.socialaccount.providers.oauth2",
    "allauth.socialaccount.providers.openid_connect",
    # -----------------------------------------------------------------------
    # MÓDULOS QUE `include()` APONTA, um a um
    # -----------------------------------------------------------------------
    # `app/urls.py:35` faz `path("health/", include("health_check.urls"))`.
    # Isto é um `import_module` com um nome montado em runtime — e o
    # `collect_submodules("health_check")`, que devia apanhar, **não
    # apanhou**: o executável congelado respondia 500 com
    #
    #     ModuleNotFoundError: No module named 'health_check.urls'
    #
    # Não se investigou porque é que a colecção o deixou de fora, e essa é
    # uma dívida assumida: a lista nominal é a rede de segurança até alguém
    # perceber a causa. Registado aqui para não voltar a ser adivinhado.
    "health_check.urls",
    "health_check.db",
    "health_check.cache",
    "health_check.storage",
    "health_check.management",
]

#: Pacotes que NAO entram. Cada um foi removido porque nenhum sitio do
#: repositorio o importa (medido), ou por ter sido provado opcional
#: (numpy - ver a prova do handshake WebSocket).
EXCLUDES = [
    "numpy",
    "pandas",
    "scipy",
    "geopandas",
    "rasterio",
    "fiona",
    "pyogrio",
    "pyproj",
    "shapely",
    "cv2",
    "opencv_python",
    "pytest",
    "_pytest",
    "playwright",
    "IPython",
    "jupyter",
    "notebook",
    "matplotlib",
    "tkinter",
    "pydoc_data",
    "lib2to3",
]


#: Pacotes cujos submódulos são importados por NOME em runtime, e que por
#: isso o PyInstaller não consegue ver.
#:
#: `celery` é o caso canónico: `celery/app/base.py:289` faz
#: `symbol_by_name("celery.fixups.django")`, que é um `import_module` com o
#: nome montado em runtime. Nenhuma análise estática o apanha, e o
#: executável morria com:
#:
#:     File "celery\app\base.py", line 289, in <listcomp>
#:     File "kombu\utils\imports.py", line 59, in symbol_by_name
#:     ModuleNotFoundError: No module named 'celery.fixups'
#:
#: `app` e `config` entram pelo mesmo motivo, e por um motivo mais geral:
#: um pacote Django tem módulos que SÓ são carregados em runtime — os
#: models pelo registo de apps, os serializers pelo DRF, as views pelo
#: `urls.py`. Enumerá-los um a um é uma lista que fica incompleta no dia
#: seguinte em que alguém acrescenta um ficheiro, e cada ausência só se
#: manifesta no executável congelado — nunca em desenvolvimento, porque o
#: Python tem o pacote inteiro à vista.
#:
#: Foi o que aconteceu duas vezes seguidas: `app.apps` foi a primeira
#: ausência, e só apareceu no build. A lição é a lista de módulos abaixo
#: não deve ser a rede de segurança; `collect_submodules` é. A lista fica
#: porque é mais rápida de construir e porque aponta para o que costuma
#: falhar.
#:
#: `collect_submodules` recebe UM nome de pacote de cada vez — passar a
#: lista toda dá `TypeError: package must be a str`.
#: Pacotes cujos submódulos são importados por NOME em runtime.
#:
#: Este é o padrão, não a excepção, e é por isso que a lista é larga.
#:
#: O Django resolve três coisas por nome de string — as entradas de
#: `INSTALLED_APPS`, as de `MIDDLEWARE` e as de `context_processors` — e
#: faz `import_module` de cada uma. Nenhum desses nomes aparece num
#: `import` que uma análise estática possa ler. Todos eles funcionam em
#: desenvolvimento e nenhum funciona no executável congelado, porque o
#: pacote não está lá.
#:
#: A lista de `MIDDLEWARE` está em `config/settings/base.py:142-170` e a de
#: `context_processors` em `base.py:182-190`. Foi daí que saíram as entradas
#: desta lista, depois de `allauth.account.middleware` (linha 160) ser a
#: quarta ausência a aparecer só no build.
#:
#: A alternativa — enumerar um a um e acrescentar a cada erro — funciona,
#: e foi o que se fez três vezes até perceber que a resposta é esta.
#: `collect_submodules` recebe UM nome de pacote por chamada: passar a lista
#: toda dá `TypeError: package must be a str`.
SUBMODULOS = [
    # Projecto.
    "app",
    "config",
    # Celery: `celery/app/base.py:289` faz `symbol_by_name("celery.fixups.django")`.
    "celery",
    "kombu",
    "billiard",
    # Apps Django de terceiros — MIDDLEWARE, INSTALLED_APPS e providers.
    "allauth",
    "axes",
    "auditlog",
    "health_check",
    "rest_framework",
    "drf_spectacular",
    "django_filters",
    "corsheaders",
    "csp",
    "whitenoise",
    "django_vite",
    "channels",
    "daphne",
    # `django_celery_results` e `django_celery_beat` fora, pela razao escrita
    # na lista de cima: nao estao em `INSTALLED_APPS` do desktop nem no
    # `requirements-desktop.txt`.
    # `PIL` NÃO entra: o Pillow é necessário (três `ImageField` em
    # `app/models/`) e não é um pacote Django com imports dinâmicos.
]


def escrever_spec(destino: Path, onedir: bool) -> None:
    """Escreve o `.spec` que faz o trabalho a serio.

    O spec e Python, e e por isso que e' a unica forma de usar
    `collect_submodules`. Os valores sao escritos com `repr()` para o spec
    ficar com os strings correctos em qualquer SO.
    """
    sep = ";" if os.name == "nt" else ":"
    dados = [(str(o), d) for o, d in DATAS if o.exists()]
    em_falta = [str(o) for o, _ in DATAS if not o.exists()]

    linhas = [
        "# -*- mode: python ; coding: utf-8 -*-",
        "# Gerado por backend/congelar.py. NAO EDITAR A MAO.",
        "",
        "from PyInstaller.utils.hooks import collect_submodules",
        "",
        f"RAIZ = {str(RAIZ)!r}",
        f"EXECUTAVEL = {str(AQUI / 'entrypoint.py')!r}",
        "",
        "# Pacotes com submódulos importados por nome em runtime.",
        "# `collect_submodules` recebe UM nome de pacote de cada vez —",
        "# passar a lista toda dá `TypeError: package must be a str`.",
        "_SUBMODULOS = []",
        f"for _p in {SUBMODULOS!r}:",
        "    _SUBMODULOS += collect_submodules(_p)",
        "",
        "a = Analysis(",
        f"    [EXECUTAVEL],",
        f"    pathex=[RAIZ, {str(AQUI)!r}],",
        "    binaries=[],",
        "    datas=[",
    ]
    for origem, destino_rel in dados:
        linhas.append(f"        ({origem!r}, {destino_rel!r}),")
    linhas += [
        "    ],",
        "    hiddenimports=[",
    ]
    for mod in HIDDEN_IMPORTS:
        linhas.append(f"        {mod!r},")
    linhas.append("        *_SUBMODULOS,")
    linhas += [
        "    ],",
        "    hookspath=[],",
        "    hooksconfig={},",
        "    runtime_hooks=[],",
        "    excludes=[",
    ]
    for mod in EXCLUDES:
        linhas.append(f"        {mod!r},")
    linhas += [
        "    ],",
        "    noarchive=False,",
        "    optimize=0,",
        ")",
        "",
        "pyz = PYZ(a.pure)",
        "",
    ]
    if onedir:
        linhas += [
            "exe = EXE(",
            "    pyz,",
            "    a.scripts,",
            "    [],",
            "    exclude_binaries=True,",
            "    name='ampliagro-runtime',",
            "    debug=False,",
            "    bootloader_ignore_signals=False,",
            "    strip=False,",
            "    upx=False,",
            "    console=True,",
            "    disable_windowed_traceback=False,",
            "    argv_emulation=False,",
            "    target_arch=None,",
            "    codesign_identity=None,",
            "    entitlements_file=None,",
            ")",
            "",
            "coll = COLLECT(",
            "    exe,",
            "    a.binaries,",
            "    a.datas,",
            "    strip=False,",
            "    upx=False,",
            "    upx_exclude=[],",
            "    name='ampliagro-runtime',",
            ")",
        ]
    else:
        linhas += [
            "exe = EXE(",
            "    pyz,",
            "    a.scripts,",
            "    a.binaries,",
            "    a.datas,",
            "    [],",
            "    name='ampliagro-runtime',",
            "    debug=False,",
            "    bootloader_ignore_signals=False,",
            "    strip=False,",
            "    upx=False,",
            "    console=True,",
            ")",
        ]

    destino.write_text("\n".join(linhas) + "\n", encoding="utf-8")

    if em_falta:
        print(
            f"[congelar] AVISO: {len(em_falta)} pasta(s) nao existem e foram omitidas:"
        )
        for p in em_falta:
            print(f"           {p}")


def tamanho_de(pasta: Path) -> tuple[int, int]:
    total = 0
    n = 0
    for raiz, _, ficheiros in os.walk(pasta):
        for f in ficheiros:
            try:
                total += (Path(raiz) / f).stat().st_size
                n += 1
            except OSError:
                pass
    return total, n


def principal() -> int:
    ap = argparse.ArgumentParser(description="Congela o runtime Python do desktop")
    ap.add_argument(
        "--onefile",
        dest="onedir",
        action="store_false",
        help="Produces one single .exe (arranque mais lento; ver o docstring).",
    )
    ap.add_argument("--limpar", action="store_true", help="Apaga build/ e dist/ antes")
    args = ap.parse_args()

    build = RAIZ / "ampliagro-app" / "desktop" / "build-runtime"
    dist = RAIZ / "ampliagro-app" / "desktop" / "dist-runtime"

    if args.limpar:
        for pasta in (build, dist):
            if pasta.exists():
                print(f"[congelar] a apagar {pasta}")
                shutil.rmtree(pasta)

    build.mkdir(parents=True, exist_ok=True)
    spec = build / "ampliagro-runtime.spec"
    escrever_spec(spec, args.onedir)

    comando = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--distpath",
        str(dist),
        "--workpath",
        str(build),
        str(spec),
    ]

    modo = "onedir" if args.onedir else "onefile"
    print(f"[congelar] modo: {modo}")
    print(f"[congelar] spec: {spec}")
    print(
        f"[congelar] dados: {len(DATAS)} pastas, hiddenimports: {len(HIDDEN_IMPORTS)}, "
        f"excludes: {len(EXCLUDES)}"
    )

    inicio = time.monotonic()
    resultado = subprocess.run(comando, cwd=str(RAIZ))
    if resultado.returncode != 0:
        print(f"[congelar] FALHOU com codigo {resultado.returncode}")
        return resultado.returncode

    decorrido = time.monotonic() - inicio
    alvo = dist / "ampliagro-runtime"
    if alvo.exists():
        bytes_, ficheiros = tamanho_de(alvo)
        print()
        print(f"[congelar] pronto em {decorrido / 60:.1f} min")
        print(f"[congelar] {alvo}")
        print(
            f"[congelar] TAMANHO: {bytes_ / 1024 / 1024:.1f} MB em {ficheiros} ficheiros"
        )
    else:
        print(f"[congelar] nao encontrei o resultado em {alvo}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(principal())
