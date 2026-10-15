import json
import logging
import math
import random
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

from app.api.serializers import *
from app.hierarquia import *
from app.models import *

from .utils import *


@extend_schema(responses=SPASimpleSerializer)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def agenda_data(request):
    props = get_propriedade_optimizada(request.user)
    if not props:
        return Response({"tarefas": [], "funcionarios": []})
    return Response(
        {
            "funcionarios": FuncionarioSerializer(
                props.funcionarios.filter(ativo=True), many=True
            ).data,
            "safras_proximas": SafraSerializer(
                props.safras.select_related("cultura", "talhao").order_by("-ano")[:10],
                many=True,
            ).data,
        }
    )


@extend_schema(responses=SPASimpleSerializer)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def agenda_producao_data(request):
    props = get_propriedade_optimizada(request.user)
    if not props:
        return Response({"safras": []})
    return Response(
        {
            "safras": SafraSerializer(
                props.safras.select_related("cultura", "talhao").order_by("-ano"),
                many=True,
            ).data,
        }
    )


@extend_schema(responses=SPASimpleSerializer)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def agenda_analises_data(request):
    props = get_propriedade_optimizada(request.user)
    if not props:
        return Response({"talhoes_mapa": [], "laudos": []})
    # `SafraSerializer` e `TalhaoSerializer` ja vem do `from app.api.serializers
    # import *` do topo do modulo (linha 27). O import local que aqui estava
    # apontava para `.serializers`, que dentro de `app/api/views/` resolve para
    # `app.api.views.serializers` — um modulo que nao existe. Resultado:
    # `ModuleNotFoundError` em CADA request a `/api/agenda-analises/`, ou seja,
    # HTTP 500. MEDIDO 2026-10-04 com sonda de request; o import local era
    # tambem redundante.
    talhoes = Talhao.objects.filter(propriedade=props).select_related("cultura_atual")
    safras = (
        Safra.objects.filter(propriedade=props)
        .select_related("cultura", "talhao")
        .order_by("-ano")[:10]
    )
    return Response(
        {
            "talhoes_mapa": TalhaoSerializer(talhoes, many=True).data,
            "laudos": SafraSerializer(safras, many=True).data,
        }
    )
