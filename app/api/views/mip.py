from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from app.api.serializers import MonitoramentoPraga_Serializer
from app.models import MonitoramentoPraga


class MonitoramentoPragaViewSet(viewsets.ModelViewSet):
    serializer_class = MonitoramentoPraga_Serializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return (
            MonitoramentoPraga.objects.filter(
                talhao__propriedade__user=self.request.user
            )
            .select_related("talhao", "cultura", "safra")
            .order_by("-data")
        )

    def perform_create(self, serializer):
        serializer.save()
