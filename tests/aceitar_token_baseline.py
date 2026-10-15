r"""Regera a baseline de cores literais (a catraca do invariante §1).

SÓ PARA BAIXAR O NÚMERO DE PROPÓSITO. Um commit que apaga cores pode correr
isto; um commit que as acrescenta, não — se as acrescenta, ou a cor vira token
em `design-tokens.css`, ou é uma decisão de produto e fica registada.

    python tests/aceitar_token_baseline.py            # escreve a baseline
    python tests/aceitar_token_baseline.py --mostrar  # só o diff, não escreve
    python tests/aceitar_token_baseline.py --migrar   # só o separador de caminho

O `--mostrar` existe porque o caminho fácil é o caminho perigoso: se isto
escreve sem dizer o que mudou, alguém corre a meio de um trabalho e o
invariante baixa sem ninguém ter lido. Ver o diff primeiro é o hábito que
mantém a §1 de pé.

O `--migrar` é diferente: renomeia as chaves de `\` para `/` sem tocar nos
números. Só foi preciso uma vez, numa baseline gerada no Windows antes de o
`varre_css()` passar a `as_posix()`. Não é baixar o invariante — é mudar o
nome das linhas.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))

from test_token_violacao import BASELINE, varre_css  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--mostrar",
        action="store_true",
        help="imprime o diff e não escreve nada",
    )
    ap.add_argument(
        "--inicial",
        action="store_true",
        help=(
            "regista a baseline quando ela ainda nao existe. Sem isto, o "
            "primeiro run ve 'tudo a subir' e nao consegue escrever. Depois "
            "disso o caminho normal passa a ser o unico."
        ),
    )
    ap.add_argument(
        "--migrar",
        action="store_true",
        help=(
            "renomeia as chaves da baseline de `\\` para `/`, sem tocar nos "
            "numeros. So e' preciso uma vez, numa baseline gerada no Windows "
            "antes da correccao do separador."
        ),
    )
    args = ap.parse_args()

    existe = BASELINE.exists()
    # `utf-8-sig`: o Notepad do Windows e o `Set-Content -Encoding UTF8` do
    # PowerShell põem BOM, e um BOM em JSON impede este script de CORRIGIR a
    # baseline — que é o pior sítio possível para ele estar. Medido a
    # acontecer enquanto este ficheiro era escrito.
    antigo = json.loads(BASELINE.read_text(encoding="utf-8-sig")) if existe else {}
    novo = varre_css()

    # --- Migracao de separador de caminho -------------------------------
    # Ate 2026-10-03 a baseline foi escrita com `str()`, que da `\` no Windows.
    # O `varre_css()` usa `as_posix()` desde a correccao do separador, e o CI
    # corre em Linux. Sem esta migracao, as 18 chaves com `\` faziam o
    # ficheiro parecer um ficheiro novo com 0 -> N cores: a catraca reportava
    # "subiu" em 18 ficheiros que nao tinham uma cor nova sequer.
    #
    # Isto NAO e baixar o invariante: e renomear as chaves. Os numeros ficam
    # os mesmos, e por isso e `--migrar` explicito, e nao parte do caminho
    # normal de escrita.
    if existe:
        com_barra = sorted(k for k in antigo if "\\" in k)
        if com_barra:
            if not args.migrar:
                print(
                    f"A baseline tem {len(com_barra)} chaves com `\\`, gravadas no "
                    "Windows. O `varre_css()` usa `/` e o CI e' Linux, portanto "
                    "essas linhas seriam lidas como ficheiros NOVOS e a catraca "
                    "falhava sem nenhuma cor ter sido escrita.\n"
                    "Para migrar so o separador (os numeros nao mudam):\n"
                    "    python tests/aceitar_token_baseline.py --migrar\n",
                    file=sys.stderr,
                )
                return 3
            migrado = {k.replace("\\", "/"): v for k, v in antigo.items()}
            if migrado != antigo and args.mostrar:
                print(f"migracao: {len(com_barra)} chaves `\\` -> `/`")
                print("(--mostrar: nada foi escrito)")
                return 0
            antigo = migrado
            if not args.mostrar:
                BASELINE.write_text(
                    json.dumps(antigo, indent=2, ensure_ascii=False, sort_keys=True)
                    + "\n",
                    encoding="utf-8",
                )
                print(
                    f"baseline migrada: {len(com_barra)} chaves `\\` -> `/`. "
                    "Numeros inalterados."
                )
                print(f"escrito: {BASELINE.relative_to(BASELINE.parents[1])}")
                return 0

    if not existe:
        if not args.inicial:
            print(
                "A baseline ainda nao existe. Para a criar a partir do estado "
                "de hoje:\n"
                "    python tests/aceitar_token_baseline.py --inicial\n",
                file=sys.stderr,
            )
            return 2
        BASELINE.write_text(
            json.dumps(novo, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(f"baseline criada a partir do estado actual: {sum(novo.values())} cores")
        print(f"escrito: {BASELINE.relative_to(BASELINE.parents[1])}")
        return 0

    subiu = {f: n for f, n in novo.items() if n > antigo.get(f, 0)}
    desceu = {
        f: (antigo[f], novo[f]) for f in novo if f in antigo and novo[f] < antigo[f]
    }

    if subiu:
        print("A subir — a catraca vai falhar até isto ser resolvido:", file=sys.stderr)
        for ficheiro, n in sorted(subiu.items()):
            print(f"  {ficheiro}: {antigo.get(ficheiro, 0)} -> {n}", file=sys.stderr)
        print(
            "\nUma cor que sobe tem de ser um token novo em design-tokens.css.\n"
            "Se a subida for mesmo intencional, acrescente-a à excepção com um\n"
            "motivo — não baixe a baseline para a tapar.",
            file=sys.stderr,
        )
        return 1

    for ficheiro, (antes, agora) in sorted(desceu.items()):
        print(f"  {ficheiro}: {antes} -> {agora}")
    for ficheiro in sorted(set(antigo) - set(novo)):
        print(f"  {ficheiro}: {antigo[ficheiro]} -> (apagado)")

    total_antes = sum(antigo.values())
    total_agora = sum(novo.values())
    print(f"\nTOTAL {total_antes} -> {total_agora}  ({total_agora - total_antes:+d})")

    if args.mostrar:
        print("\n(--mostrar: nada foi escrito)")
        return 0

    BASELINE.write_text(
        json.dumps(novo, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"\nescrito: {BASELINE.relative_to(BASELINE.parents[1])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
