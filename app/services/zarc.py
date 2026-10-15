"""Aviso de ZARC: a lavoura está dentro da janela de plantio oficial?

## O problema

Pela cadeia da Lei 15.526/2026 e das condições da MAPFRE (§11 da análise), um
produtor que planta **fora do Zoneamento Agrícola de Risco Climático (ZARC)**
pode ter a indenização **indeferida**. O ZARC é requisito, não recomendação.

O Ampliagro tem as duas peças e elas não se conhecem:

- `ZARC` (`app/models/producao.py:217`) — a janela oficial, por cultura, UF e
  município, com ciclo e risco climático;
- `Propriedade.uf` / `.cidade` (`app/models/core.py:74-75`) — onde a fazenda
  está;
- `Safra.cultura` + a data de plantio — o que o produtor fez.

O que faltava era a **junção**, e é isto. Não é um modelo novo nem uma
integração com seguradora: é uma função que junta o que já existe.

## Por que isto é o item mais urgente da lista

De todos os gaps que auditei, é o único em que a **ausência custa dinheiro ao
produtor** — e não apenas tempo. Todo o resto é feature faltando (NF-e,
carbono, ISOBUS). Este é um produtor que perde a indenização de um ano
porque ninguém lhe disse.

## O contrato — igual ao do resto do repo

- `"dentro_da_janela": True` quando há ZARC e a data cai dentro.
- `"dentro_da_janela": None` quando **não há ZARC carregado** para a
  geografia — e vem `motivo`. **Nunca `False` por ausência de dado**: `False`
  significa "fora da janela", que é um diagnóstico; "não temos o ZARC desta
  UF" é ausência. Confundir os dois faria o sistema acusar um produtor de
  algo que ele não praticou.
- O mesmo vale para a comparação: sem data de plantio, não há veredito — e o
  motivo diz qual dos dois faltou.
"""

from __future__ import annotations

from datetime import date

from app.models.core import Propriedade
from app.models.producao import ZARC
from app.models.safra import Safra


def _estado(valor, **extra):
    """Monta um veredito com a forma que o resto do repo usa.

    `None` no valor + `motivo` é o par de ausência. `True`/`False` só quando
    há comparação feita.
    """
    saida = {"dentro_da_janela": valor, "motivo": None}
    saida.update(extra)
    return saida


def zarc_para_propriedade(propriedade_id: int, cultura_id: int):
    """O ZARC aplicável a esta propriedade+cultura, ou `None`.

    Filtra por UF e município. `cidade` é `blank=True` no model, e sem
    município não dá para escolher entre janelas diferentes do mesmo estado —
    por isso devolvemos `None` em vez de adivinhar.
    """
    prop = Propriedade.objects.filter(pk=propriedade_id).first()
    if prop is None:
        return None
    if not prop.cidade:
        return None

    return (
        ZARC.objects.filter(
            cultura_id=cultura_id, uf=prop.uf, municipio__iexact=prop.cidade
        )
        .order_by("data_inicio_plantio")
        .first()
    )


def verificar_safra(safra_id: int) -> dict:
    """A safra deste produtor está dentro da janela ZARC?

    Devolve sempre as quatro coisas que tornam a resposta auditável: o que foi
    comparado, com que ZARC, e o que faltou se faltou.
    """
    safra = (
        Safra.objects.filter(pk=safra_id)
        .select_related("propriedade", "cultura")
        .first()
    )
    if safra is None:
        return {
            "safra_id": safra_id,
            **_estado(None),
            "motivo": "safra não encontrada",
        }

    base = {
        "safra_id": safra.id,
        "ano": safra.ano,
        "cultura": safra.cultura.nome if safra.cultura_id else None,
        "propriedade_id": safra.propriedade_id,
        "uf": safra.propriedade.uf if safra.propriedade_id else None,
        "municipio": safra.propriedade.cidade if safra.propriedade_id else None,
    }

    # 1. Sem geografia, não há ZARC aplicável. E a culpa é de cadastro, não
    #    do produtor: o motivo diz isso.
    if not safra.propriedade_id or not safra.propriedade.cidade:
        return {
            **base,
            **_estado(None),
            "motivo": (
                "propriedade sem município preenchido: não há como escolher a "
                "janela ZARC deste local. Preencha a cidade da propriedade."
            ),
        }

    # 2. Sem cultura, não há ZARC.
    if not safra.cultura_id:
        return {
            **base,
            **_estado(None),
            "motivo": "safra sem cultura registada: o ZARC é definido por cultura",
        }

    # 3. O ZARC pode simplesmente não estar carregado para esta geografia.
    zarc = zarc_para_propriedade(safra.propriedade_id, safra.cultura_id)
    if zarc is None:
        return {
            **base,
            **_estado(None),
            "motivo": (
                f"não há ZARC carregado para {safra.propriedade.uf}/"
                f"{safra.propriedade.cidade} nesta cultura. Não é resposta: "
                "é ausência de dado, e nada se pode afirmar sobre a "
                "indemnização sem ele."
            ),
        }

    # 4. Falta a data de plantio — sem ela não há o que comparar.
    data_plantio = getattr(safra, "data_plantio", None)
    if data_plantio is None:
        return {
            **base,
            **_estado(None),
            "zarc_id": zarc.id,
            "janela": {
                "inicio": str(zarc.data_inicio_plantio),
                "fim": str(zarc.data_fim_plantio),
            },
            "motivo": (
                "safra sem data de plantio registada: não há o que comparar "
                f"com a janela {zarc.data_inicio_plantio}.."
                f"{zarc.data_fim_plantio}."
            ),
        }

    dentro = zarc.data_inicio_plantio <= data_plantio <= zarc.data_fim_plantio
    dias_fora = 0
    if not dentro:
        dias_fora = (
            (data_plantio - zarc.data_fim_plantio).days
            if data_plantio > zarc.data_fim_plantio
            else (zarc.data_inicio_plantio - data_plantio).days
        )

    return {
        **base,
        **_estado(dentro),
        "zarc_id": zarc.id,
        "data_plantio": str(data_plantio),
        "janela": {
            "inicio": str(zarc.data_inicio_plantio),
            "fim": str(zarc.data_fim_plantio),
        },
        "ciclo_dias": zarc.ciclo_dias,
        "risco_climatico": float(zarc.risco_climatico),
        "dias_fora_da_janela": dias_fora,
        "aviso": (
            None
            if dentro
            else (
                "Plantio fora da janela ZARC. Pela regra de zoneamento, a "
                "indemnização pode ser indeferida — confirme com a seguradora "
                "antes da colheita."
            )
        ),
    }


def verificar_propriedade(propriedade_id: int) -> list[dict]:
    """Todas as safras da propriedade, com o veredito de cada uma.

     É a vista que o produtor quer: não "a sua fazenda tem um problema", mas
     "**esta** lavoura está fora da janela, e foi **há N dias**".

     Sem parâmetro "hoje" de propósito: o veredito é sobre a **data de plantio
     da safra**, não sobre o dia de hoje. Uma safra de 2025 continua dentro da
     janela de 2025 em 2027 — e um `hoje` aqui seria um parâmetro que parece
    influir e não influencia.
    """
    safras = (
        Safra.objects.filter(propriedade_id=propriedade_id)
        .select_related("cultura", "propriedade")
        .order_by("-ano")
    )
    return [verificar_safra(s.id) for s in safras]


def safras_fora_da_janela(propriedade_id: int) -> list[dict]:
    """Só as safras com veredito `False`.

    **Não inclui as que não têm veredito.** Uma safra sem ZARC carregado não
    está "dentro" nem "fora" — e listá-la como risco seria acusar o produtor de
    algo que o sistema não sabe.
    """
    return [
        v
        for v in verificar_propriedade(propriedade_id)
        if v["dentro_da_janela"] is False
    ]
