"""DRE (Demonstrativo do Resultado) — e onde ele ainda não é fiável.

## O que este serviço faz

Agrupa `LancamentoFinanceiro` por categoria e reconstrói a estrutura de um
DRE: receita bruta → deduções → receita líquida → custo de produção → lucro
bruto → despesas operacionais → resultado financeiro → lucro líquido.

## Três coisas que este serviço **não** faz, e diz

Antes do código, porque um DRE que parece completo e não é é pior do que um
DRE que se admite incompleto.

### 1. `deducoes` não é medida

Não há devolução, ou restituição modellada. A linha existe no ecrã porque
a estrutura de um DRE a tem, e estava hardcoded a `Decimal("0.00")` com o
comentário "pode ser categorizado futuramente".

**Um zero aqui não é — é uma afirmação.** "R$ 0,00 de deduções" diz ao
leitor "não devolvemos nada". A verdade é "o sistema não tem onde lançar uma
devolução". Para quem lê o DRE a avaliar crédito, a diferença é entre R$ 500
mil de receita e R$ 500 mil *menos o que foi devolvido* — e o segundo número
não existe cá.

Por isso `deducoes` é `None` com `deducoes_motivo`, e **`receita_liquida` é
`None`**, porque derivar uma líquida de uma linha não medida propaga a
mentira com ar de número.

### 2. `mapa_grupos` não inventa categorias

As chaves do mapa são as categorias de `CATEGORIAS_FINANCEIRO`
(`models/financeiro.py:11-24`). Um teste bidirecional garante que:

- nenhuma chave do mapa é uma categoria que o modelo não tem (`test_mapa_nao_inventa_categorias`);
- nenhuma categoria real fica sem grupo (`test_toda_categoria_real_tem_grupo`).

Isto não éacademic: o mapa anterior continha `SEMENTE` e `JUROS`, que **não
existem** em `CATEGORIAS_FINANCEIRO` (existem `COMPRA_SEMENTE` no
`categoria_detalhada` de `custos.py`, que é outro campo e outro vocabulário).
Chave morta não quebra nada — mente sobre a cobertura.

### 3. Uma categoria desconhecida é nomeada, não engolida

O código anterior fazia `mapa_grupos.get(categoria, <default>)`. Uma receita
que não mapeasse entrava como `receita_bruta` **sem ninguém saber**, e o DRE
ficava plausível e errado.

**Um default que classifica é pior do que um erro**, porque o erro vê-se.
Agora uma categoria fora do mapa vai para `nao_classificadas`, com o valor que
não foi publicado, e o DRE marca-se `incompleto`.

Nota sobre reachability: `categoria` tem `choices`, e `choices` no Django é
validação de formulário — **não** impede `.save()` nem `.update()`. Um
importador, um `.update()` ou um bug de oitiva escreve lá o que quiser. O
serviço não pode assumir que a base é limpa.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.db.models import Sum

from app.models.financeiro import LancamentoFinanceiro

# Mapa de grupo DRE. As chaves são categorias REAIS de
# `CATEGORIAS_FINANCEIRO` — um teste bidirecional vigia isto.
mapa_grupos = {
    # RECEITA BRUTA
    "VENDA_PROD": "receita_bruta",
    "VENDA_ANIMAL": "receita_bruta",
    "VENDA_LEITE": "receita_bruta",
    # CUSTO DE PRODUÇÃO
    "INSUMO": "custo_producao",
    "COMBUSTIVEL": "custo_producao",
    "MANUTENCAO": "custo_producao",
    # DESPESAS OPERACIONAIS
    "FOLHA": "despesa_operacional",
    "SERVICO": "despesa_operacional",
    "ENERGIA": "despesa_operacional",
    "OUTRO": "despesa_operacional",
    # RESULTADO FINANCEIRO
    "IMPOSTO": "resultado_financeiro",
    "FRETE": "resultado_financeiro",
}

GRUPOS = (
    "receita_bruta",
    "custo_producao",
    "despesa_operacional",
    "resultado_financeiro",
)

MOTIVO_DEDUCOES = (
    "devoluções, singelas e restituições não são categorias de "
    "LancamentoFinanceiro — não há onde as lançar, logo não há o que medir"
)


def gerar_dre(propriedade_id: int, data_inicio: date, data_fim: date) -> dict:
    """DRE agrupado, com `None` onde o número não é confiável.

    As garantias:

    - `deducoes` é `None` + `deducoes_motivo`; nunca um zero afirmado.
    - `receita_liquida` é `None` enquanto `deducoes` não for medido.
    - Categoria fora de `mapa_grupos` vai para `nao_classificadas` e marca o
      DRE como `incompleto` — nunca entra num grupo por default.
    """
    lancamentos = LancamentoFinanceiro.objects.filter(
        propriedade_id=propriedade_id, data__gte=data_inicio, data__lte=data_fim
    )

    totais_por_categoria = lancamentos.values("categoria", "tipo").annotate(
        total=Sum("valor")
    )

    # Todos os grupos a `0.00`: aqui **é** uma medição válida. Um grupo sem
    # lançamentos vale zero — a soma de uma conjunto vazio é zero, e isso é
    # aritmética, não ausência de medição. A distinção `None`/`0` aqui é
    # diferente da dos factores de crédito, e por isso está comentada: lá o
    # que falta é *informação que o sistema não tem*; aqui é um grupo de
    # veículos que pode legitimamente estar vazio.
    dre = {g: Decimal("0.00") for g in GRUPOS}
    dre["detalhes"] = {g: [] for g in GRUPOS}
    nao_classificadas = []

    for item in totais_por_categoria:
        categoria = item["categoria"]
        tipo = item["tipo"]
        # `Sum` sobre um grupo com linhas nunca é None; o `or` ficaria por
        # causa de um grupo vazio, que `values().annotate()` não produz.
        valor = item["total"]

        grupo = mapa_grupos.get(categoria)
        if grupo is None:
            # Não engolir. Um default que classifica é pior que um erro,
            # porque produz um DRE plausível e errado.
            nao_classificadas.append(
                {"categoria": categoria, "valor": valor, "tipo": tipo}
            )
            continue

        dre["detalhes"][grupo].append(
            {"categoria": categoria, "valor": valor, "tipo": tipo}
        )
        dre[grupo] += valor

    # `deducoes` não é medida. Ver o docstring do módulo.
    deducoes = None
    receita_liquida = None if deducoes is None else dre["receita_bruta"] - deducoes

    incompleto = list(nao_classificadas)
    if deducoes is None:
        incompleto.append({"linha": "deducoes", "motivo": MOTIVO_DEDUCOES})

    dre["deducoes"] = deducoes
    dre["deducoes_motivo"] = None if deducoes is not None else MOTIVO_DEDUCOES
    dre["receita_liquida"] = receita_liquida
    dre["nao_classificadas"] = nao_classificadas

    # `lucro_bruto` depende da líquida, que não é calculável. Logo é `None`
    # também — e `resultado_operacional` e `lucro_liquido`, que dependem dele.
    if receita_liquida is None:
        dre["lucro_bruto"] = None
        dre["resultado_operacional"] = None
        dre["lucro_liquido"] = None
    else:
        dre["lucro_bruto"] = receita_liquida - dre["custo_producao"]
        dre["resultado_operacional"] = dre["lucro_bruto"] - dre["despesa_operacional"]
        dre["lucro_liquido"] = (
            dre["resultado_operacional"] - dre["resultado_financeiro"]
        )

    dre["incompleto"] = incompleto
    dre["aviso"] = (
        None
        if not incompleto
        else (
            "DRE incompleto: "
            + "; ".join(i.get("linha") or i.get("categoria") for i in incompleto)
            + ". O lucro bruto e o líquido não são calculáveis — ver `motivo`."
        )
    )

    return dre
