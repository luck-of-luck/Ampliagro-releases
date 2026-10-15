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
def agenda_pecuaria_view(request):
    propriedades = Propriedade.objects.filter(user=request.user)
    animais = Animal.objects.filter(propriedade__user=request.user).select_related(
        "propriedade"
    )[:20]
    return render(
        request,
        "agenda-pecuaria.html",
        {"propriedades": propriedades, "animais": animais},
    )


@login_required
def racoes_nutricao_view(request):
    propriedades = Propriedade.objects.filter(user=request.user)
    animais = Animal.objects.filter(propriedade__user=request.user).select_related(
        "propriedade"
    )[:10]
    racoes = (
        Racao.objects.filter(propriedade__user=request.user)
        .select_related("propriedade")
        .order_by("-criado_em")[:100]
    )
    return render(
        request,
        "racoes-nutricao.html",
        {"propriedades": propriedades, "animais": animais, "racoes": racoes},
    )


@login_required
def animais_gado_view(request):
    from app.models.pecuaria import AnimalIndividual, Piquete
    from app.services.pecuaria import PecuariaService

    prop = Propriedade.objects.filter(user=request.user).first()
    if not prop:
        return render(
            request,
            "animais-gado.html",
            {
                "gmd_medio": 0,
                "lotacao_media": 0,
                "total_individuos": 0,
                "alertas_sanitarios": [],
                "alertas_qtd": 0,
                "sem_propriedade": True,
            },
        )
    propriedade_id = prop.id

    animais_individuais = AnimalIndividual.objects.filter(propriedade_id=propriedade_id)

    gmd_total = 0
    count_gmd = 0
    for anim in animais_individuais:
        gmd = PecuariaService.calcular_gmd(anim.id)
        if gmd is not None:
            gmd_total += gmd
            count_gmd += 1

    gmd_medio = round(gmd_total / count_gmd, 2) if count_gmd > 0 else 0

    piquetes = Piquete.objects.filter(propriedade_id=propriedade_id)
    lotacao_total_ua = 0
    area_total_piquetes = 0
    for piq in piquetes:
        lot = PecuariaService.calcular_lotacao_piquete(piq.id)
        lotacao_total_ua += lot["ua_total"]
        area_total_piquetes += float(piq.area_hectare)

    lotacao_media_ha = (
        round(lotacao_total_ua / area_total_piquetes, 2)
        if area_total_piquetes > 0
        else 0
    )

    alertas_sanitarios = PecuariaService.get_alertas_sanitarios(propriedade_id)

    context = {
        "gmd_medio": gmd_medio,
        "lotacao_media": lotacao_media_ha,
        "total_individuos": animais_individuais.count(),
        "alertas_sanitarios": alertas_sanitarios,
        "alertas_qtd": len(alertas_sanitarios),
    }

    return render(request, "animais-gado.html", context)
