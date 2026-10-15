"""Laranja greening/CVC — 006/2400 — 180d + 15 anos pomar."""


def perda_greening(incidencia_pct, produtividade_sc_ha=400):
    perda = incidencia_pct * 0.25  # 25% perda se 100% incidência
    return {
        "perda_sc_ha": round(produto := produtividade_sc_ha * perda, 1),
        "perda_R_ha": round(produto * 35, 2),
    }


def manejo_doenca(fibra_pct=35):
    # DoencaLaranja already in model, here service layer
    return {
        "acao": "poda 30% + psilideo 15d + chuva 20mm alerta",
        "reducao_perda": "35% -> 5%",
    }
