"""Hedge automático Soja Chicago (001/2400) — destrinchado 1-a-1.

O que a leitura 1-a-1 encontrou: produtor perde R$520k em 1000 ha se Chicago cai -5% (85→80) e não travou.
Este módulo recomenda hedge 50% e integra com simulacao.py via `hedge_recomendado` e `simular_com_hedge`.
"""


def hedge_recomendado(
    preco_chicago_atual, preco_trava, area_ha, produtividade_sc_ha, pct_travado=0.5
):
    """Retorna dict com R$ com vs sem hedge. Puro, determinístico."""
    preco_chicago_atual = float(preco_chicago_atual or 0)
    preco_trava = float(preco_trava or 0)
    area_ha = float(area_ha or 0)
    produtividade_sc_ha = float(produtividade_sc_ha or 0)
    pct = max(0, min(1, float(pct_travado or 0.5)))
    sc_total = produtividade_sc_ha * area_ha
    sc_travado = sc_total * pct
    sc_livre = sc_total - sc_travado
    # receita sem hedge = tudo ao preço atual
    receita_sem = sc_total * preco_chicago_atual
    # com hedge = travado ao preço trava + livre ao preço atual
    receita_com = sc_travado * preco_trava + sc_livre * preco_chicago_atual
    ganho = receita_com - receita_sem
    # queda %
    queda_pct = (
        (preco_trava - preco_chicago_atual) / preco_trava * 100 if preco_trava else 0
    )
    return {
        "preco_chicago_atual": preco_chicago_atual,
        "preco_trava": preco_trava,
        "queda_pct": round(queda_pct, 2),
        "pct_travado": pct,
        "sc_total": round(sc_total, 1),
        "sc_travado": round(sc_travado, 1),
        "receita_sem_hedge": round(receita_sem, 2),
        "receita_com_hedge": round(receita_com, 2),
        "ganho_hedge": round(ganho, 2),
        "ganho_ha": round(ganho / area_ha, 2) if area_ha else 0,
        # MEDIDO 2026-10-04: era a literal "TRAVAR 50% a R$145", com o preco
        # calculado `preco_trava` duas linhas acima. A recommendacao dizia um
        # numero que o resto do dict contradizia sempre que o preco mudava.
        # `docs/sistema/2.md` §2.2; a doutrina e' a de `proveniencia.py`: o
        # sistema nunca promove uma affirmacao a medicao.
        "recomendacao": f"TRAVAR 50% a R${preco_trava:.0f}"
        if ganho > 0
        else "NÃO travar (Chicago acima da trava)",
        "alerta": f"Chicago caiu {queda_pct:.1f}% ({preco_trava:.0f}→{preco_chicago_atual:.0f}), travar 50% evita R${ganho:,.0f} em {area_ha:.0f} ha"
        if ganho > 1000
        else "",
    }


def simular_com_hedge(base, preco_trava, pct_travado=0.5):
    """Enriquece `simular_lucro` com hedge: retorna lucro sem e com hedge."""
    from .simulacao import simular_lucro

    preco_atual = float(base.get("preco_sc", 0))
    area = float(base.get("area_ha", 0))
    prod = float(base.get("produtividade_sc_ha", 0))
    custo = float(base.get("custo_ha", 0))
    sem = simular_lucro(area, prod, preco_atual, custo)
    # com hedge: preço efetivo = pct*trava + (1-pct)*atual
    preco_efetivo = (
        pct_travado * float(preco_trava or preco_atual)
        + (1 - pct_travado) * preco_atual
    )
    com = simular_lucro(area, prod, preco_efetivo, custo)
    h = hedge_recomendado(
        preco_atual, float(preco_trava or preco_atual), area, prod, pct_travado
    )
    return {
        "sem_hedge": sem,
        "com_hedge": com,
        "preco_efetivo": round(preco_efetivo, 2),
        "hedge": h,
        "ganho_lucro": round(com["lucro"] - sem["lucro"], 2),
    }
