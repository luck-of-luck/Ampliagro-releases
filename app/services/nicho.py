"""Nicho Pet/Orquídea — 010/2400 — Rosella R$1.200 vs calopsita R$80 +15×, Orquídea 7a R$400."""


def pet_exotico(preco, custo, dias):
    margem = preco - custo
    margem_dia = margem / dias if dias else 0
    return {
        "margem": margem,
        "margem_dia": round(margem_dia, 2),
        "ganho_vs_convencional": round(preco / 80, 1) if preco else 0,
    }
