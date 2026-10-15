from django.db import models
from django.utils import timezone


class Rota(models.Model):
    propriedade = models.ForeignKey(
        "Propriedade", on_delete=models.CASCADE, related_name="rotas"
    )
    nome = models.CharField(max_length=100)
    origem = models.CharField(max_length=200)
    destino = models.CharField(max_length=200)
    distancia_km = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True
    )
    tempo_min = models.IntegerField(null=True, blank=True)
    geojson = models.JSONField(default=dict, blank=True, help_text="LineString OSRM")
    criado_em = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.nome} ({self.distancia_km or '?'} km)"

    class Meta:
        ordering = ["nome"]


class Romaneio(models.Model):
    rota = models.ForeignKey(Rota, on_delete=models.CASCADE, related_name="romaneios")
    caminhao = models.ForeignKey(
        "Maquinario", on_delete=models.SET_NULL, null=True, blank=True
    )
    peso_bruto = models.DecimalField(max_digits=8, decimal_places=2)
    peso_liquido = models.DecimalField(max_digits=8, decimal_places=2)
    quebra = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    data = models.DateTimeField(default=timezone.now)
    cte = models.CharField(max_length=50, blank=True)

    def __str__(self):
        return f"Romaneio {self.id} - {self.rota.nome}"


class Frete(models.Model):
    romaneio = models.OneToOneField(
        Romaneio, on_delete=models.CASCADE, related_name="frete"
    )
    valor = models.DecimalField(max_digits=10, decimal_places=2)
    pago = models.BooleanField(default=False)

    def __str__(self):
        return f"Frete R$ {self.valor} - {self.romaneio}"
