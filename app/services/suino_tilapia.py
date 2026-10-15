"""Suíno+Tilápia+Ostra (004/2400) — 240 epis — R$200bi.

Suíno 180d biodigestor, Tilápia mormaco 100 pele R$400/m² (+566% vs carne), Ostra Primar salinidade 35.
"""


def suino_biodigestor(cabecas, peso_kg=120, preco_kg=8.2, biogas_m3_dia=2.5):
    receita = cabecas * peso_kg * preco_kg
    energia_kwh = biogas_m3_dia * cabecas * 1.8  # 1 m3 biogás ~1,8 kWh
    economia_energia = energia_kwh * 30 * 0.85  # 30 dias * R$0,85/kWh
    return {
        "receita_suino": round(receita, 2),
        "energia_kwh_mes": round(energia_kwh * 30, 1),
        "economia_R_mes": round(economia_energia, 2),
    }


def tilapia_pele(
    alevinos,
    peso_kg=1,
    preco_carne=12,
    preco_pele_m2=400,
    m2_por_peixe=0.2,
    mormaco=False,
):
    biomassa = alevinos * peso_kg * (0.95 if not mormaco else 0.90)
    receita_carne = biomassa * preco_carne
    receita_pele = (
        alevinos * (0.95 if not mormaco else 0.90) * m2_por_peixe * preco_pele_m2
    )
    perda_mormaco = alevinos * 0.05 * peso_kg * preco_carne if mormaco else 0
    return {
        "biomassa_kg": round(biomassa, 1),
        "receita_carne": round(receita_carne, 2),
        "receita_pele": round(receita_pele, 2),
        "ganho_pele_vs_carne_pct": round(receita_pele / receita_carne * 100 - 100, 1)
        if receita_carne
        else 0,
        "perda_mormaco_R": round(perda_mormaco, 2),
    }


def ostra_primar(unidades, peso_g=80, preco_un=2.0, salinidade=35, organico=True):
    fator = 1.0 if (salinidade == 35 and organico) else 0.6
    receita = unidades * preco_un * fator
    return {"receita": round(receita, 2), "fator_qualidade": fator, "peso_g": peso_g}
