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


class ApiarioColmeiaViewSet(viewsets.ModelViewSet):
    filterset_fields = ["propriedade"]
    search_fields = ["identificacao"]
    serializer_class = ApiarioColmeiaSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return ApiarioColmeia.objects.filter(
            propriedade__user=self.request.user
        ).select_related("propriedade")

    def perform_create(self, serializer):
        prop = serializer.validated_data.get("propriedade")
        if prop and prop.user != self.request.user:
            raise PermissionDenied("Esta propriedade não pertence ao seu usuário")
        serializer.save()


class ProducaoApiarioViewSet(viewsets.ModelViewSet):
    filterset_fields = ["colmeia"]
    ordering_fields = ["data_extracao"]
    serializer_class = ProducaoApiarioSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return ProducaoApiario.objects.filter(
            colmeia__propriedade__user=self.request.user
        ).select_related("colmeia__propriedade")


@extend_schema(responses=SPASimpleSerializer)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def apiario_data(request):
    props = get_propriedade_optimizada(request.user)
    if not props:
        return Response({"colmeias": []})
    return Response(
        {
            "colmeias": ApiarioColmeiaSerializer(props.colmeias.all(), many=True).data,
            "ativas": props.colmeias.filter(ativa=True).count(),
        }
    )
