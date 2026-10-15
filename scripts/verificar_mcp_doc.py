"""Verificador de markdown para `docs/MCP_AMPLIA.md`.

Existe porque as regras do `AGENTS.md` do Ampliagro pedem uma coisa só H1 e
nenhum salto de nível de título — e porque já escrevi aqui mais do que um H1
sem dar por isso. Um ficheiro que viola a convenção da equipa é uma coisa que
a revisão apanha e devolve; melhor apanhar antes.

Corrige o que encontra? Não. Aponta. Um verificador que reescreve o
ficheiro é um verificador que ninguém lê duas vezes.
"""

from __future__ import annotations

import pathlib
import re
import sys

CANDIDATOS = [
    pathlib.Path(__file__).resolve().parents[1] / "docs" / "MCP_AMPLIA.md",
]

FENCE = re.compile(r"^\s*```")
H = re.compile(r"^(#{1,6})\s")


def verificar(caminho: pathlib.Path) -> list[str]:
    if not caminho.exists():
        return [f"{caminho.name}: nao existe"]
    with open(caminho, encoding="utf-8") as fh:
        texto = fh.read()
    problemas: list[str] = []

    h1 = 0
    niveis: list[tuple[int, int]] = []  # (linha, nivel)
    dentro = False
    for ln, linha in enumerate(texto.splitlines(), 1):
        if FENCE.match(linha):
            dentro = not dentro
            continue
        if dentro:
            continue
        m = H.match(linha)
        if m:
            nivel = len(m.group(1))
            niveis.append((ln, nivel))
            if nivel == 1:
                h1 += 1

    if h1 != 1:
        problemas.append(f"{caminho.name}: {h1} titulos H1 (a regra e' exactamente 1)")

    for (_ln_a, a), (ln_b, b) in zip(niveis, niveis[1:], strict=False):
        if b > a + 1:
            problemas.append(
                f"{caminho.name}:{ln_b}: salta de H{a} para H{b} "
                f"(a regra e' nunca saltar nivel)"
            )

    # anguage tag em cada cerca
    for i, linha in enumerate(texto.splitlines(), 1):
        if FENCE.match(linha) and "```" in linha[3:]:
            problemas.append(f"{caminho.name}:{i}: cerca sem language tag")

    # caracteres que nao deviam estar em pt-BR
    for ln, linha in enumerate(texto.splitlines(), 1):
        for ch in linha:
            cp = ord(ch)
            if (
                0x2E80 <= cp <= 0x9FFF
                or 0xFF00 <= cp <= 0xFFEF
                or 0x3000 <= cp <= 0x303F
            ):
                problemas.append(f"{caminho.name}:{ln}: caractere CJK U+{cp:04X}")
                break

    return problemas


def main() -> int:
    tudo: list[str] = []
    for c in CANDIDATOS:
        tudo.extend(verificar(c))
    if tudo:
        print("FALHA:")
        for p in tudo:
            print("  -", p)
        return 1
    print(f"OK  {len(CANDIDATOS)} ficheiro(s) conforme as regras de markdown")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
