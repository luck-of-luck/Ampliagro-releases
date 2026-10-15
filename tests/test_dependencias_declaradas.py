"""
Guarda: **toda a dependencia que o Django carrega no boot esta declarada.**

MEDIDO 2026-10-05, a partir de um caso real: `csp.middleware.CSPMiddleware`
esta no `MIDDLEWARE` (`config/settings/base.py:120`), `django-csp` 4.0 esta
instalado na maquina de desenvolvimento, e **`django-csp` nao estava em nenhum
manifesto de dependencias** — nem `requirements.txt`, nem `requirements-mcp.txt`,
nem `setup.py`.

O `MIDDLEWARE` do Django e' resolvido **no arranque**. `csp.middleware`
inexistente e' `ImportError`, e o `ImportError` no `MIDDLEWARE` impede o boot.
Ou seja: **o projecto arrancava na maquina de quem o develope porque alguem
instalou o pacote a mao, e nao arrancava noutra maquina nenhuma.**

E o teste que existe — `test_csp.py`, 13 testes, todos verdes — **nao apanha
isto**: passa com o pacote presente, que e' precisamente a condicao em que o
problema nao aparece. Um teste que so corre no ambiente que ja esta correcto
nao e' um guarda; e' uma confirmacao.

Este teste fecha essa porta.

Porque o MIDDLEWARE e' o sitio certo
------------------------------------
Porque e' o unico lugar do Django onde um modulo ausente **impede o boot**, e
porque a lista e' curta, estatica e versionada.

Sobre falsos positivos
---------------------
Este teste vai ser avaliado por quem o mantiver, e um guarda que apanha coisas
que nao sao bugs treina a ignorar o sinal — foi o que aconteceu com
`app/tests_wizard_pergunta.py`, que reprovava uma guarda *mais forte* do que a
exigida (ver a nota no `test_plano_execucao.py`).

Por isso, em vez de listar excepcoes que se podiam multiplicar, o teste
**desiste em silencio** sempre que nao consegue provar o que procura:

* modulo do stdlib -> ignorado
* modulo do proprio projecto -> ignorado
* modulo que nenhum distribution declara -> ignorado (nao e' bug de declaracao)

Prefere **deixar passar** a acusar em falso. Um guarda que falha por razoes
erradas treina a leitura a vermelho, e um guarda que nunca falha nao exerce
funcao. Entre os dois, este escolhe o primeiro — e diz no docstring que escolheu.
"""

from __future__ import annotations

import ast
import re
from importlib.metadata import distributions
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
REQUIREMENTS = BASE_DIR / "requirements.txt"

# Nome de distribuicao -> nome normalizado, e modulo de topo -> distribuicao.
# Construido a partir do que esta REALMENTE instalado, para nao hardcodar um
# mapa que envelhece com as versoes.
_MODULE_TO_DIST: dict[str, str] = {}


def _normalizar(nome: str) -> str:
    """`Django` -> `django`; `django_csp` -> `django-csp`."""
    return re.sub(r"[-_.]+", "-", nome).lower()


def _indice_modulos() -> dict[str, str]:
    """Modulo de topo -> distribuicao, derivado dos **ficheiros instalados**.

    A primeira versao deste indice usava `top_level.txt` e
    `top_level_modules`. **Isso foi um ponto cego, e apanhou o caso que
    motivou o teste:** `django-csp` declara os seus modulos de topo como
    `django_csp`, mas o modulo que se importa e' `csp`. Confiar no rotulo
    levava o guarda a nao avaliar a unica linha que estava errada — que e' o
    oposto do que um guarda deve fazer.

    Derivar dos **ficheiros** (`dist.files`, o RECORD do pip) nao e' um detalhe:
    e' a unica fonte que descreve o que esta *mesmo* em disco. `csp/` aparece
    la, portanto `csp` mapeia para `django-csp`, e a linha e' avaliada.
    """
    if _MODULE_TO_DIST:
        return _MODULE_TO_DIST

    for dist in distributions():
        nome = (dist.metadata["Name"] or "").strip()
        if not nome:
            continue
        topos: set[str] = set()
        try:
            ficheiros = dist.files or []
        except Exception:  # pragma: no cover - metadados varies
            ficheiros = []

        for fi in ficheiros:
            partes = str(fi).replace("\\", "/").split("/")
            if not partes:
                continue
            primeiro = partes[0]
            # `<dist>-<ver>.dist-info/...` e `_vendor/...` nao sao modulos
            if primeiro.endswith((".dist-info", ".egg-info", ".data")):
                continue
            if primeiro.startswith("_") and primeiro != "__init__.py":
                # `_vendor`, `_distutils_hack`... nao sao modulos publicos
                if primeiro.startswith("_vendor"):
                    continue
            if "." in primeiro and not primeiro.endswith(".py"):
                continue  # cabeceira solta na raiz
            if primeiro.endswith(".py"):
                primeiro = primeiro[:-3]
            if primeiro:
                topos.add(primeiro)

        # fallback para ambientes sem RECORD legivel
        if not topos:
            for chave in ("top_level.txt", "top_level_modules"):
                try:
                    topos |= set(dist.read_text(chave) or "")
                except Exception:  # pragma: no cover
                    pass
            topos.add(nome.replace("-", "_"))

        for topo in topos:
            topo = topo.strip()
            if topo and topo != ".":
                _MODULE_TO_DIST.setdefault(topo, _normalizar(nome))
    return _MODULE_TO_DIST


def _distribuicoes_declaradas() -> set[str]:
    """Nomes de distribuicao citados no `requirements.txt`."""
    if not REQUIREMENTS.exists():
        return set()
    declaradas: set[str] = set()
    for linha in REQUIREMENTS.read_text(encoding="utf-8").splitlines():
        linha = linha.split("#", 1)[0].strip()
        if not linha:
            continue
        nome = re.split(r"[\[<>=!~; ]", linha, maxsplit=1)[0].strip()
        if nome:
            declaradas.add(_normalizar(nome))
    return declaradas


def _caminhos_do_middleware() -> list[str]:
    """Le o `MIDDLEWARE` dos settings por `ast`, sem booting o Django.

    Importar `django.conf` arranca o Django — que e' exactamente o que este
    teste existe para nao fazer. Um teste de dependencias nao pode precisar do
    que verifica.
    """
    achados: list[str] = []
    settings_dir = BASE_DIR / "config" / "settings"
    for nome in ("base.py", "dev.py", "test.py", "prod.py"):
        ficheiro = settings_dir / nome
        if not ficheiro.exists():
            continue
        try:
            arvore = ast.parse(ficheiro.read_text(encoding="utf-8"))
        except SyntaxError:  # pragma: no cover
            continue

        for no in ast.walk(arvore):
            if not isinstance(no, ast.Assign):
                continue
            if not any(
                isinstance(a, ast.Name) and a.id == "MIDDLEWARE" for a in no.targets
            ):
                continue
            for sub in ast.walk(no.value):
                if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
                    if "." in sub.value:
                        achados.append(sub.value)
    return achados


def _modulo_de_topo(dotted: str) -> str | None:
    """`csp.middleware.CSPMiddleware` -> `csp`."""
    for i in range(len(dotted), 0, -1):
        if dotted[i - 1] != ".":
            continue
        prefixo = dotted[: i - 1]
        indice = _indice_modulos()
        if prefixo in indice:
            return prefixo
        # `a.b.c.Classe` -> tenta `a.b`, depois `a`
    return None


def test_o_middleware_carrega_somente_modulos_declarados():
    """NENHUM modulo do `MIDDLEWARE` pode vir de uma dependencia nao declarada.

    Esta e' a guarda que faltava. Sem ela, a reproducao do problema e' uma
    maquina limpa com `pip install -r requirements.txt` — e o `ImportError` so
    aparece no arranque, em producao, no dia do deploy.
    """
    declaradas = _distribuicoes_declaradas()
    assert declaradas, (
        "requirements.txt nao existe ou esta vazio — este teste nao consegue "
        "avaliar nada e vai passar a verde por cegueira."
    )

    faltando: list[str] = []
    nao_avaliados: list[str] = []

    for dotted in _caminhos_do_middleware():
        topo = _modulo_de_topo(dotted)
        if topo is None:
            nao_avaliados.append(dotted)
            continue
        dist = _indice_modulos()[topo]
        if dist not in declaradas:
            faltando.append(f"{dotted}  ->  {dist}")

    assert not faltando, (
        "Dependencias usadas no MIDDLEWARE e NAO declaradas no "
        "requirements.txt.\n"
        "O MIDDLEWARE resolve-se no BOOT: um modulo ausente e' ImportError e o "
        "Django nao arranca. Estas linhas nao install numa maquina limpa:\n"
        + "\n".join(f"  * {f}" for f in sorted(set(faltando)))
        + f"\n\n(nao avaliados: {len(nao_avaliados)} — modulos do proprio "
        "projecto ou de stdlib)"
    )


def test_a_declared_da_csp_existe_e_a_politica_e_lida():
    """A dependencia que causou isto tem de estar nomeada, nao so instalada.

    Separado do teste acima para que a falha aponte o culpado. Este e' o
    primeiro caso real: `django-csp` estava instalado e nao declarado.
    """
    declaradas = _distribuicoes_declaradas()
    # o nome pode ser declarado como `django-csp`
    assert "django-csp" in declaradas, (
        "`django-csp` nao esta em requirements.txt, mas `csp.middleware."
        "CSPMiddleware` esta no MIDDLEWARE (config/settings/base.py:120). "
        "Numa maquina limpa o Django nao arranca. ja aconteceu."
    )
