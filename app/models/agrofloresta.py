from django.db import models

# Agrofloresta + Biomassa + Restauração — dependências 51-100

CONSORCIO_AGROFLORESTA = [
    ("CAFE_INGA_MOGNO", "Café + Ingá + Mogno"),
    ("CACAU_ACAI", "Cacau + Açaí"),
    ("MILHO_EUCALIPTO", "Milho + Eucalipto"),
]


class Agrofloresta(models.Model):
    propriedade = models.ForeignKey(
        "Propriedade", on_delete=models.CASCADE, related_name="agroflorestas"
    )
    consorcio = models.CharField(max_length=20, choices=CONSORCIO_AGROFLORESTA)
    area_ha = models.DecimalField(max_digits=7, decimal_places=2)
    investimento_bilhoes = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        help_text="Globo Rural 2026-09: agroflorestas atraem bilhões, eventos extremos impulsionam adoção",
    )
    carbono_t = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Carbono sequestrado",
    )

    class Meta:
        verbose_name = "Agrofloresta (32/52)"


class BiomassaEucalipto(models.Model):
    propriedade = models.ForeignKey(
        "Propriedade", on_delete=models.CASCADE, related_name="biomassas"
    )
    area_ha = models.DecimalField(max_digits=7, decimal_places=2)
    volume_m3_ha = models.DecimalField(
        max_digits=6,
        decimal_places=1,
        help_text="Globo Rural 2026-08: biomassa eucalipto MT atrai investidores, <180 = alerta",
    )

    class Meta:
        verbose_name = "Biomassa Eucalipto (80)"


class RestauracaoMombak(models.Model):
    propriedade = models.ForeignKey(
        "Propriedade", on_delete=models.CASCADE, related_name="restauracoes_mombak"
    )
    area_ha = models.DecimalField(max_digits=7, decimal_places=2)
    valor_rs = models.DecimalField(
        max_digits=12, decimal_places=2, help_text="Mombak R$1 bi Amazônia"
    )

    class Meta:
        verbose_name = "Restauração Mombak (88)"
