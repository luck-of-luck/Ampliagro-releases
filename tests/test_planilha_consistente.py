"""Prova que a folha NAO DIVERGE do registo.

O `test_comparativo_100x50.py` valida `evidencia.py`. Nao validava o `.xlsx`
— ou seja, o registo podia ter 71 e a folha 52 sem ninguem dar por isso.
Este teste fecha essa porta.

Duas coisas que custaram tempo e ficam escritas para nao custar a proxima:
  - a folha chama-se "MATRIZ" em maiusculas; `wb["Matriz"]` levanta KeyError
    porque o openpyxl nao normaliza o nome;
  - o cabecalho de cada dimensao e' "F01\\nLCDPR — ..." (id + quebra), nao
    "[F01] ...". Ler a coluna pela posicao e' seguro; pelo texto exige corte.
"""

from __future__ import annotations

import pathlib
import sys
import unittest
from collections import Counter

from openpyxl import load_workbook

RAIZ = pathlib.Path(__file__).resolve().parents[1]
BASE = RAIZ / "docs" / "arquitetura" / "sistema" / "comparativo"
sys.path.insert(0, str(BASE))

from concorrentes import CONCORRENTES  # noqa: E402
from evidencia import EVIDENCIA  # noqa: E402
from medir_ampliagro import COLUNAS  # noqa: E402

XLSX = BASE / "comparativo-100x50.xlsx"
OFFSET = 5  # A:#, B:Aplicacao, C:Pais, D:Segmento, E:Fonte


def cabecalho_ids() -> dict[str, int]:
    """{id da dimensao: indice da coluna na folha}.

    `'F' in 'A-Z'` e' **Falso** — `"A-Z"` e' a string de tres caracteres
    A, -, Z, e nao um intervalo. A verificaicao correta e uma comparacao
    encadeada. Escrevi o teste errado primeiro e ele devolviu zero colunas
    em silencio; fica aqui para noutro commeter o mesmo.
    """
    ws = load_workbook(XLSX)["MATRIZ"]
    out: dict[str, int] = {}
    for j in range(OFFSET + 1, ws.max_column + 1):
        v = ws.cell(row=1, column=j).value
        if isinstance(v, str) and len(v) > 3:
            cab = v.split("\n", 1)[0].strip()
            if len(cab) == 3 and "A" <= cab[0] <= "Z" and cab[1:].isdigit():
                out[cab] = j
    return out


def folha() -> dict[tuple[str, str], str]:
    ws = load_workbook(XLSX)["MATRIZ"]
    cols = cabecalho_ids()

    faltam = [cid for cid, *_r in COLUNAS if cid not in cols]
    if faltam:
        msg = f"{len(faltam)} colunas ausentes do cabecalho: {faltam[:5]}"
        raise AssertionError(msg)

    out: dict[tuple[str, str], str] = {}
    for i, (nome, *_r) in enumerate(CONCORRENTES, start=2):
        lido = ws.cell(row=i, column=2).value
        if lido != nome:
            msg = f"ordem divergente na linha {i}: folha={lido!r} registo={nome!r}"
            raise AssertionError(msg)
        for cid, *_r2 in COLUNAS:
            out[(nome, cid)] = ws.cell(row=i, column=cols[cid]).value
    return out


def main() -> None:
    f = folha()
    esperado = {
        (nome, cid): (EVIDENCIA.get((nome, cid)) or ("", "", "", "?", ""))[3]
        for nome, *_r in CONCORRENTES
        for cid, *_r2 in COLUNAS
    }

    if len(f) != 5000:
        msg = f"a folha tem {len(f)} celulas de dados; esperava 5000"
        raise AssertionError(msg)

    dif = sorted(k for k in esperado if f.get(k) != esperado[k])
    if dif:
        det = [(k, esperado[k], f.get(k)) for k in dif[:8]]
        msg = f"{len(dif)} celulas divergem folha<->registo: {det}"
        raise AssertionError(msg)

    c = Counter(esperado.values())
    print("  folha == registo nas 5000 celulas")
    print(f"  marcas: {dict(sorted(c.items()))}")
    print(
        f"  provadas {c['F']} + documentadas {c['D']} = {c['F'] + c['D']}"
        f"   |   parciais {c['P']}   |   sem prova {c['?']}"
    )


if __name__ == "__main__":
    main()


class FolhaConsistenteTest(unittest.TestCase):
    """A folha e' o que o leitor abre. Se ela divergir do registo, o registo
    esta a mentir para quem nao corre codigo — e a folha e' o quecorre.

    Sem isto, `evidencia.py` podia ter 69 e o `.xlsx` 52 sem ninguem dar
    por isso. Os dois sao gerados a mao, nao por uma fonte unica.
    """

    def test_a_folha_bate_com_o_registo(self):
        main()

    def test_a_folha_tem_as_sete_folhas(self):
        wb = load_workbook(XLSX)
        self.assertEqual(
            wb.sheetnames,
            [
                "LEIA-ME",
                "COLUNAS",
                "MATRIZ",
                "AMPLIAGRO",
                "QUEM-PASSA",
                "COMERCIAL",
                "FONTES",
            ],
        )
