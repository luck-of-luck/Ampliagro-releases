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
@hierarquia_required("sensores")
def sensores_view(request):
    from app.models import EstacaoMeteo

    estacoes = EstacaoMeteo.objects.filter(
        propriedade__user=request.user
    ).select_related("propriedade")
    propriedades = Propriedade.objects.filter(user=request.user)
    return render(
        request,
        "sensores.html",
        {"sensores": estacoes, "estacoes": estacoes, "propriedades": propriedades},
    )


@login_required
@hierarquia_required("dispositivos")
def dispositivos_view(request):
    from app.models import Device, Gateway

    devices = Device.objects.filter(propriedade__user=request.user).select_related(
        "propriedade", "gateway"
    )
    gateways = Gateway.objects.filter(propriedade__user=request.user).select_related(
        "propriedade"
    )
    propriedades = Propriedade.objects.filter(user=request.user)
    return render(
        request,
        "dispositivos.html",
        {
            "dispositivos": devices,
            "devices": devices,
            "gateways": gateways,
            "propriedades": propriedades,
        },
    )


@login_required
@hierarquia_required("telemetria")
def telemetria_view(request):
    from datetime import timedelta

    from django.utils import timezone

    from app.hierarquia import propriedades_visiveis
    from app.models import AlertaTelemetria, Device, Gateway, Propriedade, TelemetryData

    props = propriedades_visiveis(request.user)
    propriedades = props
    propriedades.values_list("id", flat=True)
    gateways = Gateway.objects.filter(propriedade__in=props).select_related(
        "propriedade"
    )
    devices = Device.objects.filter(propriedade__in=props).select_related(
        "propriedade", "gateway", "talhao"
    )
    alertas = AlertaTelemetria.objects.filter(
        propriedade__in=props, resolvido=False
    ).select_related("device")[:20]
    # stats 24h
    since = timezone.now() - timedelta(hours=24)
    leituras_24h = TelemetryData.objects.filter(
        propriedade__in=props, timestamp__gte=since
    ).count()
    online_gateways = gateways.filter(status="online").count()
    # últimos dados por device para sparkline
    recentes = (
        TelemetryData.objects.filter(propriedade__in=props)
        .select_related("device")
        .order_by("-timestamp")[:30]
    )
    # perfis
    import json
    import pathlib

    profiles_path = (
        pathlib.Path(__file__).resolve().parent / "iot" / "device_profiles.json"
    )
    try:
        profiles = json.loads(profiles_path.read_text(encoding="utf-8"))["profiles"]
    except Exception:
        profiles = {}
    return render(
        request,
        "telemetria.html",
        {
            "propriedades": propriedades,
            "gateways": gateways,
            "devices": devices,
            "alertas": alertas,
            "leituras_24h": leituras_24h,
            "online_gateways": online_gateways,
            "recentes": recentes,
            "profiles": profiles,
        },
    )


@login_required
def alertas_criticos_view(request):
    return render(request, "alertas-criticos.html", {})


@login_required
def alertas_info_view(request):
    return render(request, "alertas-info.html", {})
