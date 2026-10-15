from datetime import timedelta

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone

from app.validators import validate_json_safe

CATEGORIAS_ESTOQUE = [
    ("INSUMO", "Insumo"),
    ("PRODUTO", "Produto Beneficiado"),
    ("RACAO", "Ração"),
    ("EMBALAGEM", "Embalagem"),
    ("PECA", "Peça de Reposição"),
    ("FERRAMENTA", "Ferramenta"),
    ("OUTRO", "Outro"),
]


class EstoqueItem(models.Model):
    propriedade = models.ForeignKey(
        "Propriedade", on_delete=models.CASCADE, related_name="estoque"
    )
    categoria = models.CharField(max_length=20, choices=CATEGORIAS_ESTOQUE)
    nome = models.CharField(max_length=150)
    quantidade = models.DecimalField(max_digits=10, decimal_places=2)
    quantidade_minima = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    quantidade_maxima = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    valor_unitario = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    unidade = models.CharField(max_length=20)
    local = models.CharField(max_length=100, blank=True)
    data_validade = models.DateField(null=True, blank=True)
    observacao = models.TextField(blank=True)

    def __str__(self):
        return f"{self.nome} - {self.quantidade} {self.unidade}"

    class Meta:
        verbose_name = "Item de Estoque"
        verbose_name_plural = "Itens de Estoque"
        ordering = ["categoria", "nome"]
        indexes = [
            models.Index(fields=["propriedade", "data_validade"]),
            models.Index(fields=["propriedade", "categoria"]),
        ]


class MovimentacaoEstoque(models.Model):
    TIPO_MOVIMENTACAO = [
        ("ENTRADA", "Entrada"),
        ("SAIDA", "Saída"),
        ("TRANSFERENCIA", "Transferência"),
        ("AJUSTE", "Ajuste"),
    ]
    item = models.ForeignKey(
        EstoqueItem, on_delete=models.CASCADE, related_name="movimentacoes"
    )
    tipo = models.CharField(max_length=20, choices=TIPO_MOVIMENTACAO)
    quantidade = models.DecimalField(max_digits=10, decimal_places=2)
    lote = models.CharField(max_length=50, blank=True)
    nf = models.CharField(max_length=50, blank=True, verbose_name="Nota Fiscal")
    data = models.DateField(default=timezone.now)
    responsavel = models.CharField(max_length=100, blank=True)
    observacao = models.TextField(blank=True)

    def __str__(self):
        return f"{self.get_tipo_display()} - {self.item.nome} ({self.quantidade})"


class OrdemCompra(models.Model):
    STATUS_COMPRA = [
        ("RASCUNHO", "Rascunho"),
        ("APROVADA", "Aprovada"),
        ("PEDIDA", "Pedida"),
        ("RECEBIDA", "Recebida"),
        ("CANCELADA", "Cancelada"),
    ]
    propriedade = models.ForeignKey("Propriedade", on_delete=models.CASCADE)
    fornecedor = models.CharField(max_length=150, blank=True)
    data_emissao = models.DateField(default=timezone.now)
    data_prevista = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_COMPRA, default="RASCUNHO")
    valor_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    observacao = models.TextField(blank=True)

    def __str__(self):
        return f"OC {self.id} - {self.get_status_display()}"


class Inventario(models.Model):
    propriedade = models.ForeignKey("Propriedade", on_delete=models.CASCADE)
    data = models.DateField(default=timezone.now)
    responsavel = models.CharField(max_length=100)
    status = models.CharField(
        max_length=20,
        choices=[("ABERTO", "Aberto"), ("CONCLUIDO", "Concluído")],
        default="ABERTO",
    )
    observacao = models.TextField(blank=True)

    def __str__(self):
        return f"Inventário {self.data} - {self.get_status_display()}"


class InventarioItem(models.Model):
    inventario = models.ForeignKey(
        Inventario, on_delete=models.CASCADE, related_name="itens"
    )
    estoque_item = models.ForeignKey(EstoqueItem, on_delete=models.CASCADE)
    quantidade_sistema = models.DecimalField(max_digits=10, decimal_places=2)
    quantidade_contada = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )

    def diferenca(self):
        if self.quantidade_contada is not None:
            return self.quantidade_contada - self.quantidade_sistema
        return 0

    def __str__(self):
        return f"{self.estoque_item.nome} (Sis: {self.quantidade_sistema} | Fís: {self.quantidade_contada})"
