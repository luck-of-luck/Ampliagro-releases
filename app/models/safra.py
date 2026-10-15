from datetime import timedelta

from django.contrib.auth.models import User
from django.core.validators import FileExtensionValidator
from django.db import models
from django.utils import timezone

from app.validators import validate_json_safe, validate_upload_size

CATEGORIAS_INSUMO = [
    ("SEMENTE", "Semente"),
    ("FERTILIZANTE", "Fertilizante"),
    ("DEFENSIVO", "Defensivo"),
    ("CORRETIVO", "Corretivo"),
    ("RACAO", "Ração"),
    ("COMBUSTIVEL", "Combustível"),
    ("EMBALAGEM", "Embalagem"),
    ("VETERINARIO", "Veterinário"),
    ("OUTRO", "Outro"),
]


class SafraTalhao(models.Model):
    safra = models.ForeignKey(
        "Safra", on_delete=models.CASCADE, related_name="safra_talhoes"
    )
    talhao = models.ForeignKey("Talhao", on_delete=models.CASCADE)
    area_rateio = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True
    )

    class Meta:
        unique_together = ("safra", "talhao")


class Safra(models.Model):
    propriedade = models.ForeignKey(
        "Propriedade", on_delete=models.CASCADE, related_name="safras"
    )
    talhao = models.ForeignKey(
        "Talhao", on_delete=models.SET_NULL, null=True, blank=True
    )
    talhoes = models.ManyToManyField(
        "Talhao", through="SafraTalhao", related_name="safras_m2m", blank=True
    )
    # PROTECT, e nao CASCADE. Apagar uma cultura do catalogo nao pode
    # apagar a safra de ninguem: `CASCADE` levava tres anos de producao
    # registada sem um unico aviso. Com PROTECT, a operacao e' recusada e
    # quem tenta recebe a verdade — que ha registos a depender. Ver
    # `tests_cascata_cultura.py`.
    cultura = models.ForeignKey("Cultura", on_delete=models.PROTECT)
    ano = models.IntegerField()
    safra_nome = models.CharField(max_length=50, blank=True)
    area_plantada = models.DecimalField(max_digits=8, decimal_places=2)
    area_colhida = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True
    )
    producao_total = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    produtividade = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True
    )
    receita_estimada = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    data_plantio = models.DateField(null=True, blank=True)
    data_colheita = models.DateField(null=True, blank=True)
    observacao = models.TextField(blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.cultura} - {self.safra_nome or self.ano}"

    class Meta:
        verbose_name = "Safra"
        verbose_name_plural = "Safras"
        ordering = ["-ano", "cultura"]
        indexes = [
            models.Index(fields=["propriedade", "ano"]),
            models.Index(fields=["propriedade", "cultura"]),
        ]


class Insumo(models.Model):
    propriedade = models.ForeignKey(
        "Propriedade", on_delete=models.CASCADE, related_name="insumos"
    )
    categoria = models.CharField(max_length=20, choices=CATEGORIAS_INSUMO)
    nome = models.CharField(max_length=150)
    quantidade = models.DecimalField(max_digits=10, decimal_places=2)
    unidade = models.CharField(max_length=20)
    valor_unitario = models.DecimalField(max_digits=10, decimal_places=2)
    estoque_minimo = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Alerta de ruptura quando saldo total de lotes < estoque_minimo",
    )
    data_aquisicao = models.DateField(null=True, blank=True)
    fornecedor = models.CharField(max_length=150, blank=True)
    nota_fiscal = models.CharField(max_length=50, blank=True)

    def __str__(self):
        return f"{self.nome} ({self.quantidade} {self.unidade})"

    class Meta:
        verbose_name = "Insumo"
        verbose_name_plural = "Insumos"
        ordering = ["-data_aquisicao", "nome"]


class AplicacaoInsumo(models.Model):
    insumo = models.ForeignKey(
        "Insumo", on_delete=models.CASCADE, related_name="aplicacoes"
    )
    talhao = models.ForeignKey(
        "Talhao", on_delete=models.CASCADE, related_name="aplicacoes"
    )
    data = models.DateField()
    dose = models.DecimalField(max_digits=8, decimal_places=2)
    responsavel = models.CharField(max_length=100, blank=True)
    observacao = models.TextField(blank=True)

    def __str__(self):
        return f"{self.insumo.nome} em {self.talhao.nome} ({self.data})"

    class Meta:
        verbose_name = "Aplicação de Insumo"
        verbose_name_plural = "Aplicações de Insumos"
        ordering = ["-data"]


class PlanoSafra(models.Model):
    safra = models.OneToOneField(Safra, on_delete=models.CASCADE, related_name="plano")
    orcamento_estimado = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    data_inicio_prevista = models.DateField(null=True, blank=True)
    data_fim_prevista = models.DateField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=[
            ("PLANEJAMENTO", "Planejamento"),
            ("EXECUCAO", "Em Execução"),
            ("CONCLUIDO", "Concluído"),
        ],
        default="PLANEJAMENTO",
    )

    class Meta:
        verbose_name = "Plano de Safra"
        verbose_name_plural = "Planos de Safra"

    def __str__(self):
        return f"Plano {self.safra}"


class AtividadePlanejada(models.Model):
    plano = models.ForeignKey(
        PlanoSafra, on_delete=models.CASCADE, related_name="atividades"
    )
    nome = models.CharField(max_length=100)
    data_prevista = models.DateField()
    custo_estimado = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    concluida = models.BooleanField(default=False)
    responsavel = models.CharField(
        max_length=100, blank=True, help_text="Quem executa (texto livre p/ a IA)"
    )
    # Roteamento profissional: área/pessoa da tarefa (lincagem trabalhador)
    cargo_alvo = models.CharField(
        max_length=30, blank=True, help_text="Cargo-alvo (ex: TRATORISTA)"
    )
    setor = models.CharField(
        max_length=100, blank=True, help_text="Setor/área alvo (ex: MECANICA)"
    )
    funcionario = models.ForeignKey(
        "Funcionario",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="atividades",
    )

    class Meta:
        verbose_name = "Atividade Planejada"
        verbose_name_plural = "Atividades Planejadas"
        ordering = ["data_prevista"]
        indexes = [
            models.Index(fields=["plano", "concluida", "data_prevista"]),
            models.Index(fields=["cargo_alvo"]),
            models.Index(fields=["funcionario", "concluida"]),
        ]


class ReceituarioAgronomico(models.Model):
    safra = models.ForeignKey(
        Safra, on_delete=models.CASCADE, related_name="receituarios"
    )
    talhao = models.ForeignKey(
        "Talhao", on_delete=models.SET_NULL, null=True, blank=True
    )
    art = models.CharField(max_length=50, blank=True, help_text="ART do agrônomo")
    diagnostico = models.TextField(blank=True)
    praga = models.CharField(max_length=100, blank=True)
    foto = models.ImageField(
        upload_to="receituario/",
        null=True,
        blank=True,
        validators=[
            FileExtensionValidator(["jpg", "jpeg", "png", "webp"]),
            validate_upload_size,
        ],
    )
    geo_lat = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    geo_lon = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    prescricao = models.JSONField(default=dict, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-criado_em"]
