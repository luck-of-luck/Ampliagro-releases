"""G-02 LoteSemente viewset.

- `get_queryset`: só lote rastreável que pertence ao usuário.
- POST /api/lotes-semente/: `rastro` OBRIGATÓRIO (FK one-to-one → RastroItem).
- DELETE /api/rastros/{pk}/: leva o LoteSemente (CASCADE).
- GET /api/rastros/{pk}/: retorna o RastroItem com `lote_semente` aninhado.
"""

from django.db import IntegrityError
from rest_framework import viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated

from app.api.serializers import LoteSementeSerializer
from app.models import LoteSemente, Piquete, RastroItem, Talhao


class LoteSementeViewSet(viewsets.ModelViewSet):
    serializer_class = LoteSementeSerializer
    permission_classes = [IsAuthenticated]
    queryset = LoteSemente.objects.all()

    def get_queryset(self):
        return (
            LoteSemente.objects.filter(rastro__propriedade__user=self.request.user)
            .select_related("rastro", "cultivar")
            .distinct()
        )

    def perform_create(self, serializer):
        serializer.save()

    def perform_destroy(self, instance):
        instance.rastro.delete()
