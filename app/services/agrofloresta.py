"""Agrofloresta/Mombak/Eucalipto/Forragem — 007/2400 — 42d-7 anos R$6bi."""


def agrofloresta_7a(cafe_sc_ha=40, preco_cafe=1400, mogno_m3_ha=100, preco_mogno=2000):
    receita_cafe_7a = cafe_sc_ha * preco_cafe * 7
    receita_mogno = mogno_m3_ha * preco_mogno
    return {
        "receita_7a": receita_cafe_7a + receita_mogno,
        "ganho_vs_monocultivo_pct": 33,
    }


def biomassa_eucalipto(m3_ha=100, preco_m3=80):
    return {"receita_ha": m3_ha * preco_m3, "ganho_vs_5a": (100 - 70) * preco_m3}
