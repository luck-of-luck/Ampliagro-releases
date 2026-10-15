from django.db import models

# Ficha PET exótico — resolve Bibi (garnizé SC), Rosella, Pônei, Cavalo, Asa Branca
# 4 dos 12 "com restrições" do estudo 50 vídeos

CATEGORIA_PET = [
    ("GARNIZE", "Garnizé (Bibi SC)"),
    ("ROSELLA", "Rosella eximinus"),
    ("PONEI", "Pônei"),
    ("CAVALO", "Cavalo"),
    ("ASA_BRANCA", "Ave símbolo (Asa Branca)"),
    ("OUTRO_PET", "Outro pet exótico"),
]

FUNCAO_PET = [
    ("RECEPCAO", "Recepção (Bibi)"),
    ("COMPANHIA", "Companhia"),
    ("GENETICA", "Genética / Leilão (R$5M Henrique & Juliano)"),
    ("ESPORTE", "Esporte / Rodeio"),
    ("TERAPIA", "Terapia"),
    ("OUTRA", "Outra"),
]


class PetExotico(models.Model):
    propriedade = models.ForeignKey(
        "Propriedade", on_delete=models.CASCADE, related_name="pets_exoticos"
    )
    categoria = models.CharField(max_length=15, choices=CATEGORIA_PET)
    nome = models.CharField(max_length=80, help_text="Ex: Bibi")
    idade_anos = models.DecimalField(
        max_digits=4, decimal_places=1, null=True, blank=True
    )
    funcao = models.CharField(max_length=15, choices=FUNCAO_PET, default="COMPANHIA")
    # rosella eximinus: colorido que rende — valor
    valor_estimado = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="R$ — ex: Rosella R$1.200, Pônei R$8k, Cavalo R$35k",
    )
    # Bibi: recepcionista que vai até o carro, pula no colo e canta
    comportamento = models.TextField(
        blank=True, help_text="Ex: vai até o carro, pula no colo e canta (Bibi)"
    )
    local = models.CharField(
        max_length=120,
        blank=True,
        help_text="Ex: minimercado São Domingos-SC, corredor, estacionamento",
    )
    # rastreabilidade pet
    origem = models.CharField(
        max_length=120, blank=True, help_text="Ex: choca 3 ovos 2022, só 1 vingou"
    )
    observacao = models.TextField(blank=True)

    def __str__(self):
        return f"{self.nome} ({self.get_categoria_display()})"

    class Meta:
        verbose_name = "Pet Exótico (Bibi/Rosella/Pônei)"
        verbose_name_plural = "Pets Exóticos"
        ordering = ["categoria", "nome"]
