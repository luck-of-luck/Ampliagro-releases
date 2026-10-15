"""Renumera as linhas duplicadas da FILA.

Descobri isto porque fui ver: a FILA já tinha #55, #56 e #57 e eu inseri
outros com os mesmos números. Duas linhas com o mesmo número significam que
`FILA #55` não identifica um achado — e um ficheiro partilhado onde
`#55` quer dizer duas coisas coisas diferentes deixa de ser um ponto de
verdade, que é a única coisa que ele pode ser.

Números duplicados num índice partilhado são a mesma classe de defeito da
FILA #27: um identificador que mente sobre o que aponta.
"""

import pathlib
import re
from collections import Counter

CAMINHO = pathlib.Path(__file__).resolve().parents[1] / "docs" / "COORDENACAO_IA.md"

NUM = re.compile(r"^\|\s*(\d+)\s*\|")


def numeros(linhas):
    saida = []
    for i, l in enumerate(linhas):
        m = NUM.match(l)
        if m:
            saida.append((int(m.group(1)), i))
    return saida


def main():
    with open(CAMINHO, encoding="utf-8") as fh:
        linhas = fh.read().splitlines()
    pares = numeros(linhas)
    contagem = Counter(n for n, _ in pares)
    duplicados = {n for n, c in contagem.items() if c > 1}

    if not duplicados:
        print("Nenhum numero duplicado.")
        return 0

    # O maior numero ja usado, e o maior numero duplicado (que e o mais
    # recente, porque as entradas novas vao para o fim).
    maior = max(contagem)
    seguinte = maior + 1

    trocadas = []
    # Percorre de cima para baixo e renumera APENAS a segunda ocorrencia de
    # cada numero duplicado. A primeira mantem-se: quem a leu antes continua
    # a encontrar a mesma coisa.
    vistas = set()
    for i, l in enumerate(linhas):
        m = NUM.match(l)
        if not m:
            continue
        n = int(m.group(1))
        if n not in duplicados:
            continue
        if n not in vistas:
            vistas.add(n)
            continue
        linhas[i] = re.sub(r"^\|\s*\d+\s*\|", f"| {seguinte} |", l, count=1)
        trocadas.append((n, seguinte))
        seguinte += 1

    with open(CAMINHO, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(linhas) + "\n")

    print(f"numeros duplicados: {sorted(duplicados)}")
    for antigo, novo in trocadas:
        print(f"  #{antigo} -> #{novo}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
