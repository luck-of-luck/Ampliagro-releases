import pytest
from rest_framework import status

from app.models import Device, Gateway

pytestmark = pytest.mark.django_db


class TestTelemetriaAPI:
    def test_push_telemetry(self, auth_client, user_produtor):
        from app.models import Propriedade

        prop = Propriedade.objects.filter(user=user_produtor).first()
        gw = Gateway.objects.create(
            propriedade=prop, gateway_eui="0011223344556677", nome="GW Test"
        )
        dev = Device.objects.create(
            propriedade=prop,
            gateway=gw,
            device_eui="AABBCCDDEEFF0011",
            nome="Dev Test",
            tipo="GENERIC",
        )

        payload = {
            "gateway_mac": "00:11:22:33:44:55",
            "device_mac": "AA:BB:CC:DD:EE:FF",
            "temperature": 25.5,
            "humidity": 60.0,
        }
        response = auth_client.post(
            f"/api/iot/push/?device_eui={dev.device_eui}",
            payload,
            format="json",
            HTTP_X_API_KEY=gw.api_key,
        )
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_201_CREATED]

    def test_push_sem_auth_401(self, api_client):
        response = api_client.post("/api/iot/push/", {}, format="json")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestTarefasAPI:
    def test_listar_tarefas(self, auth_client):
        response = auth_client.get("/api/tarefas-estagio/")
        assert response.status_code == status.HTTP_200_OK
