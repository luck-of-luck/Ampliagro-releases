from django.core.validators import FileExtensionValidator
from django.db import models

from app.validators import validate_upload_size


class MonitoramentoPraga(models.Model):
    """MIP — Manejo Integrado de Pragas: monitoramento por talhão."""

    talhao = models.ForeignKey(
        "Talhao", on_delete=models.CASCADE, related_name="monitoramentos_praga"
    )
    cultura = models.ForeignKey(
        "Cultura", on_delete=models.SET_NULL, null=True, blank=True
    )
    safra = models.ForeignKey("Safra", on_delete=models.SET_NULL, null=True, blank=True)
    data = models.DateField(db_index=True)
    praga = models.CharField(max_length=120)
    nivel_infestacao = models.DecimalField(
        max_digits=6, decimal_places=2, help_text="% ou nº/m — conforme a praga"
    )
    nivel_controle = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True
    )
    acao_recomendada = models.TextField(blank=True)
    foto = models.ImageField(
        upload_to="mip/",
        null=True,
        blank=True,
        validators=[
            FileExtensionValidator(["jpg", "jpeg", "png", "webp"]),
            validate_upload_size,
        ],
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-data"]
        verbose_name = "Monitoramento de Praga (MIP)"
        verbose_name_plural = "Monitoramentos de Praga (MIP)"
        indexes = [
            models.Index(fields=["talhao", "data"]),
        ]

    def __str__(self):
        return f"{self.praga} em {self.talhao} ({self.data:%d/%m/%Y})"

    @property
    def acima_controle(self):
        if self.nivel_controle is None:
            return False
        return self.nivel_infestacao > self.nivel_controle
