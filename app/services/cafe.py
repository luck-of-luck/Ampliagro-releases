"""Café Especial 270d — 005/2400 — Rainforest 86 pts + Camocim biodinâmico."""


def rainforest(prod_sc_ha=60, preco_sc=1400, sequeiro=False):
    sc = prod_sc_ha if not sequeiro else 30
    receita = sc * preco_sc
    pts = 86 if not sequeiro else 78
    return {
        "prod_sc_ha": sc,
        "pontos": pts,
        "receita_ha": receita,
        "ganho_vs_sequeiro": (prod_sc_ha - 30) * preco_sc if not sequeiro else 0,
    }


def biodinamico(pontos_base=78, preco_base=1000):
    # 500+501 +8 pontos
    pontos = pontos_base + 8
    preco = preco_base + 400
    return {"pontos": pontos, "preco_sc": preco, "ganho_sc": 400}
