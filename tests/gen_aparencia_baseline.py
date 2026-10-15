"""Regenera `tests/aparencia_baseline.json`.

NAO EDITAR A MAO. A baseline e' o ponto de partida da catraca de
`tests/test_aparencia_invariante.py`; o objectivo e' fazer o numero BAIXAR.

Aceitar uma subida e' uma decisao de produto, nao um commit de arrumacao.
O caminho feliz e: primeiro corrigir o CSS, depois correr isto e o numero desce.

    python tests/gen_aparencia_baseline.py            # regera
    python tests/gen_aparencia_baseline.py --mostra   # so mostra o diff

Porquê um script e nao um `--aceitar` como o `test_token_violacao.py` tem:
o token tem uma regeneracao simples porque a regra e' "conta literais". Aqui ha
tres eixos com criterios diferentes - tokens de runtime (um conjunto de nomes),
tokens so em runtime (uma lista classificada) e estrutura (11 contagens por
ficheiro) - e o "--aceitar" seria um ditador silencioso sobre tres
decisoes diferentes.
"""

from __future__ import annotations

import argparse
import datetime
import json
import pathlib
import re
import sys

RAIZ = pathlib.Path(__file__).resolve().parents[1]
CSS = RAIZ / "app" / "static" / "css"
JS = RAIZ / "app" / "static" / "js"
DESTINO = RAIZ / "tests" / "aparencia_baseline.json"

#: Tem de ser a MESMA expressao regular do teste. Se divergirem, a baseline
#: mede uma coisa e a catraca mede outra - e a falha aparece como "o numero
#: subiu" sem ninguem ter mexido em nada. Foi o que aconteceu uma vez.
COMENTARIO = re.compile(r"/\*.*?\*/", re.S)
SET_PROPERTY = re.compile(r"""setProperty\(\s*['"`](--[\w-]+)['"`]""")

PADROES: dict[str, str] = {
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


#: Ficheiros GERADOS. Tem de ser a MESMA lista que `test_aparencia_invariante.py`
#: usa — se os dois divergirem, a baseline mede uma coisa e a catraca mede outra,
#: e a falha aparece como "o numero subiu" sem ninguem ter mexido em nada.
#: Foi o que aconteceu com `tailwind-compiled.css`: o `test_token_violacao.py`
#: excluia-o desde o inicio e o meu nao. Reconstruir o CSS disparou a catraca
#: com +1 font-size, +2 height, -1 padding e -2 z-index — todas num ficheiro
#: gerado, zero em CSS escrito a mao. Um alarme falso treina a ignorar o alarme.
GERADOS = {
    # `package.json` -> `build:css` -> `npx @tailwindcss/cli`. Saida do build.
    "tailwind-compiled.css",
}


def tokens_runtime() -> tuple[dict[str, int], int, list[str]]:
    por_ficheiro: dict[str, int] = {}
    todos: set[str] = set()
    for f in sorted(JS.rglob("*.js")):
        nomes = set(
            SET_PROPERTY.findall(f.read_text(encoding="utf-8", errors="replace"))
        )
        if nomes:
            por_ficheiro[f.relative_to(JS).as_posix()] = len(nomes)
            todos |= nomes
    css = "\n".join(
        p.read_text(encoding="utf-8", errors="replace")
        for p in sorted(CSS.rglob("*.css"))
    )
    so_runtime = sorted(n for n in todos if n not in css)
    return por_ficheiro, len(todos), so_runtime


def estrutura() -> dict[str, dict[str, int]]:
    por_ficheiro: dict[str, dict[str, int]] = {}
    for f in [p for p in sorted(CSS.rglob("*.css")) if p.name not in GERADOS]:
        limpo = COMENTARIO.sub(" ", f.read_text(encoding="utf-8", errors="replace"))
        contagens = {
            chave: len(re.findall(pat, limpo)) for chave, pat in PADROES.items()
        }
        contagens = {k: v for k, v in contagens.items() if v}
        if contagens:
            por_ficheiro[f.relative_to(CSS).as_posix()] = contagens
    return por_ficheiro


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mostra", action="store_true", help="nao escreve, so mostra")
    ap.add_argument(
        "--motivo",
        default="",
        help=(
            "Por que este numero subiu. Escreve uma entrada em `_decisoes` "
            "com o ANTIGO e o NOVO, para o proximo que chegar ver porque o "
            "guard esta neste numero e nao noutro."
        ),
    )
    args = ap.parse_args()

    # O que a baseline JA dizia, antes de reescrever. O `_decisoes` e' lido
    # daqui e NAO de `novo` — porque `novo` e' reconstruido do zero, e sem
    # este `get` cada regeneracao apagava o historico de decisoes.
    #
    # MEDIDO 2026-10-04 (agente 4). Foi assim que o registo de decisoes
    # desapareceu da primeira vez que tentei escreve-lo: o gerador corre e o
    # ficheiro ficou sem `_decisoes`. Um registo que se apaga sozinho e' um
    # registo que nao existe.
    antes_bruto: dict = {}
    if DESTINO.exists():
        antes_bruto = json.loads(DESTINO.read_text(encoding="utf-8-sig"))
    decisoes = list(antes_bruto.get("_decisoes", []))

    por_fich, total, so_runtime = tokens_runtime()
    layout = estrutura()
    novo = {
        "_leia_me": (
            "Baseline da aparencia (A1). Ver tests/test_aparencia_invariante.py. "
            "NAO editar a mao: e' o ponto de partida, e o objectivo e' fazer o numero "
            "BAIXAR. Aceitar uma subida e' uma decisao de produto — e uma decisao "
            "precisa de motivo. Ver `_decisoes`, e regenere com `--motivo`."
        ),
        "tokens_runtime_por_ficheiro": por_fich,
        "tokens_runtime_total": total,
        "tokens_so_em_runtime": so_runtime,
        "layout_por_ficheiro": layout,
        "layout_total": {k: sum(v.get(k, 0) for v in layout.values()) for k in PADROES},
    }
    if decisoes or args.motivo:
        novo["_decisoes"] = decisoes

    if args.mostra:
        if not DESTINO.exists():
            print("ainda nao existe baseline")
            return 1
        antes = json.loads(DESTINO.read_text(encoding="utf-8-sig"))
        print(
            f"tokens runtime: {antes['tokens_runtime_total']} -> {novo['tokens_runtime_total']}"
        )
        print(
            f"so em runtime : {antes['tokens_so_em_runtime']} -> {novo['tokens_so_em_runtime']}"
        )
        for chave, novo_v in novo["layout_total"].items():
            velho = antes["layout_total"].get(chave, 0)
            marca = (
                "  " if novo_v == velho else ("SUBIU" if novo_v > velho else "desceu")
            )
            print(f"  {chave:<16} {velho:>6} -> {novo_v:>6}  {marca}")
        return 0

    DESTINO.write_text(json.dumps(novo, indent=1, ensure_ascii=False), encoding="utf-8")
    print("escrito:", DESTINO)
    print("tokens runtime distintos:", total)
    print("tokens so em runtime:", so_runtime)

    # ── A decisao, se a houve ────────────────────────────────────────────
    #
    # Sem isto, aceitar uma subida e' um acto mudo: o numero muda e o ficheiro
    # nao diz porque. Daqui a tres meses ninguem sabe se o +12 de `order` foi
    # layout novo ou deriva — e o teste volta a ser ruido em vez de guarda.
    #
    # O registo e' OBRIGATORIO quando algum total sobe. Nao e' burocracia: e' o
    # que separa "aceitei porque e' justo" de "aceitei porque estava vermelho".
    if args.motivo:
        antes_layout = antes_bruto.get("layout_total", {})
        delta = {
            k: f"{antes_layout.get(k, 0)} -> {v}"
            for k, v in novo["layout_total"].items()
            if v != antes_layout.get(k, 0)
        }
        if not delta:
            print("AVISO: --motivo dado mas nada mudou. Entrada nao escrita.")
        else:
            novo["_decisoes"].append(
                {
                    "motivo": args.motivo,
                    "data": datetime.date.today().isoformat(),
                    "delta_totais": delta,
                    "nota": (
                        "Aceitar uma subida muda o numero de REFERENCIA. "
                        "Nao afrouxa a regra: a proxima subida volta a falhar."
                    ),
                }
            )
            DESTINO.write_text(
                json.dumps(novo, indent=1, ensure_ascii=False), encoding="utf-8"
            )
            print(f"decisao registada: {len(novo['_decisoes'])} entrada(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
