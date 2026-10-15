from django import forms
from django.db.models import Q
from app.models import ContaBancaria, LancamentoFinanceiro
from app.api.fiscal_serializers import ContribuinteFiscalSerializer, ContadorFiscalSerializer, ContraparteFiscalSerializer, UFS


class ContribuinteFiscalForm(forms.Form):
    nome = forms.CharField(label="Nome do contribuinte", max_length=255, required=False)
    endereco = forms.CharField(label="Logradouro", max_length=150, required=False)
    numero = forms.CharField(label="Número", max_length=6, required=False)
    complemento = forms.CharField(max_length=50, required=False)
    bairro = forms.CharField(max_length=50, required=False)
    uf = forms.ChoiceField(label="UF", choices=[("", "Selecione")] + [(uf, uf) for uf in UFS], required=False)
    cod_municipio = forms.CharField(label="Código IBGE do município (7 dígitos)", max_length=7, required=False)
    cep = forms.CharField(label="CEP (8 dígitos)", max_length=8, required=False)
    email = forms.EmailField(label="E-mail", max_length=115, required=False)
    telefone = forms.CharField(label="Telefone com DDD", max_length=11, required=False)

    def clean(self):
        dados = super().clean()
        serializer = ContribuinteFiscalSerializer(data=dados)
        if not serializer.is_valid():
            for campo, erros in serializer.errors.items():
                self.add_error(campo if campo in self.fields else None, [str(erro) for erro in erros])
        return dados


class ContadorFiscalForm(forms.Form):
    nome = forms.CharField(label="Nome do contador", max_length=255, required=False)
    documento = forms.CharField(label="CPF/CNPJ (somente dígitos)", max_length=14, required=False)
    crc = forms.CharField(label="Inscrição no CRC", max_length=255, required=False)
    email = forms.EmailField(label="E-mail", max_length=115, required=False)
    telefone = forms.CharField(label="Telefone com DDD", max_length=15, required=False)

    def clean(self):
        dados = super().clean()
        serializer = ContadorFiscalSerializer(data=dados)
        if not serializer.is_valid():
            for campo, erros in serializer.errors.items():
                self.add_error(campo if campo in self.fields else None, [str(erro) for erro in erros])
        return dados


class ContraparteFiscalForm(forms.Form):
    tipo = forms.ChoiceField(initial="1", choices=[("1", "Condômino"), ("2", "Arrendador"), ("3", "Parceiro"), ("4", "Comodante"), ("5", "Outro")])
    documento = forms.CharField(label="CPF/CNPJ (somente dígitos)", max_length=14)
    nome = forms.CharField(max_length=50)
    participacao = forms.DecimalField(label="Participação (%)", max_digits=5, decimal_places=2, min_value=0, max_value=100)

    def clean(self):
        dados = super().clean()
        serializer = ContraparteFiscalSerializer(data={k: v for k, v in dados.items() if k != "DELETE"})
        if not serializer.is_valid():
            for campo, erros in serializer.errors.items():
                if campo not in self.errors:
                    self.add_error(campo if campo in self.fields else None, [str(erro) for erro in erros])
        else:
            dados.update(serializer.validated_data)
        return dados


ContrapartesFiscalFormSet = forms.formset_factory(
    ContraparteFiscalForm, extra=1, can_delete=True,
    max_num=100, validate_max=True, absolute_max=120,
)


class RevisaoLancamentoFiscalForm(forms.ModelForm):
    participante_doc = forms.RegexField(
        regex=r"^(?:[0-9]{11}|[0-9]{14})$", required=False,
        label="CPF/CNPJ do participante (somente dígitos)", max_length=14,
        error_messages={"invalid": "Informe 11 ou 14 dígitos, sem pontuação."},
    )
    descricao = forms.CharField(label="Histórico", max_length=255, required=False)
    data_pagamento = forms.DateField(
        label="Data efetiva do pagamento/recebimento", required=False,
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
        input_formats=["%Y-%m-%d"],
    )

    class Meta:
        model = LancamentoFinanceiro
        fields = ("tipo", "descricao", "participante", "participante_doc",
                  "tipo_documento_lcdpr", "numero_documento", "tipo_lancamento_lcdpr",
                  "conta_bancaria", "pago", "data_pagamento")
        labels = {"tipo": "Receita ou despesa", "participante": "Cliente/fornecedor",
                  "tipo_documento_lcdpr": "Tipo do documento", "numero_documento": "Número do documento",
                  "tipo_lancamento_lcdpr": "Classificação LCDPR", "conta_bancaria": "Conta bancária",
                  "pago": "Pagamento/recebimento confirmado"}

    def __init__(self, *args, propriedade, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["conta_bancaria"].queryset = ContaBancaria.objects.filter(
            propriedade=propriedade,
        ).filter(Q(ativa=True) | Q(pk=self.instance.conta_bancaria_id)).order_by("banco", "pk")
        self.fields["tipo_lancamento_lcdpr"].choices = [
            ("", "Pendente de classificação"), *LancamentoFinanceiro.TIPO_LANCAMENTO_LCDPR,
        ]

    def clean(self):
        dados = super().clean()
        classe, tipo = dados.get("tipo_lancamento_lcdpr"), dados.get("tipo")
        if (classe in ("1", "3") and tipo != "RECEITA") or (classe == "2" and tipo != "DESPESA"):
            self.add_error("tipo_lancamento_lcdpr", "A classificação deve corresponder a receita ou despesa do lançamento.")
        if dados.get("pago") and not dados.get("data_pagamento"):
            self.add_error("data_pagamento", "Informe quando o pagamento ou recebimento ocorreu.")
        if not dados.get("pago") and dados.get("data_pagamento"):
            self.add_error("data_pagamento", "Confirme o pagamento ou deixe a data vazia enquanto estiver em aberto.")
        if dados.get("pago") and classe and not dados.get("participante_doc"):
            self.add_error("participante_doc", "Informe o CPF/CNPJ do participante para incluir este movimento no LCDPR.")
        for campo in ("descricao", "participante", "numero_documento"):
            valor = dados.get(campo, "")
            if any(ch == "|" or ord(ch) < 32 or ord(ch) == 127 for ch in valor):
                self.add_error(campo, "Não use barras verticais ou caracteres de controle neste campo.")
        return dados
