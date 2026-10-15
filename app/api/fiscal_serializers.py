"""Cadastros fiscais estruturados; rascunhos não equivalem a arquivo válido."""
from rest_framework import serializers

UFS = "AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO".split()


class FiscalEstritoSerializer(serializers.Serializer):
    def to_internal_value(self, data):
        if isinstance(data, dict):
            desconhecidos = set(data) - set(self.fields)
            if desconhecidos:
                raise serializers.ValidationError({nome: "Campo desconhecido." for nome in sorted(desconhecidos)})
            for nome, valor in data.items():
                if isinstance(valor, str) and any(c == "|" or ord(c) < 32 for c in valor):
                    raise serializers.ValidationError({nome: "Não use delimitador | ou caracteres de controle."})
        return super().to_internal_value(data)


def texto(limite):
    return serializers.CharField(max_length=limite, required=False, allow_blank=True)


class ContribuinteFiscalSerializer(FiscalEstritoSerializer):
    nome = texto(255)
    endereco = texto(150)
    numero = texto(6)
    complemento = texto(50)
    bairro = texto(50)
    uf = serializers.ChoiceField(choices=UFS, required=False, allow_blank=True)
    cod_municipio = serializers.RegexField(r"^[0-9]{7}$", required=False, allow_blank=True)
    cep = serializers.RegexField(r"^[0-9]{8}$", required=False, allow_blank=True)
    email = serializers.EmailField(max_length=115, required=False, allow_blank=True)
    telefone = serializers.RegexField(r"^[0-9]{10,11}$", required=False, allow_blank=True)


class ContadorFiscalSerializer(FiscalEstritoSerializer):
    nome = texto(255)
    documento = serializers.RegexField(r"^(?:[0-9]{11}|[0-9]{14})$", required=False, allow_blank=True)
    crc = texto(255)
    email = serializers.EmailField(max_length=115, required=False, allow_blank=True)
    telefone = serializers.RegexField(r"^[0-9]{1,15}$", required=False, allow_blank=True)


class ContraparteFiscalSerializer(FiscalEstritoSerializer):
    tipo = serializers.ChoiceField(choices=list("12345"))
    documento = serializers.RegexField(r"^(?:[0-9]{11}|[0-9]{14})$")
    nome = serializers.CharField(max_length=50)
    participacao = serializers.DecimalField(max_digits=5, decimal_places=2, min_value=0, max_value=100)

    def to_internal_value(self, data):
        resultado = super().to_internal_value(data)
        resultado["participacao"] = str(resultado["participacao"])
        return resultado


class CadastroFiscalSerializer(FiscalEstritoSerializer):
    contribuinte = ContribuinteFiscalSerializer(required=False)
    contador = ContadorFiscalSerializer(required=False)
    contrapartes = ContraparteFiscalSerializer(many=True, required=False, max_length=100)
