"""G-01 Cultivar — cultivar (linha do catálogo de cereais)."""

from django.db import models

from app.models import Cultura


class Cultivar(models.Model):
    """Uma cultivar registrada no catálogo do produtor (linha do saco)."""

    TECNICAS = [
        ("convencional", "Convencional"),
        ("transgenia", "Transgenia"),
        ("edicao_genica", "Edição gênica"),
        ("hibridacao", "Hibridação"),
    ]
    HABITOS = [
        ("determinado", "Determinado"),
        ("indeterminado", "Indeterminado"),
        ("semideterminado", "Semideterminado"),
    ]
    TOLERANCIAS = [
        ("alta", "Alta"),
        ("media", "Média"),
        ("baixa", "Baixa"),
    ]

    nome_comercial = models.CharField(max_length=100)
    obtentor = models.CharField(blank=True, max_length=100)
    evento = models.CharField(
        blank=True,
        max_length=60,
        help_text="O que o produtor leu no saco (RR2 PRO, Intacta, Convencional)",
    )
    tecnica = models.CharField(
        max_length=20, choices=TECNICAS, default="convencional"
    )
    grupo_maturacao = models.DecimalField(
        blank=True, null=True, max_digits=3, decimal_places=1
    )
    ciclo_min = models.IntegerField(blank=True, null=True)
    ciclo_max = models.IntegerField(blank=True, null=True)
    habito = models.CharField(
        blank=True, null=True, max_length=20, choices=HABITOS
    )
    densidade_mil_plantas_ha = models.DecimalField(
        blank=True, null=True, max_digits=6, decimal_places=1
    )
    tol_seca = models.CharField(
        blank=True, null=True, max_length=10, choices=TOLERANCIAS
    )
    tol_sal = models.CharField(
        blank=True, null=True, max_length=10, choices=TOLERANCIAS
    )
    resistencias = models.JSONField(blank=True, default=list)
    fonte_dado = models.CharField(max_length=20, default="declarado")
    ativo = models.BooleanField(default=True)

    cultura = models.ForeignKey(
        Cultura,
        on_delete=models.PROTECT,
        related_name="cultivares",
    )

    class Meta:
        verbose_name = "Cultivar"
        verbose_name_plural = "Cultivares"
        ordering = ["nome_comercial"]

    def __str__(self):
        return self.nome_comercial
