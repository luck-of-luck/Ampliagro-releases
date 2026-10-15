from django.urls import include, path
from rest_framework.routers import DefaultRouter

from app.iot import views as iot_views
from app.iot.viewsets import (
    AlertaViewSet,
    ComandoViewSet,
    DeviceViewSet,
    FonteExternaViewSet,
    GatewayViewSet,
    RegraAlertaViewSet,
)
from app.views.iot_dinamico import evento as iot_dinamico_evento

router = DefaultRouter()
router.register(r"gateways", GatewayViewSet, basename="iot-gateway")
router.register(r"devices", DeviceViewSet, basename="iot-device")
router.register(r"regras-alerta", RegraAlertaViewSet, basename="iot-regra")
router.register(r"alertas", AlertaViewSet, basename="iot-alerta")
router.register(r"comandos", ComandoViewSet, basename="iot-comando")
router.register(r"fontes-externas", FonteExternaViewSet, basename="iot-fonte")

urlpatterns = [
    path("push/", iot_views.push_telemetry, name="iot-push"),
    path("push/<str:device_eui>/", iot_views.push_telemetry, name="iot-push-device"),
    path("mqtt/webhook/", iot_views.ttn_webhook, name="iot-ttn-webhook"),
    path("telemetry/", iot_views.query_telemetry, name="iot-telemetry-query"),
    # O `verificar` do ciclo: o gateway confirma que o comando aconteceu.
    # Mesma autenticacao da telemetria (X-API-Key), pela mesma razao — uma
    # credencial que empurra telemetria pode confirmar um comando.
    path("comando/ack/", iot_views.comando_ack, name="iot-comando-ack"),
    path("sensor-lookup/", iot_views.sensor_lookup, name="iot-sensor-lookup"),
    path("sensor-stats/", iot_views.sensor_stats, name="iot-sensor-stats"),
    path("", include(router.urls)),
    # BUILD 4: receptor de evento do dispositivo dinamico. Endpoint PUBLICO
    # (unico do AmplIA): o ESP32 nao tem sessao nem token CSRF, e a autenticacao
    # e' por token revogavel no header. Ver `app/views/iot_dinamico.py`.
    path(
        "dinamico/evento/",
        iot_dinamico_evento,
        name="iot-dinamico-evento",
    ),
]
