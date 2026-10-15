from datetime import timedelta

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone

from app.validators import validate_json_safe

TIPOS_MAQUINARIO = [
    ("TRATOR", "Trator"),
    ("COLHEITADEIRA", "Colheitadeira"),
    ("PULVERIZADOR", "Pulverizador"),
    ("CAMINHAO", "Caminhão"),
    ("IMPLEMENTO", "Implemento"),
    ("PLANTADEIRA", "Plantadeira"),
    ("DRONE", "Drone"),
    ("OUTRO", "Outro"),
]


class Maquinario(models.Model):
    propriedade = models.ForeignKey(
        "Propriedade", on_delete=models.CASCADE, related_name="maquinarios"
    )
    tipo = models.CharField(max_length=20, choices=TIPOS_MAQUINARIO)
    nome = models.CharField(max_length=100)
    marca = models.CharField(max_length=100, blank=True)
    modelo = models.CharField(max_length=100, blank=True)
    ano_fabricacao = models.IntegerField(null=True, blank=True)
    horas_uso = models.DecimalField(max_digits=8, decimal_places=1, default=0)
    ultima_manutencao = models.DateField(null=True, blank=True)
    proxima_manutencao = models.DateField(null=True, blank=True)
    ativo = models.BooleanField(default=True)

    # Depreciação
    valor_aquisicao = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    valor_residual = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    vida_util_anos = models.IntegerField(null=True, blank=True)
    data_aquisicao = models.DateField(null=True, blank=True)

    @property
    def valor_atual(self):
        """Depreciação linear: valor de aquisição menos desgaste proporcional.

        Retorna None se faltar base (valor, vida útil ou data). Nunca abaixo
        do residual. Ex: 100k, residual 10k, 10 anos, 5 anos de uso -> 55k.
        """
        try:
            if not (
                self.valor_aquisicao and self.vida_util_anos and self.data_aquisicao
            ):
                return None
            total = float(self.valor_aquisicao) - float(self.valor_residual or 0)
            anos_uso = (timezone.now().date() - self.data_aquisicao).days / 365.25
            fracao = min(max(anos_uso, 0) / float(self.vida_util_anos), 1)
            return round(float(self.valor_aquisicao) - total * fracao, 2)
        except (TypeError, ValueError, ArithmeticError):
            return None

    def __str__(self):
        return f"{self.nome} ({self.get_tipo_display()})"

    class Meta:
        verbose_name = "Maquinário"
        verbose_name_plural = "Maquinários"
        ordering = ["nome"]


class ManutencaoMaquinario(models.Model):
    maquinario = models.ForeignKey(
        Maquinario, on_delete=models.CASCADE, related_name="manutencoes"
    )
    data = models.DateField(default=timezone.now)
    tipo = models.CharField(
        max_length=30,
        choices=[
            ("PREVENTIVA", "Preventiva"),
            ("CORRETIVA", "Corretiva"),
            ("PREDITIVA", "Preditiva"),
        ],
        default="PREVENTIVA",
    )
    descricao = models.TextField()
    custo = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    horimetro = models.DecimalField(
        max_digits=8, decimal_places=1, null=True, blank=True
    )
    pecas = models.JSONField(default=list, blank=True)
    responsavel = models.CharField(max_length=100, blank=True)

    class Meta:
        ordering = ["-data"]
