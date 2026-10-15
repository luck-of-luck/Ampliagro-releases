"""Testes das automações: ação física, auto-resolve e job offline."""

from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from app.iot.alert_engine import check_offline_devices, evaluate_batch
from app.models import (
    AlertaTelemetria,
    ComandoDevice,
    Device,
    Propriedade,
    RegraAlertaTelemetria,
)


def _mkuser(name):
    return User.objects.create_user(username=name, password="x")


class AutomacaoFisicaTest(TestCase):
    def setUp(self):
        self.u = _mkuser("auto")
        self.prop = Propriedade.objects.create(
            user=self.u, nome="Faz Auto", area_total=10, uf="MT", cidade="X"
        )
        self.dev = Device.objects.create(
            propriedade=self.prop, device_eui="EUIAUTO01", nome="Válvula 1"
        )
        self.regra = RegraAlertaTelemetria.objects.create(
            propriedade=self.prop,
            nome="Solo seco",
            metric="umidade_solo",
            tipo="threshold_min",
            valor_ref=20,
            acao_fisica="abrir_valvula",
        )

    def _leituras(self, valor):
        return [
            {
                "metric": "umidade_solo",
                "value": valor,
                "timestamp": timezone.now(),
                "unit": "%",
            }
        ]

    def test_disparo_abre_valvula(self):
        criados = evaluate_batch(self.prop, self.dev, self._leituras(10))
        self.assertEqual(len(criados), 1)
        cmd = ComandoDevice.objects.filter(device=self.dev, comando="valve_open")
        self.assertTrue(cmd.exists())
        self.assertEqual(cmd.first().payload.get("via"), "regra_auto")

    def test_sem_flood_dedupe(self):
        evaluate_batch(self.prop, self.dev, self._leituras(10))
        evaluate_batch(self.prop, self.dev, self._leituras(9))
        self.assertEqual(
            ComandoDevice.objects.filter(device=self.dev, comando="valve_open").count(),
            1,
        )

    def test_auto_resolve_ao_normalizar(self):
        evaluate_batch(self.prop, self.dev, self._leituras(10))
        al = AlertaTelemetria.objects.get(regra=self.regra, device=self.dev)
        self.assertFalse(al.resolvido)
        evaluate_batch(self.prop, self.dev, self._leituras(50))
        al.refresh_from_db()
        self.assertTrue(al.resolvido)

    def test_sem_acao_so_alerta(self):
        self.regra.acao_fisica = ""
        self.regra.save(update_fields=["acao_fisica"])
        evaluate_batch(self.prop, self.dev, self._leituras(10))
        self.assertTrue(AlertaTelemetria.objects.filter(regra=self.regra).exists())
        self.assertFalse(ComandoDevice.objects.exists())


class OfflineJobTest(TestCase):
    def test_device_offline_gera_alerta(self):
        u = _mkuser("off")
        prop = Propriedade.objects.create(
            user=u, nome="Faz Off", area_total=10, uf="MT", cidade="X"
        )
        dev = Device.objects.create(
            propriedade=prop,
            device_eui="EUIOFF01",
            nome="Sensor Off",
            ultimo_push=timezone.now() - timedelta(hours=3),
        )
        RegraAlertaTelemetria.objects.create(
            propriedade=prop,
            nome="Offline",
            metric="bateria",
            tipo="offline",
        )
        check_offline_devices()
        self.assertTrue(
            AlertaTelemetria.objects.filter(device=dev, metric="offline").exists()
        )

    def test_verificar_offline_command(self):
        from django.core.management import call_command

        call_command("verificar_offline")
