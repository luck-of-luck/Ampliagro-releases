"""Validação dos itens revisados antes da gravação de um rascunho OCR."""

from decimal import Decimal

from rest_framework import serializers


class QuantidadeOCRField(serializers.DecimalField):
    def to_internal_value(self, data):
        if isinstance(data, str):
            data = data.replace(",", ".")
        return super().to_internal_value(data)


class ItemEstoqueOCRSerializer(serializers.Serializer):
    nome = serializers.CharField(min_length=2, max_length=150)
    quantidade = QuantidadeOCRField(
        max_digits=10, decimal_places=2, min_value=Decimal("0.01")
    )
    unidade = serializers.CharField(max_length=20, default="un")


class ConfirmacaoEstoqueOCRSerializer(serializers.Serializer):
    artefato_id = serializers.IntegerField(min_value=1)
    propriedade_id = serializers.IntegerField(required=False, min_value=1)
    itens = ItemEstoqueOCRSerializer(many=True, allow_empty=False, max_length=1000)
