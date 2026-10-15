import json
import logging
import math
import traceback
from collections import defaultdict
from datetime import date, datetime, timedelta

import requests
from django.conf import settings
from django.contrib.auth import authenticate, login
from django.contrib.auth.models import User
from django.core.cache import cache
from django.db import transaction
from django.db.models import Avg, Count, F, Q, Sum
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_date
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from app.api.pagination import LargeTableCursorPagination, SensorCursorPagination
from app.api.serializers import *
from app.hierarquia import *
from app.models import *

from .utils import *  # noqa: F403

# Fix: import * não traz nomes com _ — sem isto, o cache de clima e o
# fallback histórico estouravam NameError (500) no primeiro cache miss.
#
# `_get_real_weather` entrou aqui por um motivo mais grave (2026-09-30).
# Este ficheiro tinha uma CÓPIA da função, e a cópia era a que a rota
# `/api/weather/` usava — enquanto a de `utils.py`, corrigida, ficava morta.
# A cópia daqui ainda fazia `or 25` e `or 60`: quando o INMET não dava
# temperatura nem humidade, saíam 25 °C e 60 % com o carimbo
# `"fonte": "inmet"`. Números inventados com o nome de uma instituição
# pública. A correcção existia, estava feita, e não chegava ao ecrã —
# porque `scripts/split_api_views.py` copiou a função para aqui e ninguém
# reparou que a cópia ficou para trás.
#
# A cópia foi apagada. A implementação passa a ser a de `utils.py`, uma só.
from .utils import (  # noqa: F401
    _WEATHER_CACHE,
    _WEATHER_CACHE_TTL,
    _get_real_weather,
    _parse_value,
)


class EstacaoMeteoViewSet(viewsets.ModelViewSet):
    search_fields = ["nome"]
    serializer_class = EstacaoMeteoSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return EstacaoMeteo.objects.filter(propriedade__user=self.request.user)


class LeituraSensorViewSet(viewsets.ModelViewSet):
    filterset_fields = ["estacao"]
    ordering_fields = ["timestamp"]
    serializer_class = LeituraSensorSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # PERF: select_related("estacao") — o serializer expoe estacao_nome via
        # CharField(source="estacao.nome"); sem eager loading eram 63 queries
        # numa página de 50 (tabela de telemetria = a que mais cresce).
        return LeituraSensor.objects.filter(
            estacao__propriedade__user=self.request.user
        ).select_related("estacao")


@extend_schema(responses=SPASimpleSerializer)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def sensores_data(request):
    """Estações do utilizador, contadas a sério.

    Era `return Response({"sensores": [], "total": 0})` — um placeholder que
    respondia "zero estações" sem perguntar à base. Havia DUAS estações
    cadastradas, uma na Fazenda Muzambinho. O painel dizia 0 e a pessoa
    concluía que a instalação nunca tinha acontecido.

    É a classe do `umidade: 50` e do `total: 0` dos widgets: um zero que
    não é medido parece uma medição, e "0 sensores" é mais acreditável
    do que "não sei".

    Quando não há mesmo zero, `total` é 0 — mas é um zero CONTADO, e a
    lista vem vazia à mesma. A diferença entre os dois é invisível na
    resposta e tudo nesta resposta.
    """
    from app.models import EstacaoMeteo

    qs = EstacaoMeteo.objects.filter(propriedade__user=request.user)
    # `select_related` porque o payload leva o nome da fazenda, e sem
    # isto são uma query por estação.
    qs = qs.select_related("propriedade").order_by("nome")

    sensores = [
        {
            "id": e.id,
            "nome": e.nome,
            "propriedade": e.propriedade.nome if e.propriedade_id else None,
            "codigo_inmet": e.codigo_inmet,
            "ativa": bool(e.ativa),
            "latitude": float(e.latitude) if e.latitude is not None else None,
            "longitude": float(e.longitude) if e.longitude is not None else None,
            "instalada_em": (
                e.data_instalacao.isoformat() if e.data_instalacao else None
            ),
        }
        for e in qs
    ]
    return Response({"sensores": sensores, "total": len(sensores)})


@extend_schema(responses=SPASimpleSerializer)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def dispositivos_data(request):
    """Dispositivos IoT — e a honestidade sobre não haver modelo.

     `{"dispositivos": [], "total": 0}` dizia "não tens dispositivos". Não
     tens: o MODELO não existe. São coisas diferentes, e a segunda é
    Responsavel por uma tela que parece funcionar.

     Aqui não se inventa um modelo para preencher a lista. Diz-se que a
     fonte não existe, que é a verdade e é accionável.
    """
    return Response(
        {
            "dispositivos": [],
            "total": 0,
            "fonte": "modelo_inexistente",
            "aviso": (
                "não há modelo de dispositivo IoT neste projecto. "
                "A lista está vazia porque a fonte não existe, não "
                "porque não há dispositivos."
            ),
        }
    )


@extend_schema(responses=SPASimpleSerializer)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def weather_integracao(request):
    """Weather data real: INMET -> OpenWeatherMap -> fallback (via helper compartilhado)."""
    props = get_propriedade_optimizada(request.user)
    clima = _get_real_weather(props)
    if not clima:
        return Response({"cidade": "Não informado", "previsao": []})
    return Response(
        {
            "cidade": clima["cidade"],
            "fonte": clima.get("fonte"),
            "atual": clima.get("atual"),
            "previsao": clima["previsao"],
            "api_key_faltando": False,
        }
    )


@extend_schema(responses=SPASimpleSerializer)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def weather_forecast(request):
    props = get_propriedade_optimizada(request.user)
    clima = _get_real_weather(props)
    if not clima:
        return Response({"cidade": "Não informado", "previsao": []})
    return Response(
        {
            "cidade": clima["cidade"],
            "fonte": clima.get("fonte"),
            "atual": clima.get("atual"),
            "previsao": clima["previsao"],
        }
    )


def _owm_icon(main, desc):
    m = (main or "").lower()
    d = (desc or "").lower()
    if "clear" in m or "sol" in d:
        return "bi-sun"
    if "thunder" in m or "storm" in d:
        return "bi-cloud-lightning-rain"
    if "snow" in m:
        return "bi-snow"
    if "rain" in m or "drizzle" in m or "chuva" in d:
        return "bi-cloud-rain"
    if "cloud" in m:
        return "bi-cloud-sun"
    return "bi-cloud"
