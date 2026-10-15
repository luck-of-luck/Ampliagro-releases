from datetime import timedelta
from uuid import uuid4

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from app.seguranca import EncryptedCharField
from app.validators import validate_json_safe

CATEGORIAS_FINANCEIRO = [
    ("VENDA_PROD", "Venda de Produção"),
    ("VENDA_ANIMAL", "Venda de Animal"),
    ("VENDA_LEITE", "Venda de Leite"),
    ("INSUMO", "Compra de Insumo"),
    ("FOLHA", "Folha de Pagamento"),
    ("MANUTENCAO", "Manutenção"),
    ("COMBUSTIVEL", "Combustível"),
    ("FRETE", "Frete"),
    ("IMPOSTO", "Imposto"),
    ("SERVICO", "Serviço Terceiro"),
    ("ENERGIA", "Energia"),
    ("OUTRO", "Outro"),
]

# Categorias que NUNCA sao receita. Todas as outras sao de entrada.
#
# Estas sao as de saida de dinheiro da fazenda. `OUTRO` fica dos dois lados
# de proposito: o produtor que escreve "OUTRO" quer dizer o que quiser, e
# inventar regra aqui seria chatear quem sabe o que esta lancando. Quem nao
# cabe em lista nenhuma e' o que o `diagnostico_dados` aponta.
CATEGORIAS_SO_DESPESA = frozenset(
    {
        "INSUMO",
        "FOLHA",
        "MANUTENCAO",
        "COMBUSTIVEL",
        "FRETE",
        "IMPOSTO",
        "SERVICO",
        "ENERGIA",
    }
)


class LancamentoFinanceiro(models.Model):
    TIPOS = [("RECEITA", "Receita"), ("DESPESA", "Despesa")]
    propriedade = models.ForeignKey(
        "Propriedade", on_delete=models.CASCADE, related_name="lancamentos"
    )
    tipo = models.CharField(max_length=10, choices=TIPOS)
    categoria = models.CharField(max_length=20, choices=CATEGORIAS_FINANCEIRO)
    valor = models.DecimalField(max_digits=12, decimal_places=2)
    data = models.DateField()
    descricao = models.TextField(blank=True)

    # --- Item de documento (NF-e) -------------------------------------
    # Um lançamento pode ser **um item** de uma nota, não a nota inteira. Sem
    # estes três campos, a quantidade morre na fronteira: a NF-e diz
    # "20 KG de café a R$ 38,90" e o sistema guardava só R$ 778,00 — sem
    # quantidade não há preço por unidade, não há comparação entre produtos,
    # e não há mediana nem P25/P75 para a rede de preços (§21.5).
    #
    # Nullable de propósito: um lançamento escrito à mão não tem item de NF-e,
    # e essa ausência **não** significa quantidade zero.
    quantidade = models.DecimalField(
        max_digits=14,
        decimal_places=4,
        null=True,
        blank=True,
        help_text="Quantidade do item. Nulo = lançamento não vem de uma NF-e "
        "ou a nota não trazia quantidade — não é zero.",
    )
    unidade = models.CharField(
        max_length=12,
        blank=True,
        default="",
        help_text="Unidade do item (KG, L, SC, UN …). Vazio = desconhecida.",
    )
    cfop = models.CharField(
        max_length=4,
        blank=True,
        default="",
        help_text="CFOP do item. Determina o sinal: 1/2/3xxx entrada (despesa), "
        "5xxx saída (receita), 6/7xxx apuração (não lança). Vazio = lançado à mão.",
    )

    # Preço por unidade **derivado**, nunca guardado. Guardar um valor derivado
    # é guardar duas fontes de verdade: se `quantidade` mudar, o preço fica
    # errado em silêncio. Ver a property abaixo.
    @property
    def preco_unitario(self):
        """Preço por unidade, ou `None` se não é calculável.

        `None` (não `0`) quando falta a quantidade ou quando a quantidade é
        zero — dividir por zero não é "preço zero", é ausência de preço.
        """
        if self.quantidade is None or self.unidade == "":
            return None
        if self.quantidade == 0:
            return None
        return float(self.valor) / float(self.quantidade)

    participante = models.CharField(
        max_length=120, blank=True, help_text="Cliente/fornecedor (LCDPR)"
    )
    participante_doc = EncryptedCharField(
        max_length=255,
        blank=True,
        help_text="CPF/CNPJ do participante (LCDPR, criptografado)",
    )
    talhao = models.ForeignKey(
        "Talhao", on_delete=models.SET_NULL, null=True, blank=True
    )
    safra = models.ForeignKey("Safra", on_delete=models.SET_NULL, null=True, blank=True)
    comprovante = models.CharField(max_length=255, blank=True)
    pago = models.BooleanField(default=False)
    data_pagamento = models.DateField(null=True, blank=True)

    # LCDPR Fields
    conta_bancaria = models.ForeignKey(
        "ContaBancaria",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        help_text="Conta bancária do lançamento (Reg 0050 do LCDPR)",
    )
    TIPO_DOCUMENTO_LCDPR = [
        ("1", "Nota Fiscal"),
        ("2", "Fatura"),
        ("3", "Recibo"),
        ("4", "Contrato"),
        ("5", "Folha de Pagamento"),
        ("6", "Outros"),
    ]
    tipo_documento_lcdpr = models.CharField(
        max_length=2,
        choices=TIPO_DOCUMENTO_LCDPR,
        default="6",
        help_text="Tipo de documento (Reg Q100)",
    )
    numero_documento = models.CharField(
        max_length=50, blank=True, help_text="Número do Documento (LCDPR)"
    )

    TIPO_LANCAMENTO_LCDPR = [
        ("1", "Receita da Atividade Rural"),
        ("2", "Despesa de Custeio e Investimentos"),
        ("3", "Produtos Entregues no Ano Referente a Adiantamento de Recursos"),
    ]
    tipo_lancamento_lcdpr = models.CharField(
        max_length=2,
        choices=TIPO_LANCAMENTO_LCDPR,
        default="2",
        blank=True,
        null=True,
        help_text="Tipo de Lançamento no LCDPR (Reg Q100)",
    )
    saldo_lcdpr = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Saldo acumulado após este lançamento (apenas para arquivo do LCDPR)",
    )

    def __str__(self):
        return f"{self.get_tipo_display()} - {self.descricao or self.get_categoria_display()} R$ {self.valor}"

    def clean(self):
        """Folha de pagamento e' despesa. Sempre.

        Este lancamento existeu no banco real: R$ 100,00, tipo RECEITA,
        categoria FOLHA, descricao "pagamento dos funcionarios". O painel
        somava aquilo na receita, o ROI subia, e o produtor multiplicava
        hectare pelo numero. Ninguem viu nada errado: R$ 100 e' pouco, e um
        valor pequeno e' o tipo de erro que passa a vida inteira sem ser
        notado.

        O `diagnostico_dados` pegava este caso, mas so quando alguem lembra de
        rodar o diagnostico. Aqui a regra e' verificada em TODA gravacao —
        API, formulario, admin e script — porque o preco de errar e' alto e o
        de avisar e' uma frase.

        `app/services/dre.py` JA classificava FOLHA como despesa
        operacional, independente do `tipo`. Ou seja: dois lugares
        classificavam o mesmo lancamento e discordavam. O DRE acertava pelo
        rotulo da categoria; o painel confiava no campo `tipo`. Agora os dois
        concordam porque o dado incoerente nao entra.
        """
        super().clean()
        if self.tipo == "RECEITA" and self.categoria in CATEGORIAS_SO_DESPESA:
            raise ValidationError(
                {
                    "tipo": (
                        f"“{self.get_categoria_display()}” ({self.categoria}) é despesa, "
                        f"não receita. Escolha “Despesa”, ou troque a categoria se o "
                        f"lançamento for mesmo uma entrada. "
                        f"(descrição: {self.descricao or '—'})"
                    )
                }
            )

    class Meta:
        verbose_name = "Lançamento Financeiro"
        verbose_name_plural = "Lançamentos Financeiros"
        ordering = ["-data"]
        indexes = [
            models.Index(fields=["propriedade", "data"]),
            models.Index(fields=["propriedade", "tipo"]),
            models.Index(fields=["propriedade", "data", "tipo"]),
        ]


class ContaBancaria(models.Model):
    propriedade = models.ForeignKey(
        "Propriedade", on_delete=models.CASCADE, related_name="contas_bancarias"
    )
    banco = models.CharField(max_length=100)
    agencia = models.CharField(max_length=20)
    conta = models.CharField(max_length=30)
    digito = models.CharField(max_length=5, blank=True)
    tipo = models.CharField(
        max_length=20,
        choices=[
            ("CORRENTE", "Corrente"),
            ("POUPANCA", "Poupança"),
            ("INVESTIMENTO", "Investimento"),
        ],
        default="CORRENTE",
    )
    saldo_atual = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    ativa = models.BooleanField(default=True)

    class Meta:
        unique_together = ("propriedade", "banco", "agencia", "conta", "digito")

    def __str__(self):
        return f"{self.banco} {self.agencia}/{self.conta}-{self.digito}"


class MovimentacaoBancaria(models.Model):
    conta = models.ForeignKey(
        ContaBancaria, on_delete=models.CASCADE, related_name="movimentacoes"
    )
    data = models.DateField()
    descricao = models.TextField()
    valor = models.DecimalField(max_digits=14, decimal_places=2)
    tipo = models.CharField(
        max_length=20, choices=[("CREDITO", "Crédito"), ("DEBITO", "Débito")]
    )
    categoria = models.CharField(max_length=50, blank=True)
    documento = models.CharField(max_length=100, blank=True)
    conciliado = models.BooleanField(default=False)
    data_conciliacao = models.DateField(null=True, blank=True)
    hash_unico = models.CharField(max_length=64, unique=True, default=uuid4)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-data", "-criado_em"]

    def __str__(self):
        return f"{self.conta} - {self.data} - {self.tipo} R$ {self.valor}"


class Parcelamento(models.Model):
    TIPO_CHOICES = [("PAGAR", "Contas a Pagar"), ("RECEBER", "Contas a Receber")]
    STATUS_CHOICES = [
        ("ABERTA", "Aberta"),
        ("PAGA", "Paga"),
        ("CANCELADA", "Cancelada"),
        ("VENCIDA", "Vencida"),
    ]

    propriedade = models.ForeignKey(
        "Propriedade", on_delete=models.CASCADE, related_name="parcelamentos"
    )
    lancamento = models.ForeignKey(
        "LancamentoFinanceiro",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="parcelamentos",
    )
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES)
    numero = models.IntegerField()
    total_parcelas = models.IntegerField()
    valor_total = models.DecimalField(max_digits=14, decimal_places=2)
    valor_parcela = models.DecimalField(max_digits=14, decimal_places=2)
    data_vencimento = models.DateField()
    status = models.CharField(
        max_length=10,
        choices=[
            ("ABERTA", "Aberta"),
            ("PAGA", "Paga"),
            ("CANCELADA", "Cancelada"),
            ("VENCIDA", "Vencida"),
        ],
        default="ABERTA",
    )
    juros_mes = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    multa_atraso = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    data_pagamento = models.DateField(null=True, blank=True)
    data_cancelamento = models.DateField(null=True, blank=True)
    observacao = models.TextField(blank=True)

    class Meta:
        ordering = ["data_vencimento"]


class ConciliacaoBancaria(models.Model):
    conta = models.ForeignKey(
        ContaBancaria, on_delete=models.CASCADE, related_name="conciliacoes"
    )
    data_inicio = models.DateField()
    data_fim = models.DateField()
    saldo_sistema_inicio = models.DecimalField(max_digits=14, decimal_places=2)
    saldo_banco_inicio = models.DecimalField(max_digits=14, decimal_places=2)
    saldo_sistema_fim = models.DecimalField(max_digits=14, decimal_places=2)
    saldo_banco_fim = models.DecimalField(max_digits=14, decimal_places=2)
    diferenca = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    status = models.CharField(
        max_length=20,
        choices=[
            ("ABERTA", "Aberta"),
            ("FECHADA", "Fechada"),
            ("COM_DIFERENCA", "Com Diferença"),
        ],
        default="ABERTA",
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    fechada_em = models.DateTimeField(null=True, blank=True)
    criado_por = models.ForeignKey(
        "auth.User", on_delete=models.SET_NULL, null=True, blank=True
    )
    observacao = models.TextField(blank=True)

    class Meta:
        unique_together = ("conta", "data_fim")
        ordering = ["-data_fim"]

    def __str__(self):
        return f"Conciliacao {self.conta} {self.data_inicio} a {self.data_fim}"


class PushSubscription(models.Model):
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="push_subscriptions"
    )
    endpoint = models.TextField()
    p256dh = models.CharField(max_length=100)
    auth = models.CharField(max_length=100)
    ativa = models.BooleanField(default=True)
    criada_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "endpoint")


class NotaFiscalImportada(models.Model):
    """Registo de que NF-e ja entraram no sistema, para nunca entrar duas.

    MEDIDO 2026-10-05 (agente 7). Este modelo nao inventa nada: e' o que
    faltava para o import de NF-e **saber o que ja fez**.

    O codigo anterior (`app/views/nfe_auto.py`) nao guardava identificacao
    nenhuma da nota. O `EstoqueItem.local` era `f"NF-e {data:%d/%m/%Y}"` — a
    data de emissao, que nao distingue duas notas do mesmo dia, quanto mais a
    mesma nota importada duas vezes. O produtor carregava o mesmo XML, via
    duas vezes no banco, e o estoque duplicava. O sistema nao se queixava:
    respondia `{"ok": true, "criados": [...]}` nas duas vezes.

    A identidade de uma NF-e e' a **chave de acesso** — 44 digitos que a
    SEFAZ emite por documento e que nao se repetem. E' o que fica aqui, com
    `unique` por propriedade: o mesmo produtor nao pode ter duas notas com a
    mesma chave, e duas propriedades diferentes podem ter o mesmo numero sem
    colidir.

    O que este registo NAO e': um arquivo fiscal. Nao e' a NF-e, nao substitui
    a SEFAZ e nao e' o registo de um fornecedor. E' a marca de que este
    documento ja foi lido por este sistema — e existe para o `ok: true` ser
    verdade.
    """

    propriedade = models.ForeignKey(
        "Propriedade", on_delete=models.CASCADE, related_name="notas_importadas"
    )
    #: Os 44 digitos da chave de acesso, sem barras.
    chave = models.CharField(max_length=44)
    numero = models.CharField(max_length=20, blank=True)
    fornecedor_doc = models.CharField(max_length=20, blank=True)
    fornecedor_nome = models.CharField(max_length=200, blank=True)
    emissao = models.DateField()
    total = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    itens = models.PositiveIntegerField(default=0)
    importada_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Nota Fiscal Importada"
        verbose_name_plural = "Notas Fiscais Importadas"
        ordering = ["-emissao"]
        constraints = [
            models.UniqueConstraint(
                fields=["propriedade", "chave"], name="uniq_nfe_por_propriedade"
            ),
        ]
        indexes = [models.Index(fields=["propriedade", "emissao"])]

    def __str__(self):
        return f"NF-e {self.numero or self.chave[:8]} ({self.emissao:%d/%m/%Y})"


class NotificacaoTemplate(models.Model):
    nome = models.CharField(max_length=100, unique=True)
    titulo = models.CharField(max_length=200)
    mensagem = models.TextField()
    nivel = models.CharField(
        max_length=10,
        choices=[("info", "Info"), ("warning", "Warning"), ("critical", "Crítico")],
        default="info",
    )
    canais = models.JSONField(
        default=list, help_text="Ex: ['push', 'email', 'whatsapp']"
    )
    ativa = models.BooleanField(default=True)
    variaveis = models.JSONField(
        default=list, help_text="Ex: ['cultura', 'valor', 'data']"
    )

    def __str__(self):
        return self.nome
