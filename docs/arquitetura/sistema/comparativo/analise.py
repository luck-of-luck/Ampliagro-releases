"""Onde o Ampliagro esta sozinho, e onde perde."""

import pathlib
import sys
from collections import Counter

sys.path.insert(0, str(pathlib.Path(__file__).parent))

from concorrentes import CONCORRENTES
from evidencia import EVIDENCIA
from medir_ampliagro import COLUNAS
from vereditos import VEREDITOS

sozinho, perde, para_ninguem = [], [], []

for cid, grupo, nome, _ in COLUNAS:
    # Um produto conta uma vez. A versao anterior usava dois comprehension
    # separados e imprimia "Aegro, Aegro" — o que parece duas empresas.
    leaders: list[str] = []
    parcial: list[str] = []
    for n, *_ in CONCORRENTES:
        reg = EVIDENCIA.get((n, cid))
        if not reg or reg[3] not in ("F", "D") or n in leaders:
            continue
        leaders.append(n)
        if (reg[4] or "").strip():
            parcial.append(n)
    est = VEREDITOS[cid][0]
    if est in ("C", "E") and not leaders:
        sozinho.append((cid, grupo, nome, est, parcial))
    elif est == "N" and (leaders or parcial):
        perde.append((cid, nome, leaders, parcial))
    elif est == "N" and not leaders and not parcial:
        para_ninguem.append((cid, nome))

print("=" * 78)
print("1. ONDE O AMPLIaGRO TEM E NENHUM CONCORRENTE TEM EVIDENCIA")
print("=" * 78)
for cid, _grupo, nome, est, parcial in sozinho:
    extra = (
        f"  (parcial em {len(parcial)}: {', '.join(parcial[:3])})" if parcial else ""
    )
    print(f"  {cid} [{est}] {nome[:46]:48}{extra}")
print(f"\n  TOTAL: {len(sozinho)} de 50")

print()
print("=" * 78)
print("2. ONDE O AMPLIaGRO NAO TEM E O MERCADO TEM")
print("=" * 78)
for cid, nome, leaders, _parcial in perde:
    print(f"  {cid} {nome[:38]:40} <- {len(leaders)}: {', '.join(leaders[:4])}")
print(f"\n  TOTAL: {len(perde)} de 50")

print()
print("=" * 78)
print("3. ONDE NINGUEM TEM EVIDENCIA")
print("=" * 78)
for cid, nome in para_ninguem:
    print(f"  {cid} {nome}")
print(f"\n  TOTAL: {len(para_ninguem)} de 50")

print()
print("=" * 78)
print("RESUMO")
print("=" * 78)
print("  Ampliagro:", dict(Counter(v[0] for v in VEREDITOS.values())))
cobertura = sum(
    1 for n, *_ in CONCORRENTES if any(EVIDENCIA.get((n, c[0])) for c in COLUNAS)
)
print(f"  concorrentes com pelo menos uma celula com fonte: {cobertura}/100")
print(f"  celulas com fonte: {len(EVIDENCIA)} de {len(CONCORRENTES) * len(COLUNAS)}")
