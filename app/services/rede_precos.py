"""Rede de preços: o que o Ampliagro tem e a Aegro não.

## O que isto é

O §21.5 promete o que a Aegro **não** mostra. A Aegro publica "839 registos" —
um número de registo. O Ampliagro pode publicar *"839 registos de 312 fazendas
distintas, 41% de concentração no maior comprador"*.

A diferença não é o preço: é a **estrutura** do mercado que o preço esconde. E
a estrutura é poder de negociação — é o que diz a um produtor se vale a pena
discutir com o comprador ou se já não tem contrapeso.

## De onde vêm os pontos

De `LancamentoFinanceiro`, que desde a migration `0060` guarda **quantidade,
unidade e CFOP por item** — **das propriedades que o user pode ver**, e
não de todas. Antes disso a quantidade morria na fronteira e isto
era impossível: sem quantidade não há preço por unidade.

Só entram lançamentos com `quantidade` e `unidade` — os escritos à mão ficam de
fora, e o serviço diz quantos. Um preço calculado a partir de itens sem unidade
compara KG com sc e produz uma mediana que não significa nada.

## A honestidade do número

**Uma mediana de 3 registos não é um preço de mercado.** É a média de três
transações, e publicá-la sem o `n` é o mesmo defeito do `custo_por_hectare`
inventado: um número plausível que não pode ser ajeno.

Por isso `n_transacoes` e `n_fazendas` viajam **sempre**, e o serviço declara
quando a amostra é pequena demais para chamar de preço de referência.

`concentracao` responde: que fracção das transações vem da fazenda que mais
transaciona. 100% é um mercado sem contrapeso. Este é o número que a Aegro
não dá.

## Percentis: interpolação explícita

`statistics.quantiles` com `method="inclusive"` (a convenção de R-7 / NumPy).
Não uso `exclusive` porque muda os valores em amostras pequenas, e o serviço
declara a convenção em `fonte` — quem compara dois números de.methods diferentes
está a comparar coisas diferentes.
"""

from __future__ import annotations

import statistics
from datetime import date
from decimal import Decimal

from django.db.models import Count

from app.hierarquia import propriedades_visiveis
from app.models import LancamentoFinanceiro

# Abaixo disto não é preço de mercado, é amostra. O número sai na mesma e
# marcado — some-lo seria esconder a fraqueza do dado.
MINIMO_REFERENCIA = 5


def _preco_unitario(lanc: LancamentoFinanceiro) -> float | None:
    return lanc.preco_unitario


def _percentis(valores: list[float]) -> dict:
    """Mediana e quartis por interpolação inclusiva (R-7)."""
    v = sorted(valores)
    n = len(v)
    mediana = statistics.median(v)
    if n < 2:
        return {"mediana": mediana, "p25": None, "p75": None, "min": v[0], "max": v[0]}
    quartis = statistics.quantiles(v, n=4, method="inclusive")
    return {
        "mediana": mediana,
        "p25": quartis[0],
        "p75": quartis[2],
        "min": v[0],
        "max": v[-1],
    }


def preco_referencia(
    user,
    produto: str,
    *,
    uf: str | None = None,
    data_inicio: date | None = None,
    data_fim: date | None = None,
) -> dict:
    """Preço de referência de um produto, com a estrutura do mercado.

    `produto` casa por `descricao__icontains` — que é o que o produtor escreve
    na NF-e ("SOJA EM GRÃO", "SOJA"). Uma correspondência exacta não encontraria
    nada, e um serviço de preço que devolve vazio para "soja" é inútil.
    """
    # **Filtro de posse obrigatorio.** A primeira versao deste servico filtrava
    # so por produto e tipo, e devolvia a mediana das vendas de *todos* os
    # produtores da base.
    #
    # O `TenantIsolationMiddleware` nao cobre isto: ele valida ids que chegam
    # *no pedido*, e nao filtra querysets (ver a docstring do proprio
    # middleware). Uma query de servico que nao filtra por dono passa por ele
    # intacta.
    #
    # Num deploy multi-tenant, o produtor A perguntava "qual o preco da soja" e
    # recebia a mediana, a contagem de transacoes e a contagem de fazendas do
    # produtor B. A docstring do middleware chama a isto de "pior que um bug de
    # dados inventados": dado inventado diz "isto e' um exemplo"; dado de outra
    # pessoa diz "isto e' seu", e o produtor nao tem forma de saber que nao e'.
    qs = LancamentoFinanceiro.objects.filter(
        tipo="RECEITA",
        descricao__icontains=produto,
        propriedade__in=propriedades_visiveis(user),
    )
    if uf:
        qs = qs.filter(propriedade__uf=uf)
    if data_inicio:
        qs = qs.filter(data__gte=data_inicio)
    if data_fim:
        qs = qs.filter(data__lte=data_fim)

    lancamentos = list(qs.select_related("propriedade"))

    # Só os que têm unidade. Comparar KG com sc não é um preço, é ruído.
    com_unidade = [
        l for l in lancamentos if l.quantidade and l.unidade and l.quantidade != 0
    ]
    sem_unidade = len(lancamentos) - len(com_unidade)

    # Uma referência por **unidade**: 1 KG de soja e 1 sc de soja não podem
    # entrar na mesma distribuição.
    por_unidade: dict[str, list[float]] = {}
    for l in com_unidade:
        preco = _preco_unitario(l)
        if preco is not None:
            por_unidade.setdefault(l.unidade.upper(), []).append(preco)

    # As transações por fazenda, para a concentração.
    por_fazenda: dict[int, int] = {}
    for l in com_unidade:
        pid = l.propriedade_id
        por_fazenda[pid] = por_fazenda.get(pid, 0) + 1

    n_fazendas = len(por_fazenda)
    n_transacoes = len(com_unidade)
    maior = max(por_fazenda.values()) if por_fazenda else 0
    concentracao = (maior / n_transacoes) if n_transacoes else None

    aviso = None
    if n_transacoes == 0:
        aviso = (
            "Nenhuma transação de venda com quantidade e unidade. "
            "Sem quantidade não há preço por unidade — importe a NF-e de venda."
        )
    elif n_transacoes < MINIMO_REFERENCIA:
        aviso = (
            f"{n_transacoes} transacao(oes) em {n_fazendas} fazenda(s). "
            f"Isto não é preço de mercado — é amostra. O limiar é "
            f"{MINIMO_REFERENCIA} transações."
        )
    elif len(por_unidade) > 1:
        aviso = (
            f"Preços em {len(por_unidade)} unidades diferentes "
            f"({', '.join(sorted(por_unidade))}). Cada unidade tem a sua "
            "distribuição — não são somáveis."
        )

    return {
        "produto": produto,
        "uf": uf,
        "unidades": {u: _percentis(vals) for u, vals in sorted(por_unidade.items())},
        "n_transacoes": n_transacoes,
        "n_fazendas": n_fazendas,
        # A concentração é sobre as transações COM unidade. Dizer 41% com base
        # só nas que têm quantidade seria apresentar uma amostra parcial como
        # se fosse o mercado todo.
        "concentracao_top1": concentracao,
        "transacoes_por_fazenda": dict(sorted(por_fazenda.items())),
        "descartados_sem_unidade": sem_unidade,
        "e_preco_de_referencia": n_transacoes >= MINIMO_REFERENCIA,
        "fonte": (
            "LancamentoFinanceiro tipo=RECEITA com quantidade e unidade "
            "por item (migration 0060); percentis por interpolação inclusiva "
            "(R-7)"
        ),
        "aviso": aviso,
    }
