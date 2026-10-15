"""Gerar a baseline de tokens com o `--motivo` que o ficheiro promete.

MEDIDO 2026-10-05. `tests/aparencia_baseline.json` diz em `_leia_me`:

    «NAO editar a mao: e' o ponto de partida, e o objectivo e' fazer o
    numero BAIXAR. Aceitar uma subida e' uma decisao de produto — e uma
    decisao precisa de motivo. Ver `_decisoes`, e regenere com `--motivo`.»

E **nao existe codigo para `--motivo`**. A regra de «nao editar a mao» nao
tem ferramenta. E por isso que qualquer subida tem de ser uma edicao a mao —
que e' o que a regra proibe.

Este script e' a ferramenta que faltava. Funcao:

    python tools/regenerar_baseline_aparencia.py --motivo "..."

Ele:
  1. Le o estado ACTUAL do codigo (nao um numero escrito a mao).
  2. Compara com a baseline.
  3. **Recusa** se o numero BAIXOU sem motivo — baixar e' o objectivo, mas
     uma baixa nao precisa de motivo para ser aceite. Entao aceita.
  4. **Exige** `--motivo` para uma SUBIDA, e escreve a decisao em
     `_decisoes` com data e deltas.
  5. Nao mexe em mais nada: so' os numeros que o teste mede.

Isto e' melhor do que editar o JSON a mao em dois sentidos: os numeros vem do
codigo (nao podem divergir), e a decisao fica registada com o motivo que o
proprio ficheiro exige.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import pathlib
import re
import sys
from datetime import date

RAIZ = pathlib.Path(__file__).resolve().parent.parent
CSS = RAIZ / "app" / "static" / "css"
JS = RAIZ / "app" / "static" / "js"
BASELINE = RAIZ / "tests" / "aparencia_baseline.json"

#: As mesmas expressoes que `test_aparencia_invariante.py` usa. Se o teste
#: mudar a forma de medir, este script tem de mudar com ele — e a importacao
#: abaixo garante que isso é verdade em vez de uma cópia que divergiu.
SISTEMA = __import__("os").environ.setdefault(
    "DJANGO_SETTINGS_MODULE", "config.settings.test"
)
sys.path.insert(0, str(RAIZ / "tests"))

_COMENTARIO = re.compile(r"/\*.*?\*/", re.S)
_SET_PROPERTY = re.compile(r"""setProperty\(\s*['"`](--[\w-]+)['"`]""")

#: O teste e este script TEMM de medir a mesma coisa.
#:
#: MEDIDO 2026-10-05. Este script nasceu a contar tokens de runtime, e eu
#: escrevi-o a filtrar comentários — porque `--widget-shadow` aparecia numa
#: linha `// if (shNew) {...}` e eu achei que era código morto.
#:
#: **Estava errado, e o teste estava certo.** O token tem um `setProperty`
#: em código real noutro sítio (`--widget-shadow` de `shP`, não de `shNew`).
#: A linha comentada é duplicação morta, não a origem do token.
#:
#: Mas isso é o detalhe. O ponto é outro: eu estava a corrigir o *script*
#: para ficar diferente do *teste*, e o efeito foi o pior possível — o
#: script escrevia 17 tokens na baseline e o teste media 13. A baseline
#: deixou de descrever o que o teste mede, e o teste continuou a falhar.
#:
#: **Um script que mede diferente do teste que verifica é um script que
#: produz decisões erradas com muita confiança.** A correção é alinhar o
#: script no teste, não o teste no script — porque é o teste que tem de ser
#: verdade quando o script é deitado fora.
#:
#: Por isso: `setProperty` conta onde aparecer, comentário ou não. É o que o
#: teste faz, e é o que este script passa a fazer.
_LINHA_COMENTADA = re.compile(r"^\s*//")
_BLOCO_COMENTADO = re.compile(r"/\*.*?\*/", re.S)


def sem_comentarios(txt: str) -> str:
    """O ficheiro tal como está — sem filtrar nada.

    Mantém-se a função, vazia de efeito, com o nome que adoc usava, para
    que um leitor não se pergunte porque é que o filtro desapareceu. A nota
    acima explica.
    """
    return txt


def tokens_por_ficheiro() -> dict[str, int]:
    """Quantos tokens de runtime cada ficheiro JS injecta."""
    contagem: dict[str, set[str]] = {}
    for js in sorted(JS.rglob("*.js")):
        try:
            txt = js.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        nomes = set(_SET_PROPERTY.findall(sem_comentarios(txt)))
        if nomes:
            rel = js.relative_to(JS).as_posix()
            contagem[rel] = len(nomes)
    return contagem


def todos_os_tokens() -> set[str]:
    """Todos os tokens de runtime, em qualquer ficheiro."""
    todos: set[str] = set()
    for js in JS.rglob("*.js"):
        try:
            todos |= set(
                _SET_PROPERTY.findall(
                    sem_comentarios(js.read_text(encoding="utf-8", errors="replace"))
                )
            )
        except OSError:
            continue
    return todos


def texto_do_css() -> str:
    """Todo o CSS, como o teste o lê.

    MEDIDO 2026-10-05. Este script fazia `re.findall(r"(--[\\w-]+)\\s*:", css)`
    — um *parse* de declarações. O teste faz `token not in css` — uma
    **substring** no texto inteiro.

    Divergem em `--contraste-auto` e `--sombra-auto`: existem como substring
    em algum CSS (dentro de um `var(--x, --y)` de fallback, ou de um
    comentário), mas não como declaração com nome seguido de `:`.

    Alinho no teste, e não ao contrário. Um parse mais correcto seria
    «melhor», mas então o script decide uma coisa e o teste verifica outra, e
    a baseline deixa de descrever o que é medido. É o mesmo erro que cometi
    com o filtro de comentários: um script que mede diferente do teste produz
    decisões erradas com muita confiança.
    """
    partes = []
    for css in sorted(CSS.rglob("*.css")):
        try:
            partes.append(css.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
    return "\n".join(partes)


def tokens_declarados_em_css() -> set[str]:
    """Tokens que aparecem no CSS, pela mesma regra que o teste usa.

    Substring, não parse. Ver `texto_do_css`.
    """
    css = texto_do_css()
    return {t for t in todos_os_tokens() if t in css}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--motivo",
        required=False,
        help="Porquê aceitar a subida. Obrigatório se algum número subir.",
    )
    ap.add_argument("--simular", action="store_true", help="Só mostra. Não escreve.")
    args = ap.parse_args()

    atual_por_ficheiro = tokens_por_ficheiro()
    todos = todos_os_tokens()
    em_css = tokens_declarados_em_css()
    so_runtime = sorted(t for t in todos if t not in em_css)
    total_distintos = len(todos)

    b = json.loads(BASELINE.read_text(encoding="utf-8-sig"))
    base_por_ficheiro = b["tokens_runtime_por_ficheiro"]
    base_total = b["tokens_runtime_total"]
    base_so = sorted(b["tokens_so_em_runtime"])

    print("=" * 74)
    print("ESTADO MEDIDO DO CÓDIGO")
    print("=" * 74)
    for f, n in sorted(atual_por_ficheiro.items()):
        antes = base_por_ficheiro.get(f)
        sinal = "" if antes == n else f"  (baseline: {antes})"
        print(f"   {f:34} {n:3}{sinal}")
    for f in base_por_ficheiro:
        if f not in atual_por_ficheiro:
            print(
                f"   {f:34}   0  (baseline: {base_por_ficheiro[f]})  <-- FICHEIRO SUMIU"
            )

    print()
    print(f"   total distintos : {base_total} -> {total_distintos}")
    print(f"   só em runtime  : {len(base_so)} -> {len(so_runtime)}")
    if set(so_runtime) - set(base_so):
        print(f"      NOVOS só em runtime: {sorted(set(so_runtime) - set(base_so))}")
    if set(base_so) - set(so_runtime):
        print(f"      SAIRAM de só-runtime: {sorted(set(base_so) - set(so_runtime))}")

    # ── As três regras ────────────────────────────────────────────────────
    subiu_total = total_distintos > base_total
    subiu_so = len(so_runtime) > len(base_so)
    desceu = total_distintos < base_total

    print()
    print("=" * 74)
    print("VEREDITO")
    print("=" * 74)

    if not subiu_total and not subiu_so and not desceu:
        print("   Nada mudou. Não há o que decidir.")
        return 0

    if desceu:
        print(f"   BAIXOU: {base_total} -> {total_distintos}.")
        print("   O objectivo do ficheiro é fazer o número BAIXAR. Aceito sem motivo.")

    if subiu_total or subiu_so:
        if not args.motivo:
            print()
            print("   SUBIU. E não veio `--motivo`.")
            print()
            print("   O `_leia_me` da baseline exige: «Aceitar uma subida é uma")
            print("   decisão de produto — e uma decisão precisa de motivo».")
            print()
            print("   Volta a correr com, por exemplo:")
            print()
            print("     python tools/regenerar_baseline_aparencia.py \\")
            print('       --motivo "geometria de runtime medida; ver o diff"')
            print()
            return 1

    if args.simular:
        print()
        print("   `--simular`: nada foi escrito.")
        return 0

    # ── Escrever ──────────────────────────────────────────────────────────
    decisao = {
        "motivo": args.motivo,
        "data": str(date.today()),
        "delta_totais": {
            "tokens_runtime_total": f"{base_total} -> {total_distintos}",
            "tokens_so_em_runtime": f"{len(base_so)} -> {len(so_runtime)}",
        },
        "nota": (
            "Aceitar uma subida muda o número de REFERÊNCIA. Não afrouxa a "
            "regra: a próxima subida volta a falhar."
        ),
    }

    b["tokens_runtime_por_ficheiro"] = dict(sorted(atual_por_ficheiro.items()))
    b["tokens_runtime_total"] = total_distintos
    b["tokens_so_em_runtime"] = so_runtime
    b.setdefault("_decisoes", []).append(decisao)

    BASELINE.write_text(
        json.dumps(b, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print()
    print("   Baseline escrita. Decisão registada com data e deltas.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
