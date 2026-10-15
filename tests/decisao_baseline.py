"""A DECISAO DA BASELINE, EM UMA PALAVRA.

Este script existe para que o dono nao tenha de ler um `pytest` a falhar para
descobrir o que mudou. Responde a uma pergunta: **o que grew desde a baseline, e
onde?**

Alem disso imprime o diff por ficheiro, que e' o que interessa — porque a §1.3
proibe o total global (tirar 10 literals de um ficheiro e por 10 noutro nao mexe
no total e muda o debito de sitio).

NAO ACEITA NADA. Nao escreve a baseline. Aceitar e' uma decisao de produto e
esta' aqui para tornar essa decisao barata, nao para a tomar.

    python tests/decisao_baseline.py
"""

from __future__ import annotations

import json
import pathlib
import re

RAIZ = pathlib.Path(__file__).resolve().parents[1]
CSS = RAIZ / "app" / "static" / "css"
JS = RAIZ / "app" / "static" / "js"
BASE = pathlib.Path(__file__).parent / "aparencia_baseline.json"

COMENTARIO = re.compile(r"/\*.*?\*/", re.S)
SET_PROPERTY = re.compile(r"""setProperty\(\s*['"`](--[\w-]+)['"`]""")

PROPRIEDADES = {
    "z_index": "z-index",
    "grid_template": "grid-template",
    "grid_column": "grid-column",
    "order": "order",
    "font_size_px": "font-size (px)",
    "font_weight": "font-weight",
    "line_height": "line-height",
    "height_px": "height (px)",
    "gap_px": "gap (px)",
    "espacamento_px": "padding/margin (px)",
    "radius_px": "border-radius (px)",
}
PADROES = {
    "z_index": r"(?<!-)z-index\s*:",
    "grid_template": r"grid-template-(?:columns|areas)\s*:",
    "grid_column": r"(?<!-)grid-column\s*:",
    "order": r"(?<!-)order\s*:\s*-?\d",
    "font_size_px": r"font-size\s*:\s*\d+(?:\.\d+)?px",
    "font_weight": r"font-weight\s*:\s*\d{3}",
    "line_height": r"line-height\s*:\s*\d",
    "height_px": r"(?<!-)height\s*:\s*\d+px",
    "gap_px": r"(?<!-)(?:gap|row-gap|column-gap)\s*:\s*\d+px",
    "espacamento_px": r"(?<!-)(?:padding|margin)(?:-[a-z]+)?\s*:\s*\d+px",
    "radius_px": r"border-radius\s*:\s*\d+px",
}


#: A MESMA lista de `test_aparencia_invariante.py`. Se os tres divergirem, o
#: gerador, a catraca e este relatorio medem tres coisas diferentes.
GERADOS = {"tailwind-compiled.css"}


def medir() -> tuple[dict, dict, dict, int]:
    layout: dict[str, dict[str, int]] = {}
    for f in [p for p in sorted(CSS.rglob("*.css")) if p.name not in GERADOS]:
        limpo = COMENTARIO.sub(" ", f.read_text(encoding="utf-8", errors="replace"))
        c = {k: len(re.findall(p, limpo)) for k, p in PADROES.items()}
        c = {k: v for k, v in c.items() if v}
        if c:
            layout[f.relative_to(CSS).as_posix()] = c

    tokens: dict[str, int] = {}
    for f in sorted(JS.rglob("*.js")):
        nomes = set(
            SET_PROPERTY.findall(f.read_text(encoding="utf-8", errors="replace"))
        )
        if nomes:
            tokens[f.relative_to(JS).as_posix()] = len(nomes)

    css_tudo = "\n".join(
        p.read_text(encoding="utf-8", errors="replace")
        for p in sorted(CSS.rglob("*.css"))
    )
    todos: set[str] = set()
    for f in sorted(JS.rglob("*.js")):
        todos.update(
            SET_PROPERTY.findall(f.read_text(encoding="utf-8", errors="replace"))
        )
    so_runtime = sorted(n for n in todos if n not in css_tudo)
    return layout, tokens, so_runtime, len(todos)


def main() -> int:
    if not BASE.exists():
        print("ainda nao existe baseline; corre gen_aparencia_baseline.py")
        return 1

    antes = json.loads(BASE.read_text(encoding="utf-8-sig"))
    layout, tokens, so_runtime, total = medir()

    print("=" * 72)
    print("A DECISAO: a aparencia mudou desde a baseline?")
    print("=" * 72)

    mudou = False

    print("\n-- totais de estrutura --")
    for chave, rotulo in PROPRIEDADES.items():
        velho = antes["layout_total"].get(chave, 0)
        novo = sum(v.get(chave, 0) for v in layout.values())
        if novo == velho:
            continue
        mudou = True
        sinal = "SUBIU" if novo > velho else "desceu"
        print(f"  {rotulo:<22} {velho:>5} -> {novo:<5} {sinal} ({novo - velho:+d})")

    print("\n-- por ficheiro (so o que mudou) --")
    achados = []
    for ficheiro, contagens in sorted(layout.items()):
        base = antes["layout_por_ficheiro"].get(ficheiro, {})
        for chave, novo in sorted(contagens.items()):
            velho = base.get(chave, 0)
            if novo != velho:
                achados.append((ficheiro, PROPRIEDADES[chave], velho, novo))
    if not achados:
        print("  (nada mudou por ficheiro)")
    for ficheiro, rotulo, velho, novo in achados:
        sinal = "SUBIU" if novo > velho else "desceu"
        print(f"  {ficheiro:<44} {rotulo:<22} {velho:>4} -> {novo:<4} {sinal}")

    print("\n-- tokens de runtime (identidade visual via JS) --")
    if (
        total == antes["tokens_runtime_total"]
        and so_runtime == antes["tokens_so_em_runtime"]
    ):
        print(f"  {total} tokens, sem mudanca")
    else:
        mudou = True
        print(f"  total: {antes['tokens_runtime_total']} -> {total}")
        print(f"  so em runtime: {antes['tokens_so_em_runtime']} -> {so_runtime}")

    print()
    print("=" * 72)
    if not mudou:
        print("NADA MUDOU. A baseline esta correcta e o teste devia passar.")
        print("Se o teste falha com 'nada mudou', o problema e' do proprio teste.")
    else:
        print("HÁ MUDANCA. Tres respostas possiveis:")
        print()
        print("  (a) MEXEU-ME A MIM: a baseline tem de subir. Comandos:")
        print("        python tests/gen_aparencia_baseline.py")
        print("      Faz isto SO depois de olhar para o diff acima e concordar")
        print("      que a mudanca de aparencia e' pretendida.")
        print()
        print("  (b) A MUDANCA E' UM REGRESSO: o CSS tem de voltar. Nao se")
        print("      regenera a baseline — regenerar e' dizer que o erro e' o novo")
        print("      estado certo, e foi assim que a deuda de tokens chegou aos 4.245.")
        print()
        print("  (c) PARCIALmente: se uns numeros sobem e outros descem, a pergunta")
        print("      nao e' o total. E' se a pagina continua igual. Alguem tem de")
        print("      OLHAR a pagina.")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
