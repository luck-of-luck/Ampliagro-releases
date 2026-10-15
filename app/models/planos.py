from datetime import date
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.utils import timezone

from app.models.core import Talhao


class ZonaManejo(models.Model):
    """Zona de manejo — agrupamento agronômico de talhões.

    Exemplo: "Topo", "Baixada", "Encosta Norte". Talhões na mesma zona
    recebem a mesma recomendação de adubação/calagem.
    """

    propriedade = models.ForeignKey(
        "Propriedade", on_delete=models.CASCADE, related_name="zonas_manejo"
    )
    nome = models.CharField(max_length=80)
    descricao = models.TextField(blank=True)
    cor = models.CharField(
        max_length=7, blank=True, help_text="Hex #RRGGBB para o mapa"
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Zona de Manejo"
        verbose_name_plural = "Zonas de Manejo"
        ordering = ["propriedade", "nome"]
        unique_together = [("propriedade", "nome")]

    def __str__(self):
        return f"{self.nome} ({self.propriedade.nome})"


TIPO_CUSTO = [
    ("MAO_DE_OBRA", "Mão de obra"),
    ("COMBUSTIVEL", "Combustível"),
    ("INSUMO", "Insumo (fertilizante, defensivo, semente, corretivo)"),
    ("DEPRECIACAO", "Depreciação de máquina/implemento"),
    ("SERVICO_TERCEIRO", "Serviço de terceiro"),
    ("OUTRO", "Outro"),
]


class CustoOperacao(models.Model):
    """Linha de custo operacional — o "que" compõe o orçado.

    O orçado total de um PlanoSafra deixa de ser um único Decimal e passa a
    ser a soma de `CustoOperacao` por categoria. Isto permite:
      - roll-up por categoria (ex: todo combustível da safra)
      - roll-up por mês (ex: mão de obra em janeiro vs fevereiro)
      - roll-up por zona (ex: custo/ha na baixada vs no topo)
      - comparativo orçado x realizado por linha
    """

    TIPO_CHOICES = TIPO_CUSTO

    plano = models.ForeignKey(
        "PlanoSafra", on_delete=models.CASCADE, related_name="custos_operacao"
    )
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    descricao = models.CharField(max_length=150, blank=True)
    valor = models.DecimalField(max_digits=14, decimal_places=2)
    # Para roll-up por mês/ano
    mes_referencia = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(12)],
        null=True,
        blank=True,
        help_text="Mês de referência (1-12). Se vazio, soma ao total do plano.",
    )
    # Para roll-up por zona
    zona = models.ForeignKey(
        "ZonaManejo",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="custos",
        help_text="Se preenchido, este custo aplica-se apenas à zona indicada.",
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Custo Operacional"
        verbose_name_plural = "Custos Operacionais"
        ordering = ["plano", "tipo", "mes_referencia", "id"]

    def __str__(self):
        base = f"{self.get_tipo_display()}: {self.valor}"
        if self.mes_referencia:
            base += f" (mês {self.mes_referencia})"
        if self.zona_id:
            base += f" [{self.zona.nome}]"
        return base


class PlanoSafraNovo(models.Model):
    """Plano de safra — substitui o antigo `app.models.safra.PlanoSafra`.

    O orçado agora é a soma de `CustoOperacao` (campos `orcamento_estimado`
    e `receita_estimada` mantêm-se para compatibilidade e migração).
    """

    STATUS_CHOICES = [
        ("PLANEJAMENTO", "Planejamento"),
        ("EXECUCAO", "Em Execução"),
        ("CONCLUIDO", "Concluído"),
    ]

    safra = models.OneToOneField(
        "Safra", on_delete=models.CASCADE, related_name="plano_novo"
    )
    # Campos legados (mantidos para migração e compatibilidade)
    orcamento_estimado = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
        help_text="Soma de CustoOperacao. Mantido para compatibilidade.",
    )
    receita_estimada = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Receita estimada total da safra.",
    )
    data_inicio_prevista = models.DateField(null=True, blank=True)
    data_fim_prevista = models.DateField(null=True, blank=True)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="PLANEJAMENTO"
    )
    # Novos campos
    observacao = models.TextField(blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Plano de Safra"
        verbose_name_plural = "Planos de Safra"
        ordering = ["-safra__ano", "safra__cultura"]

    def __str__(self):
        return f"Plano {self.safra}"

    @property
    def orcamento_total(self) -> Decimal:
        """Soma de CustoOperacao do plano (ignora `orcamento_estimado`)."""
        from django.db.models import Sum

        agg = self.custos_operacao.aggregate(s=Sum("valor"))
        return agg["s"] or Decimal("0")

    @property
    def orcamento_por_categoria(self):
        """Dicionário {tipo: Decimal} para roll-up rápido."""
        from django.db.models import Sum

        qs = self.custos_operacao.values("tipo").annotate(total=Sum("valor"))
        return {r["tipo"]: r["total"] or Decimal("0") for r in qs}

    @property
    def orcamento_por_mes(self):
        """Dicionário {mes: Decimal} para roll-up temporal."""
        from django.db.models import Sum

        qs = (
            self.custos_operacao.filter(mes_referencia__isnull=False)
            .values("mes_referencia")
            .annotate(total=Sum("valor"))
        )
        return {r["mes_referencia"]: r["total"] or Decimal("0") for r in qs}

    @property
    def orcamento_por_zona(self):
        """Dicionário {zona_id: Decimal} para roll-up espacial."""
        from django.db.models import Sum

        qs = (
            self.custos_operacao.filter(zona__isnull=False)
            .values("zona_id")
            .annotate(total=Sum("valor"))
        )
        return {r["zona_id"]: r["total"] or Decimal("0") for r in qs}


class AtividadePlanejadaNova(models.Model):
    """Atividade planejada — substitui o antigo `app.models.safra.AtividadePlanejada`.

    Cada atividade pode ter o seu próprio breakdown de custos via
    `CustoAtividade`, o que alimenta o roll-up por mês/categoria.
    """

    plano = models.ForeignKey(
        PlanoSafraNovo, on_delete=models.CASCADE, related_name="atividades_novas"
    )
    nome = models.CharField(max_length=120)
    data_prevista = models.DateField()
    # Custo estimado total da atividade (mantido para compatibilidade)
    custo_estimado = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    concluida = models.BooleanField(default=False)
    data_conclusao = models.DateField(null=True, blank=True)
    responsavel = models.CharField(max_length=100, blank=True)
    cargo_alvo = models.CharField(max_length=30, blank=True)
    setor = models.CharField(max_length=100, blank=True)
    funcionario = models.ForeignKey(
        "Funcionario",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="atividades_novas",
    )
    # Novos campos
    observacao = models.TextField(blank=True)
    prioridade = models.IntegerField(default=0, help_text="Maior = mais urgente")
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Atividade Planejada"
        verbose_name_plural = "Atividades Planejadas"
        ordering = ["data_prevista", "prioridade"]
        indexes = [
            models.Index(fields=["plano", "concluida", "data_prevista"]),
            models.Index(fields=["cargo_alvo"]),
            models.Index(fields=["funcionario", "concluida"]),
        ]

    def __str__(self):
        return f"{self.nome} ({self.data_prevista:%d/%m/%Y})"


class CustoAtividade(models.Model):
    """Breakdown de custo de uma AtividadePlanejada.

    Permite saber, por exemplo, que a atividade "Plantio" custa R$ 5.000,
    sendo R$ 2.000 de insumo, R$ 1.500 de combustível, R$ 1.500 de mão
    de obra. Alimenta o roll-up sem duplicar o `custo_estimado` total.
    """

    atividade = models.ForeignKey(
        AtividadePlanejadaNova, on_delete=models.CASCADE, related_name="custos"
    )
    tipo = models.CharField(max_length=20, choices=TIPO_CUSTO)
    valor = models.DecimalField(max_digits=12, decimal_places=2)
    descricao = models.CharField(max_length=150, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Custo da Atividade"
        verbose_name_plural = "Custos das Atividades"
        ordering = ["atividade", "tipo"]

    def __str__(self):
        return f"{self.atividade.nome} · {self.get_tipo_display()}: {self.valor}"


class CenarioPlano(models.Model):
    """Cenário de simulação — "e se?".

    Dados de entrada: área (ha), preço esperado (R$/sc ou R$/ha),
    custo estimado (R$/ha). Saída: margem, ponto de equilíbrio.
    """

    plano = models.ForeignKey(
        PlanoSafraNovo, on_delete=models.CASCADE, related_name="cenarios"
    )
    nome = models.CharField(max_length=100, help_text="Ex: otimista, base, pessimista")
    area_ha = models.DecimalField(
        max_digits=8, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))]
    )
    preco_esperado = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Preço esperado por sc (soja/milho) ou por ha (café/cana)",
    )
    custo_ha = models.DecimalField(
        max_digits=10, decimal_places=2, help_text="Custo estimado por hectare"
    )
    produtividade_estimada = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="sc/ha ou kg/ha. Se preenchido, valida margem vs receita.",
    )
    # Saídas calculadas
    margem_ha = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    margem_total = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True
    )
    ponto_equilibrio_sc = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="sc/ha necessários para cobrir o custo (se preço/sc informado)",
    )
    observacao = models.TextField(blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Cenário do Plano"
        verbose_name_plural = "Cenários do Plano"
        ordering = ["plano", "nome"]

    def __str__(self):
        return f"{self.plano} · {self.nome}"

    def calcular(self) -> dict:
        """Calcula margem e ponto de equilíbrio.

        Retorna dict com as chaves calculadas; também grava no modelo.
        """
        # Margem por ha = preço × produtividade - custo/ha
        if self.produtividade_estimada and self.preco_esperado:
            receita_ha = self.preco_esperado * self.produtividade_estimada
        else:
            # Se não tem produtividade, assume que preço_esperado já é por ha
            receita_ha = self.preco_esperado

        margem_ha = receita_ha - self.custo_ha
        margem_total = margem_ha * self.area_ha

        # Ponto de equilíbrio em sc/ha = custo_ha / preco_por_sc
        ponto_eq = None
        if self.preco_esperado and self.preco_esperado > 0:
            # Assume que preco_esperado é por sc se há produtividade,
            # senão por ha (nesse caso ponto de equilíbrio = 1 ha)
            if self.produtividade_estimada:
                ponto_eq = (self.custo_ha / self.preco_esperado).quantize(
                    Decimal("0.01")
                )

        self.margem_ha = margem_ha.quantize(Decimal("0.01"))
        self.margem_total = margem_total.quantize(Decimal("0.01"))
        self.ponto_equilibrio_sc = ponto_eq
        self.save(
            update_fields=[
                "margem_ha",
                "margem_total",
                "ponto_equilibrio_sc",
                "atualizado_em",
            ]
        )

        return {
            "receita_ha": receita_ha.quantize(Decimal("0.01")),
            "margem_ha": self.margem_ha,
            "margem_total": self.margem_total,
            "ponto_equilibrio_sc": self.ponto_equilibrio_sc,
        }

    def save(self, *args, **kwargs):
        # Recalcula sempre que gravar
        self.calcular()
        super().save(*args, **kwargs)


class ComparativoOrcadoRealizado(models.Model):
    """Comparativo orçado vs realizado por safra/talhão/categoria.

    Não é um modelo de dado persistido pelo usuário — é gerado sob
    demanda pelo serviço e pode ser salvo para histórico/auditoria.
    """

    safra = models.ForeignKey(
        "Safra", on_delete=models.CASCADE, related_name="comparativos"
    )
    talhao = models.ForeignKey(
        Talhao,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="comparativos",
    )
    categoria = models.CharField(max_length=20, choices=TIPO_CUSTO)
    zona = models.ForeignKey(
        ZonaManejo,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="comparativos",
    )
    mes = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(12)],
        null=True,
        blank=True,
        help_text="Se preenchido, comparativo mensal; se vazio, acumulado.",
    )
    orcado = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    realizado_pago = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    realizado_comprometido = models.DecimalField(
        max_digits=14, decimal_places=2, default=0
    )
    desvio = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    desvio_pct = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    gerado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Comparativo Orçado × Realizado"
        verbose_name_plural = "Comparativos Orçado × Realizado"
        ordering = ["-gerado_em"]
        indexes = [
            models.Index(fields=["safra", "talhao", "categoria", "mes"]),
            models.Index(fields=["safra", "gerado_em"]),
        ]

    def __str__(self):
        base = f"{self.safra} · {self.get_categoria_display()}"
        if self.talhao_id:
            base += f" · {self.talhao.nome}"
        if self.mes:
            base += f" · mês {self.mes}"
        return base

    @property
    def realizado_total(self) -> Decimal:
        return self.realizado_pago + self.realizado_comprometido

    @property
    def status(self) -> str:
        if self.desvio > 0:
            return "acima"
        elif self.desvio < 0:
            return "abaixo"
        return "no_orcado"

    def as_dict(self) -> dict:
        return {
            "categoria": self.categoria,
            "categoria_display": self.get_categoria_display(),
            "orcado": float(self.orcado),
            "realizado_pago": float(self.realizado_pago),
            "realizado_comprometido": float(self.realizado_comprometido),
            "realizado_total": float(self.realizado_total),
            "desvio": float(self.desvio),
            "desvio_pct": float(self.desvio_pct),
            "status": self.status,
            "talhao_id": self.talhao_id,
            "talhao": self.talhao.nome if self.talhao_id else None,
            "zona_id": self.zona_id,
            "zona": self.zona.nome if self.zona_id else None,
            "mes": self.mes,
            "gerado_em": self.gerado_em.isoformat(),
        }
