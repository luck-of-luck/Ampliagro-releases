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


class AnimalViewSet(viewsets.ModelViewSet):
    filterset_fields = ["especie", "propriedade"]
    search_fields = ["raca", "especie", "observacao"]
    ordering_fields = ["data_entrada"]
    serializer_class = AnimalSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Animal só tem FK propriedade (lote é de AnimalIndividual) — fix FieldError
        return Animal.objects.filter(
            propriedade__user=self.request.user
        ).select_related("propriedade")

    def perform_create(self, serializer):
        prop = serializer.validated_data.get("propriedade")
        if prop and prop.user != self.request.user:
            raise PermissionDenied("Esta propriedade não pertence ao seu usuário")
        serializer.save()


class ProducaoAnimalViewSet(viewsets.ModelViewSet):
    filterset_fields = ["animal"]
    ordering_fields = ["data"]
    serializer_class = ProducaoAnimalSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return ProducaoAnimal.objects.filter(
            animal__propriedade__user=self.request.user
        ).select_related("animal")


@extend_schema(responses=SPASimpleSerializer)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def pecuaria_data(request):
    props = get_propriedade_optimizada(request.user)
    if not props:
        return Response({"animais": [], "producoes_leite": []})
    return Response(
        {
            "animais": AnimalSerializer(props.animais.all(), many=True).data,
            "total_cabecas": sum(a.quantidade for a in props.animais.all()),
            "producoes_leite": ProducaoAnimalSerializer(
                ProducaoAnimal.objects.filter(animal__propriedade=props)
                .select_related("animal")
                .order_by("-data")[:20],
                many=True,
            ).data,
        }
    )


class RacaoViewSet(viewsets.ModelViewSet):
    serializer_class = RacaoSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return (
            Racao.objects.filter(propriedade__user=self.request.user)
            .select_related("propriedade")
            .order_by("-criado_em")
        )

    def perform_create(self, serializer):
        serializer.save()


class MixPastagemViewSet(viewsets.ModelViewSet):
    """Mix forrageiro do piquete. Escopo atravessa `piquete__propriedade__user`
    (piquete nao tem user direto — mesmo formato de
    `LoteSementeViewSet`: `rastro__propriedade__user`)."""

    serializer_class = MixPastagemSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return MixPastagem.objects.filter(
            piquete__propriedade__user=self.request.user
        ).select_related("piquete", "cultura")
