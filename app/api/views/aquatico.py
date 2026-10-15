from django.core.exceptions import PermissionDenied
from rest_framework import permissions, viewsets
from rest_framework.permissions import IsAuthenticated

from app.api.serializers import *
from app.hierarquia import *
from app.models import *

from .utils import *


class LoteAquaticoViewSet(viewsets.ModelViewSet):
    filterset_fields = ["especie", "sistema", "propriedade"]
    search_fields = ["ambiente"]
    ordering_fields = ["data_povoamento"]
    serializer_class = LoteAquaticoSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return LoteAquatico.objects.filter(
            propriedade__user=self.request.user
        ).select_related("propriedade")

    def perform_create(self, serializer):
        prop = serializer.validated_data.get("propriedade")
        if prop and prop.user != self.request.user:
            raise PermissionDenied("Esta propriedade não pertence ao seu usuário")
        serializer.save()


class DespescaViewSet(viewsets.ModelViewSet):
    filterset_fields = ["lote"]
    ordering_fields = ["data"]
    serializer_class = DespescaSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Despesca.objects.filter(
            lote__propriedade__user=self.request.user
        ).select_related("lote")
