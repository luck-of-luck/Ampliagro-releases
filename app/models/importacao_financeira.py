"""Origem e identidade externa de lançamentos importados por arquivo."""

from django.conf import settings
from django.db import models


class LinhaFinanceiraImportada(models.Model):
    propriedade = models.ForeignKey("Propriedade", on_delete=models.PROTECT)
    lancamento = models.OneToOneField("LancamentoFinanceiro", on_delete=models.PROTECT)
    origem = models.CharField(max_length=100)
    id_externo = models.CharField(max_length=100)
    hash_conteudo = models.CharField(max_length=64)
    arquivo = models.CharField(max_length=255)
    fonte_dado = models.CharField(max_length=20, default="declarado", editable=False)
    importado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["propriedade", "origem", "id_externo"],
                name="financeiro_origem_id_unico",
            )
        ]
