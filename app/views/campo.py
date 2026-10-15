import json

from decimal import Decimal

from django import forms
from django.db.models import F, Sum
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from app.models.estoque import MovimentacaoEstoque
from app.models.rastreabilidade import MovimentoEstoque
from app.hierarquia import get_propriedade_optimizada, hierarquia_required
from app.models import *

from .utils import *


@login_required
def setor_campo_view(request):
    propriedades = Propriedade.objects.filter(user=request.user)
    talhoes = Talhao.objects.filter(propriedade__user=request.user).select_related("propriedade", "cultura_atual")[:20]
    return render(request, "setor-campo.html", {"propriedades": propriedades, "talhoes": talhoes})


@login_required
def setor_estoque_view(request):
    """As estatisticas desta tela sao MEDIDAS, aqui, sobre a mesma queryset.

    O template tinha quatro numeros LITERAIS — 156 itens, 8 categorias,
    "R$ 487.320,00" e 3 alertas — enquanto esta view passava `itens` do banco e
    o template nunca o lia. A tela tem rota activa e link na navegacao, portanto
    um produtor lia um valor de estoque que nunca existiu.

    `valor_total` pode ser zero mesmo com itens cadastrados: `valor_unitario`
    nao esta no serializer (so o admin Django o preenche). Por isso zero aqui
    significa "ninguem mediu o valor", e o template diz `sem dado` em vez de
    R$ 0,00 — que afirmaria que o estoque vale nada.
    """
    propriedades = Propriedade.objects.filter(user=request.user)
    base = EstoqueItem.objects.filter(propriedade__user=request.user)
    itens = base.select_related("propriedade")[:20]

    valor_total = base.aggregate(
        v=Sum(F("quantidade") * F("valor_unitario"))
    )["v"] or Decimal("0")

    # Alerta de ruptura: so conta onde o limite foi mesmo preenchido. Onde
    # `quantidade_minima` e' 0, nao ha nada a comparar — e um "alerta" ai seria uma
    # mentira.
    em_ruptura = list(
        base.filter(quantidade_minima__gt=0)
        .filter(quantidade__lt=F("quantidade_minima"))
        .order_by("nome")[:20]
    )
    alertas = len(em_ruptura)

    # As "movimentacoes recentes" nao sao ligadas a nada, de proposito. Os dois
    # ledgers de estoque (`MovimentacaoEstoque` e `MovimentoEstoque`) existem no
    # model e NAO TEM QUEM ESCREVA neles — nenhum signal, nenhum service, nenhuma
    # view cria uma movimentacao. Uma tabela ligada a essa queryset ficaria
    # sempre vazia. Dizer "sem dado" e a razao e' melhor que encher de fiction.
    #
    # Isto tambem torna visivel um buraco real: o registo de entrada e saida de
    # estoque nao existe na pratica, o que torna a Curva ABC e o alerta de
    # ruptura menos confiaveis do que parecem.
    # MovimentacaoEstoque nao tem campo propriedade: liga-se ao item.
    # MovimentoEstoque liga-se ao rastro OU ao talhao. Campos verificados em
    # runtime — manage.py check nao apanha um filtro com um caminho errado.
    tem_ledger = (
        MovimentacaoEstoque.objects.filter(item__propriedade__user=request.user).exists()
        or MovimentoEstoque.objects.filter(talhao__propriedade__user=request.user).exists()
    )

    return render(
        request,
        "setor-estoque.html",
        {
            "propriedades": propriedades,
            "itens": itens,
            "total_itens": base.count(),
            "total_categorias": base.values("categoria").distinct().count(),
            "valor_total": valor_total,
            "valor_medido": valor_total > 0,
            "alertas": alertas,
            "em_ruptura": em_ruptura,
            "tem_ledger": tem_ledger,
        },
    )


@login_required
def agenda_agricola_view(request):
    propriedades = Propriedade.objects.filter(user=request.user)
    safras = Safra.objects.filter(propriedade__user=request.user).select_related("cultura", "talhao", "propriedade").order_by("-ano")[:10]
    return render(request, "agenda-agricola.html", {"propriedades": propriedades, "safras": safras})


@login_required
def agenda_pecuaria_view(request):
    propriedades = Propriedade.objects.filter(user=request.user)
    animais = Animal.objects.filter(propriedade__user=request.user).select_related("propriedade")[:20]
    return render(request, "agenda-pecuaria.html", {"propriedades": propriedades, "animais": animais})


@login_required
@hierarquia_required("previsao-clima")
def previsao_clima_view(request):
    return render(request, "previsao-clima.html", {})


@login_required
@hierarquia_required("previsao-safra")
def previsao_safra_view(request):
    from app.hierarquia import get_propriedade_optimizada

    prop = get_propriedade_optimizada(request.user)
    safras = (
        Safra.objects.filter(propriedade__user=request.user)
        .select_related("cultura", "talhao")
        .order_by("-ano")[:20]
    )
    from datetime import date

    return render(
        request,
        "previsao-safra.html",
        {
            "safras": safras,
            "safras_andamento": safras.filter(status__in=["EM_ANDAMENTO", "PLANEJADA"])
            if hasattr(Safra, "status")
            else safras,
            "propriedade": prop,
            "today": date.today(),
        },
    )


@login_required
@hierarquia_required("ndvi-view")
def ndvi_view(request):
    talhoes = Talhao.objects.filter(propriedade__user=request.user).select_related(
        "propriedade", "cultura_atual"
    )
    return render(request, "agronomia/ndvi.html", {"talhoes": talhoes})


@login_required
@hierarquia_required("compliance-view")
def compliance_view(request):
    from app.models import Propriedade

    propriedades = Propriedade.objects.filter(user=request.user)
    return render(request, "agronomia/compliance.html", {"propriedades": propriedades})
