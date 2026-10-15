"""G-04 — Viveiro e LoteMuda (muda clonal).

Escopo por `propriedade__user` (leitura) + `perform_create` checando o dono
da propriedade/viveiro (padrão `rastreabilidade.py`): sem isso o POST e' um
vector de escrita na base alheia.
"""

from rest_framework import viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated

from app.api.serializers import LoteMudaSerializer, ViveiroSerializer
from app.models import LoteMuda, Viveiro


class ViveiroViewSet(viewsets.ModelViewSet):
    serializer_class = ViveiroSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Viveiro.objects.filter(
            propriedade__user=self.request.user
        ).select_related("propriedade")

    def perform_create(self, serializer):
        prop = serializer.validated_data.get("propriedade")
        if prop and prop.user != self.request.user:
            raise PermissionDenied("Propriedade não pertence ao usuário.")
        serializer.save()

    def perform_update(self, serializer):
        prop = serializer.validated_data.get("propriedade")
        if prop and prop.user != self.request.user:
            raise PermissionDenied("Propriedade não pertence ao usuário.")
        serializer.save()


class LoteMudaViewSet(viewsets.ModelViewSet):
    serializer_class = LoteMudaSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return LoteMuda.objects.filter(
            viveiro__propriedade__user=self.request.user
        ).select_related("viveiro", "cultura", "talhao_destino")

    def perform_create(self, serializer):
        viveiro = serializer.validated_data.get("viveiro")
        if viveiro and viveiro.propriedade.user != self.request.user:
            raise PermissionDenied("Viveiro não pertence ao usuário.")
        serializer.save()

    def perform_update(self, serializer):
        viveiro = serializer.validated_data.get("viveiro")
        if viveiro and viveiro.propriedade.user != self.request.user:
            raise PermissionDenied("Viveiro não pertence ao usuário.")
        serializer.save()
