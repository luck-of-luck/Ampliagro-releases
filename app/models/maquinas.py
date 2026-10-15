from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from app.models.iot import Device, TelemetryData


TIPO_MAQUINA = [
    ("TRATOR", "Trator"),
    ("COLHEITADEIRA", "Colheitadeira"),
    ("PULVERIZADOR", "Pulverizador"),
    ("CAMINHAO", "Caminhão"),
    ("IMPLEMENTO", "Implemento"),
    ("PLANTADEIRA", "Plantadeira"),
    ("DRONE", "Drone"),
    ("OUTRO", "Outro"),
]


class Maquina(models.Model):
    """Máquina = Maquinário + Device IoT.

    O `Maquinario` antigo era só cadastro. A `Maquina` liga o cadastro a um
    `Device` (tipo MAQUINARIO) que já traz telemetria (GPS, CAN, horímetro).
    Isto evita duplicar campos: o horímetro real vem do `TelemetryData`
    metric `horimetro`; o combustível vem de `combustivel`; a posição vem
    de `gps_lat`/`gps_lon`.
    """

    maquinario = models.OneToOneField(
        "Maquinario", on_delete=models.CASCADE, related_name="maquina"
    )
    device = models.OneToOneField(
        Device,
        on_delete=models.PROTECT,
        related_name="maquina",
        null=True,
        blank=True,
        help_text="Device IoT (tipo MAQUINARIO) que reporta a telemetria",
    )
    # Configuração de consumo para custo/hora real
    consumo_medio_l_h = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Consumo médio estimado (L/h). Usado como fallback quando não há telemetria.",
    )
    custo_hora_mao_obra = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=0,
        help_text="Custo de operador/hora (R$). Para custo total hora = combustível + mão de obra.",
    )
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Máquina"
        verbose_name_plural = "Máquinas"
        ordering = ["maquinario__nome"]

    def __str__(self):
        return f"{self.maquinario.nome} [{self.device.device_eui[:8]}]"

    # ---------- Telemetria recente (últimos N dias) ----------

    def _telemetria_recente(self, metric: str, dias: int = 7):
        """Últimas leituras de uma métrica para o device desta máquina."""
        if not self.device_id:
            return TelemetryData.objects.none()
        desde = timezone.now() - timedelta(days=dias)
        return TelemetryData.objects.filter(
            device=self.device, metric=metric, timestamp__gte=desde
        ).order_by("-timestamp")

    @property
    def horimetro_atual(self) -> Decimal | None:
        """Último horímetro reportado (h)."""
        ult = self._telemetria_recente("horimetro", dias=30).first()
        return ult.value if ult else None

    @property
    def combustivel_pct_atual(self) -> Decimal | None:
        """Último % de combustível reportado."""
        ult = self._telemetria_recente("combustivel", dias=7).first()
        return ult.value if ult else None

    @property
    def posicao_atual(self) -> tuple[Decimal, Decimal] | None:
        """Última posição GPS (lat, lon)."""
        lat = self._telemetria_recente("gps_lat", dias=1).first()
        lon = self._telemetria_recente("gps_lon", dias=1).first()
        if lat and lon:
            return (lat.value, lon.value)
        return None

    @property
    def velocidade_atual(self) -> Decimal | None:
        ult = self._telemetria_recente("velocidade", dias=1).first()
        return ult.value if ult else None

    @property
    def rpm_atual(self) -> Decimal | None:
        ult = self._telemetria_recente("rpm", dias=1).first()
        return ult.value if ult else None

    @property
    def temp_motor_atual(self) -> Decimal | None:
        ult = self._telemetria_recente("temp_motor", dias=1).first()
        return ult.value if ult else None

    # ---------- Consumo real (últimos 7 dias) ----------

    def consumo_real_ultimos_dias(self, dias: int = 7) -> dict:
        """Calcula consumo real a partir da telemetria `combustivel`.

        Regra: consumo = (primeiro_pct - último_pct) / 100 * capacidade_tanque.
        Se não há capacidade, usa `consumo_medio_l_h * horas_trabalhadas`.
        Retorna dict com litros, horas, custo_combustivel, custo_total_hora.
        """
        if not self.device_id:
            return {"erro": "sem_device"}

        serie = self._telemetria_recente("combustivel", dias=dias).order_by("timestamp")
        if serie.count() < 2:
            return {"erro": "dados_insuficientes"}

        primeiro = serie.first()
        ultimo = serie.last()
        delta_pct = float(primeiro.value) - float(ultimo.value)
        if delta_pct <= 0:
            return {"erro": "sem_consumo_detetado"}

        # Horas trabalhadas no período (horimetro delta)
        horimetro_serie = self._telemetria_recente("horimetro", dias=dias).order_by(
            "timestamp"
        )
        if horimetro_serie.count() >= 2:
            h_inicio = float(horimetro_serie.first().value)
            h_fim = float(horimetro_serie.last().value)
            horas = max(h_fim - h_inicio, 0)
        else:
            horas = float(dias) * 8  # fallback

        # Capacidade do tanque: se não tem, estima pelo consumo médio
        capacidade = getattr(self.maquinario, "capacidade_tanque_l", None)
        if capacidade:
            litros = (delta_pct / 100) * float(capacidade)
        elif self.consumo_medio_l_h:
            litros = float(self.consumo_medio_l_h) * horas
        else:
            return {"erro": "sem_capacidade_nem_consumo_medio"}

        custo_comb_l = getattr(settings, "CUSTO_DIESEL_L", 6.50)
        custo_combustivel = litros * custo_comb_l
        custo_mao_obra = float(self.custo_hora_mao_obra or 0) * horas
        custo_total = custo_combustivel + custo_mao_obra
        custo_hora = custo_total / horas if horas > 0 else 0

        return {
            "litros": round(litros, 2),
            "horas": round(horas, 1),
            "custo_combustivel": round(custo_combustivel, 2),
            "custo_mao_obra": round(custo_mao_obra, 2),
            "custo_total": round(custo_total, 2),
            "custo_hora": round(custo_hora, 2),
            "periodo_dias": dias,
        }

    # ---------- Depreciação (usa campos do Maquinario) ----------

    @property
    def valor_atual(self):
        return self.maquinario.valor_atual


TIPO_MANUTENCAO = [
    ("PREVENTIVA", "Preventiva"),
    ("CORRETIVA", "Corretiva"),
    ("PREDITIVA", "Preditiva"),
]


class Manutencao(models.Model):
    """Manutenção com gatilhos preditivos.

    `tipo=PREDITIVA` significa: foi criada automaticamente porque a telemetria
    cruzou um limite (horímetro, tempo, vibração, temp. motor). O campo
    `gatilho` guarda qual regra disparou.
    """

    maquina = models.ForeignKey(
        Maquina, on_delete=models.CASCADE, related_name="manutencoes"
    )
    data = models.DateField(default=timezone.now)
    tipo = models.CharField(max_length=15, choices=TIPO_MANUTENCAO)
    gatilho = models.CharField(
        max_length=40,
        blank=True,
        help_text="Ex: horimetro_250h, temp_motor_105C, vibracao_pico",
    )
    descricao = models.TextField()
    custo = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    horimetro = models.DecimalField(
        max_digits=8, decimal_places=1, null=True, blank=True
    )
    pecas = models.JSONField(default=list, blank=True)
    responsavel = models.CharField(max_length=100, blank=True)
    concluida = models.BooleanField(default=False)
    data_conclusao = models.DateField(null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-data"]
        indexes = [
            models.Index(fields=["maquina", "tipo", "data"]),
            models.Index(fields=["maquina", "concluida"]),
        ]

    def __str__(self):
        return f"{self.maquina} · {self.get_tipo_display()} · {self.data:%d/%m/%Y}"


class CustoMaquina(models.Model):
    """Custo real por hora de máquina, calculado da telemetria.

    Não é um campo escrito à mão: é gerado periodicamente (tarefa agendada)
    a partir de `Maquina.consumo_real_ultimos_dias()`. Guarda histórico
    para evolução do custo/hora.
    """

    maquina = models.ForeignKey(
        Maquina, on_delete=models.CASCADE, related_name="custos_hora"
    )
    periodo_inicio = models.DateField()
    periodo_fim = models.DateField()
    horas = models.DecimalField(max_digits=8, decimal_places=1)
    litros = models.DecimalField(max_digits=8, decimal_places=2)
    custo_combustivel = models.DecimalField(max_digits=10, decimal_places=2)
    custo_mao_obra = models.DecimalField(max_digits=10, decimal_places=2)
    custo_total = models.DecimalField(max_digits=10, decimal_places=2)
    custo_hora = models.DecimalField(max_digits=10, decimal_places=2)
    custo_diesel_l = models.DecimalField(max_digits=6, decimal_places=2)
    gerado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-periodo_fim"]
        unique_together = [("maquina", "periodo_inicio", "periodo_fim")]

    def __str__(self):
        return (
            f"{self.maquina} · {self.periodo_inicio:%d/%m}–{self.periodo_fim:%d/%m} "
            f"· R$ {self.custo_hora}/h"
        )

    @classmethod
    def gerar_do_periodo(cls, maquina: Maquina, dias: int = 7):
        """Gera/actualiza CustoMaquina a partir da telemetria real."""
        dados = maquina.consumo_real_ultimos_dias(dias)
        if "erro" in dados:
            return None, dados["erro"]

        fim = timezone.now().date()
        inicio = fim - timedelta(days=dias)
        obj, created = cls.objects.update_or_create(
            maquina=maquina,
            periodo_inicio=inicio,
            periodo_fim=fim,
            defaults={
                "horas": dados["horas"],
                "litros": dados["litros"],
                "custo_combustivel": dados["custo_combustivel"],
                "custo_mao_obra": dados["custo_mao_obra"],
                "custo_total": dados["custo_total"],
                "custo_hora": dados["custo_hora"],
                "custo_diesel_l": Decimal(
                    str(getattr(settings, "CUSTO_DIESEL_L", 6.50))
                ),
            },
        )
        return obj, "created" if created else "updated"
