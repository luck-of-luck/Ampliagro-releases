from django.db import models

# Dependências 51-100 — Laranja, Orquídea, Jaca, etc.

DOENCA_LARANJA = [
    ("GREENING", "Greening (HLB)"),
    ("CVC", "CVC Clorose Variegada"),
    ("CANCRO", "Cancro cítrico"),
    ("MELANOSE", "Melanose"),
]


class DoencaLaranja(models.Model):
    propriedade = models.ForeignKey(
        "Propriedade", on_delete=models.CASCADE, related_name="doencas_laranja"
    )
    talhao = models.ForeignKey(
        "Talhao", on_delete=models.CASCADE, null=True, blank=True
    )
    doenca = models.CharField(max_length=15, choices=DOENCA_LARANJA)
    severidade = models.IntegerField(help_text="0-100")
    chuva_mm = models.DecimalField(
        max_digits=5,
        decimal_places=1,
        null=True,
        blank=True,
        help_text="Chuva que aumenta doença (Globo Rural 2026-09: chuvas beneficiam pomares mas aumentam doenças)",
    )
    observacao = models.TextField(blank=True)

    class Meta:
        verbose_name = "Doença Laranja (51)"
        verbose_name_plural = "Doenças Laranja"


class CultivoOrquidea(models.Model):
    propriedade = models.ForeignKey(
        "Propriedade", on_delete=models.CASCADE, related_name="orquideas"
    )
    especie = models.CharField(max_length=80, help_text="Ex: Phalaenopsis, Cattleya")
    umidade_pct = models.DecimalField(
        max_digits=4, decimal_places=1, help_text="60-80%"
    )
    livro_ref = models.CharField(
        max_length=120,
        blank=True,
        help_text="Livro 'como cultivar orquídeas' Globo Rural 2026-09",
    )

    class Meta:
        verbose_name = "Orquídea (68)"


class PosColheitaJaca(models.Model):
    propriedade = models.ForeignKey(
        "Propriedade", on_delete=models.CASCADE, related_name="jacas"
    )
    peso_kg = models.DecimalField(max_digits=5, decimal_places=1)
    mofada = models.BooleanField(
        default=False, help_text="GR Responde: como evitar jaca mofada"
    )
    tratamento = models.CharField(
        max_length=120, blank=True, help_text="Ex: cura 20°C, ventilação"
    )

    class Meta:
        verbose_name = "Jaca Pós-colheita (61)"


class BovinoDigestao(models.Model):
    animal = models.ForeignKey(
        "Animal", on_delete=models.CASCADE, related_name="digestao"
    )
    rumen_pct = models.DecimalField(
        max_digits=4, decimal_places=1, help_text="Rúmen 80%"
    )
    reticulo_pct = models.DecimalField(
        max_digits=4, decimal_places=1, help_text="Retículo 5%"
    )
    omaso_pct = models.DecimalField(
        max_digits=4, decimal_places=1, help_text="Omaso 7%"
    )
    abomaso_pct = models.DecimalField(
        max_digits=4, decimal_places=1, help_text="Abomaso 8% — total 4 estômagos"
    )

    class Meta:
        verbose_name = "Digestão Boi 4 estômagos (55)"
