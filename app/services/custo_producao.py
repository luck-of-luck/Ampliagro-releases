"""Custo de produção por safra — e o contrato de honestidade do número.

O QUE ESTE MÓDULO FAZIA, E PORQUÊ ERA ERRADO
=============================================

A versão anterior tinha três defeitos. Nenhum era subjectivo; os três eram
observáveis, e um deles fazia o módulo **não funcionar para ninguém**.

1. `area_total = sum(t.area_hectare for t in talhoes) or Decimal("1.0")`
   `safra.talhoes` **não existe**. O campo é `talhoes` com
   `related_name="safras_m2m"` (`models/safra.py`), e a área plantada da safra
   vive em `area_plantada`, que é NOT NULL. A linha levantava `AttributeError`.

2. `safra.producao_estimada` **não existe**. O campo é `producao_total`.
   `AttributeError` de novo — portanto `calcular_custo_producao` nunca
   devolveu um número para nenhuma safra real.

3. `or Decimal("1.0")` em dois sítios. O `or` existe para evitar divisão por
   zero — e esse objetivo é legítimo. Mas o valor mascarado **ia para o
   JSON**: o produtor via "1 ha" e "custo por hectare = 15.000" numa fazenda
   que ninguém mediu.

   Isto é o mesmo defeito que `user.py:190-208` já corrigiu — com um
   comentário de duas páginas entitled "A ÁREA É A DA FAZENDA, OU NÃO É NADA" —
   e que `proveniencia.py` transformou em **tipo**. O bug não foi propagado.

POR QUE IMPORTA MAIS DO QUE PARECE
==================================

Este módulo vai alimentar um cálculo de **capacidade de pagamento para crédito
rural** (§10 da análise competitiva). Um `custo_por_hectare` inventado não é um
erro de ecrã: é uma capacidade de pagamento ao banco que não existe.

A regra que sigo, e que é do repo e não minha:

- `proveniencia.py:98-120` — `SemDado` recusa-se a ter `valor`, porque "um
  número sem procedência é pior que a ausência dele".
- `cotacoes.py:3-7` — "um preço só entra no payload se veio de uma fonte que
  realmente respondeu".

O contrato: **ausência é `None` com motivo; `0` é `0`.** São coisas diferentes.
Tratar `0` como ausência apaga informação real (o produtor gastou zero); tratar
ausência como `1` inventa informação (o produtor mediu 1 ha).
"""

from decimal import Decimal

from django.db.models import Sum

from app.models.financeiro import LancamentoFinanceiro
from app.models.safra import Safra


def _f(valor) -> float | None:
    """Decimal -> float, preservando `None`.

    Existe para tornar explícito o ponto do módulo: converter não pode
    transformar ausência em número.
    """
    return None if valor is None else float(valor)


def calcular_custo_producao(safra_id: int) -> dict:
    """Custo da safra, com `None` onde não há dado.

    Devolve sempre, por campo:
      * o valor, quando existe;
      * `None`, quando não existe;
      * `motivo`, quando algo falta — porque "sem dado" sem motivo obriga o
        produtor a adivinhar o que falta, e adivinhar mal num painel é pior
        do que não ter nada (`proveniencia.py:99-105`).
    """
    try:
        safra = Safra.objects.select_related("cultura").get(id=safra_id)
    except Safra.DoesNotExist:
        return {"error": "Safra não encontrada"}

    despesas = LancamentoFinanceiro.objects.filter(safra_id=safra_id, tipo="DESPESA")

    # `Sum` devolve `None` quando NÃO HÁ LINHAS — e "não há linhas" é uma
    # situação normal (safra recém-plantada, sem despesa lançada). Não é a
    # mesma coisa que "as despesas somam zero", mas nos dois casos o custo
    # registado é 0. O que NÃO pode é propagar o `None` para uma divisão, onde
    # viraria `Decimal("None")` e levantaria `InvalidOperation`.
    #
    # Aqui o `or Decimal("0.00")` é CORRECTO e é a distinção que importa.
    # Zero é medição — o produtor não gastou nada. Ausência de despesa não é
    # ausência de custo.
    custo_total = despesas.aggregate(total=Sum("valor"))["total"] or Decimal("0.00")

    # Área e produção vêm da SAFRA, não da soma de talhões: um talhão pode
    # existir sem estar plantado (reserva legal, APP), e somar talhões daria
    # uma área que ninguém plantou.
    area_plantada = safra.area_plantada
    producao_total = safra.producao_total

    breakdown = {}
    for d in despesas.values("categoria").annotate(total=Sum("valor")):
        breakdown[d["categoria"]] = float(d["total"])

    motivos = []
    # `0` é um valor válido: uma safra de 0 ha existe. O que não pode é
    # dividir por ela e devolver um custo inventado.
    if area_plantada and Decimal(str(area_plantada)) > 0:
        custo_ha = Decimal(str(custo_total)) / Decimal(str(area_plantada))
    else:
        custo_ha = None
        motivos.append(
            "Safra sem area plantada registada: custo por hectare nao pode "
            "ser calculado. Nao se assume 1 ha."
        )

    if producao_total and Decimal(str(producao_total)) > 0:
        custo_unidade = Decimal(str(custo_total)) / Decimal(str(producao_total))
    else:
        custo_unidade = None
        motivos.append(
            "Safra sem producao registada: custo por unidade nao pode ser calculado."
        )

    resultado = {
        "safra_id": safra.id,
        "cultura": safra.cultura.nome if safra.cultura_id else None,
        "custo_total": float(custo_total),
        "area_total_ha": _f(area_plantada),
        "custo_por_hectare": _f(custo_ha),
        "producao_total": _f(producao_total),
        "custo_por_unidade": _f(custo_unidade),
        "breakdown_categorias": breakdown,
    }

    if motivos:
        resultado["motivo"] = " ".join(motivos)

    return resultado
