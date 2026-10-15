from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from app.validators import validate_json_safe

ESPECIES_ANIMAL = [
    ("BOVINO", "Bovino"),
    ("SUINO", "Suíno"),
    ("OVINO", "Ovino"),
    ("CAPRINO", "Caprino"),
    ("EQUINO", "Equino"),
    ("BUFALO", "Búfalo"),
    ("AVES", "Aves"),
    ("COELHO", "Coelho"),
    ("PEIXE", "Peixe"),
]

TIPOS_PRODUCAO_ANIMAL = [
    ("CORTE", "Corte"),
    ("LEITE", "Leite"),
    ("OVOS", "Ovos"),
    ("MISTO", "Misto"),
    ("MEL", "Mel"),
    ("OUTRO", "Outro"),
]


class Animal(models.Model):
    propriedade = models.ForeignKey(
        "Propriedade", on_delete=models.CASCADE, related_name="animais"
    )
    especie = models.CharField(max_length=10, choices=ESPECIES_ANIMAL)
    tipo_producao = models.CharField(
        max_length=10, choices=TIPOS_PRODUCAO_ANIMAL, default="CORTE"
    )
    raca = models.CharField(max_length=100, blank=True)
    quantidade = models.IntegerField()
    peso_medio = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True
    )
    data_entrada = models.DateField(null=True, blank=True)
    observacao = models.TextField(blank=True)

    def __str__(self):
        return f"{self.get_especie_display()} - {self.quantidade} cab ({self.get_tipo_producao_display()})"

    class Meta:
        verbose_name = "Animal (Rebanho)"
        verbose_name_plural = "Animais (Rebanho)"
        ordering = ["especie", "raca"]
        indexes = [
            models.Index(fields=["propriedade", "especie"]),
        ]


class ProducaoAnimal(models.Model):
    animal = models.ForeignKey(
        "Animal", on_delete=models.CASCADE, related_name="producoes"
    )
    data = models.DateField()
    quantidade_produzida = models.DecimalField(max_digits=8, decimal_places=2)
    unidade = models.CharField(max_length=20)
    valor_estimado = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True
    )
    observacao = models.TextField(blank=True)

    def __str__(self):
        return (
            f"{self.animal} - {self.data}: {self.quantidade_produzida} {self.unidade}"
        )

    class Meta:
        verbose_name = "Produção Animal"
        verbose_name_plural = "Produções Animais"
        ordering = ["-data"]


class AnimalIndividual(models.Model):
    propriedade = models.ForeignKey(
        "Propriedade", on_delete=models.CASCADE, related_name="animais_individuais"
    )
    lote = models.ForeignKey(
        Animal,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="individuos",
    )
    brinco = models.CharField(
        max_length=20
    )  # Não unique=True globalmente para evitar conflito inter-fazendas, mas ideal na aplicação ser validado por fazenda
    brinco_eletronico = models.CharField(max_length=30, blank=True)
    nome = models.CharField(max_length=50, blank=True)
    especie = models.CharField(max_length=10, choices=ESPECIES_ANIMAL)
    raca = models.CharField(max_length=100, blank=True)
    sexo = models.CharField(max_length=1, choices=[("M", "Macho"), ("F", "Fêmea")])
    data_nascimento = models.DateField(null=True, blank=True)
    pai = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="filhos_pai",
    )
    mae = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="filhos_mae",
    )
    status = models.CharField(
        max_length=20,
        choices=[
            ("ativo", "Ativo"),
            ("vendido", "Vendido"),
            ("morto", "Morto"),
            ("descartado", "Descartado"),
        ],
        default="ativo",
    )
    peso_nascimento = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True
    )
    observacao = models.TextField(blank=True)

    def __str__(self):
        return f"{self.brinco} - {self.nome or self.especie}"


class Pesagem(models.Model):
    animal = models.ForeignKey(
        AnimalIndividual, on_delete=models.CASCADE, related_name="pesagens"
    )
    data = models.DateField(default=timezone.now)
    peso = models.DecimalField(max_digits=6, decimal_places=2)
    tipo = models.CharField(
        max_length=20,
        choices=[("entrada", "Entrada"), ("rotina", "Rotina"), ("saida", "Saída")],
        default="rotina",
    )

    def __str__(self):
        return f"{self.animal.brinco} - {self.peso}kg ({self.data})"


class ProtocoloSanitario(models.Model):
    propriedade = models.ForeignKey("Propriedade", on_delete=models.CASCADE)
    nome = models.CharField(max_length=100)
    especie = models.CharField(max_length=10, choices=ESPECIES_ANIMAL)
    descricao = models.TextField(blank=True)
    dias_para_repeticao = models.IntegerField(
        null=True, blank=True, help_text="Dias para próxima dose"
    )

    def __str__(self):
        return f"{self.nome} ({self.especie})"


class EventoSanitario(models.Model):
    animal = models.ForeignKey(
        AnimalIndividual, on_delete=models.CASCADE, related_name="eventos_sanitarios"
    )
    protocolo = models.ForeignKey(
        ProtocoloSanitario, on_delete=models.SET_NULL, null=True, blank=True
    )
    data = models.DateField(default=timezone.now)
    tipo = models.CharField(
        max_length=30,
        choices=[
            ("vacina", "Vacina"),
            ("vermifugo", "Vermífugo"),
            ("tratamento", "Tratamento"),
        ],
    )
    produto = models.CharField(max_length=100)
    dose = models.CharField(max_length=50, blank=True)
    responsavel = models.CharField(max_length=100, blank=True)
    proxima_dose = models.DateField(null=True, blank=True)

    def __str__(self):
        return f"{self.tipo} - {self.animal.brinco} em {self.data}"


class Piquete(models.Model):
    propriedade = models.ForeignKey(
        "Propriedade", on_delete=models.CASCADE, related_name="piquetes"
    )
    talhao = models.ForeignKey(
        "Talhao",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="piquetes",
    )
    nome = models.CharField(max_length=100)
    area_hectare = models.DecimalField(max_digits=8, decimal_places=2)
    capacidade_ua_ha = models.DecimalField(
        max_digits=6, decimal_places=2, help_text="Capacidade suporte UA/ha estimada"
    )
    status = models.CharField(
        max_length=20,
        choices=[
            ("descanso", "Descanso"),
            ("pastejo", "Pastejo"),
            ("manutencao", "Manutenção"),
        ],
        default="descanso",
    )
    animais = models.ManyToManyField(
        AnimalIndividual, blank=True, related_name="piquetes_atuais"
    )

    def __str__(self):
        return f"{self.nome} ({self.area_hectare} ha)"


# --------------------------------------------------------------------------
# G-06 — MIX PASTAGEM: o que esta plantado no piquete
# --------------------------------------------------------------------------
# Sem isto, `Piquete.capacidade_ua_ha` e' numero sem lastro (VISAO §2.1):
# a capacidade depende do que esta no piquete, e o piquete nao diz o que
# esta nele.
# --------------------------------------------------------------------------


def checar_soma_mix(piquete_id, pct, exclude_pk=None):
    """Soma do mix do piquete com `pct` incluido. Devolve (soma, erro).

    Uma funcao, dois chamadores (`MixPastagem.clean` e o serializer DRF):
    regra de validacao escrita em dois sitios e regra que diverge.

    Soma > 100 = impossivel fisico -> erro. Soma < 100 = aceiro, cocho,
    area nao semeada — passa sempre: bloquear ate' 100 seria inventar
    exigencia para ter o que registrar (mesma critica de
    `producao.py:471-472`).
    """
    if piquete_id is None or pct is None:
        return None, None
    outras = (
        MixPastagem.objects.filter(piquete_id=piquete_id)
        .exclude(pk=exclude_pk)
        .aggregate(s=models.Sum("pct"))["s"]
        or Decimal("0")
    )
    soma = outras + pct
    if soma > 100:
        return soma, f"Soma do mix ({soma}%) passa de 100%."
    return soma, None


class MixPastagem(models.Model):
    """Mix forrageiro (porcentagem por especie) de um piquete.

    `pct` 0 e' soma valida (0% da especie — a especie esta no mix, so que
    nenhuma area), nao razao de ausencia: razao de ausencia e' a linha que
    nao existe.
    """

    piquete = models.ForeignKey(
        Piquete, on_delete=models.CASCADE, related_name="mixes"
    )
    # Oitavo PROTECT de `Cultura` (`tests_cascata_cultura.py`): o mix e'
    # o que o piquete contem; apagar a especie do catalogo nao apaga o
    # que ja foi plantado.
    cultura = models.ForeignKey(
        "Cultura",
        on_delete=models.PROTECT,
        related_name="mixes_pastagem",
    )
    pct = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("100"))],
    )
    # Null ate' declarar — nenhuma taxa e' gerada pelo sistema (tabela de
    # taxa recomendada por especie sem fonte seria meta, ver plano G-06).
    taxa_semeadura_kg_ha = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True
    )
    data_semeadura = models.DateField(null=True, blank=True)
    fonte_dado = models.CharField(max_length=20, default="declarado")
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Mix de Pastagem"
        verbose_name_plural = "Mixes de Pastagem"
        ordering = ["piquete_id", "cultura_id"]
        constraints = [
            models.UniqueConstraint(
                fields=["piquete", "cultura"], name="uniq_mix_piquete_cultura"
            ),
        ]

    @property
    def pct_nao_atribuido(self):
        """100 - soma real do mix no banco. Nunca negativo: soma > 100 e'
        recusada antes de gravar (`clean`/serializer)."""
        soma, _ = checar_soma_mix(self.piquete_id, self.pct, exclude_pk=self.pk)
        return max(Decimal("100") - (soma or 0), Decimal("0.00"))

    def clean(self):
        _, erro = checar_soma_mix(self.piquete_id, self.pct, exclude_pk=self.pk)
        if erro:
            raise ValidationError({"pct": erro})

    def __str__(self):
        return f"{self.pct}% no piquete {self.piquete_id}"


TIPOS_RACAO = [
    ("CONCENTRADO", "Concentrado"),
    ("VOLUMOSO", "Volumoso"),
    ("MINERAL", "Mineral"),
]

ESPECIES_RACAO = [
    ("BOVINO", "Bovino"),
    ("SUINO", "Suíno"),
    ("OVINO", "Ovino"),
    ("CAPRINO", "Caprino"),
    ("AVES", "Aves"),
    ("PEIXE", "Peixe"),
]

FASES_RACAO = [
    ("CRESCIMENTO", "Crescimento"),
    ("TERMINACAO", "Terminação"),
    ("LACTACAO", "Lactação"),
    ("REPRODUCAO", "Reprodução"),
    ("MANUTENCAO", "Manutenção"),
]


class Racao(models.Model):
    """Ração: estoque (nutrição) + formulação (cadastro animal)."""

    propriedade = models.ForeignKey(
        "Propriedade", on_delete=models.CASCADE, related_name="racoes"
    )
    nome = models.CharField(max_length=120)
    # Estoque/nutrição (tela racoes-nutricao)
    tipo = models.CharField(max_length=15, choices=TIPOS_RACAO, blank=True, default="")
    quantidade = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text="Estoque em kg",
    )
    fornecedor = models.CharField(max_length=120, blank=True)
    data_validade = models.DateField(null=True, blank=True)
    # Formulação (aba rações do cadastro animal)
    especie_alvo = models.CharField(
        max_length=10, choices=ESPECIES_RACAO, blank=True, default=""
    )
    fase = models.CharField(max_length=15, choices=FASES_RACAO, blank=True, default="")
    composicao = models.TextField(
        blank=True, help_text="Composição percentual (texto/JSON)"
    )
    custo_kg = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Ração"
        verbose_name_plural = "Rações"
        ordering = ["-criado_em"]
        indexes = [
            models.Index(fields=["propriedade", "nome"]),
        ]

    def __str__(self):
        return f"{self.nome} ({self.get_tipo_display() or self.get_fase_display() or 'ração'})"
