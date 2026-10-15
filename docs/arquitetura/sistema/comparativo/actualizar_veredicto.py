"""Actualiza o veredicto de uma linha da folha 100x50, com a evidencia.

Porque este script existe
========================

A folha `comparativo-100x50.xlsx` tem 50 dimensoes com um veredicto cada. Quando
uma capacidade passa a existir, o veredicto ficawrong e o proximo agente le
'NAO TEM' num sitio que tem codigo — e reconstroi a coisa que ja existe.

Este script NAO decide o veredicto: recebe. Quem decide e' quem mediu, e tem
de escrever o porque, porque a folha ja provou (pelo `f782051`) que um motivo
errado e' pior do que um motivo ausente.

O QUE ESTE SCRIPT NAO FAZ
==========================

Nao adivinha. Nao le codigo para inferir capacidade. Se nao lhe disserem o
veredicto com evidencia, ele nao escreve — por causa disso e' preciso passar
`--veredicto`, e o default e' NAO FAZER NADA.
"""

import argparse
import pathlib

import openpyxl

RAIZ = pathlib.Path(__file__).resolve().parent
PLANILHA = RAIZ / "comparativo-100x50.xlsx"

#: As marcas de que a folha fala em M02/M03. Nao ha integracao oficial com
#: nenhuma delas, e `app/services/conectores.py` declara isso no catalogo.
#: Nao escrever aqui um "integrado com" — seria uma promessa que o codigo nao
#: cumpre.
SEM_INTEGRACAO_OFICIAL = ("John Deere", "Stara", "Climate FieldView", "Solinftec")


def localiza(ws, cid):
    """A linha da celula `cid`. `None` se nao existe."""
    cab = [c.value for c in ws[1]]
    if "ID" not in cab:
        return None, None
    col_id = cab.index("ID") + 1
    for r in range(2, ws.max_row + 1):
        if ws.cell(row=r, column=col_id).value == cid:
            return r, cab
    return None, None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("id", help="o ID da celula, ex.: X02")
    ap.add_argument("--veredicto", help="C, E ou N")
    ap.add_argument("--evidencia", help="ficheiro:linha")
    ap.add_argument("--porque", help="o que a linha diz, e porque este veredicto")
    ap.add_argument(
        "--porque-de-ficheiro",
        help="le o `--porque` de um ficheiro. Existe porque o texto do porque "
        "tem aspas epontos-e-virgulas, e um `-c` na shell parte-os em varios "
        "argumentos. O porque errado e' pior do que a falta dele.",
    )
    ap.add_argument("--simular", action="store_true", help="nao escreve")
    args = ap.parse_args()

    if not args.veredicto:
        print(
            "Nada a fazer: sem --veredicto. Este script nao adivinha o "
            "veredicto de uma capacidade — quem mede, escreve.\n\n"
            "Ver `--help` para os campos."
        )
        return 1

    if args.veredicto not in ("C", "E", "N"):
        print(f"Veredicto invalido: {args.veredicto!r}. E' C, E ou N.")
        return 1

    wb = openpyxl.load_workbook(PLANILHA)
    ws = wb["AMPLIAGRO"]
    linha, cab = localiza(ws, args.id)
    if linha is None:
        print(f"A celula {args.id!r} nao esta na folha.")
        return 1

    if args.simular:
        print(f"[simular] {args.id} -> {args.veredicto}")
        return 0

    def escreve(nome, valor):
        if nome in cab:
            ws.cell(row=linha, column=cab.index(nome) + 1).value = valor

    escreve("Veredicto", args.veredicto)
    if args.evidencia:
        escreve("Evidencia (ficheiro:linha)", args.evidencia)
    porque = args.porque
    if args.porque_de_ficheiro:
        porque = pathlib.Path(args.porque_de_ficheiro).read_text(encoding="utf-8")
    if porque:
        escreve("O que a linha diz", porque.strip())

    wb.save(PLANILHA)
    print(f"{args.id} -> {args.veredicto}. Folha actualizada.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
