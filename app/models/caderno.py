from django.contrib.auth.models import User
from django.db import models


class Nota(models.Model):
    """Caderno de Campo: anotação offline sincronizada."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="notas")
    talhao_id = models.IntegerField(null=True, blank=True)
    cultura_id = models.IntegerField(null=True, blank=True)
    conteudo = models.TextField()
    tipo = models.CharField(max_length=50, default="observacao")
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    offline_id = models.CharField(max_length=100, blank=True, default="")
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Nota de Campo"
        verbose_name_plural = "Notas de Campo"
        ordering = ["-criado_em"]

    def __str__(self):
        return f"Nota {self.id} - {self.tipo}"


class Foto(models.Model):
    """Foto anexada a uma nota de campo."""

    nota = models.ForeignKey(Nota, on_delete=models.CASCADE, related_name="fotos")
    imagem = models.ImageField(upload_to="caderno/fotos/")
    caption = models.CharField(max_length=255, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Foto de Campo"
        verbose_name_plural = "Fotos de Campo"
        ordering = ["-criado_em"]

    def __str__(self):
        return f"Foto {self.id} - nota {self.nota_id}"
