from django.db import models


class CentroCusto(models.Model):
    """
    Divisão por área/negócio da fazenda. Criado automaticamente ao cadastrar
    Propriedade via signal (ver app/signals.py).
    """

    TIPO_CHOICES = [
        ("AGRICULTURA", "Agricultura"),
        ("PECUARIA", "Pecuária"),
        ("MECANICA", "Mecânica/Oficina"),
        ("SEDE", "Sede/Administração"),
        ("GERAL", "Geral"),
    ]

    propriedade = models.ForeignKey(
        "Propriedade", on_delete=models.CASCADE, related_name="centros_custo"
    )
    nome = models.CharField(
        max_length=100, help_text="Ex.: Agricultura — Talhão 4, Pecuária — Leite"
    )
    descricao = models.TextField(blank=True)
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default="GERAL")
    ativo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Centro de Custo"
        verbose_name_plural = "Centros de Custo"
        ordering = ["propriedade", "tipo", "nome"]
        constraints = [
            models.UniqueConstraint(
                fields=["propriedade", "nome"], name="uniq_centro_nome_por_propriedade"
            ),
        ]

    def __str__(self):
        return f"{self.nome} [{self.get_tipo_display()}] — {self.propriedade.nome}"


class CustoProducao(models.Model):
    """
    Custo consolidado por safra (e opcionalmente por talhão).
    Todos os campos monetários são denormalizados e recalculados em save()
    a partir das fontes (RastreabilidadeSafra + LancamentoDetalhado).
    Somente leitura via API (ReadOnlyModelViewSet); recalculo via signal
    ou management command.
    """

    safra = models.ForeignKey("Safra", on_delete=models.CASCADE, related_name="custos")
    talhao = models.ForeignKey(
        "Talhao",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text="Se null, é o custo agregado da safra inteira",
    )
    centro_custo = models.ForeignKey(
        CentroCusto,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Centro principal (quando talhão null, indica rateio geral)",
    )
    insumos = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    maquina = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    mao_de_obra = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    embalagem = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    frete = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    impostos = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    outros = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    custo_total = models.DecimalField(
        max_digits=14, decimal_places=2, default=0, editable=False
    )
    custo_por_ha = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True, editable=False
    )
    custo_por_saca = models.DecimalField(
        max_digits=12, decimal_places=4, null=True, blank=True, editable=False
    )
    receita = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True, editable=False
    )
    lucro = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True, editable=False
    )
    margem = models.DecimalField(
        max_digits=6,
        decimal_places=4,
        null=True,
        blank=True,
        editable=False,
        help_text="lucro / receita (null se receita = 0)",
    )
    observacao = models.TextField(blank=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Custo de Produção"
        verbose_name_plural = "Custos de Produção"
        ordering = ["-safra__ano", "-talhao__nome"]
        constraints = [
            models.UniqueConstraint(
                fields=["safra", "talhao"], name="uniq_custo_por_safra_talhao"
            ),
        ]
        indexes = [
            models.Index(fields=["safra", "talhao"]),
        ]

    def __str__(self):
        alvo = self.talhao.nome if self.talhao_id else f"safra {self.safra}"
        return (
            f"Custo {alvo} — R$ {self.custo_total} (R$ {self.custo_por_saca or '—'}/sc)"
        )

    def save(self, *args, **kwargs):
        self.custo_total = (
            self.insumos
            + self.maquina
            + self.mao_de_obra
            + self.embalagem
            + self.frete
            + self.impostos
            + self.outros
        )
        area_ref = None
        if self.talhao_id:
            area_ref = self.talhao.area_hectare
        elif self.safra_id:
            area_ref = self.safra.area_plantada
        if area_ref and area_ref > 0:
            self.custo_por_ha = self.custo_total / area_ref
        else:
            self.custo_por_ha = None

        prod = self.safra.producao_total if self.safra_id else None
        if prod and prod > 0:
            self.custo_por_saca = self.custo_total / prod
        else:
            self.custo_por_saca = None

        if self.receita is not None:
            self.lucro = self.receita - self.custo_total
            self.margem = (self.lucro / self.receita) if self.receita != 0 else None
        else:
            self.lucro = None
            self.margem = None

        super().save(*args, **kwargs)


class LancamentoDetalhado(models.Model):
    """
    Categorização fina de um LancamentoFinanceiro para DRE/LCDPR.
    Um LancamentoFinanceiro pode ter 0..N detalhamentos (rateio).
    Quando existe, o DRE usa estes; quando não, usa LancamentoFinanceiro.categoria.
    Evita FK redundante para propriedade: herda de lancamento.propriedade quando
    vinculado; só exige propriedade própria quando standalone (sem lancamento).
    """

    CATEGORIA_DETALHADA_CHOICES = [
        ("VENDA_SOJA", "Venda de Soja"),
        ("VENDA_MILHO", "Venda de Milho"),
        ("VENDA_ALGODAO", "Venda de Algodão"),
        ("VENDA_CAFE", "Venda de Café"),
        ("VENDA_BOVINO", "Venda de Boi"),
        ("VENDA_LEITE", "Venda de Leite"),
        ("VENDA_SUINO", "Venda de Suíno"),
        ("OUTRA_RECEITA", "Outra Receita"),
        ("COMPRA_SEMENTE", "Compra de Semente"),
        ("COMPRA_FERTILIZANTE", "Compra de Fertilizante"),
        ("COMPRA_DEFENSIVO", "Compra de Defensivo"),
        ("COMPRA_CORRETIVO", "Compra de Corretivo"),
        ("COMPRA_RACAO", "Compra de Ração"),
        ("COMPRA_COMBUSTIVEL", "Compra de Combustível"),
        ("COMPRA_OUTRO_INSUMO", "Compra de Outro Insumo"),
        ("FOLHA_PAGAMENTO", "Folha de Pagamento"),
        ("DIARISTA", "Diarista/Safrista"),
        ("TERCEIRO", "Serviço Terceirizado"),
        ("MANUTENCAO", "Manutenção"),
        ("PECA", "Peça de Reposição"),
        ("COMBUSTIVEL", "Combustível"),
        ("DEPRECIACAO", "Depreciação"),
        ("IMPOSTO", "Imposto"),
        ("ENERGIA", "Energia"),
        ("SEGURO", "Seguro"),
        ("FINANCEIRO", "Despesa Financeira"),
        ("OUTRA_DESPESA", "Outra Despesa"),
    ]

    lancamento = models.ForeignKey(
        "LancamentoFinanceiro",
        on_delete=models.CASCADE,
        related_name="detalhamentos",
        null=True,
        blank=True,
    )
    _propriedade = models.ForeignKey(
        "Propriedade",
        on_delete=models.CASCADE,
        related_name="lancamentos_detalhados",
        null=True,
        blank=True,
        db_column="propriedade_id",
    )
    centro_custo = models.ForeignKey(
        CentroCusto,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    safra = models.ForeignKey("Safra", on_delete=models.SET_NULL, null=True, blank=True)
    talhao = models.ForeignKey(
        "Talhao", on_delete=models.SET_NULL, null=True, blank=True
    )
    categoria_detalhada = models.CharField(
        max_length=30, choices=CATEGORIA_DETALHADA_CHOICES, default="OUTRA_DESPESA"
    )
    valor_rateado = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Se null, assume lancamento.valor integral",
    )
    observacao = models.TextField(blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Lançamento Detalhado"
        verbose_name_plural = "Lançamentos Detalhados"
        ordering = ["-criado_em"]

    def __str__(self):
        if self.lancamento_id and self.lancamento.descricao:
            base = self.lancamento.descricao
        else:
            base = self.get_categoria_detalhada_display()
        return f"{base} — {self.categoria_detalhada} R$ {self.valor_rateado or '—'}"

    @property
    def propriedade(self):
        if self.lancamento_id:
            return self.lancamento.propriedade
        return self._propriedade

    @property
    def valor_efetivo(self):
        if self.valor_rateado is not None:
            return self.valor_rateado
        if self.lancamento_id:
            return self.lancamento.valor
        return 0
