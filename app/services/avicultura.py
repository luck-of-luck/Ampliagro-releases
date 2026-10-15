"""Avicultura — Lego / Big Brother / Moba (003/2400).

Lego 10d viabiliza 6,4 lotes/ano vs 5,4 alvenaria = +R$150k/aviário.
Big Brother 12 balanças prevê peso 95% vs 8% erro = +R$30k/lote.
Moba 30k/h + aveconfort 9,5% vs 15% = +R$99k.
"""


def lotes_por_ano(dias_engorda=42, dias_vazio=15, construcao_dias=10, tipo="lego"):
    ciclo = dias_engorda + dias_vazio
    # Lego 10d vs alvenaria 90d perde 80d = 1 lote
    perda_construcao = 80 if tipo == "alvenaria" else 0
    dias_uteis = 365 - perda_construcao
    lotes = dias_uteis / ciclo
    return {
        "ciclo_dias": ciclo,
        "lotes_ano": round(lotes, 2),
        "aves_ano": int(lotes * 25000),
        "receita_ano": round(lotes * 25000 * 6, 2),
        "ganho_vs_alvenaria": round((lotes - 5.4) * 25000 * 6, 2)
        if tipo == "lego"
        else 0,
    }


def big_brother_previsao(peso_dia35, balancas=12, erro_pct=2):
    # sem IA 10 aves dia 42 erro 8% → -200g
    peso_previsto = peso_dia35 * 1.18  # 2,8kg dia 42 / 2,37kg dia 35
    erro = erro_pct / 100 * peso_previsto
    return {
        "peso_dia35": peso_dia35,
        "peso_previsto_42d": round(peso_previsto, 2),
        "erro_kg": round(erro, 3),
        "balancas": balancas,
        "ganho_vs_sem_ia": round(0.2 * 25000 * 6, 2) if balancas >= 12 else 0,
    }


def moba_descarte(aves=100000, descarte_pct=9.5, moba=True, aveconfort_ok=True):
    descarte = descarte_pct if (moba and aveconfort_ok) else 15
    ovos = aves * 300 * (1 - descarte / 100)  # 300 ovos/ave/72 sem
    ovos_sem = aves * 300 * (1 - 15 / 100)
    ganho_ovos = ovos - ovos_sem
    return {
        "descarte_pct": descarte,
        "ovos_ano": int(ovos),
        "ganho_ovos": int(ganho_ovos),
        "ganho_R": round(ganho_ovos * 0.40, 2),
    }
