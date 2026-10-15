"""G-03 EnsaioCultivar viewset.

- POST /api/ensaios-cultivar/: idempotente por `uid` (reenvio do aparelho).
- GET /api/ensaios-cultivar/{pk}/: detalhe do ensaio + faixas.
- GET /api/ensaios-cultivar/{pk}/ranking/: ranking puro (sem BD).
- POST /api/faixas-ensaio/: cria faixa; ensaio alheio → 400.
- GET /api/faixas-ensaio/{pk}/: detalhe da faixa.
"""

from decimal import Decimal

from django.db import IntegrityError, transaction
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from app.api.serializers import (
    EnsaioCultivarSerializer,
    EnsaioRankingSerializer,
    FaixaEnsaioSerializer,
)
from app.models import Cultivar, EnsaioCultivar, FaixaEnsaio, Piquete, Talhao
from app.services.ensaio import ranking_ensaio


class EnsaioCultivarViewSet(viewsets.ModelViewSet):
    serializer_class = EnsaioCultivarSerializer
    permission_classes = [IsAuthenticated]
    queryset = EnsaioCultivar.objects.all()

    def get_queryset(self):
        return (
            EnsaioCultivar.objects.filter(user=self.request.user)
            .select_related(
                "cultura", "propriedade", "safra", "talhao", "testemunha"
            )
            .distinct()
        )

    def perform_create(self, serializer):
        prop = serializer.validated_data.get("propriedade")
        if prop and prop.user != self.request.user:
            raise PermissionDenied("Propriedade não pertence ao usuário.")
        serializer.save(user=self.request.user)

    @action(detail=True, methods=["get"], url_path="ranking")
    def ranking(self, request, pk=None):
        ensaio = self.get_object()
        # Só pode ver/ordenar o seu.
        if ensaio.user_id != request.user.id:
            return Response(
                {"detail": "Não encontrado."}, status=404
            )

        linhas = ranking_ensaio(
            [{"cultivar_id": f.cultivar_id, "produtividade_sc_ha": f.produtividade_sc_ha} for f in ensaio.faixas.all()],
            testemunha_id=ensaio.testemunha_id,
        )
        return Response(
            {
                "ranking": EnsaioRankingSerializer(linhas, many=True).data,
                "fonte_dado": ensaio.fonte_dado,
            }
        )


class FaixaEnsaioViewSet(viewsets.ModelViewSet):
    serializer_class = FaixaEnsaioSerializer
    permission_classes = [IsAuthenticated]
    queryset = FaixaEnsaio.objects.all()

    def get_queryset(self):
        return (
            FaixaEnsaio.objects.filter(
                ensaio__user=self.request.user
            )
            .select_related("ensaio", "cultivar")
            .distinct()
        )

    def perform_create(self, serializer):
        ensaio = serializer.validated_data.get("ensaio")
        if ensaio and ensaio.user_id != self.request.user.id:
            raise ValidationError({"ensaio": "Este ensaio não pertence ao usuário."})
        serializer.save()
