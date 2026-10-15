"""Tributos por item de NF-e — o regime atual e o que vem a seguir.

## O que se perdeu, e porquê se chama assim

`nfe_auto.py` extraía `CFOP`, `qCom` e `vUnCom` do `<prod>` e **deitava
fora o grupo `<imposto>` inteiro**: ICMS com a sua CST e a sua base, IPI, PIS,
COFINS. O ficheiro de teste do próprio projecto
(`tests/fixtures/nfe_sample.xml`) tem tudo isso, e nada era importado.

Para quem vende 13.750 reais de soja, o ICMS de 1.650 é um custo real que o
ledger não via. O `custo_producao.py` não o encontra, o DRE não o subtract, e
o produtor compara o preço de venda com um custo incompleto — **sem nunca
saber que está incompleto**.

## Dois regimes, um model

A NF-e hoje traz ICMS/IPI/PIS/COFINS (`<ICMS00>`, `<IPINT>`, `<PISNT>`,
`<COFINSNT>`). A reforma traz o grupo 9906 (`IBSCBS`). Os dois não coexistem
no mesmo documento durante a transição — e **não vou inventar as tags do 9906**:
não há uma NF-e com esse grupo em lado nenhum deste repositório, e a
documentação oficial exige autenticação.

Por isso `regime` distingue os dois e os campos do 9906 ficam `None` com
motivo. **Estrutura pronta, números honestos.** Quando uma nota real com o
grupo 9906 aparecer, é só preencher — e o `parse` precisa de ser verificado
contra essa nota, não contra a memória.

## `fonte_obrigatoria` em vez de uma mistura

O `AliquotaReforma` da §23H exige `fonte` porque uma alíquota sem dono é um
índice tributário sem dono. Aqui a regra é mais fraca e por isso está
nomeada: o valor vem **da nota**, e a nota é o documento legal. O que este
model garante é que ninguém escreve aqui à mão um valor que não veio da nota.
"""

from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models


class AliquotaReforma(models.Model):
    """Alíquota de IBS ou CBS, com a fonte que a justifica."""

    TRIBUTO_CHOICES = [
        ("IBS", "IBS — Imposto sobre Bens e Serviços"),
        ("CBS", "CBS — Contribuição sobre Bens e Serviços"),
    ]

    codigo = models.CharField(max_length=12, choices=TRIBUTO_CHOICES)
    aliquota = models.DecimalField(
        max_digits=7,
        decimal_places=4,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text="Percentual, ex.: 0.9000 para 0,9%. Nulo = não sei, e isso "
        "é diferente de zero.",
    )
    reducao_percentual = models.DecimalField(
        max_digits=7,
        decimal_places=4,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
    )
    vigencia_inicio = models.DateField(null=True, blank=True)
    vigencia_fim = models.DateField(null=True, blank=True)
    fonte = models.TextField(
        help_text="OBRIGATÓRIO. URL e data de publicação da tabela oficial, ou "
        "o documento legal. Uma linha sem fonte não entra no cálculo."
    )
    observacao = models.TextField(blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Alíquota da Reforma Tributária"
        verbose_name_plural = "Alíquotas da Reforma Tributária"
        ordering = ["-vigencia_inicio", "codigo"]

    def __str__(self):
        if self.aliquota is None:
            return f"{self.codigo} — não apurada"
        return f"{self.codigo} {self.aliquota}%"


class ItemTributario(models.Model):
    """Um item de lançamento com os tributos que a NF-e declarava.

    Ligado ao `LancamentoFinanceiro` porque é o lançamento que se fiscaliza, e
    não a nota — a mesma nota tem uma linha por item e o produtor decide o que
    entra no próprio ledger.
    """

    REGIME_CHOICES = [
        ("ICMS_IPI", "Regime atual — ICMS/IPI/PIS/COFINS"),
        ("IBS_CBS", "Reforma tributária — grupo 9906"),
        ("DESCONHECIDO", "Sem grupo de tributos na nota"),
    ]

    lancamento = models.ForeignKey(
        "LancamentoFinanceiro",
        on_delete=models.CASCADE,
        related_name="itens_tributarios",
    )
    descricao = models.CharField(max_length=255, blank=True)
    ncm = models.CharField(
        max_length=12,
        blank=True,
        default="",
        help_text="NCM do item. Sem NCM a nota está incompleta.",
    )
    regime = models.CharField(
        max_length=14,
        choices=REGIME_CHOICES,
        default="DESCONHECIDO",
        help_text="Qual grupo de tributos a nota trazia.",
    )

    # --- Regime atual: valores que vieram da nota ---
    base_calculo = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="`vBC` da nota. Nulo = a nota não trazia base.",
    )
    icms_cst = models.CharField(max_length=4, blank=True, default="")
    icms_origem = models.CharField(max_length=2, blank=True, default="")
    icms_aliquota = models.DecimalField(
        max_digits=7, decimal_places=4, null=True, blank=True
    )
    valor_icms = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True
    )
    ipi_cst = models.CharField(max_length=4, blank=True, default="")
    valor_ipi = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True
    )
    pis_cst = models.CharField(max_length=4, blank=True, default="")
    valor_pis = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True
    )
    cofins_cst = models.CharField(max_length=4, blank=True, default="")
    valor_cofins = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True
    )

    # --- Reforma: o grupo 9906 ainda não foi verificado contra uma nota real ---
    cbs_codigo = models.CharField(
        max_length=10,
        blank=True,
        default="",
        help_text="Vazio = sem grupo 9906. Não é preenchido por inferência.",
    )
    ibs_codigo = models.CharField(max_length=10, blank=True, default="")

    motivo = models.TextField(
        blank=True,
        help_text="Porque é que o tributo não está preenchido. Vazio = a nota "
        "trazia o grupo.",
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Item com tributos de NF-e"
        verbose_name_plural = "Itens com tributos de NF-e"
        indexes = [models.Index(fields=["lancamento"])]

    def __str__(self):
        return f"{self.descricao[:40]} ({self.ncm or 'sem NCM'}, {self.regime})"

    @property
    def total_tributos(self) -> Decimal | None:
        """Soma dos tributos **declarados na nota**.

        `None` quando nenhum dos quatro veio. Uma nota sem grupo de tributos
        tem imposto **desconhecido**, não zero — e a diferença é a mesma entre
        "não houve imposto" e "não sei".
        """
        valores = [
            v
            for v in (
                self.valor_icms,
                self.valor_ipi,
                self.valor_pis,
                self.valor_cofins,
            )
            if v is not None
        ]
        if not valores:
            return None
        return sum(valores, Decimal("0.00"))
