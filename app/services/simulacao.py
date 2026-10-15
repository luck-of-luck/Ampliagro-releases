"""Motor de simulação agro (nível "melhores do mundo").

Tudo puro e determinístico (sem banco, sem HTTP): cenários otimista/base/
pessimista, ponto de equilíbrio, sensibilidade, Monte Carlo com seed,
financiamento PRICE/SAC e ranking de culturas. Usado pela API /api/simulacao/,
pela IA (intent simular_cenario) e pelas páginas de simulação.
"""

import random


def simular_lucro(area_ha, produtividade_sc_ha, preco_sc, custo_ha):
    area_ha = float(area_ha or 0)
    produtividade_sc_ha = float(produtividade_sc_ha or 0)
    preco_sc = float(preco_sc or 0)
    custo_ha = float(custo_ha or 0)
    receita = produtividade_sc_ha * area_ha * preco_sc
    custo = custo_ha * area_ha
    lucro = receita - custo
    return {
        "area_ha": area_ha,
        "produtividade_sc_ha": produtividade_sc_ha,
        "preco_sc": preco_sc,
        "custo_ha": custo_ha,
        "receita": round(receita, 2),
        "custo": round(custo, 2),
        "lucro": round(lucro, 2),
        "lucro_ha": round(lucro / area_ha, 2) if area_ha else 0,
        "margem_pct": round(lucro / receita * 100, 1) if receita else 0,
    }


def cenarios(base, pessimista=0.8, otimista=1.2):
    """3 cenários variando produtividade e preço juntos."""
    out = {}
    for nome, fator in (
        ("pessimista", pessimista),
        ("base", 1.0),
        ("otimista", otimista),
    ):
        out[nome] = simular_lucro(
            base.get("area_ha", 0),
            base.get("produtividade_sc_ha", 0) * fator,
            base.get("preco_sc", 0) * fator,
            base.get("custo_ha", 0),
        )
    return out


def ponto_equilibrio(custo_ha, preco_sc):
    """Produtividade mínima (sc/ha) e preço mínimo p/ não ter prejuízo."""
    custo_ha = float(custo_ha or 0)
    preco_sc = float(preco_sc or 0)
    return {
        "produtividade_equilibrio_sc_ha": round(custo_ha / preco_sc, 1)
        if preco_sc
        else None,
        "custo_ha": custo_ha,
        "preco_sc": preco_sc,
    }


def sensibilidade(base, variavel, valores):
    """Tabela lucro variando um parâmetro (produtividade_sc_ha, preco_sc, custo_ha)."""
    if variavel not in ("produtividade_sc_ha", "preco_sc", "custo_ha"):
        raise ValueError(
            "variável inválida (use produtividade_sc_ha, preco_sc, custo_ha)"
        )
    linhas = []
    for v in valores:
        p = dict(base)
        p[variavel] = v
        r = simular_lucro(
            p.get("area_ha", 0),
            p.get("produtividade_sc_ha", 0),
            p.get("preco_sc", 0),
            p.get("custo_ha", 0),
        )
        linhas.append({"valor": v, "lucro": r["lucro"], "margem_pct": r["margem_pct"]})
    return linhas


def monte_carlo(base, n=1000, seed=42, var_prod=0.15, var_preco=0.12):
    """Distribuição do lucro com ruído gaussiano (seed = reproduzível)."""
    rng = random.Random(seed)
    lucros = []
    for _ in range(max(1, int(n))):
        p = dict(base)
        p["produtividade_sc_ha"] = max(
            0,
            rng.gauss(
                base.get("produtividade_sc_ha", 0),
                base.get("produtividade_sc_ha", 0) * var_prod,
            ),
        )
        p["preco_sc"] = max(
            0, rng.gauss(base.get("preco_sc", 0), base.get("preco_sc", 0) * var_preco)
        )
        lucros.append(
            simular_lucro(
                p.get("area_ha", 0),
                p["produtividade_sc_ha"],
                p["preco_sc"],
                p.get("custo_ha", 0),
            )["lucro"]
        )
    lucros.sort()

    def pct(q):
        i = min(len(lucros) - 1, max(0, int(q * len(lucros))))
        return lucros[i]

    return {
        "n": len(lucros),
        "media": round(sum(lucros) / len(lucros), 2),
        "p10": round(pct(0.10), 2),
        "p50": round(pct(0.50), 2),
        "p90": round(pct(0.90), 2),
        "prob_lucro_pct": round(sum(1 for x in lucros if x > 0) / len(lucros) * 100, 1),
    }


def financiamento(valor, taxa_mes_pct, meses, sistema="price"):
    """Parcelas PRICE ou SAC. Retorna parcela(s), total e juros."""
    valor = float(valor or 0)
    i = float(taxa_mes_pct or 0) / 100
    n = max(1, int(meses or 1))
    sistema = (sistema or "price").lower()
    if sistema == "sac":
        amort = valor / n
        saldo, parcelas, juros_total = valor, [], 0
        for _ in range(n):
            j = saldo * i
            juros_total += j
            parcelas.append(round(amort + j, 2))
            saldo -= amort
        return {
            "sistema": "sac",
            "parcelas": parcelas,
            "primeira": parcelas[0],
            "ultima": parcelas[-1],
            "total": round(sum(parcelas), 2),
            "juros_total": round(juros_total, 2),
        }
    if i <= 0:
        p = round(valor / n, 2)
        return {
            "sistema": "price",
            "parcela": p,
            "total": round(p * n, 2),
            "juros_total": round(p * n - valor, 2),
        }
    p = valor * i / (1 - (1 + i) ** -n)
    return {
        "sistema": "price",
        "parcela": round(p, 2),
        "total": round(p * n, 2),
        "juros_total": round(p * n - valor, 2),
    }


def ranking_culturas(area_ha, opcoes):
    """Compara culturas: [{cultura, produtividade_sc_ha, preco_sc, custo_ha}]."""
    linhas = []
    for op in opcoes or []:
        r = simular_lucro(
            area_ha,
            op.get("produtividade_sc_ha", 0),
            op.get("preco_sc", 0),
            op.get("custo_ha", 0),
        )
        r["cultura"] = op.get("cultura", "?")
        linhas.append(r)
    linhas.sort(key=lambda r: r["lucro"], reverse=True)
    return linhas


# 001 — Hedge automático (Soja Chicago) — exposto aqui para API /api/simulacao/?tipo=hedge
def hedge(*args, **kwargs):
    """Proxy para app.services.hedge.hedge_recomendado (evita import circular no topo)."""
    from .hedge import hedge_recomendado as _h

    return _h(*args, **kwargs)


# 002 — Ruminante pH (Pecuária) — exposto para API /api/simulacao/?tipo=ruminante
def ruminante(*args, **kwargs):
    """Proxy para app.services.ruminante.simular_ganho."""
    from .ruminante import simular_ganho as _r

    return _r(*args, **kwargs)


# 003 — Avicultura (Lego/Big Brother/Moba) — API tipo=avicultura
def avicultura(*args, **kwargs):
    from .avicultura import lotes_por_ano as _a

    return _a(*args, **kwargs)
