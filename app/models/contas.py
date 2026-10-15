"""CONTAS A PAGAR E A RECEBER — a lacuna F10, fechada.

PORQUE ISTO EXISTE
==================
A matriz `100 x 50` marca `F10` (Contas a pagar e a receber) como `NAO TEM`,
e tres ERPs tem a capacidade **provada por fetch**: Aegro, Sage X3 e SYSPRO.
Isto nao e' uma funcionalidade decorativa — e' o primeiro que um produtor
compara quando olha para um ERP. Sem isso, o Ampliagro perde a conversa antes
de ela comecar.

ATE ONDE IA "CONTAS A PAGAR"
===========================
`h_contas_a_pagar`, em `app/ia/intents2.py:260`, e' uma **LEITURA**: soma
`LancamentoFinanceiro` onde `tipo="DESPESA" e pago=False`. Isso e' um extrato
de despesas nao pagas, nao e' contas a pagar. Faltava-lhe tudo o que faz uma
obrigacao ser uma obrigacao:

  - vencimento (`LancamentoFinanceiro` tem `data`, que e' quando ACONTECEU,
    nao quando e' para pagar)
  - contraparte como entidade, nao como texto livre
  - estado: aberta, paga, vencida
  - baixa com ligacao a `LancamentoFinanceiro`, para o LCDPR nao ficar dois
    campos a descrever a mesma dinheiro

O QUE ESTE MODELO FAZ DE DIFERENTE (o fosso)
============================================
Nao e' um modulo de ERP a mais. E' o que liga tres coisas que os concorrentes
têm separadas:

  1. o LCDPR — a conta paga escreve o Q100 com `saldo_lcdpr`, para o ficheiro
     da Receita fechar certo sem o produtor refazer nada
  2. a fila offline — a baixa da conta viaja na mesma fila de escrita, entao
     funciona sem rede (que e' onde o agro realmente esta)
  3. a proveniencia — `fonte_dado` diz se o vencimento foi MEDIDO, DECLARADO
     pelo produtor ou INVENTADO. Um ERP que diz "vence dia 10" sem saber de
     onde veio esta a inventar, e o produtor decide em cima dessa invencao.

Este ultimo ponto e' o que um concorrente nao copia em seis meses: nao e' o
campo, e' a obrigaçao de nunca mostrar um numero sem dizer de onde veio.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from app.seguranca import EncryptedCharField

#: Estados. `VENCIDA` nao se guarda: e' derivado do vencimento e de hoje, e
#: guardar seria um segundo lugar onde a verdade pode estar errada.
ESTADOS = [
    ("ABERTA", "Em aberto"),
    ("PAGA", "Paga"),
    ("CANCELADA", "Cancelada"),
]

#: De onde veio o vencimento. Ver `app/ia/proveniencia.py`.
FONTE_DADO = [
    ("MEDIDO", "Medido — veio de um documento (NF-e, extrato, contrato)"),
    ("DECLARADO", "Declarado — o produtor disse a data"),
    ("INVENTADO", "Inventado — SEM DATA FIÁVEL. Não usar para decidir"),
]


class ContaAPagar(models.Model):
    """Uma obrigação de pagamento com vencimento.

    Deliberadamente NAO substitui o `LancamentoFinanceiro`: o lancamento e' o
    facto contabil, a conta e' o compromisso. Uma compra paga na hora nao gera
    conta; uma conta vencida que nunca foi paga precisa de virar lancamento
    quando for liquidada. Sao coisas diferentes com momentos diferentes.
    """

    propriedade = models.ForeignKey(
        "Propriedade", on_delete=models.CASCADE, related_name="contas_a_pagar"
    )
    descricao = models.CharField(max_length=200)
    valor = models.DecimalField(max_digits=14, decimal_places=2)
    vencimento = models.DateField(help_text="Quando e' para pagar")

    #: Contraparte. Texto livre e' o que o `LancamentoFinanceiro` faz e nao
    #: chega: "FORTE AGRO" e "Forte Agro Ltda" sao o mesmo credor e nenhuma
    #: consulta por um dos dois nomes o encontra.
    fornecedor = models.CharField(max_length=200, blank=True)
    fornecedor_doc = EncryptedCharField(
        max_length=255, blank=True, help_text="CNPJ/CPF do fornecedor (criptografado)"
    )

    categoria = models.CharField(max_length=20, blank=True, default="INSUMO")
    estado = models.CharField(max_length=12, choices=ESTADOS, default="ABERTA")

    #: A mesma tesouraria do LCDPR. `null=True` porque um produtor rural que
    #: paga em dinheiro tem conta a pagar sem conta bancaria.
    conta_bancaria = models.ForeignKey(
        "ContaBancaria",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="contas_pagas",
    )
    lancamento = models.ForeignKey(
        "LancamentoFinanceiro",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="conta_origem",
        help_text="Lancamento gerado quando a conta foi paga",
    )

    data_pagamento = models.DateField(null=True, blank=True)

    #: Ver `FONTE_DADO`. `INVENTADO` e' um estado real, nao um valor por
    #: omissao: quando o vencimento nao vem de nenhum sitio, dizemos.
    fonte_dado = models.CharField(
        max_length=12, choices=FONTE_DADO, default="DECLARADO"
    )
    documento_ref = models.CharField(
        max_length=60, blank=True, help_text="NF-e, contrato ou fatura que originou"
    )

    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["vencimento", "valor"]
        indexes = [
            models.Index(fields=["propriedade", "estado", "vencimento"]),
            models.Index(fields=["propriedade", "vencimento"]),
        ]
        verbose_name = "Conta a Pagar"
        verbose_name_plural = "Contas a Pagar"

    def __str__(self) -> str:
        return f"{self.descricao} — R$ {self.valor} (vence {self.vencimento:%d/%m/%Y})"

    # ---- estado derivado -------------------------------------------------
    @property
    def vencida(self) -> bool:
        """Vencida e' uma pergunta, nao um campo.

        Guardar `VENCIDA` no base criaria um segundo sitio onde a verdade
        pode estar errada, e `open()` nao volta atras. Deriva de hoje, sempre.
        """
        if self.estado != "ABERTA":
            return False
        return self.vencimento < timezone.localdate()

    @property
    def dias_atraso(self) -> int:
        if not self.vencida:
            return 0
        return (timezone.localdate() - self.vencimento).days

    @property
    def confiavel(self) -> bool:
        """Um numero com `fonte_dado=INVENTADO` nao deve abrir uma decisao.

        E' a regra que o resto do Ampliagro ja aplica (ver
        `app/ia/proveniencia.py`): o numero aparece, mas carimbado. Aqui o
        carimbo impede que a conta entre num fluxo automatico.
        """
        return self.fonte_dado != "INVENTADO"

    def clean(self) -> None:
        if self.valor is not None and self.valor <= 0:
            msg = "valor tem de ser maior que zero"
            raise ValidationError({"valor": msg})
        if self.estado == "PAGA" and not self.data_pagamento:
            msg = "marcar como paga exige a data de pagamento"
            raise ValidationError({"data_pagamento": msg})

    # ---- o que fecha a conta --------------------------------------------
    def liquidar(self, *, data_pagamento, conta_bancaria=None, user=None):
        """Marca paga e escreve o `LancamentoFinanceiro` que o LCDPR le.

        Feito como metodo e nao como view porque a regra e' a mesma seja quem
        chama: pela IA, pelo produtor ou pela fila offline. Se cada caminho
        tivesse a sua versao, um deles acabaria por esquecer o lancamento e o
        LCDPR deixaria de fechar.
        """
        from app.models.financeiro import LancamentoFinanceiro

        if self.estado == "PAGA":
            msg = f"conta ja paga em {self.data_pagamento:%d/%m/%Y}"
            raise ValidationError({"estado": msg})

        lanc = LancamentoFinanceiro.objects.create(
            propriedade=self.propriedade,
            tipo="DESPESA",
            categoria=self.categoria or "OUTRO",
            valor=self.valor,
            data=data_pagamento,
            descricao=self.descricao,
            participante=self.fornecedor,
            participante_doc=self.fornecedor_doc,
            conta_bancaria=conta_bancaria or self.conta_bancaria,
            comprovante=self.documento_ref,
            pago=True,
            data_pagamento=data_pagamento,
            tipo_lancamento_lcdpr="2",
        )
        self.estado = "PAGA"
        self.data_pagamento = data_pagamento
        if conta_bancaria:
            self.conta_bancaria = conta_bancaria
        self.lancamento = lanc
        self.save(
            update_fields=[
                "estado",
                "data_pagamento",
                "conta_bancaria",
                "lancamento",
            ]
        )
        return lanc


class ContaAReceber(models.Model):
    """O espelho: o que o produtor tem para receber.

    Mesma forma de `ContaAPagar` e pelo mesmo motivo — quem compra no agro
    compra a prazo, e um ERP que so sabe dizer quanto saiu nao diz quanto
    entra. `vencimento` e' a data em que o dinheiro deve cair.
    """

    propriedade = models.ForeignKey(
        "Propriedade", on_delete=models.CASCADE, related_name="contas_a_receber"
    )
    descricao = models.CharField(max_length=200)
    valor = models.DecimalField(max_digits=14, decimal_places=2)
    vencimento = models.DateField(help_text="Quando e' para receber")
    cliente = models.CharField(max_length=200, blank=True)
    cliente_doc = EncryptedCharField(
        max_length=255, blank=True, help_text="CNPJ/CPF do cliente (criptografado)"
    )
    categoria = models.CharField(max_length=20, blank=True, default="VENDA_PROD")
    estado = models.CharField(max_length=12, choices=ESTADOS, default="ABERTA")
    conta_bancaria = models.ForeignKey(
        "ContaBancaria",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="contas_recebidas",
    )
    lancamento = models.ForeignKey(
        "LancamentoFinanceiro",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="conta_recebida_origem",
    )
    data_recebimento = models.DateField(null=True, blank=True)
    fonte_dado = models.CharField(
        max_length=12, choices=FONTE_DADO, default="DECLARADO"
    )
    documento_ref = models.CharField(max_length=60, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["vencimento", "valor"]
        indexes = [
            models.Index(fields=["propriedade", "estado", "vencimento"]),
            models.Index(fields=["propriedade", "vencimento"]),
        ]
        verbose_name = "Conta a Receber"
        verbose_name_plural = "Contas a Receber"

    def __str__(self) -> str:
        return f"{self.descricao} — R$ {self.valor} (vence {self.vencimento:%d/%m/%Y})"

    @property
    def vencida(self) -> bool:
        if self.estado != "ABERTA":
            return False
        return self.vencimento < timezone.localdate()

    @property
    def dias_atraso(self) -> int:
        if not self.vencida:
            return 0
        return (timezone.localdate() - self.vencimento).days

    @property
    def confiavel(self) -> bool:
        return self.fonte_dado != "INVENTADO"

    def clean(self) -> None:
        if self.valor is not None and self.valor <= 0:
            msg = "valor tem de ser maior que zero"
            raise ValidationError({"valor": msg})
        if self.estado == "PAGA" and not self.data_recebimento:
            msg = "marcar como recebida exige a data de recebimento"
            raise ValidationError({"data_recebimento": msg})

    def receber(self, *, data_recebimento, conta_bancaria=None):
        """Marca recebida e escreve o `LancamentoFinanceiro` de receita."""
        from app.models.financeiro import LancamentoFinanceiro

        if self.estado == "PAGA":
            msg = f"conta ja recebida em {self.data_recebimento:%d/%m/%Y}"
            raise ValidationError({"estado": msg})

        lanc = LancamentoFinanceiro.objects.create(
            propriedade=self.propriedade,
            tipo="RECEITA",
            categoria=self.categoria or "VENDA_PROD",
            valor=self.valor,
            data=data_recebimento,
            descricao=self.descricao,
            participante=self.cliente,
            participante_doc=self.cliente_doc,
            conta_bancaria=conta_bancaria or self.conta_bancaria,
            comprovante=self.documento_ref,
            pago=True,
            data_pagamento=data_recebimento,
            tipo_lancamento_lcdpr="1",
        )
        self.estado = "PAGA"
        self.data_recebimento = data_recebimento
        if conta_bancaria:
            self.conta_bancaria = conta_bancaria
        self.lancamento = lanc
        self.save(
            update_fields=[
                "estado",
                "data_recebimento",
                "conta_bancaria",
                "lancamento",
            ]
        )
        return lanc


#: Alertas que o motor proativo dispara sozinho. `dias` e' a antecedencia:
#: o produtor quer ser avisado ANTES de faltar dinheiro, e o dia da
#: vencimento ja e' tarde para ele.
AVISOS_CONTA = [
    ("VENCE_3_DIAS", 3),
    ("VENCE_HOJE", 0),
    ("VENCIDA", -1),
]
