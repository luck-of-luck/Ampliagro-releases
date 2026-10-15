import hashlib
import secrets
from datetime import date

from django.db import models


class RastroItem(models.Model):
    """
    Lote rastreável de insumo/produto. Um registro = um lote físico recebido.
    Coexiste com EstoqueItem: EstoqueItem = itens genéricos sem lote/expiração
    (peças, ferramentas); RastroItem = itens agrícolas rastreáveis por lote
    (sementes, defensivos, fertilizantes) que exigem validade, NF e QR code.
    """

    propriedade = models.ForeignKey(
        "Propriedade", on_delete=models.CASCADE, related_name="rastros"
    )
    insumo = models.ForeignKey(
        "Insumo", on_delete=models.CASCADE, related_name="rastros"
    )
    numero_lote = models.CharField(
        max_length=50, blank=True, help_text="Lote do fabricante"
    )
    numero_serie = models.CharField(max_length=50, blank=True)
    nf_entrada = models.CharField(
        max_length=20, blank=True, help_text="Nota fiscal de entrada"
    )
    quantidade_recebida = models.DecimalField(max_digits=10, decimal_places=2)
    unidade = models.CharField(max_length=20, help_text="kg, L, sc, cx …")
    data_recebimento = models.DateField()
    fornecedor = models.CharField(max_length=150, blank=True)
    data_validade = models.DateField(null=True, blank=True)
    qr_code_hash = models.CharField(max_length=64, unique=True, null=True, blank=True)
    observacao = models.TextField(blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Rastro de Item"
        verbose_name_plural = "Rastros de Itens"
        ordering = ["-data_recebimento"]
        indexes = [
            models.Index(fields=["propriedade", "insumo", "data_recebimento"]),
            models.Index(fields=["propriedade", "data_validade"]),
        ]

    def __str__(self):
        lote = self.numero_lote or f"#{self.pk}"
        return f"{self.insumo.nome} [{lote}] — {self.propriedade.nome}"

    def save(self, *args, **kwargs):
        if not self.qr_code_hash:
            raw = f"{self.propriedade_id}:{self.insumo_id}:{self.numero_lote}:{self.data_recebimento}:{secrets.token_hex(8)}"
            self.qr_code_hash = hashlib.sha256(raw.encode()).hexdigest()[:32]
        super().save(*args, **kwargs)

    @property
    def saldo(self):
        """
        Quantidade ainda em estoque = recebido − soma das saídas.
        Evita campo denormalizado quantidade_saida (que divergiria do histórico).
        Usar annotate(Sum) na API para evitar N+1.
        """
        from django.db.models import Sum

        saidas = (
            self.movimentos.filter(tipo="SAIDA").aggregate(s=Sum("quantidade"))["s"]
            or 0
        )
        ajustes_neg = (
            self.movimentos.filter(tipo="AJUSTE").aggregate(s=Sum("quantidade"))["s"]
            or 0
        )
        return self.quantidade_recebida - saidas + ajustes_neg

    @property
    def vencido(self) -> bool:
        if self.data_validade:
            return self.data_validade < date.today()
        return False

    @property
    def dias_para_vencer(self):
        if not self.data_validade:
            return None
        return (self.data_validade - date.today()).days


class MovimentoEstoque(models.Model):
    """
    Uma movimentação de um RastroItem. Histórico completo — nunca editar, só criar
    novos registros (ledger append-only).
    quantidade sempre positiva; direção é dada por tipo.
    """

    TIPO_CHOICES = [
        ("ENTRADA", "Entrada (Compra/Retorno)"),
        ("SAIDA", "Saída (Uso/Venda/Perda)"),
        ("TRANSF", "Transferência entre talhões"),
        ("AJUSTE", "Ajuste de inventário"),
    ]
    rastro_item = models.ForeignKey(
        RastroItem, on_delete=models.CASCADE, related_name="movimentos"
    )
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES)
    quantidade = models.DecimalField(
        max_digits=10, decimal_places=2, help_text="Sempre positiva; direção via tipo"
    )
    data_movimento = models.DateField(default=date.today)
    talhao = models.ForeignKey(
        "Talhao",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Talhão de destino/origem (se aplicável)",
    )
    funcionario = models.ForeignKey(
        "Funcionario",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Quem retirou/entregou",
    )
    nota_fiscal = models.CharField(max_length=20, blank=True)
    motivo = models.TextField(blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Movimento de Estoque"
        verbose_name_plural = "Movimentos de Estoque"
        ordering = ["-data_movimento", "-criado_em"]
        indexes = [
            models.Index(fields=["rastro_item", "tipo"]),
            models.Index(fields=["rastro_item", "data_movimento"]),
        ]

    def __str__(self):
        return f"{self.get_tipo_display()} {self.quantidade} — {self.rastro_item} ({self.data_movimento})"


class RastreabilidadeSafra(models.Model):
    """
    Vínculo insumo → safra → talhão com custo. Estende AplicacaoInsumo com
    contexto de safra e custo (sem duplicar insumo/talhão quando já houver
    AplicacaoInsumo vinculada).
    """

    safra = models.ForeignKey("Safra", on_delete=models.CASCADE, related_name="rastros")
    aplicacao = models.ForeignKey(
        "AplicacaoInsumo",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="rastros_safra",
        help_text="Aplicação de origem (se existir); quando preenchida, insumo/talhão são herdados",
    )
    insumo = models.ForeignKey(
        "Insumo", on_delete=models.CASCADE, null=True, blank=True
    )
    rastro_item = models.ForeignKey(
        RastroItem,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text="Lote específico de origem do insumo",
    )
    talhao = models.ForeignKey(
        "Talhao", on_delete=models.CASCADE, null=True, blank=True
    )
    quantidade_aplicada = models.DecimalField(max_digits=10, decimal_places=2)
    custo_unitario = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        help_text="Snapshot de Insumo.valor_unitario na data da aplicação",
    )
    custo_total = models.DecimalField(max_digits=12, decimal_places=2, editable=False)
    operacao = models.CharField(
        max_length=100, blank=True, help_text="Adubação, Pulverização, Semeadura …"
    )
    data_aplicacao = models.DateField()
    observacao = models.TextField(blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Rastreabilidade de Safra"
        verbose_name_plural = "Rastreabilidades de Safra"
        ordering = ["-data_aplicacao"]
        indexes = [
            models.Index(fields=["safra", "talhao"]),
            models.Index(fields=["safra", "data_aplicacao"]),
        ]

    def __str__(self):
        if self.insumo_id:
            insumo_nome = self.insumo.nome
        elif self.aplicacao_id:
            insumo_nome = self.aplicacao.insumo.nome
        else:
            insumo_nome = "—"
        return f"{insumo_nome} → {self.safra} ({self.data_aplicacao}) R$ {self.custo_total}"

    def save(self, *args, **kwargs):
        self.custo_total = self.quantidade_aplicada * self.custo_unitario
        super().save(*args, **kwargs)

    @property
    def insumo_efetivo(self):
        """Insumo real, seja via FK direta ou via AplicacaoInsumo vinculada."""
        if self.insumo_id:
            return self.insumo
        if self.aplicacao_id:
            return self.aplicacao.insumo
        return None

    @property
    def talhao_efetivo(self):
        if self.talhao_id:
            return self.talhao
        if self.aplicacao_id:
            return self.aplicacao.talhao
        return None
