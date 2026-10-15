"""Filtra a descoberta: so os achados que resistem a leitura.

O bruto deu 375 celulas. A maioria e' ruido de substring — 'map' dentro de
'roadmap', 'OTA' dentro de 'TOTAL'. Este script aplica tres filtros e mostra o
que sobra, para que a decisao de escrever no registo seja humana.

Filtros
    1. o fragmento e' uma FRASE (tem espaco)? -> quase sempre e' citacao real
    2. o fragmento e' um ACRONIMO curto? -> so passa com contagem >= 3
    3. o resto? -> so passa com contagem >= 5

O resultado NAO escreve no registo.
"""

from __future__ import annotations

import json
import pathlib
import re
import sys

BASE = pathlib.Path(__file__).parent
sys.path.insert(0, str(BASE))

from descobrir_em_massa import CANDIDATOS  # noqa: E402
from verificar_evidencia import contar_fragmento, textos  # noqa: E402

if __name__ == "__main__":
    alvos = json.loads((BASE / "paginas_alcancaveis.json").read_text(encoding="utf-8"))
    tx = textos(list(alvos.values()), usar_cache=True)

    fortes, medio = [], []
    for produto, url in alvos.items():
        estado, t = tx.get(url, ("SEM ACESSO", ""))
        if estado != "OK" or len(t) < 400:
            continue
        for cid, cands in CANDIDATOS.items():
            melhor, n = "", 0
            for c in cands:
                k = contar_fragmento(t, c)
                if k > n:
                    melhor, n = c, k
            if not n:
                continue
            e_frase = " " in melhor
            e_acronimo = len(_ := melhor) <= 4
            if e_frase and n >= 1:
                fortes.append((produto, cid, melhor, n))
            elif e_acronimo and n >= 3 or n >= 5:
                medio.append((produto, cid, melhor, n))

    print("=" * 84)
    print(f"FRASES (forte) — {len(fortes)} celulas")
    print("=" * 84)
    atual = ""
    for prod, cid, frag, n in fortes:
        if prod != atual:
            print(f"\n  {prod}")
            atual = prod
        print(f"    {cid}  {frag!r} x{n}")

    print()
    print("=" * 84)
    print(f"ACRONIMOS/OUTROS (media) — {len(medio)} celulas")
    print("=" * 84)
    atual = ""
    for prod, cid, frag, n in medio:
        if prod != atual:
            print(f"\n  {prod}")
            atual = prod
        print(f"    {cid}  {frag!r} x{n}")

    print()
    print(f"  forte {len(fortes)} + medio {len(medio)} = {len(fortes) + len(medio)}")
    print("  As 'fortes' sao as que entrou no registo. As 'media' precisam de leitura.")
