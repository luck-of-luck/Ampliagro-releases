import json

from django import forms
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from app.hierarquia import hierarquia_required
from app.models import *

from .utils import *


@login_required
@hierarquia_required("estoque-geral")
def estoque_geral_view(request):
    from app.services.estoque import EstoqueService

    prop = Propriedade.objects.filter(user=request.user).first()
    if not prop:
        return render(
            request,
            "estoque-geral.html",
            {
                "alertas_ruptura": [],
                "alertas_fefo": [],
                "curva_abc": [],
                "total_alertas": 0,
                "sem_propriedade": True,
            },
        )

    ruptura = EstoqueService.alerta_ruptura(prop.id)
    fefo = EstoqueService.alerta_fefo(prop.id)
    abc = EstoqueService.analise_curva_abc(prop.id)

    context = {
        "alertas_ruptura": ruptura,
        "alertas_fefo": fefo,
        "curva_abc": abc,
        "total_alertas": len(ruptura) + len(fefo),
        "propriedade": prop,
    }
    return render(request, "estoque-geral.html", context)


@login_required
def estoque_insumos_view(request):
    itens = EstoqueItem.objects.filter(propriedade__user=request.user).select_related(
        "propriedade"
    )[:50]
    return render(
        request,
        "estoque-insumos.html",
        {"itens": itens, "propriedades": Propriedade.objects.filter(user=request.user)},
    )
