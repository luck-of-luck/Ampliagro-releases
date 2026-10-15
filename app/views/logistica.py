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
def logistica_caminhao_view(request):
    propriedades = Propriedade.objects.filter(user=request.user)
    caminhoes = Maquinario.objects.filter(
        propriedade__user=request.user, tipo="CAMINHAO"
    ).select_related("propriedade")
    return render(
        request,
        "logistica-caminhao.html",
        {"propriedades": propriedades, "caminhoes": caminhoes},
    )


@login_required
def logistica_rotas_view(request):
    propriedades = Propriedade.objects.filter(user=request.user)
    return render(request, "logistica-rotas.html", {"propriedades": propriedades})


@login_required
@hierarquia_required("mapa")
def mapa_view(request):
    # mapa.html não existe → usa mapa-georgia.html (Leaflet + leaflet-draw completo)
    return render(request, "mapa-georgia.html", {})
