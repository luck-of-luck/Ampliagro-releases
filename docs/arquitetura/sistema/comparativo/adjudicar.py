"""Le a linha de cada achado e obriga a adjudicar.

O `medir_ampliagro.py` da 43/50. Este ficheiro existe porque esse numero
**nao pode ser publicado**: `F14 Orcado x realizado` aponta para
`app/amplia_mcp/servidor.py:24`, que e' a descricao do servidor MCP, e
`M04 ISOBUS` aponta para `app/services/top_globais.py:23`, que e' o ficheiro
dos widgets **clonados**.

E' a mesma armadilha da §A.0 do `docs/sistema/9.md`: tres "OK" de palavras
que estavam em ficheiros de teste. Aqui sao palavras em codigo — o que e'
pior, porque parece mais confiancavel.

Regra: um `IMPL` so fica `CONFIRMADO` depois de a linha ser lida e de
responder a "isto e' implementacao, ou e' uma lista de nomes?".

Veredito possivel por linha:
  CONFIRMADO  — a linha e' codigo que produz a capacidade
  ENFRAQUECIDO — a linha existe mas nao prova a capacidade (campo, docstring,
                 constante, lista de marcas)
  FALSO        — a linha nao tem relacao com a capacidade
"""

from __future__ import annotations

import io
import pathlib

from medir_ampliagro import COLUNAS, MEDIDA, RAIZ, ficheiros

#: O que cada coluna exige de ver, para o veredicto ser CONFIRMADO. Se a
#: unica evidencia for uma docstring ou uma constante de nomes, e'
#: ENFRAQUECIDO — e a celula da planilha diz isso.
VEREDITOS: dict[str, str] = {}


def ler(ev: str) -> str:
    rel, _, ln = ev.rpartition(":")
    p = RAIZ / rel
    if not p.exists():
        return "(ficheiro nao existe)"
    with p.open(encoding="utf-8", errors="replace") as fh:
        linhas = fh.read().splitlines()
    n = int(ln)
    if n > len(linhas):
        return "(linha fora)"
    return linhas[n - 1].strip()


def vizinhos(ev: str, n: int = 2) -> list[str]:
    """As linhas acima — o contexto e' onde se ve se e' docstring."""
    rel, _, ln = ev.rpartition(":")
    p = RAIZ / rel
    with p.open(encoding="utf-8", errors="replace") as fh:
        linhas = fh.read().splitlines()
    i = int(ln) - 1
    return [x.strip() for x in linhas[max(0, i - n) : i]]


if __name__ == "__main__":
    import re

    from medir_ampliagro import procurar

    print("=" * 96)
    print("ADJUDICACAO — a linha de cada achado, lida antes de virar celula")
    print("=" * 96)

    for cid, _grupo, nome, _ in COLUNAS:
        padrao, globs, excluir = MEDIDA[cid]
        estado, ev = procurar(padrao, *globs, excluir=excluir)

        if estado == "FALTA":
            print(f"\n[c] {cid} {nome}")
            print("     FALTA — nenhum achado em codigo de execucao")
            VEREDITOS[cid] = "FALTA"
            continue

        linha = ler(ev)
        ctx = vizinhos(ev)

        # Heuristicas que NAO decidem: apenas assinalam para leitura.
        eh_docstring = any(
            re.match(r'^(r?["\']{3}|#:|"""|\'\'\')', c) for c in ctx
        ) or linha.startswith(('"""', "'''"))
        eh_comentario = linha.startswith("#")
        eh_descricao_mcp = "amplia_mcp/servidor.py" in ev
        eh_widgets_clonados = "top_globais.py" in ev
        eh_admin = "/admin.py" in ev or ev.startswith("app/admin.py")

        print(f"\n[{cid}] {nome}")
        print(f"     {ev}")
        print(f"     | {ascii(linha[:110])}")
        marcas = []
        if eh_docstring:
            marcas.append("DOCSTRING/COMENTARIO")
        if eh_comentario:
            marcas.append("COMENTARIO")
        if eh_descricao_mcp:
            marcas.append("DESCRICAO DO MCP")
        if eh_widgets_clonados:
            marcas.append("WIDGETS CLONADOS")
        if eh_admin:
            marcas.append("ADMIN")
        if marcas:
            print(f"     >>> {', '.join(marcas)}")
        VEREDITOS[cid] = "REVER"

    print()
    print("=" * 96)
    rever = [c for c, v in VEREDITOS.items() if v == "REVER"]
    falta = [c for c, v in VEREDITOS.items() if v == "FALTA"]
    print(f"  a adjudicar a mao : {len(rever)}  {rever}")
    print(f"  FALTA sem mais    : {len(falta)}  {falta}")
