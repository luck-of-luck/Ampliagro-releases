"""G-01 Cultivar viewset.

Escopo: `piquete__propriedade__user` (apenas o dono vê o catálogo de sua
fazenda). PATCH/DELETE são restritos a `staff`; POST a propriedade deve
pertencer ao usuário.
"""

from rest_framework import viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated

from app.api.serializers import CultivarSerializer
from app.models import Cultivar


class CultivarViewSet(viewsets.ModelViewSet):
    serializer_class = CultivarSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Cultivar.objects.all()

    def perform_create(self, serializer):
        prop = serializer.validated_data.get("propriedade")
        if prop and prop.user != self.request.user:
            raise PermissionDenied("Propriedade não pertence ao usuário.")
        serializer.save()

    def perform_update(self, serializer):
        if not self.request.user.is_staff:
            raise PermissionDenied("Apenas funcionários podem alterar cultivares.")
        serializer.save()

    def perform_destroy(self, instance):
        if not self.request.user.is_staff:
            raise PermissionDenied("Apenas funcionários podem apagar cultivares.")
        instance.delete()
