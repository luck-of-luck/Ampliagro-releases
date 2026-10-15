"""O sensor sozinho deve gerar contexto, sem inventar uma prescrição."""

from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from app.ia import proativo
from app.ia.sensores_proativo import sensores_para_cenario
from app.models import Device, Propriedade, RegraAlertaTelemetria, TelemetryData


class SensoresProativoTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("sensor-owner")
        self.outro = User.objects.create_user("sensor-other")
        self.prop = Propriedade.objects.create(
            user=self.user, nome="Sítio", area_total=10, cidade="Sorriso", uf="MT"
        )
        self.device = Device.objects.create(
            propriedade=self.prop, nome="Solo norte", device_eui="ABC123", tipo="SOLO"
        )
        self.regra = RegraAlertaTelemetria.objects.create(
            propriedade=self.prop,
            nome="Limite local",
            metric="ph_solo",
            tipo="threshold_min",
            valor_ref=5.5,
        )
        self.leitura = TelemetryData.objects.create(
            propriedade=self.prop,
            device=self.device,
            metric="ph_solo",
            value=4.2,
            timestamp=timezone.now(),
            qualidade="good",
        )

    def test_leitura_sozinha_gera_cenario_e_proposta_com_clima(self):
        previsao = {
            "ok": True,
            "dias": [
                {"dia": "2026-10-15", "mm": 20, "prob": 80, "tmin": 18, "tmax": 30}
            ],
        }
        with patch.object(proativo, "obter_previsao", return_value=previsao):
            cenario = proativo.montar_cenario(self.user, self.prop)
        self.assertTrue(cenario["tem_cenario"])
        self.assertIn("ph_solo", cenario["contexto"])
        achado = next(
            a
            for a in proativo.regras_deterministicas(cenario)
            if a["regra"] == "sensor_contextual"
        )
        self.assertEqual(achado["leitura_id"], self.leitura.pk)
        self.assertIn("20 mm", achado["mensagem"])
        self.assertIn("antes de definir produto e dose", achado["mensagem"])

    def test_nao_le_outra_conta(self):
        self.assertFalse(sensores_para_cenario(self.outro, self.prop)["tem_algo"])

    def test_sem_limite_configurado_nao_inventa_limite(self):
        self.regra.delete()
        self.assertFalse(sensores_para_cenario(self.user, self.prop)["tem_algo"])

    def test_leitura_antiga_ou_ruim_nao_vira_alarme(self):
        self.leitura.qualidade = "bad"
        self.leitura.save()
        self.assertFalse(sensores_para_cenario(self.user, self.prop)["tem_algo"])
        self.leitura.qualidade = "good"
        self.leitura.timestamp = timezone.now() - timedelta(days=2)
        self.leitura.save()
        self.assertFalse(sensores_para_cenario(self.user, self.prop)["tem_algo"])

    def test_leitura_recente_normal_supera_historico_acido(self):
        TelemetryData.objects.create(
            propriedade=self.prop,
            device=self.device,
            metric="ph_solo",
            value=6,
            timestamp=timezone.now(),
            qualidade="good",
        )
        self.assertFalse(sensores_para_cenario(self.user, self.prop)["tem_algo"])

    def test_fingerprint_muda_quando_sensor_muda(self):
        a = {"sensores": {"lista": [{"leitura_id": 1}]}}
        b = {"sensores": {"lista": [{"leitura_id": 2}]}}
        self.assertNotEqual(
            proativo._fingerprint_cenario(self.user, self.prop, a),
            proativo._fingerprint_cenario(self.user, self.prop, b),
        )
