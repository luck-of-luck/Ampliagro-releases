"""G-02 LoteSemente — lote de semente vinculado a um RastroItem (1:1)."""

from django.db import models

from app.models import Cultivar, RastroItem


class LoteSemente(models.Model):
    """Laudo de qualidade de um lote de semente, rastreado por RastroItem."""

    CATEGORIAS = [
        ("S1", "S1"),
        ("S2", "S2"),
        ("C1", "C1"),
        ("C2", "C2"),
        ("basica", "Básica"),
        ("fiscalizada", "Fiscalizada"),
    ]
    TSI_FUNCOES = [
        ("fungicida", "Fungicida"),
        ("inseticida", "Inseticida"),
        ("nematicida", "Nematicida"),
        ("inoculante", "Inoculante"),
        ("micronutriente", "Micronutriente"),
    ]
    REVESTIMENTOS = [
        ("nu", "Nua"),
        ("grafite", "Grafite"),
        ("polimero", "Polímero"),
        ("pellet", "Pellet"),
    ]

    categoria = models.CharField(
        blank=True, null=True, max_length=15, choices=CATEGORIAS
    )
    germinacao_pct = models.DecimalField(
        blank=True, null=True, max_digits=5, decimal_places=2
    )
    vigor_pct = models.DecimalField(
        blank=True, null=True, max_digits=5, decimal_places=2
    )
    pureza_pct = models.DecimalField(
        blank=True, null=True, max_digits=5, decimal_places=2
    )
    peneira = models.CharField(blank=True, max_length=20)
    tsi_produto = models.CharField(blank=True, max_length=150)
    tsi_dose_ml_100kg = models.DecimalField(
        blank=True, null=True, max_digits=8, decimal_places=2
    )
    tsi_funcao = models.CharField(
        blank=True, null=True, max_length=20, choices=TSI_FUNCOES
    )
    tsi_prestador = models.CharField(blank=True, max_length=150)
    tsi_data = models.DateField(blank=True, null=True)
    revestimento = models.CharField(
        blank=True, null=True, max_length=15, choices=REVESTIMENTOS
    )
    fonte_dado = models.CharField(max_length=20, default="declarado")

    cultivar = models.ForeignKey(
        Cultivar,
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="lotes_semente",
    )
    rastro = models.OneToOneField(
        RastroItem,
        on_delete=models.CASCADE,
        related_name="lote_semente",
    )

    class Meta:
        verbose_name = "Lote de Semente"
        verbose_name_plural = "Lotes de Semente"
        indexes = [
            models.Index(fields=["cultivar"]),
        ]

    def __str__(self):
        return (
            f"LoteSemente {self.pk} "
            f"(lote {self.rastro_numero_lote or self.rastro_id})"
        )
