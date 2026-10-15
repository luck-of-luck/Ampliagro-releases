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
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from app.api.serializers import *
from app.hierarquia import *
from app.models import *

from .utils import *


class MaquinarioViewSet(viewsets.ModelViewSet):
    filterset_fields = ["tipo", "propriedade"]
    search_fields = ["nome", "marca", "modelo"]
    ordering_fields = ["nome"]
    serializer_class = MaquinarioSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Maquinario.objects.filter(
            propriedade__user=self.request.user
        ).select_related("propriedade")  # optimized P2.3

    def perform_create(self, serializer):
        prop = serializer.validated_data.get("propriedade")
        if prop and prop.user != self.request.user:
            raise PermissionDenied("Esta propriedade não pertence ao seu usuário")
        serializer.save()


@extend_schema(responses=SPASimpleSerializer)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def maquinarios_data(request):
    props = get_propriedade_optimizada(request.user)
    if not props:
        return Response({"maquinas": []})
    return Response(
        {
            "maquinas": MaquinarioSerializer(props.maquinarios.all(), many=True).data,
            "total": props.maquinarios.count(),
            "em_manutencao": props.maquinarios.filter(
                proxima_manutencao__isnull=False
            ).count(),
        }
    )


@extend_schema(responses=SPASimpleSerializer)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def caminhoes_data(request):
    """Caminhos: NAO EXISTE o modelo que os conte.

    Nao ha Caminhao no projecto. "total": 0 dizia "nao tens
    caminhos", e o painel lia isso como um fact. "Nao existe fonte" e
    "fui perguntar e deu zero" chegam com a mesma cara — e a segunda
    leva a pessoa a concluir pela primeira.

    A mesma regra que dispositivos_data (7dca708).
    """
    return Response(
        {
            "caminhoes": [],
            "total": 0,
            "fonte": "modelo_inexistente",
            "aviso": "nao existe modelo de caminhos neste projecto",
        }
    )


@extend_schema(responses=SPASimpleSerializer)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def rotas_data(request):
    """Placeholder for rotas data"""
    return Response({"rotas": [], "total": 0})
