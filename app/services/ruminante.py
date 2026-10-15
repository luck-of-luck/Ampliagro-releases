"""Ruminante — pH rúmen e acidose (002/2400 Pecuária).

Leitura 1-a-1 (Pecuária 300 epis): boi perde 0,2 kg/d se pH <5,8 (acidose) = -12 kg em 60d = -R$180/boi.
Este serviço calcula pH estimado por dieta e recomenda tamponante, integrando com BovinoDigestao e IoT.
"""


def ph_rumen(fibra_pct, amido_pct, tamponante=False):
    """Estima pH rúmen 0-14. Fibra ↑ pH, amido ↓ pH. Tamponante +0,3."""
    fibra_pct = float(fibra_pct or 0)
    amido_pct = float(amido_pct or 0)
    # base 6,2 + 0,02*fibra -0,03*amido
    ph = 6.2 + 0.02 * fibra_pct - 0.03 * amido_pct
    if tamponante:
        ph += 0.3
    return round(max(4.5, min(7.5, ph)), 2)


def risco_acidose(ph):
    if ph < 5.5:
        return {
            "nivel": "ALTO",
            "perda_kg_d": 0.4,
            "acao": "PARAR amido, tamponante + fibra 40%",
        }
    if ph < 5.8:
        return {
            "nivel": "MÉDIO",
            "perda_kg_d": 0.2,
            "acao": "Reduzir amido 10%, tamponante",
        }
    if ph < 6.0:
        return {"nivel": "BAIXO", "perda_kg_d": 0.05, "acao": "Monitorar, fibra 35%"}
    return {"nivel": "OK", "perda_kg_d": 0, "acao": "Dieta OK"}


def simular_ganho(
    peso_kg, dias, ganho_kg_d_base, fibra_pct, amido_pct, tamponante=False
):
    ph = ph_rumen(fibra_pct, amido_pct, tamponante)
    risco = risco_acidose(ph)
    ganho_real = max(0, ganho_kg_d_base - risco["perda_kg_d"])
    peso_final = peso_kg + ganho_real * dias
    perda_total = risco["perda_kg_d"] * dias
    return {
        "ph": ph,
        "risco": risco,
        "ganho_kg_d_base": ganho_kg_d_base,
        "ganho_kg_d_real": round(ganho_real, 2),
        "peso_inicial": peso_kg,
        "peso_final": round(peso_final, 1),
        "perda_kg_total": round(perda_total, 1),
        "perda_R": round(perda_total * 15, 2),  # R$15/kg vivo
        "tamponante": tamponante,
    }


def recomendar_dieta(ph_atual, meta_ph=6.2):
    if ph_atual >= meta_ph:
        return {"acao": "Manter", "fibra_pct": 35, "amido_pct": 30}
    # precisa +fibra -amido: cada 1% fibra +0,02, cada 1% amido -0,03 → troca 1% amido por fibra = +0,05
    delta = meta_ph - ph_atual
    ajuste = max(5, int(delta / 0.05))
    return {
        "acao": f"+{ajuste}% fibra, -{ajuste}% amido, tamponante",
        "fibra_pct": 35 + ajuste,
        "amido_pct": 30 - ajuste,
        "tamponante": True,
    }
