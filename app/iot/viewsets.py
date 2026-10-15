from rest_framework import permissions, viewsets

from app.iot.serializers import (
    AlertaTelemetriaSerializer,
    ComandoDeviceSerializer,
    DeviceSerializer,
    FonteDadosExternaSerializer,
    GatewaySerializer,
    RegraAlertaSerializer,
)
from app.models import (
    AlertaTelemetria,
    ComandoDevice,
    Device,
    FonteDadosExterna,
    Gateway,
    RegraAlertaTelemetria,
)


class IsOwnerPropriedade(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        prop = getattr(obj, "propriedade", None)
        if prop:
            return prop.user_id == request.user.id
        # para Device: verifica propriedade
        if hasattr(obj, "propriedade_id"):
            return obj.propriedade.user_id == request.user.id
        return False


class GatewayViewSet(viewsets.ModelViewSet):
    serializer_class = GatewaySerializer
    permission_classes = [IsOwnerPropriedade]

    def get_queryset(self):
        return Gateway.objects.filter(
            propriedade__user=self.request.user
        ).select_related("propriedade")


class DeviceViewSet(viewsets.ModelViewSet):
    serializer_class = DeviceSerializer
    permission_classes = [IsOwnerPropriedade]

    def get_queryset(self):
        return Device.objects.filter(
            propriedade__user=self.request.user
        ).select_related("propriedade", "gateway", "talhao")


class RegraAlertaViewSet(viewsets.ModelViewSet):
    serializer_class = RegraAlertaSerializer
    permission_classes = [IsOwnerPropriedade]

    def get_queryset(self):
        return RegraAlertaTelemetria.objects.filter(propriedade__user=self.request.user)


class AlertaViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = AlertaTelemetriaSerializer
    permission_classes = [IsOwnerPropriedade]

    def get_queryset(self):
        qs = AlertaTelemetria.objects.filter(
            propriedade__user=self.request.user
        ).select_related("device", "regra")
        if self.request.query_params.get("resolvido") in ("0", "false", "False"):
            qs = qs.filter(resolvido=False)
        return qs.order_by("-timestamp")


class ComandoViewSet(viewsets.ModelViewSet):
    serializer_class = ComandoDeviceSerializer
    permission_classes = [IsOwnerPropriedade]

    def get_queryset(self):
        return ComandoDevice.objects.filter(
            device__propriedade__user=self.request.user
        ).select_related("device")


class FonteExternaViewSet(viewsets.ModelViewSet):
    serializer_class = FonteDadosExternaSerializer
    permission_classes = [IsOwnerPropriedade]

    def get_queryset(self):
        return FonteDadosExterna.objects.filter(propriedade__user=self.request.user)
