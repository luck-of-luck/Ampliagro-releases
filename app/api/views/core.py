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
from django.db import connection, transaction
from django.db.models import Avg, Count, F, Q, Sum
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_date
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from app.api.serializers import *
from app.hierarquia import *
from app.models import *

from .utils import *


@extend_schema(
    responses={200: dict},
    summary="Health check for load balancers",
    description="Returns status of database, redis, and celery. No authentication required.",
)
@api_view(["GET"])
@permission_classes([AllowAny])
def healthz(request):
    """Health check endpoint for load balancers and monitoring."""
    checks = {}
    overall = True

    # Database check
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        checks["database"] = True
    except Exception:
        checks["database"] = False
        overall = False

    # Redis check
    try:
        cache.set("healthz_test", "ok", 10)
        if cache.get("healthz_test") == "ok":
            checks["redis"] = True
        else:
            checks["redis"] = False
            overall = False
    except Exception:
        checks["redis"] = False
        overall = False

    # Celery check (check if broker is reachable)
    try:
        import redis
        from django.conf import settings

        # Parse Redis URL from settings
        broker_url = getattr(settings, "CELERY_BROKER_URL", "redis://localhost:6379/1")
        # Simple connection test to Redis
        r = redis.from_url(broker_url, socket_connect_timeout=2, socket_timeout=2)
        r.ping()
        checks["celery"] = True
    except Exception:
        checks["celery"] = False
        # Don't mark overall as failed for celery - it's optional for basic health
        # overall = False

    status_code = 200 if overall else 503
    return JsonResponse(
        {"status": "ok" if overall else "degraded", "checks": checks},
        status=status_code,
    )


@extend_schema(responses=SPASimpleSerializer)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def visao_geral_data(request):
    props = get_propriedade_optimizada(request.user)
    return Response(
        {
            "propriedade": {
                "nome": props.nome if props else "",
                "area": float(props.area_total) if props else 0,
                "uf": props.uf if props else "",
            }
            if props
            else {}
        }
    )


@extend_schema(responses=SPASimpleSerializer)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def commodities_data(request):
    # External API data via AgroDoc adapter (frontend-side)
    # Backend returns user's own production data
    props = get_propriedade_optimizada(request.user)
    if not props:
        return Response({"culturas": []})
    safras = (
        Safra.objects.filter(propriedade=props)
        .select_related("cultura")
        .order_by("-ano")[:30]
    )
    return Response(
        {
            "culturas": [
                {
                    "cultura": s.cultura.nome if s.cultura else "—",
                    "ano": s.ano,
                    "producao": float(s.producao_total or 0),
                    "area": float(s.area_plantada),
                    "produtividade": float(s.produtividade or 0),
                }
                for s in safras
            ],
        }
    )


@extend_schema(responses=SPASimpleSerializer)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def previsao_safra_data(request):
    """Previsão de safra por talhão e cultura, contada a sério.

    Era `{"previsao": [], "total": 0}` — placeholder, sem perguntar à
    base. Havia 8 safras. Um `total: 0` sem consulta é um zero
    fabricado: "não tens safras" e "não sei quantas tens" chegam ao
    painel com a mesma cara, e a pessoa conclui pela primeira.
    """
    prop = get_propriedade_optimizada(request.user)
    if not prop:
        return Response(
            {"previsao": [], "total": 0, "aviso": "sem propriedade"},
            status=status.HTTP_404_NOT_FOUND,
        )

    qs = (
        Safra.objects.filter(propriedade=prop)
        .select_related("cultura")
        .order_by("-ano")
    )
    previsao = [
        {
            "safra_id": s.id,
            "safra": s.safra_nome,
            "cultura": s.cultura.nome if s.cultura_id else None,
            "ano": s.ano,
            # `area_plantada` / `area_colhida` — `Safra` nao tem
            # `area_hectare`. Foi a confusion que a IA-H encontrou no
            # comparativo (`order_by("-data_inicio")`, um campo que nao
            # existe), e que engole num `except Exception` devolve 500.
            "area_plantada": (
                float(s.area_plantada) if s.area_plantada is not None else None
            ),
            "area_colhida": (
                float(s.area_colhida) if s.area_colhida is not None else None
            ),
            "producao_total": (
                float(s.producao_total) if s.producao_total is not None else None
            ),
            "produtividade_sc_ha": (
                float(s.produtividade) if s.produtividade is not None else None
            ),
        }
        for s in qs
    ]
    return Response({"previsao": previsao, "total": len(previsao)})


@extend_schema(responses=SPASimpleSerializer)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def previsao_clima_data(request):
    """Previsão de clima — o MESMO pipeline da página, não um placeholder.

    Era `{"previsao": [], "fonte": "placeholder"}`, e é usado por
    `ia-local.js` (`clima: '/api/previsao-clima/'`). Ou seja: quando a IA
    local não sabia o tempo, recebia "placeholder" com lista vazia — e
    respondia ao produtor que não sabia.

    Agora delega ao mesmo `ClimaService` + `services.coordenadas` que a
    página usa. Um caminho só para "que tempo está na minha fazenda", que
    foi exactamente o que faltava quando a página e a IA discordavam.
    """
    from app.services.clima import ClimaService
    from app.services.coordenadas import resolver as resolver_coordenadas

    prop = get_propriedade_optimizada(request.user)
    if not prop:
        return Response(
            {"erro": "sem propriedade"},
            status=status.HTTP_404_NOT_FOUND,
        )

    coord = resolver_coordenadas(prop)
    if not coord.ok:
        return Response(
            {
                "erro": coord.aviso or "sem coordenada para a propriedade",
                "fonte": coord.fonte,
            },
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    dados = ClimaService.get_previsao(coord.lat, coord.lon)
    if isinstance(dados, dict) and dados.get("error"):
        return Response(dados, status=status.HTTP_503_SERVICE_UNAVAILABLE)

    dados = dict(dados or {})
    dados["fonte"] = coord.fonte
    if coord.origem_detalhe:
        dados["fonte_coordenadas_detalhe"] = coord.origem_detalhe
    if coord.aviso:
        dados["aviso_coordenadas"] = coord.aviso
    return Response(dados)


@extend_schema(responses=SPASimpleSerializer)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def gestao_data(request):
    props = get_propriedade_optimizada(request.user)
    if not props:
        return Response({"indicadores": []})
    safras = (
        Safra.objects.filter(propriedade=props)
        .select_related("cultura")
        .order_by("-ano")
    )
    lancs = LancamentoFinanceiro.objects.filter(propriedade=props)
    return Response(
        {
            "indicadores": {
                "total_safras": safras.count(),
                "media_produtividade": float(
                    sum(s.produtividade or 0 for s in safras) / max(safras.count(), 1)
                ),
                "total_receitas": float(
                    sum(l.valor for l in lancs if l.tipo == "RECEITA")
                ),
                "total_despesas": float(
                    sum(l.valor for l in lancs if l.tipo == "DESPESA")
                ),
            },
            "safras_por_cultura": [
                {
                    "cultura": s.cultura.nome,
                    "ano": s.ano,
                    "producao": float(s.producao_total or 0),
                }
                for s in safras[:20]
            ],
        }
    )


class ErroReportViewSet(viewsets.ModelViewSet):
    ordering_fields = ["criado_em"]
    serializer_class = ErroReportSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return ErroReport.objects.filter(user=self.request.user).order_by("-criado_em")

    def perform_create(self, serializer):
        serializer.save(
            user=self.request.user,
            email=self.request.user.email or "",
        )


class NotaViewSet(viewsets.ModelViewSet):
    ordering_fields = ["criado_em"]
    serializer_class = NotaSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Nota.objects.filter(user=self.request.user).order_by("-criado_em")

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class FotoViewSet(viewsets.ModelViewSet):
    ordering_fields = ["criado_em"]
    serializer_class = FotoSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Foto.objects.filter(nota__user=self.request.user).order_by("-criado_em")

    def perform_create(self, serializer):
        serializer.save()
