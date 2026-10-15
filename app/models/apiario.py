from datetime import timedelta

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone

from app.validators import validate_json_safe


class ApiarioColmeia(models.Model):
    propriedade = models.ForeignKey(
        "Propriedade", on_delete=models.CASCADE, related_name="colmeias"
    )
    identificacao = models.CharField(max_length=50)
    tipo_abelha = models.CharField(max_length=50, blank=True, default="Apis mellifera")
    data_instalacao = models.DateField()
    ativa = models.BooleanField(default=True)
    localizacao = models.CharField(max_length=150, blank=True)
    observacao = models.TextField(blank=True)

    def __str__(self):
        return f"{self.identificacao} ({self.tipo_abelha})"

    class Meta:
        verbose_name = "Colmeia"
        verbose_name_plural = "Colmeias"
        ordering = ["identificacao"]


class ProducaoApiario(models.Model):
    colmeia = models.ForeignKey(
        "ApiarioColmeia", on_delete=models.CASCADE, related_name="producoes"
    )
    data_extracao = models.DateField()
    producao_mel_kg = models.DecimalField(max_digits=8, decimal_places=2)
    producao_cera_kg = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True
    )
    valor_venda = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True
    )
    observacao = models.TextField(blank=True)

    def __str__(self):
        return f"{self.colmeia} - {self.data_extracao}: {self.producao_mel_kg}kg mel"

    class Meta:
        verbose_name = "Produção de Apiário"
        verbose_name_plural = "Produções de Apiário"
        ordering = ["-data_extracao"]
