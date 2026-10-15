"""A6 como comando: mede o estudo e mostra o que entrou.

    python tests/estudo_volume.py              # mede e mostra
    python tests/estudo_volume.py --aceitar    # so depois de MEDIR a unicidade

O `--aceitar` nao aceita "porque quero". Ele imprime a unica pergunta que
importa antes de aceitar volume — **a taxa de unicidade** — e escreve o numero ao
lado do que gravou. Aceitar volume sem essa medida e' a coisa que produziu 237 MB
de ficheiros com 11,4% de conteudo unico.

Porquê um script e nao um `--aceitar` nos testes: o `test_estudo_volume.py` tem de
falhar alto, e um script que aceita em silencio e' um script que ninguem lê antes
de correr.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parents[1]
ESTUDO = RAIZ / "docs" / "super-estudo-globo-rural"
DESTINO = RAIZ / "tests" / "estudo_baseline.json"
IGNORAR = {".git", "__pycache__", "node_modules"}

#: O exemplar medido. Vai para dentro da baseline de proposito: e' o numero que
#: impede que o proximo aceitação de volume seja feita sem o repetir.
UNICIDADE_EXEMPLO = {
    "ficheiro": "ANALISE-1001-2400-PROXIMO.md",
    "linhas_totais": 26606,
    "linhas_unicas": 3037,
    "unicidade": 0.114,
    "medido_em": "2026-10-03",
    "nota": (
        "89% de repeticao. A meta de 1.000.000 de linhas equivale, a esta taxa, "
        "a ~114.000 linhas de conhecimento real. O proprio "
        "SISTEMA-TOP1-INTEGRACAO.md admite 'vs repeticao atual para bater 1M'."
    ),
}


def medir() -> dict:
    ficheiros = 0
    total = 0
    por_subpasta: dict[str, int] = {}
    for p in ESTUDO.rglob("*"):
        if not p.is_file():
            continue
        if any(parte in IGNORAR for parte in p.parts):
            continue
        ficheiros += 1
        total += p.stat().st_size
        rel = p.relative_to(ESTUDO)
        chave = rel.parts[0] if len(rel.parts) > 1 else "(raiz)"
        por_subpasta[chave] = por_subpasta.get(chave, 0) + 1
    return {"ficheiros": ficheiros, "bytes": total, "por_subpasta": por_subpasta}


def unicidade_de(ficheiro: pathlib.Path, passo: int = 1) -> dict:
    """Taxa de linhas unicas. Lento de proposito: e' uma medicao de Occasional."""
    if not ficheiro.exists():
        return {}
    linhas = ficheiro.read_text(encoding="utf-8", errors="replace").splitlines()
    unicas = len(set(linhas))
    return {
        "linhas_totais": len(linhas),
        "linhas_unicas": unicas,
        "unicidade": round(unicas / len(linhas), 4) if linhas else 0.0,
    }


def unicidade_de_ficheiro() -> pathlib.Path:
    return ESTUDO / UNICIDADE_EXEMPLO["ficheiro"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--aceitar",
        action="store_true",
        help="grava a baseline no estado de hoje (so depois de medir a unicidade)",
    )
    ap.add_argument(
        "--porque",
        default="",
        help=(
            "OBRIGATORIO quando o volume DIMINUI. A razao fica escrita dentro "
            "da baseline, para que a remocao tenha dono e fique registada."
        ),
    )
    args = ap.parse_args()

    atual = medir()

    # O que SE APAGOU, e nao so o que entrou. Uma baseline que so cresce
    # transforma uma remocao em silencio num facto consumado: em 2026-10-04
    # desapareceram 91 ficheiros (analises-profundas 67 -> 0, raiz 24 -> 0) e
    # nenhuma das verificacoes de `test_estudo_volume.py` disse nada, porque
    # todas barravam em direccao contraria. Ver `test_nenhuma_sub_pasta_desaparece`.
    try:
        base_anterior = json.loads(DESTINO.read_text(encoding="utf-8-sig"))
    except Exception:
        base_anterior = {}
    antes = base_anterior.get("ficheiros", 0)
    delta = atual["ficheiros"] - antes
    perdidos = [
        (chave, n)
        for chave, n in sorted(base_anterior.get("por_subpasta", {}).items())
        if n > 0 and atual["por_subpasta"].get(chave, 0) < n
    ]

    if not args.aceitar:
        print("=" * 70)
        print("O ESTUDO, AGORA")
        print("=" * 70)
        print(f"  ficheiros : {atual['ficheiros']:,}")
        print(f"  bytes     : {atual['bytes']:,}  ({atual['bytes'] / 1e6:.1f} MB)")
        print()
        print(f"  baseline  : {antes:,}  (delta {delta:+,})")
        if perdidos:
            print()
            print("  PERDIDOS face a baseline:")
            for chave, n in perdidos:
                agora = atual["por_subpasta"].get(chave, 0)
                print(f"    {chave:<28} {n:>7,} -> {agora:>7,}  ({agora - n:+,})")
            print()
            print("  Uma remocao tambem e' decisao. Aceitar exige razao escrita:")
            print('      python tests/estudo_volume.py --aceitar --porque "..."')
        print()
        print("  por sub-pasta:")
        for chave, n in sorted(atual["por_subpasta"].items(), key=lambda x: -x[1]):
            print(f"    {chave:<28} {n:>7,}")
        print()
        print("-" * 70)
        print("A MEDIDA QUE TEM DE PRECEDER QUALQUER ACEITAÇÃO")
        print("-" * 70)
        m = unicidade_de(unicidade_de_ficheiro())
        if m:
            print(f"  {UNICIDADE_EXEMPLO['ficheiro']}:")
            print(f"    linhas totais   {m['linhas_totais']:,}")
            print(f"    linhas unicas   {m['linhas_unicas']:,}")
            print(f"    unicidade       {m['unicidade']:.1%}")
        print()
        print("  237 MB de ficheiros que ninguem le nao sao conhecimento.")
        print("  Se o conteudo novo e' gerado, a taxa diz isso antes de")
        print("  alguem gastar um dia a ler.")
        print()
        print("  Para aceitar (so depois de medir a unicidade do que entra):")
        print('      python tests/estudo_volume.py --aceitar --porque "..."')
        return 0

    # ---- aceitar ----
    #
    # A recusa olha para `perdidos` (sub-pastas que ENCOLHERAM), e nao para o
    # delta liquido. MEDIDO 2026-10-04: a primeira versao desta guarda usava
    # `delta < 0`, e nao disparou nada — porque o total subiu (+659 em `v2/`)
    # enquanto 91 ficheiros desapareceram. O delta liquido e' exactamente o
    # numero que esconde uma remocao: uma pasta a crescer compensa uma pasta a
    # dying, e o total continua a subir. Foi assim que os 91 passaram sem
    # alarme, e foi assim que passariam outra vez com o codigo "corrigido".
    if perdidos and not args.porque.strip():
        print()
        print("=" * 70)
        print("A RECUSA")
        print("=" * 70)
        print(f"  A baseline tem {antes:,} ficheiros e hoje ha {atual['ficheiros']:,}.")
        print(f"  Delta liquido {delta:+,} — e' ele que MASCARRA o que interessa:")
        print("  sub-pastas que encolheram:")
        for chave, n in perdidos:
            agora = atual["por_subpasta"].get(chave, 0)
            print(f"    {chave:<28} {n:>7,} -> {agora:>7,}  ({agora - n:+,})")
        print()
        print("  Uma sub-pasta a crescer compensa uma sub-pasta a morrer, e o")
        print("  total continua a subir. Por isso a recusa olha para as que")
        print("  encolheram, e nao para o delta.")
        print()
        print("  Aceitar uma remocao sem razao escrita e' como os 91 ficheiros")
        print("  de `analises-profundas/` desapareceram sem ninguem notar.")
        print()
        print("  Duas saidas, e ambas sao legitimas:")
        print("    1. o conteudo volta (git, ou o galho de arquivo);")
        print("    2. a remocao e' certa e fica escrita:")
        print("         python tests/estudo_volume.py --aceitar \\")
        print('             --porque "movido para docs/arquivo/ em <commit>"')
        return 1

    print()
    print("=" * 70)
    print("A ACEITAR O VOLUME DE HOJE")
    print("=" * 70)
    if perdidos:
        print(
            f"  ATENCAO: {len(perdidos)} sub-pasta(s) encolheram. Delta liquido {delta:+,}."
        )
        print(f"  razao: {args.porque}")
        print("  esta razao fica escrita na baseline.")
    m = unicidade_de(unicidade_de_ficheiro())
    if m:
        print(f"  unicidade do exemplar: {m['unicidade']:.1%}")
        if m["unicidade"] < 0.5:
            print()
            print("  AVISO: o exemplar esta abaixo de 50% de unicidade.")
            print("  Aceitar volume com esta taxa e' o que produziu os 237 MB.")
            print("  Se o que entra e' do mesmo tipo, a resposta e' nao aceitar")
            print("  e reduzir o existente — e essa decisao e' do dono.")
    print()
    print(f"  a gravar: {atual['ficheiros']:,} ficheiros, {atual['bytes']:,} bytes")
    print()

    atual["unicidade_exemplo"] = {**UNICIDADE_EXEMPLO, **(m or {})}

    # A BASELINE E' UM LIVRO DE RAZÕES, NAO UMA FOTOGRAFIA.
    #
    # MEDIDO 2026-10-05 (agente 9). O `remocao_aceite` so era escrito quando
    # `perdidos` era verdade na ACEITAÇÃO. Mas `perdidos` compara com
    # `base_anterior["por_subpasta"]` — e depois de aceitar, as sub-pastas
    # removidas ja nao constam da baseline. Na seguinte aceitacao, `perdidos`
    # e' vazio e o registo **nunca mais volta a ser escrito**.
    #
    # O que aconteceu, medido: `HEAD:tests/estudo_baseline.json` diz
    # `{"(raiz)": 24, "analises-profundas": 67, "v2": 1321}`. A baseline de
    # hoje diz `{"v2": 1980}` e nao tem `remocao_aceite`. Ou seja: 91 ficheiros
    # de analise desapareceram, +659 entraram, e o ficheiro que existe para
    # dizer isso **esqueceu-se**. So o git guarda a prova — e o git nao e' o
    # lugar onde alguem vai procurar.
    #
    # A correccao e' de uma linha de ideia: o registo antigo passa para a
    # baseline nova. `remocoes_aceites` e' uma lista, e uma aceitacao nova
    # acrescenta em vez de substituir. A baseline passa a contar a sua propria
    # historia, que e' o unico jeito de "ninguem apaga sem deixar rasto" sobreviver
    # a um segundo `--aceitar`.
    historico = list(base_anterior.get("remocoes_aceites") or [])
    if isinstance(base_anterior.get("remocao_aceite"), dict):
        historico.append(base_anterior["remocao_aceite"])

    if perdidos and args.porque.strip():
        historico.append(
            {
                "ficheiros_antes": antes,
                "ficheiros_agora": atual["ficheiros"],
                "delta_liquido": delta,
                "porque": args.porque.strip(),
                "sub_pastas_que_encolheram": {
                    chave: [n, atual["por_subpasta"].get(chave, 0)]
                    for chave, n in perdidos
                },
            }
        )

    if historico:
        atual["remocoes_aceites"] = historico

    DESTINO.write_text(
        json.dumps(atual, indent=1, ensure_ascii=False), encoding="utf-8"
    )
    print(f"  escrito: {DESTINO}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
