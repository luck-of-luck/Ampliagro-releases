"""G-03 EnsaioCultivar + FaixaEnsaio — ensaios de cultivares.

Ensaio (criação livre): sem faixas é válido, ranking vazio não é erro.
Faixa: uma "medida" de um cultivar dentro do ensaio; a repetição agrupa
as métricas.
"""

import uuid

from django.conf import settings
from django.db import models



class EnsaioCultivar(models.Model):
    """Ensaio de desempenho de cultivar num talhão/propriedade."""

    STATUS = [
        ("ativo", "Ativo"),
        ("concluido", "Concluído"),
        ("arquivado", "Arquivado"),
    ]

    uid = models.CharField(
        default=uuid.uuid4, max_length=64, unique=True
    )
    nome = models.CharField(blank=True, max_length=150)
    data_plantio = models.DateField(blank=True, null=True)
    status = models.CharField(
        max_length=20, choices=STATUS, default="ativo"
    )
    fonte_dado = models.CharField(max_length=20, default="declarado")
    criado_em = models.DateTimeField(auto_now_add=True)

    cultura = models.ForeignKey(
        "Cultura",
        blank=True,
        null=True,
        on_delete=models.PROTECT,
        related_name="ensaios_cultivar",
    )
    propriedade = models.ForeignKey(
        "Propriedade",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="ensaios_cultivar",
    )
    safra = models.ForeignKey(
        "Safra",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="ensaios_cultivar",
    )
    talhao = models.ForeignKey(
        "Talhao",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="ensaios_cultivar",
    )
    testemunha = models.ForeignKey(
        "Cultivar",
        blank=True,
        null=True,
        on_delete=models.PROTECT,
        related_name="ensaios_testemunha",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="ensaios_cultivar",
    )

    class Meta:
        verbose_name = "Ensaio de Cultivar"
        verbose_name_plural = "Ensaios de Cultivar"
        ordering = ["-criado_em", "-id"]
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["safra", "status"]),
        ]

    def __str__(self):
        return (
            f"Ensaio {self.uid} ({self.nome or 'sem nome'}) — {self.user_id}"
        )


class FaixaEnsaio(models.Model):
    """Uma faixa/repetição de medida dentro de um ensaio."""

    repeticao = models.PositiveIntegerField(default=1)
    area_m2 = models.DecimalField(
        blank=True, null=True, max_digits=10, decimal_places=2
    )
    produtividade_sc_ha = models.DecimalField(
        blank=True, null=True, max_digits=8, decimal_places=2
    )
    umidade_pct = models.DecimalField(
        blank=True, null=True, max_digits=5, decimal_places=2
    )
    registada_em = models.DateTimeField(
        blank=True, null=True, help_text="Quando o produtor mediu (relogio dele)"
    )
    sincronizado_em = models.DateTimeField(auto_now_add=True)

    cultivar = models.ForeignKey(
        "Cultivar",
        on_delete=models.PROTECT,
        related_name="faixas_ensaio",
    )
    ensaio = models.ForeignKey(
        EnsaioCultivar,
        on_delete=models.CASCADE,
        related_name="faixas",
    )

    class Meta:
        verbose_name = "Faixa de Ensaio"
        verbose_name_plural = "Faixas de Ensaio"
        constraints = [
            models.UniqueConstraint(
                fields=["ensaio", "cultivar", "repeticao"],
                name="uniq_faixa_ensaio",
            ),
        ]

    def __str__(self):
        return (
            f"Faixa {self.pk} "
            f"(ensaio {self.ensaio_id}, cultivar {self.cultivar_id}, "
            f"rep {self.repeticao})"
        )
