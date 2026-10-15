from django.db import models
from django.utils import timezone

ESPECIES_AQUATICO = [
    ("TILAPIA", "Tilápia"),
    ("TAMBAQUI", "Tambaqui"),
    ("CARPA", "Carpa"),
    ("PINTADO", "Pintado"),
    ("PIRARUCU", "Pirarucu"),
    ("TRUTA", "Truta"),
    ("CAMARAO", "Camarão"),
    ("OUTRO_PEIXE", "Outro peixe"),
    ("OUTRO_CRUSTACEO", "Outro crustáceo"),
]

SISTEMAS_AQUATICO = [
    ("VIVEIRO_ESCAVADO", "Viveiro escavado"),
    ("TANQUE_REDE", "Tanque-rede"),
    ("TANQUE_ELEVADO", "Tanque elevado / caixa d'água"),
    ("AQUAPONIA", "Aquaponia"),
    ("BIOFLOCOS", "Bioflocos (BFT)"),
    ("OUTRO", "Outro"),
]


class LoteAquatico(models.Model):
    propriedade = models.ForeignKey(
        "Propriedade", on_delete=models.CASCADE, related_name="lotes_aquaticos"
    )
    especie = models.CharField(max_length=15, choices=ESPECIES_AQUATICO)
    sistema = models.CharField(
        max_length=20, choices=SISTEMAS_AQUATICO, default="VIVEIRO_ESCAVADO"
    )
    ambiente = models.CharField(
        max_length=100, blank=True, help_text="Viveiro/tanque onde está o lote"
    )
    quantidade = models.IntegerField()
    biomassa_media = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Peso médio por indivíduo (g)",
    )
    data_povoamento = models.DateField(null=True, blank=True)
    observacao = models.TextField(blank=True)

    def __str__(self):
        return f"{self.get_especie_display()} - {self.quantidade} un ({self.get_sistema_display()})"

    class Meta:
        verbose_name = "Lote Aquícola"
        verbose_name_plural = "Lotes Aquícolas"
        ordering = ["especie", "ambiente"]
        indexes = [
            models.Index(fields=["propriedade", "especie"]),
        ]


class Despesca(models.Model):
    lote = models.ForeignKey(
        "LoteAquatico", on_delete=models.CASCADE, related_name="despescas"
    )
    data = models.DateField(default=timezone.now)
    quantidade_kg = models.DecimalField(max_digits=8, decimal_places=2)
    valor_estimado = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True
    )
    observacao = models.TextField(blank=True)

    def __str__(self):
        return f"{self.lote} - {self.data}: {self.quantidade_kg} kg"

    class Meta:
        verbose_name = "Despesca"
        verbose_name_plural = "Despescas"
        ordering = ["-data"]
