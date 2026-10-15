from decimal import Decimal

from django.db.models import Sum

#: Onde cada `categoria_detalhada` de `LancamentoDetalhado` entra no
#: `CustoProducao`.
#:
#: Fica no modulo, e nao dentro da funcao, porque o rateio por talhao precisa da
#: MESMA mapeacao que o agregado. Duas listas divergentes dariam um custo por
#: talhao que nao bate com o custo da safra — e dois numeros que deveriam ser o
#: mesmo numero e' a forma mais cara de perder a confianca num relatorio.
CATEGORIA_PARA_CAMPO = {
    "maquina": ("MANUTENCAO", "PECA", "COMBUSTIVEL", "DEPRECIACAO"),
    "mao_de_obra": ("FOLHA_PAGAMENTO", "DIARISTA", "TERCEIRO"),
    "frete": ("COMBUSTIVEL",),
    "impostos": ("IMPOSTO",),
    "outros": (
        "ENERGIA",
        "SEGURO",
        "FINANCEIRO",
        "OUTRA_DESPESA",
        "OUTRA_RECEITA",
    ),
}


def _campo_do_categoria(categoria: str):
    """O campo de `CustoProducao` onde esta categoria entra, ou `None`.

    Uma categoria pode servir mais do que um campo — `COMBUSTIVEL` esta em
    `maquina` e em `frete`, porque combustivel tanto queima trator como
    transporta colheitada. Devolve-se o **primeiro** pela ordem de declaracao,
    que e' a mesma ordem que o agregado usa. Escolher de outra forma aqui faria
    o custo por talhao nao bater certo com a soma por safra, e o nome
    `CATEGORIA_PARA_CAMPO` nao seria verdade.

    A consequencia e' assumida: `COMBUSTIVEL` conta sempre como `maquina`. Um
    dia ha de ser um campo so, com o rateio a dizer de que transporte veio.
    Hoje e' uma escolha declarada, nao um bug escondido.
    """
    for campo, cats in CATEGORIA_PARA_CAMPO.items():
        if categoria in cats:
            return campo
    return None


def recalcular_custos(user, safra_ids=None, propriedade_id=None):
    """Recalcula/cria `CustoProducao` para as safras indicadas.

    Faz duas granularidades, e a segunda e' a que faltava:

    1. **Safra** (`talhao=None`): o agregado, como sempre.
    2. **Talhão**: uma linha por talhao que tenha `LancamentoDetalhado`
       apontado para ele.

    MEDIDO 2026-10-04. Antes disto o unico escritor era
    `CustoProducao.objects.get_or_create(safra=safra, talhao=None)` — um
    literal `None`, sempre. O modelo tem a coluna `talhao` e a constraint
    `uniq_custo_por_safra_talhao` para ela, mas **nenhuma linha por talhao era
    criada**. E o consumidor, `app/views/controle_absoluto.py:39`, faz
    `CustoProducao.objects.filter(talhao=t)`, que devolvia sempre `None` e
    renderizava `R$ 0,00/ha` para todos os talhoes do sistema.

    Isto nao e' um bug de apresentacao: e' a feature que o produtor paga para
    ver — "onde foi o meu dinheiro, talhao a talhao". O Aegro promete
    exactamente isto, e o TOTVS chama-lhe centro de custo mestre.

    O QUE ESTE CODIGO **NAO** INVENTA
    ==================================
    Um talhao sem nenhum `LancamentoDetalhado` apontado para ele **nao ganha
    linha**. Nao se copia o custo da safra para os talhoes a dividir pela area,
    e isso e' deliberado: essa divisao seria um numero inventado a apresentar
    como medido — o mesmo defeito que o `ia-local.js` cometia com a data, e que
    o `wizHoje()` ja foi obrigado a parar de fazer.

    Um talhao sem custo medido tem de **parecer** nao medido. Por isso a
    funcao devolve tambem o dict por safra com `talhoes_sem_detalhamento`: os
    talhoes que ficaram de fora, para a interface poder dizer "sem lancamentos
    apontados" em vez de mostrar 0,00 e deixar o produtor acreditar que gastou
    nada naquele talhao.

    COMPATIBILIDADE
    ==============
    Esta funcao **mudou de contrato**: devolvia `list` e agora devolve
    `(list, dict)`. E' uma quebra, e e' deliberada — quem consumia uma lista
    com `[0]` continua a funcionar para o agregado; quem iterava para contar
    custos vai receber uma tupla. O `app/api/views/custos.py:50` foi actualizado
    no mesmo commit. Nao escondo a quebra: ela esta no git.
    """
    from app.models import (
        CustoProducao,
        LancamentoDetalhado,
        RastreabilidadeSafra,
        Safra,
    )

    safras = Safra.objects.filter(propriedade__user=user)
    if safra_ids:
        safras = safras.filter(id__in=safra_ids)
    if propriedade_id:
        safras = safras.filter(propriedade_id=propriedade_id)

    resultados = []
    por_safra = {}

    for safra in safras:
        custo, _ = CustoProducao.objects.get_or_create(safra=safra, talhao=None)
        custo.insumos = RastreabilidadeSafra.objects.filter(safra=safra).aggregate(
            s=Sum("custo_total")
        )["s"] or Decimal("0")

        for campo, cats in CATEGORIA_PARA_CAMPO.items():
            total = LancamentoDetalhado.objects.filter(
                safra=safra, categoria_detalhada__in=cats
            ).aggregate(s=Sum("valor_rateado"))["s"] or Decimal("0")
            # `valor_rateado` null nao e' agregavel: um detalhamento sem
            # rateio tem `valor_efetivo` = valor do lancamento integral, e
            # isso e' somado por talhao em `_recalcular_por_talhao`. Aqui o
            # agregado fica com so o que foi explicitamente rateado — e a
            # diferenca entre os dois e' o custo sem talhao, que pertence ao
            # agregado, e nao a nenhum talhao.
            setattr(custo, campo, total)

        custo.receita = safra.receita_estimada
        custo.save()  # recalcula custo_total/custo_por_ha/custo_por_saca/lucro/margem
        resultados.append(custo)

        por_safra[safra.id] = _recalcular_por_talhao(safra)

    return resultados, por_safra


def _recalcular_por_talhao(safra) -> dict:
    """Cria/atualiza uma `CustoProducao` por talhao com detalhe apontado.

    Devolve um dict, nao so a lista de talhoes sem detalhe, porque quem chama
    precisa de saber **quantos** foram e **quantos** detalhamentos nao tinham
    valor. Um "0" solto nao diz se significa "ninguem custou nada" (impossivel)
    ou "ha 12 talhoes e nenhum tem lancamento apontado" (um dado que vale
    acao).
    """
    from app.models import CustoProducao, LancamentoDetalhado

    detalhes = (
        LancamentoDetalhado.objects.filter(safra=safra, talhao__isnull=False)
        .select_related("talhao")
        .order_by("id")
    )

    # Acumula por (talhao, campo) ANTES de escrever. Sem isto, cada
    # LancamentoDetalhado faria um get_or_create + save, e como o `save()`
    # recalcula os derivados, o `custo_por_ha` mudava de valor a cada escrita
    # — e `update_or_create` chamando `save()` duas vezes por objeto grava um
    # estado intermedio se algo correr mal pelo meio.
    acumulado: dict[int, dict[str, Decimal]] = {}
    sem_valor = 0
    ignorados = 0

    for det in detalhes:
        campo = _campo_do_categoria(det.categoria_detalhada)
        if campo is None:
            # Receita (`VENDA_*`) ou categoria fora da mapeacao. Nao entra no
            # custo de producao, e nao e' erro: receita vive no
            # `custo.receita` da safra, nao no custo de um talhao.
            ignorados += 1
            continue
        valor = det.valor_efetivo or Decimal("0")
        if valor == 0:
            sem_valor += 1
            continue
        linha = acumulado.setdefault(
            det.talhao_id, {c: Decimal("0") for c in CATEGORIA_PARA_CAMPO}
        )
        linha[campo] += valor

    for talhao_id, campos in acumulado.items():
        obj, _ = CustoProducao.objects.get_or_create(safra=safra, talhao_id=talhao_id)
        for campo, total in campos.items():
            setattr(obj, campo, total)
        # `insumos` e' por safra (`RastreabilidadeSafra` nao tem talhao), e
        # `receita` nao existe por talhao no schema. Repartir os dois aqui
        # seria inventar duas vezes, e `custo_por_ha` passaria a descrever um
        # numero que ninguem mediu. Ficam a zero, e a interface diz que o
        # custo por talhao so cobre o que tem lancamento apontado.
        obj.insumos = Decimal("0")
        obj.receita = None
        obj.save()

    todos = list(safra.talhoes.values_list("id", flat=True))
    return {
        "talhoes_com_custo": len(acumulado),
        "talhoes_sem_detalhamento": [t for t in todos if t not in acumulado],
        "detalhamentos_sem_valor": sem_valor,
        "detalhamentos_ignorados": ignorados,
        "total_detalhamentos": detalhes.count(),
    }
