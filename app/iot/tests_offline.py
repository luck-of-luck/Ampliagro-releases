"""Um device que calou nao pode ficar "online" para sempre.

`check_offline_devices` (alert_engine.py) e o job que SHOULD marca um device
como offline quando ele para de enviar leitura. Nao existe outro caminho:
`evaluate_batch` faz `continue` explicito nas regras de tipo `offline`
("tratado separadamente por job periodico").

O bug: o job procurava a regra offline com `metric="bateria"`. `metric` e um
campo independente de `tipo` — a lista de metricas e de sensores
(temperatura, umidade_solo, ph_solo...) e "bateria" nao tem relacao nenhuma com
estar offline. Resultado: so recebia alerta de offline quem tivesse, por
coincidencia, uma regra de bateria marcada como `tipo="offline"`. Para todos
os outros devices, o `continue` do `if not regras.exists()` saltava o device
inteiro e ele ficava `ativo=True` para sempre, sem alerta e sem log.

Este ficheiro fixa o comportamento: uma regra `tipo="offline"` deve ser
suficiente para o device ser detectado, qualquer que seja a metrica.
"""

from __future__ import annotations

from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from app.iot.alert_engine import check_offline_devices
from app.models import (
    AlertaTelemetria,
    Device,
    Propriedade,
    RegraAlertaTelemetria,
)


class DeviceOfflineTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("produtor", password="x")
        self.prop = Propriedade.objects.create(
            user=self.user, nome="Fazenda Boa", area_total=100
        )
        self.device = Device.objects.create(
            device_eui="AA:BB:CC:DD:EE:FF",
            nome="Sensor 1",
            propriedade=self.prop,
            intervalo_seg=900,
            ativo=True,
            ultimo_push=timezone.now() - timedelta(hours=6),
        )

    def test_regra_offline_nao_precisa_de_metric_bateria(self):
        """Regra tipo=offline com metrica de sensor normal (ex: temperatura).

        Este e o cenario real: o produtor cria a regra de offline pela UI e a
        metrica gravada e a do sensor, nao "bateria".
        """
        RegraAlertaTelemetria.objects.create(
            propriedade=self.prop,
            nome="Sensor calado",
            metric="temperatura",  # <- nada a ver com offline
            tipo="offline",
            severidade="warning",
            ativa=True,
        )

        check_offline_devices()

        self.assertTrue(
            AlertaTelemetria.objects.filter(
                device=self.device, metric="offline"
            ).exists(),
            "device que calou ha 6h nao gerou alerta de offline",
        )

    def test_sem_regra_offline_nao_cria_alerta(self):
        """Sem regra de offline nao ha alerta — mas o job tambem nao pode
        explodir nem marcar device ativo como inativo por conta propria."""
        check_offline_devices()
        self.assertFalse(AlertaTelemetria.objects.filter(device=self.device).exists())
        self.device.refresh_from_db()
        self.assertTrue(self.device.ativo)

    def test_device_em_silencio_nao_recebe_alerta(self):
        """Device que NAO calou (ultimo_push recente) nao gera alerta."""
        Device.objects.filter(pk=self.device.pk).update(ultimo_push=timezone.now())
        RegraAlertaTelemetria.objects.create(
            propriedade=self.prop,
            nome="Sensor calado",
            metric="temperatura",
            tipo="offline",
            ativa=True,
        )

        check_offline_devices()

        self.assertFalse(
            AlertaTelemetria.objects.filter(device=self.device).exists(),
            "device que enviou agora ha pouco foi marcado offline",
        )

    def test_debounce_nao_duplica_alerta(self):
        """O job e periodico: rodar duas vezes nao pode duplicar o alerta."""
        RegraAlertaTelemetria.objects.create(
            propriedade=self.prop,
            nome="Sensor calado",
            metric="temperatura",
            tipo="offline",
            ativa=True,
        )
        check_offline_devices()
        check_offline_devices()

        self.assertEqual(
            AlertaTelemetria.objects.filter(
                device=self.device, metric="offline"
            ).count(),
            1,
        )
