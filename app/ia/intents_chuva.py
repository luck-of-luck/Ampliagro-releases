"""Chuva da semana em NÚMEROS + série para gráfico.

O QUE ESTE MÓDULO É
===================
O `vai_chover` responde "hoje/amanhã" em prosa; o `previsao_estendida`
responde 3 dias em prosa. Nenhum dos dois entrega SÉRIE — e sem série não
há gráfico, e sem gráfico o modo "Criar no chat" continua a prometer peça
e a entregar parágrafo. Este intent responde a semana (7 dias, até 14) em
prosa E em `dados.serie`, no contrato que o cliente desenha sozinho:

    serie = {
        "titulo": str, "rotulo": str, "colunas": ["dia", "mm"],
        "linhas": [[rotulo_dia, mm], ...],
        "fonte": "chuva-semana", "filtros": {"dias": N},
    }

O `fonte` diz qual fonte do `chamado_fontes` recalcula a série — é o que
permite ao sandbox compor a peça do dashboard sem confiar nos números que
viajam: `aplicar_fontes` recalcula e carimba MEDIDO.

SOBRE O None
============
`mm` ausente NÃO vira 0.0: soma inexistente não é soma zero, e um zero
desenhado onde a fonte calou é "sem chuva" dito sem prova. O dia sai da
série; se sobrarem menos de 2 dias, não há série (prosa honesta em vez de
gráfico vazio).
"""

from __future__ import annotations

from datetime import date
from typing import Any

from app.ia.propriedade import resolver as _prop_chuva

DIAS_PADRAO = 7
DIAS_MAXIMO = 14
#: mm a partir do qual o dia "chove" na prosa. Garoa (<0,5) não decide dia.
MM_CHOVE = 0.5

_DIA_SEMANA_PT = ["seg", "ter", "qua", "qui", "sex", "sáb", "dom"]


def rotulo_dia(iso: str | None) -> str:
    """'2026-10-14' -> 'qua 14/10'. Sem locale: mapa próprio.

    O `locale` do servidor é o do servidor, não o do produtor — e um dia
    "Wednesday" no meio da frase portuguesa é ruído. Sete strings fixas
    não dependem de nada instalado.
    """
    s = str(iso or "")
    try:
        d = date.fromisoformat(s[:10])
        return f"{_DIA_SEMANA_PT[d.weekday()]} {d.day:02d}/{d.month:02d}"
    except (ValueError, TypeError):
        return s[5:] or s


def serie_de(dias_previstos) -> tuple[list, int]:
    """(linhas, ausentes) de [[rotulo, mm]] a partir de `obter_previsao`.

    Pura e sem rede: recebe os dias e devolve a forma do gráfico. É a mesma
    função que o intent e a fonte usam — duas formatações da mesma série
    divergiriam no primeiro dia em que uma delas mudasse.
    """
    linhas: list = []
    ausentes = 0
    for d in dias_previstos or []:
        d = d or {}
        mm = d.get("mm")
        if mm is None:
            ausentes += 1
            continue
        try:
            mm = round(float(mm), 1)
        except (TypeError, ValueError):
            ausentes += 1
            continue
        linhas.append([rotulo_dia(d.get("dia")), mm])
    return linhas, ausentes


def h_chuva_semana(user, params, ctx):
    """Vai chover ESSA SEMANA? Sim/não + quando + série dias×mm."""
    prop = _prop_chuva(user, params)
    if not prop:
        return {"ok": False, "erro": "nenhuma propriedade encontrada"}
    dias = DIAS_PADRAO
    try:
        dias = max(1, min(int((params or {}).get("dias") or DIAS_PADRAO), DIAS_MAXIMO))
    except (TypeError, ValueError):
        dias = DIAS_PADRAO
    from app.ia.proativo import obter_previsao

    prev = obter_previsao(user, prop, dias=dias)
    if not prev.get("ok"):
        motivo = prev.get("motivo") or "indisponível"
        return {
            "ok": False,
            "erro": (
                f"previsão indisponível ({motivo}). "
                "Cadastre cidade/UF ou estação na propriedade."
            ),
        }
    dias_prev = prev.get("dias") or []
    linhas, ausentes = serie_de(dias_prev)
    if len(linhas) < 2:
        return {
            "ok": True,
            "resposta": (
                f"A fonte respondeu, mas sem milímetros aproveitáveis para os "
                f"próximos {dias} dias em {prop.nome}. Não vou desenhar "
                f"gráfico sem número."
            ),
            "dados": {"propriedade": prop.nome, "dias": dias, "sem_dado": "mm"},
            "artefato": (f"chuva-semana/{prop.id}", "clima"),
        }
    com_chuva = [(rot, mm) for rot, mm in linhas if mm >= MM_CHOVE]
    total = round(sum(mm for _, mm in linhas), 1)
    maior = max(linhas, key=lambda p: p[1])
    rotulos = ", ".join(rot for rot, _ in com_chuva)
    if com_chuva:
        resposta = (
            f"Sim, chove em {len(com_chuva)} de {len(linhas)} dias "
            f"({rotulos}): maior volume {maior[1]:g} mm em {maior[0]}, "
            f"total {total:g} mm em {prop.nome}."
        )
    else:
        resposta = (
            f"Não há chuva relevante nos próximos {len(linhas)} dias em "
            f"{prop.nome} (máximo {maior[1]:g} mm em {maior[0]})."
        )
    if ausentes:
        resposta += f" ({ausentes} dia(s) sem medição ficaram fora do gráfico.)"
    return {
        "ok": True,
        "resposta": resposta,
        "dados": {
            "propriedade": prop.nome,
            "dias": dias,
            "serie": {
                "titulo": f"Chuva prevista por dia (mm) — {prop.nome}",
                "rotulo": "mm",
                "colunas": ["dia", "mm"],
                "linhas": linhas,
                "fonte": "chuva-semana",
                "filtros": {"dias": dias},
            },
        },
        "artefato": (f"chuva-semana/{prop.id}", "clima"),
    }


INTENTS_CHUVA = {
    "chuva_semana": {
        "descricao": (
            "INSTRUÇÃO IA: use para 'vai chover ESSA SEMANA', 'chuva nos "
            "próximos 7 dias', 'quantos mm por dia'. NÃO use para hoje/amanhã "
            "(isso é vai_chover). Devolve a resposta em prosa E a série "
            "dias×mm em `dados.serie` para o gráfico."
        ),
        "exemplos": [
            "vai chover essa semana",
            "previsão de chuva para os próximos 7 dias",
            "quantos mm de chuva essa semana",
            "chove quais dias essa semana",
            "chuva dia a dia",
            "gráfico de chuva da semana",
        ],
        "flags": ["clima.read"],
        "handler": h_chuva_semana,
    },
}
