# gerado por `makemigrations app` — ver o docstring do 0059.
"""A2 — proveniencia do `PrescricaoVRA`: o que foi previsto, e com que evidencia.

O QUE ESTA MIGRATION FAZ
------------------------
`PrescricaoVRA` era um receituario de escrita: guardava a dose que se mandou
aplicar e nada mais. Nao guardava **o que se esperava que a dose produzisse**,
nem **a evidencia** que produziu a recomendacao, nem **a versao** do
conhecimento agronomico usado.

Sem esses tres campos, `dose_ha` e' um numero sem justificacao. Nao se responde
a "porque mandou isto?" seis meses depois, e — o que e' o ponto — **nao se
aprende com o erro**. E' a aposta do §4.3 da carta: *procedencia auditavel por
talhao e por decisao*, que e' o diferençador defensavel porque um competidor
com 9 anos de dados nao versionados nao a consegue retrofitar.

O ELO PARA O DESFECHO JA EXISTIA
-------------------------------
`PrescricaoVRA.safra` aponta para `Safra`, que tem `produtividade` e
`data_colheita`, e `Safra` pode estar Pogiada num talhao. Nao foi preciso modelo
novo: `erro_percentual` (property no modelo) le as duas pontas — a prevista,
nova, e a realizada, que ja la estava.

DE ONDE VEIO A EXIGENCIA DE `NULL` E NAO `0`
--------------------------------------------
`produtividade_esperada`, `produtividade_realizada` e `erro_percentual` devolvem
`None` quando falta uma ponta. Um erro de 0% (acertou em cheio) e um erro
desconhecido sao coisas diferentes, e so um deles e' `None`. Um `0` nao os
distingue — e' o `sem_dado` declarado a tratar-se de `medido`, que e' a regra
`fonte_dado` do projecto a ser cumprida no sitio onde ela mas dói.

Nota de proceso: o `makemigrations` deste projecto devolve o que estiver
pendente, de todas as sessoes. Esta migration foi separada de uma pendencia de outra sessao
— ver o docstring do 0059 para a razao.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("app", "0058_create_cache_table_painel"),
    ]

    operations = [
        migrations.AddField(
            model_name="prescricaovra",
            name="contexto_recomendacao",
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text=(
                    "Evidencia que produziu a recomendacao: clima e solo medidos no "
                    "momento, com o carimbo fonte_dado de cada um (medido | sem_dado | "
                    "suspect). Vazio = recomendacao sem evidencia registada."
                ),
            ),
        ),
        migrations.AddField(
            model_name="prescricaovra",
            name="produtividade_esperada",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text=(
                    "O que a recomendacao previa que a dose produziria, na mesma "
                    "unidade de Safra.produtividade. NULL = previsao nao registada."
                ),
                max_digits=8,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="prescricaovra",
            name="versao_analise",
            field=models.CharField(
                blank=True,
                help_text=(
                    "Versao do conhecimento agronomico que produziu a dose. Sem isto, "
                    "dois anos de prescricoes sao indistinguiveis e nao se pode melhorar a "
                    "calibracao."
                ),
                max_length=60,
            ),
        ),
        migrations.AddIndex(
            model_name="prescricaovra",
            index=models.Index(
                fields=["safra", "talhao"], name="app_prescri_safra_i_2d6bb9_idx"
            ),
        ),
    ]
