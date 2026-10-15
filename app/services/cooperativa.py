"""Cooperativa: um agregado que vê N produtores, sem ver o que não lhe cabe.

## O que isto é

O item nº 2 do plano (§21.9). Uma cooperativa é **N produtores com um
agregado**: o técnico ve a soma, o cooperado não.

E a parte interessante é que **isto já está construído**. O Ampliagro tem:

- `PerfilUsuario.tipo_usuario` com `agronomo`, `servidor`, `administrativo`
  (`models/usuario.py:11-18`);
- `PerfilUsuario.propriedade_vinculada` — a propriedade que o perfil serve;
- `TenantIsolationMiddleware`, que defende **por tabela** e não por lista de
  parâmetros (`app/middleware.py:60-70`);
- `propriedades_visiveis(user)` — o filtro de posse, já usado por toda a API.

Uma cooperativa é um perfil com muitas propriedades. **Não falta modelo: falta
a intenção e a vista.** Por isso este módulo não altera o schema — o que é
deliberado e explico abaixo.

## Por que NÃO acrescento um `tipo_usuario = "cooperativa"`

Porque mudaria o schema e, com ele, o `TenantIsolationMiddleware` — que é a
defesa de multi-tenancy do sistema. Um tipo novo precisa de entrar na tabela de
verificação por tabela, e essa tabela é escrita à mão (ver o meu teste
`test_todo_modelo_da_lista_tem_caminho_ate_o_dono`, que existe precisamente
para apanhar isso).

O caminho barato é o mesmo que o `servidor` usa: uma propriedade que pertence
à cooperativa, e perfis vinculados a ela. `PerfilUsuario.propriedade_vinculada`
já aceita qualquer `Propriedade` — inclusive uma que represente o escritório da
cooperativa.

**O que falta para isto ser um produto:** um `tipo` ou um flag que diga "este
perfil agrega várias propriedades". Até lá, este módulo funciona **por
delegação explícita**: o caller diz quais propriedades agregar, e este módulo
verifica se o caller pode vê-las. **A verificação é o produto** — a agregação
sem verificação seria um vazamento com nome bonito.

## O contrato

- `pode_agregar(user, propriedade)` responde por cada propriedade
  **individualmente**. Uma cooperativa não vê tudo do cooperado: vê o que a
  propriedade expõe, e o resto continua fechado.
- `agregado` devolve os fatores por propriedade **e** a soma, mas a soma traz
  `incompleta: true` e a lista do que falta. Somar valores que não cobrem tudo
  e chamar isso de "total da cooperativa" é inventar uma ordem de grandeza.
"""

from __future__ import annotations

from decimal import Decimal

from app.hierarquia import propriedades_visiveis
from app.services.capacidade_pagamento import capacidade_pagamento


def pode_agregar(user, propriedade_id: int) -> bool:
    """Este perfil pode ver esta propriedade?

    **Uma por uma.** É a mesma doutrina do `TenantIsolationMiddleware`: a
    verificação é por TABELA, não por parâmetro. Uma lista de parâmetros é uma
    lista para se esquecer de acrescentar um.
    """
    return propriedades_visiveis(user).filter(pk=propriedade_id).exists()


def propriedades_agregaveis(user, candidatas: list[int]) -> tuple[list[int], list[int]]:
    """Separa o que o perfil pode agregar do que não pode.

    Devolve `(permitidas, recusadas)` com os **ids**, para que o caller possa
    dizer ao produtor o que ficou de fora e porquê — e não apenas devolver
    uma lista menor, que ele leria como "a cooperativa não tem isso".
    """
    permitidas, recusadas = [], []
    for pid in candidatas:
        (permitidas if pode_agregar(user, pid) else recusadas).append(pid)
    return permitidas, recusadas


def _acumula(por_propriedade, permitidas, fator):
    """Separa os que têm valor apurado dos que não têm.

    Devolve `(valores_decimais, incompletos)`. Um factor sem apuração **não
    entra como zero**: entra como desconhecido, e a soma sai marcada.

    A área tem uma regra à parte: um `area_total_ha` com `valor` e
    `area_medida` falso é um zero administrativo (propriedade cadastrada sem
    metragem), não uma medição de 0 ha. Somar 0 ha não muda a soma, mas
    **mudaria** a contagem `propriedades_no_total` — que é o que diz ao
    produtor quantas propriedades o número cobre.
    """
    valores, incompletos = [], []
    for pid in permitidas:
        f = por_propriedade[pid]["fatores"][fator]
        sem_apuracao = f["valor"] is None
        zero_administrativo = fator == "area_total_ha" and not f.get("area_medida")
        if sem_apuracao or zero_administrativo:
            incompletos.append(
                {"propriedade_id": pid, "fator": fator, "motivo": f["motivo"]}
            )
        else:
            valores.append(Decimal(str(f["valor"])))
    return valores, incompletos


def agregado(user, propriedade_ids: list[int]) -> dict:
    """Fatores de cada propriedade autorizada + soma, com o que falta declarado.

    A soma **só** soma propriedades com todos os factores presentes. Uma
    propriedade sem receitas apuradas não entra como zero — entra como
    desconhecida, e a soma sai marcada como incompleta.
    """
    permitidas, recusadas = propriedades_agregaveis(user, propriedade_ids)

    por_propriedade = {pid: capacidade_pagamento(pid) for pid in permitidas}

    receitas, inc_receitas = _acumula(por_propriedade, permitidas, "receitas_periodo")
    despesas, inc_despesas = _acumula(por_propriedade, permitidas, "despesas_periodo")
    area, inc_area = _acumula(por_propriedade, permitidas, "area_total_ha")

    incompletos = inc_receitas + inc_despesas + inc_area

    soma_receitas = sum(receitas) if receitas else None
    soma_despesas = sum(despesas) if despesas else None
    saldo = (
        float(soma_receitas - soma_despesas)
        if soma_receitas is not None and soma_despesas is not None
        else None
    )

    return {
        "propriedades_agregadas": permitidas,
        "propriedades_recusadas": recusadas,
        "por_propriedade": por_propriedade,
        "totais": {
            "receitas": None if soma_receitas is None else float(soma_receitas),
            "despesas": None if soma_despesas is None else float(soma_despesas),
            "saldo": saldo,
            "area_ha": None if not area else float(sum(area)),
            "propriedades_no_total": {
                "receitas": len(receitas),
                "despesas": len(despesas),
                "area_ha": len(area),
            },
        },
        # A soma de N propriedades não é o total da cooperativa se alguma
        # ficou de fora. Dizer "R$ 1.2M" sem dizer "de 3 de 5" é a mesma
        # mentira do `or Decimal("1.0")` que o `custo_producao.py` tinha.
        "incompleta": bool(incompletos or recusadas),
        "incompletos": incompletos,
        "aviso": (
            None
            if not (incompletos or recusadas)
            else (
                f"Totais de {len(permitidas)} propriedades, com "
                f"{len(incompletos)} fator(es) sem apuração e "
                f"{len(recusadas)} fora do seu escopo. Os totais são dos "
                "valores apurados — não da cooperativa inteira."
            )
        ),
        "decisao_de_credito": None,
    }
