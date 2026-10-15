from datetime import date
from decimal import Decimal

from django.db.models import QuerySet

from app.models.maquinario import Maquinario


def calcular_depreciacao_mensal(maquinario: Maquinario) -> Decimal:
    """
    Calcula a depreciação mensal de um maquinário pelo método linear.
    Fórmula: (Valor de Aquisição - Valor Residual) / (Vida Útil em Anos * 12)
    """
    if not maquinario.valor_aquisicao or not maquinario.vida_util_anos:
        return Decimal("0.00")

    valor_residual = maquinario.valor_residual or Decimal("0.00")
    valor_depreciavel = maquinario.valor_aquisicao - valor_residual

    if valor_depreciavel <= 0:
        return Decimal("0.00")

    meses_vida_util = maquinario.vida_util_anos * 12
    return valor_depreciavel / Decimal(str(meses_vida_util))


def relatorio_depreciacao_propriedade(propriedade_id: int) -> dict:
    """
    Gera o relatório de depreciação mensal total e por ativo para uma propriedade.
    """
    maquinarios = Maquinario.objects.filter(
        propriedade_id=propriedade_id,
        ativo=True,
        valor_aquisicao__isnull=False,
        vida_util_anos__isnull=False,
    )

    depreciacao_total = Decimal("0.00")
    detalhes = []

    for maq in maquinarios:
        dep_mensal = calcular_depreciacao_mensal(maq)
        depreciacao_total += dep_mensal

        # Calcular valor contábil atual aproximado
        meses_uso = 0
        valor_contabil = maq.valor_aquisicao
        if maq.data_aquisicao:
            hoje = date.today()
            meses_uso = (hoje.year - maq.data_aquisicao.year) * 12 + (
                hoje.month - maq.data_aquisicao.month
            )
            if meses_uso > 0:
                # Não depreciar abaixo do valor residual
                max_meses = maq.vida_util_anos * 12
                meses_depreciados = min(meses_uso, max_meses)
                depreciacao_acumulada = dep_mensal * Decimal(str(meses_depreciados))
                valor_contabil = maq.valor_aquisicao - depreciacao_acumulada
                if valor_contabil < (maq.valor_residual or Decimal("0.00")):
                    valor_contabil = maq.valor_residual or Decimal("0.00")

        detalhes.append(
            {
                "maquinario_id": maq.id,
                "nome": maq.nome,
                "tipo": maq.get_tipo_display(),
                "valor_aquisicao": float(maq.valor_aquisicao),
                "valor_residual": float(maq.valor_residual or 0),
                "vida_util_anos": maq.vida_util_anos,
                "meses_uso": meses_uso,
                "depreciacao_mensal": float(dep_mensal),
                "valor_contabil_atual": float(valor_contabil),
            }
        )

    return {
        "depreciacao_mensal_total": float(depreciacao_total),
        "ativos_depreciaveis": len(detalhes),
        "detalhes": detalhes,
    }
