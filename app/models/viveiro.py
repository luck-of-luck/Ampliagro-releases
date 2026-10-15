"""G-04 — Viveiro e LoteMuda (muda clonal).

Nicho 8 (micropropagacao/viveiro) nao tinha cadastro: a muda nascia sem
origem. Quem compra resultado paga por procedencia (§2.2), e a cadeia
matriz -> lote -> talhao precisa de comecar em `LoteMuda.origem_matriz` —
texto do produtor, nunca seed oficial (mesma regra de `Viveiro.protocolo`).

Datas de etapa (`data_repique`, `data_aclimatacao`, `data_expedicao`) sao
null ate acontecer: gerar data seria fabricar acontecimento (§0.3).
"""

from django.db import models


class Viveiro(models.Model):
    """Estrutura onde a muda e' produzida. Dado operacional, nao catalogo."""

    TIPOS = [
        ("in_vitro", "In vitro"),
        ("estaquia", "Estaquia"),
        ("enxertia", "Enxertia"),
        ("semente", "Semente"),
    ]

    propriedade = models.ForeignKey(
        "Propriedade", on_delete=models.CASCADE, related_name="viveiros"
    )
    nome = models.CharField(max_length=100)
    tipo = models.CharField(max_length=20, choices=TIPOS)
    # Texto livre do produtor: protocolo oficial por especie seria meta
    # (fora do escopo G-04 — ver "O que NAO entra" do plano-correcao).
    protocolo = models.TextField(blank=True, help_text="Pratica real do produtor")
    fonte_dado = models.CharField(max_length=20, default="declarado")
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Viveiro"
        verbose_name_plural = "Viveiros"
        ordering = ["-criado_em", "-id"]

    def __str__(self):
        return f"{self.nome} ({self.get_tipo_display()})"


class LoteMuda(models.Model):
    """Um lote de muda produzido num viveiro. Cadeia: matriz (texto) ->
    lote -> talhao de destino."""

    viveiro = models.ForeignKey(
        Viveiro, on_delete=models.CASCADE, related_name="lotes"
    )
    origem_matriz = models.CharField(
        max_length=150,
        blank=True,
        help_text="Matriz/planta-mae em texto livre — sem tabela oficial",
    )
    # Setimo PROTECT de `Cultura` (`tests_cascata_cultura.py`): muda e' tres
    # meses de viveiro; apagar a cultura nao apaga a muda ja produzida.
    cultura = models.ForeignKey(
        "Cultura",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="lotes_muda",
    )
    # `qtd_expedida` comeca em 0 (soma pode ser 0); `qtd_produzida` null e'
    # ausencia de contagem — afirmar 0 seria dizer "produzi nada".
    qtd_produzida = models.IntegerField(null=True, blank=True)
    qtd_expedida = models.IntegerField(default=0)
    # Cada etapa nula ate acontecer; nenhuma data e' gerada pelo sistema.
    data_repique = models.DateField(null=True, blank=True)
    data_aclimatacao = models.DateField(null=True, blank=True)
    data_expedicao = models.DateField(null=True, blank=True)
    # Muda plantada sai do lote; o talhao sobrevive ao lote (SET_NULL).
    talhao_destino = models.ForeignKey(
        "Talhao",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="lotes_muda",
    )
    sobrevivencia_pct = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    observacao = models.TextField(blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Lote de Muda"
        verbose_name_plural = "Lotes de Muda"
        ordering = ["-criado_em", "-id"]
        indexes = [
            models.Index(fields=["viveiro", "-criado_em"]),
        ]

    def __str__(self):
        return f"LoteMuda {self.pk} ({self.viveiro_id})"
