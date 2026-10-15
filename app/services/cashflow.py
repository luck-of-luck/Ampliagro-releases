from datetime import date
from decimal import Decimal

from dateutil.relativedelta import relativedelta
from django.db.models import Sum

from app.models.financeiro import LancamentoFinanceiro


def projetar_fluxo_caixa(propriedade_id, meses=12):
    """
    Projeta o fluxo de caixa para os próximos X meses.
    Retorna uma lista de dados de Receitas, Despesas e Saldo por mês.
    A projeção é baseada nos lançamentos com data_pagamento futura (ou data se não pago)
    e/ou média histórica (simplificada nesta versão).
    """
    hoje = date.today()
    resultado = []

    # Busca os lançamentos futuros não pagos
    # Aqui poderíamos expandir para projetar safras em andamento
    lancamentos_futuros = LancamentoFinanceiro.objects.filter(
        propriedade_id=propriedade_id, pago=False, data__gte=hoje
    )

    saldo_acumulado = Decimal("0.00")  # Idealmente seria o saldo atual real

    for i in range(meses):
        # Mês alvo
        mes_alvo = hoje + relativedelta(months=i)
        ano_alvo, mes_num = mes_alvo.year, mes_alvo.month

        # Filtra lançamentos previstos para este mês
        lancs_mes = lancamentos_futuros.filter(data__year=ano_alvo, data__month=mes_num)

        receitas = lancs_mes.filter(tipo="RECEITA").aggregate(total=Sum("valor"))[
            "total"
        ] or Decimal("0.00")
        despesas = lancs_mes.filter(tipo="DESPESA").aggregate(total=Sum("valor"))[
            "total"
        ] or Decimal("0.00")
        saldo_mensal = receitas - despesas
        saldo_acumulado += saldo_mensal

        resultado.append(
            {
                "mes": f"{mes_alvo.strftime('%B')} {ano_alvo}".capitalize(),
                "mes_num": f"{ano_alvo}-{mes_num:02d}",
                "receitas": float(receitas),
                "despesas": float(despesas),
                "saldo_mensal": float(saldo_mensal),
                "saldo_acumulado": float(saldo_acumulado),
            }
        )

    return resultado
