"""Ponto de entrada do runtime congelado (PyInstaller).

Porquê um ficheiro só para isto, e não o `bootstrap.py` directamente:

`bootstrap.py` descobre a raiz do código com `Path(__file__).resolve()` e
sobe a árvore à procura de `manage.py`. Debaixo do PyInstaller isso não
serve: o `__file__` aponta para dentro de `_MEIPASS` (uma pasta temporária
quando é `--onefile`), onde não há `manage.py`. O bootstrap sairia com
"Não encontrei a raiz do Ampliagro" — num produto que foi feito para
funcionar.

Aqui a raiz é dada pelo próprio empacotador: congelado, é `sys._MEIPASS`;
em desenvolvimento, é a árvore normal. O resto do arranque é o
`bootstrap.py` de sempre, sem uma linha duplicada.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def _raiz_do_codigo() -> Path:
    congelado = getattr(sys, "frozen", False)

    if congelado:
        # PyInstaller põe os dados do pacote em `sys._MEIPASS`. Em
        # `--onefile` é uma pasta temporária; em `--onedir` é o próprio
        # directório de distribuição. Em ambos os casos é esta a raiz com
        # `app/` e `config/`.
        #
        # `sys._MEIPASS` não existe num Python normal — é injectado pelo
        # PyInstaller no arranque. O type checker não o conhece, e está
        # certo: o atributo só existe quando `sys.frozen` é verdadeiro.
        return Path(sys._MEIPASS).resolve()  # type: ignore[attr-defined]

    # Em desenvolvimento, NÃO se conta níveis com `.parent.parent` — é um
    # número que mente assim que a pasta ganha um nível, e mente em
    # silêncio (dá o `ampliagro-app/` em vez da raiz). Pergunta-se ao
    # `bootstrap`, que tem a busca correcta.
    from bootstrap import _procurar_raiz

    return _procurar_raiz()


def _modo_daphne() -> bool:
    """O executável foi lançado para servir, e não para arrancar o bootstrap?

    ---------------------------------------------------------------------------
    O QUE ESTA MODO RESOLVE
    ---------------------------------------------------------------------------
    O `bootstrap.py` arranca o Daphne como processo **filho**, para poder
    matá-lo a sério quando o Electron fecha (Job Object no Windows,
    `PR_SET_PDEATHSIG` no Linux — ver ADR-001).

    Descongelado, esse filho é `sys.executable -m daphne ...`, e
    `sys.executable` é o Python. Corre bem.

    **Congelado, `sys.executable` é o próprio `ampliagro-runtime.exe`.**
    O comando passa a ser:

        ampliagro-runtime.exe -m daphne --bind 127.0.0.1 --port 63829

    O que é o mesmo executável a ser lançado de novo, com argumentos que o
    `entrypoint.py` não entende. O filho não é um servidor: sai, e o
    bootstrap fica à espera de um `/healthz` que nunca responde. Medido:

        [bootstrap] A arrancar Daphne em http://127.0.0.1:63829 .
        [bootstrap] /healthz não ficou OK em 45.0s. Último:
          URLError(ConnectionRefusedError(10061, ...))

    A solução é não fingir que o congelado é um interpretador. O mesmo
    executável recebe uma flag que lhe diz "serve tu", e o `daphne` corre
    no processo filho — mantendo a separação de processos e o Job Object.
    """
    return "--daphne" in sys.argv


def _servir_com_daphne() -> int:
    """Corre o Daphne com os argumentos que ficaram em `sys.argv`.

    Usa `CommandLineInterface.entrypoint()`, que é o que o
    `daphne/__main__.py` chama quando se faz `python -m daphne`. É o mesmo
    caminho, sem ter de reimplementar o parsing de argumentos — que tem
    validações próprias (`_check_proxy_headers_passed` e companhia) e que
    reescrever seria uma segunda implementação a divergir.
    """
    # `--daphne` é nossa. O daphne parseia `sys.argv[1:]` e não conhece a
    # flag, por isso tem de sair de lá antes.
    sys.argv = [a for a in sys.argv if a != "--daphne"]

    from daphne.cli import CommandLineInterface

    CommandLineInterface.entrypoint()
    return 0


def principal() -> int:
    # Este teste vem ANTES de tudo o resto: nem sequer vale a pena
    # preparar o bootstrap num processo que vai só servir.
    if _modo_daphne():
        return _servir_com_daphne()

    # O `sys.path` primeiro, e só depois a raiz do código.
    #
    # `_raiz_do_codigo()` faz `from bootstrap import _procurar_raiz` no
    # caminho não-congelado. Se a pasta do `bootstrap` ainda não estiver
    # no `sys.path`, esse import falha — e a falha é um `ModuleNotFoundError`
    # numa linha que não tem nada a ver com o que se perguntou.
    pasta_backend = str(Path(__file__).resolve().parent)
    if pasta_backend not in sys.path:
        sys.path.insert(0, pasta_backend)

    congelado = getattr(sys, "frozen", False)
    raiz = _raiz_do_codigo()

    # ---------------------------------------------------------------------------
    # A VERIFICAÇÃO É DIFERENTE CONGELADO E NÃO CONGELADO — e tem de ser
    # ---------------------------------------------------------------------------
    # Descongelado, a raiz tem de conter `config/settings/desktop.py` como
    # FICHEIRO, e a busca por `manage.py` acima é o teste.
    #
    # Congelado, esse ficheiro **não existe em lado nenhum do disco**: o
    # PyInstaller mete os módulos Python num arquivo comprimido (o PYZ) e
    # não os solta. `sys._MEIPASS/config/settings/desktop.py` não está lá.
    #
    # A primeira versão deste ficheiro fazia `is_file()` nos dois casos e o
    # executável congelado saía com:
    #
    #     [entrypoint] Raiz de código inválida: ...\_internal
    #
    # Numa pasta que tem 86,7 MB de runtime dentro, feita pelo próprio
    # empacotador, no caminho certo. A verificação é que estava errada, não
    # a raiz.
    #
    # Por isso: congelado, a prova é o **import**. É o que interessa — se o
    # módulo importa, o Django tem o que precisa.
    if congelado:
        os.environ["AMPLIAGRO_CODE_ROOT"] = str(raiz)
        import importlib.util

        if importlib.util.find_spec("config.settings.desktop") is None:
            sys.stderr.write(
                f"[entrypoint] config.settings.desktop não está no pacote "
                f"congelado. A raiz é {raiz}.\n"
                f"[entrypoint] Isto é um build partido: o spec tem de "
                f"incluir o pacote `config` como módulo (collect_submodules), "
                f"não como ficheiro de dados.\n"
            )
            return 2
    else:
        if not (raiz / "config" / "settings" / "desktop.py").is_file():
            sys.stderr.write(
                f"[entrypoint] Raiz de código inválida: {raiz}\n"
                f"[entrypoint] Esperava config/settings/desktop.py dentro dela.\n"
            )
            return 2
        os.environ["AMPLIAGRO_CODE_ROOT"] = str(raiz)

    import bootstrap

    return bootstrap.principal_ponto_de_entrada()


if __name__ == "__main__":
    raise SystemExit(principal())
