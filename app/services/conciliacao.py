"""Conciliação bancária assistida: casa movimento do extrato com lançamento.

Regra conservadora: valor EXATO + data dentro da janela (default ±3 dias),
só para lançamentos em aberto (pago=False) da mesma propriedade da conta.
Cada lançamento casa no máximo 1 vez por rodada (evita duplicar).
Ao casar: movimento.conciliado=True + lançamento pago=True (baixa automática).
"""

from datetime import timedelta


def conciliar_conta(conta, dias=3, dry_run=False):
    from django.utils import timezone

    from app.models import LancamentoFinanceiro, MovimentacaoBancaria

    pares = []
    usados = set()
    pendentes = MovimentacaoBancaria.objects.filter(
        conta=conta, conciliado=False
    ).order_by("data")
    for mov in pendentes:
        cand = (
            LancamentoFinanceiro.objects.filter(
                propriedade=conta.propriedade,
                pago=False,
                valor=mov.valor,
                data__gte=mov.data - timedelta(days=dias),
                data__lte=mov.data + timedelta(days=dias),
            )
            .exclude(id__in=usados)
            .first()
        )
        if not cand:
            continue
        usados.add(cand.id)
        pares.append((mov, cand))
        if not dry_run:
            mov.conciliado = True
            mov.data_conciliacao = timezone.now().date()
            mov.save(update_fields=["conciliado", "data_conciliacao"])
            cand.pago = True
            cand.data_pagamento = mov.data
            cand.save(update_fields=["pago", "data_pagamento"])
    return pares
