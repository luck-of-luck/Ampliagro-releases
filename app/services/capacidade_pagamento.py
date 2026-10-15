"""Capacidade de pagamento — os dados que um banco pede e que ninguém tinha.

## O problema que este módulo resolve

O `E-agro` do Bradesco (§10 da análise competitiva) decide crédito rural com
"dados comportamentais e **agronômicos**". O Ampliagro **tem** esses dados:
custo por hectare, histórico de safras, receitas e despesas.

Até agora não havia forma de os entregar. Este módulo é essa forma — e a
decisão de arquitectura que o acompanha é a mesma do §21.3 da análise: **não
concorrer com o banco, ser a fonte auditável que o banco consulta.**

## O que este módulo NÃO faz

**Não decide crédito.** Não há score, não há "aprovado", não há "reprovado".

Um sistema de gestão que emite uma opinião sobre a capacidade de pagamento de
um produtor está a fazer algo que não pode medir. Este módulo entrega
**factores observáveis**, com a fonte de cada um, e deixa a decisão para quem
tem o dinheiro e a regulação. O que ele faz é tornar a decisão *auditável* —
que é o que um auditor de crédito pede primeiro.

## A regra que este módulo aplica

Vem de `proveniencia.py` e `cotacoes.py`, não de mim:

- Um número entra no payload **com a fonte que o produziu**.
- Quando não há dado, o número é `None` e vem o **motivo** — nunca um valor
  inventado. `proveniencia.py:99-105`: "Sem dado" sem motivo obriga o produtor
  a adivinhar o que falta, e adivinhar mal num painel é pior do que não ter
  nada.

Isto é diferente de um dashboard, e a diferença é o ponto: **aqui o "não sei"
é o valor mais importante do payload.** Um factor ausente que se lê como "0"
ou "baixo" pode custar ao produtor um crédito que ele pagava.

## Por que isto não é uma feature

Um dashboard mostra o que já está no banco. Isto **agrega safras** que o
produtor tem mas ninguém relationou, e o resultado é um histórico de custo por
hectare que **ninguém** tem hoje — nem o produtor (que usa o sistema há uma
safra), nem o banco (que pede três anos de histórico e recebe uma planilha).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.db.models import Q, Sum

from app.models.core import Propriedade
from app.models.financeiro import LancamentoFinanceiro
from app.models.safra import Safra
from app.services.custo_producao import calcular_custo_producao


def _f(valor):
    """Decimal -> float; `None` fica `None`.

    Wrapper explícito para tornar o ponto visível: a conversão nunca transforma
    ausência em número. `Decimal(str(None))` levantaria `InvalidOperation` —
    que é uma protecção, não um acidente.
    """
    return None if valor is None else float(valor)


def historico_safras(propriedade_id: int) -> list[dict]:
    """Cada safra da propriedade, com o custo por hectare quando existe.

    Só safras com `ano` **válido** entram. `ano` é NOT NULL no model
    (`models/safra.py:52`), então a defesa real não é `isnull` — é `ano > 0`.
    Uma safra de "ano 0" passa pelo banco e chegaria aqui como um ano que não
    existe, e uma safra de 2026 não pode ser comparada com ela.
    """
    qs = (
        Safra.objects.filter(propriedade_id=propriedade_id, ano__gt=0)
        .select_related("cultura")
        .order_by("-ano")
    )

    serie = []
    for s in qs:
        custo = calcular_custo_producao(s.id)
        serie.append(
            {
                "safra_id": s.id,
                "ano": s.ano,
                "cultura_id": s.cultura_id,
                "cultura": s.cultura.nome if s.cultura_id else None,
                "custo_por_hectare": custo.get("custo_por_hectare"),
                "custo_total": custo.get("custo_total"),
                "area_plantada_ha": custo.get("area_total_ha"),
                "producao_total": custo.get("producao_total"),
            }
        )
    return serie


def custo_por_hectare_medio(propriedade_id: int, *, n_safras: int = 3) -> dict:
    """Média do custo por hectare das últimas N safras COM área medida.

    Devolve `None` quando nenhuma safra tem área, e diz porquê. A média só
    existe sobre safras medidas: meter uma safra sem área introduz erro, e
    preencher a lacuna com a média anterior é inventar.
    """
    serie = historico_safras(propriedade_id)[:n_safras]
    medidas = [s for s in serie if s["custo_por_hectare"] is not None]

    if not medidas:
        return {
            "valor": None,
            "safras_consideradas": 0,
            "safras_disponiveis": len(serie),
            "motivo": (
                "Nenhuma das últimas safras tem area plantada registada, ou "
                "custo por hectare apurável. Sem área medida não há custo por "
                "hectare — e não se assume 1 ha."
            ),
        }

    media = sum(Decimal(str(s["custo_por_hectare"])) for s in medidas) / len(medidas)
    return {
        "valor": float(media),
        "safras_consideradas": len(medidas),
        "safras_disponiveis": len(serie),
        "anos": [s["ano"] for s in medidas],
        "motivo": None,
    }


def capacidade_pagamento(
    propriedade_id: int,
    *,
    data_inicio: date | None = None,
    data_fim: date | None = None,
) -> dict:
    """Factores observáveis de capacidade de pagamento. Não é decisão de crédito.

    Cada factor vem com `valor`, `fonte` e — quando ausente — `motivo`. Um
    factor ausente **não** entra como zero: entra como ausente, que é a
    diferença entre "não houve despesa" e "não sabemos".
    """
    if data_fim is None:
        data_fim = date.today()
    if data_inicio is None:
        # 12 meses: um ciclo de safra. Mais curto não fecha uma lavoura; mais
        # longo mistura safras que não se comparam.
        data_inicio = date(data_fim.year - 1, data_fim.month, 1)

    lancamentos = LancamentoFinanceiro.objects.filter(
        propriedade_id=propriedade_id, data__gte=data_inicio, data__lte=data_fim
    )
    agg = lancamentos.aggregate(
        receitas=Sum("valor", filter=Q(tipo="RECEITA")),
        despesas=Sum("valor", filter=Q(tipo="DESPESA")),
    )
    receitas = agg["receitas"]
    despesas = agg["despesas"]

    # `None` = não há lançamentos no período. `0` = há lançamentos a somar zero.
    # `0` é medição; `None` é ausência. Confundi-los seria exactamente o
    # defeito que `custo_producao.py` tinha.
    fatores: dict[str, dict] = {}

    fatores["receitas_periodo"] = {
        "valor": _f(receitas),
        "fonte": f"LancamentoFinanceiro tipo=RECEITA, {data_inicio}..{data_fim}",
        "motivo": None
        if receitas is not None
        else "sem lançamentos de receita no período",
    }
    fatores["despesas_periodo"] = {
        "valor": _f(despesas),
        "fonte": f"LancamentoFinanceiro tipo=DESPESA, {data_inicio}..{data_fim}",
        "motivo": None
        if despesas is not None
        else "sem lançamentos de despesa no período",
    }

    saldo = None
    if receitas is not None and despesas is not None:
        saldo = float(Decimal(str(receitas)) - Decimal(str(despesas)))
    fatores["saldo_periodo"] = {
        "valor": saldo,
        "fonte": "receitas_periodo - despesas_periodo",
        "motivo": None
        if saldo is not None
        else "saldo exige receitas e despesas ambas registadas",
    }

    custo_ha = custo_por_hectare_medio(propriedade_id)
    fatores["custo_por_hectare_medio"] = {
        "valor": custo_ha["valor"],
        "fonte": (
            "custo_producao por safra, últimas "
            f"{custo_ha['safras_consideradas']} safras com área"
        ),
        "safras_consideradas": custo_ha["safras_consideradas"],
        "anos": custo_ha.get("anos"),
        "motivo": custo_ha["motivo"],
    }

    area = (
        Propriedade.objects.filter(pk=propriedade_id)
        .values_list("area_total", flat=True)
        .first()
    )
    area_medida = bool(area) and Decimal(str(area)) > 0
    fatores["area_total_ha"] = {
        "valor": _f(area),
        "fonte": "Propriedade.area_total",
        "area_medida": area_medida,
        "motivo": None if area_medida else "propriedade sem área total registada",
    }

    incompletos = [k for k, f in fatores.items() if f["valor"] is None]
    return {
        "propriedade_id": propriedade_id,
        "periodo": {"inicio": str(data_inicio), "fim": str(data_fim)},
        "fatores": fatores,
        "fatores_incompletos": incompletos,
        # A frase que o banco precisa de ler primeiro, e que este módulo não
        # pode escrever: quem decide é quem tem o dinheiro e a regulação.
        "decisao_de_credito": None,
        "aviso": (
            "Isto são fatores observáveis, não uma avaliação de crédito. "
            "A decisão é da instituição financeira."
        ),
    }
