"""G-06 MixPastagem viewset.

- `get_queryset`: só mixes que pertencem a piquetes do usuário.
- POST /api/mixes-pastagem/: `pct` soma <= 100 (cheque no clean do modelo).
- DELETE piquete → leva mixes (CASCADE).
- DELETE cultura com mix → ProtectedError (8º PROTECT).
"""

from rest_framework import viewsets, serializers
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated

from app.api.serializers import MixPastagemSerializer
from app.models import MixPastagem, Piquete


class MixPastagemViewSet(viewsets.ModelViewSet):
    serializer_class = MixPastagemSerializer
    permission_classes = [IsAuthenticated]
    queryset = MixPastagem.objects.all()

    def get_queryset(self):
        return (
            MixPastagem.objects.filter(
                piquete__propriedade__user=self.request.user
            )
            .select_related("piquete", "cultura")
            .distinct()
        )

    def perform_create(self, serializer):
        piquete = serializer.validated_data.get("piquete")
        if piquete and piquete.propriedade.user != self.request.user:
            raise serializers.ValidationError(
                {"piquete": "Piquete não pertence ao usuário."}
            )
        serializer.save()

    def perform_update(self, serializer):
        piquete = serializer.validated_data.get("piquete")
        if piquete and piquete.propriedade.user != self.request.user:
            raise PermissionDenied(
                "Piquete não pertence ao usuário.", code="permission_denied"
            )
        serializer.save()
