"""Os serviços que construímos, ligados à automação.

## O problema que este ficheiro resolve

`capacidade_pagamento`, `rede_precos`, `zarc`, `cfop`,
`reforma_tributaria` e `custo_producao` existem e funcionam — 154 testes
verificam-no. **Nenhum é alcançável pela IA.**

Isto não é um detalhe de arquitectura. É a diferença entre uma feature e código
morto: um produtor que pergunta "qual a minha capacidade de pagamento?" oubebe
"não tenho essa informação" sobre um dado que está na base dele. E a
automação prometida — a IA a responder de rotina, sem o produtor pedir — não
cobre nada disto.

`app/tests_automacao_completude.py` mede a lacuna. Este ficheiro fecha-a.

## Todos de leitura

**Todos estes intents são só-leitura.** Não é coincidência e não é
pundonorismo: `somente_leitura()` é o que separa um sistema que consulta de um
sistema que age, e a §VI do `8.md` fixa que a IA não escreve no layout do
produtor sem ele pedir. Um factor de crédito que a IA altera é um factor que
alguém deixou de auditar.

Nenhum destes handlers escreve. Todos devolvem `motivo`/`fonte`/`fonte_dado`
para que a camada de apresentação carimbe a resposta.

## A propriedade vem do produtor, nunca de um parâmetro solto

Todos usam `_prop(user, params)` — a mesma resolução dos outros handlers. Um
intent que aceite `propriedade_id` cru é um `TenantIsolationMiddleware`
esperado a ser o único porteiro, e a propriedade é a linha mais fina do
sistema.
"""

from __future__ import annotations


def _prop(user, params):
    """A propriedade do produtor, **com o filtro de posse do projecto**.

    Não delego em `intents.py::_prop`, que faz `Propriedade.objects.filter(
    user=user)` — mais estrito, e por isso seguro, mas **só** para quem é
    dono. Um perfil `servidor`/`agronomo` não é dono das fazendas que serve,
    e portanto a versão estrita devolve `None` para ele — o que matava
    exactamente o caso da cooperativa (§23D), onde o técnico pergunta pelos
    campos de várias fazendas.

    `propriedades_visiveis` é o filtro de posse canónico do projecto: as
    próprias mais a vinculada ao perfil mais a do funcionário. Mais largo,
    e continua a ser um filtro — não um "qualquer uma".
    """
    from app.hierarquia import propriedades_visiveis

    qs = propriedades_visiveis(user)

    pid = params.get("propriedade_id")
    if pid:
        return qs.filter(pk=pid).first()

    nome = (params.get("propriedade") or "").strip()
    if nome:
        return qs.filter(nome__icontains=nome).first()

    return qs.first()


def _base(dados, resposta, fonte):
    """Envelope comum: resposta curta + dados estruturados + proveniência.

    `fonte_dado` é o carimbo que a camada de apresentação mostra. Sem ele, um
    `None` pode ser mostrado como 0 — que é o defeito que a §23E do `8.md`
    corrigiu no DRE.
    """
    return {
        "ok": True,
        "resposta": resposta,
        "dados": dados,
        "fonte_dado": fonte,
    }


# ---------------------------------------------------------------------------
# Capacidade de pagamento
# ---------------------------------------------------------------------------


def h_capacidade_pagamento(user, params, ctx):
    """Factores de crédito — e a recusa de decidir."""
    from app.services.capacidade_pagamento import capacidade_pagamento

    prop = _prop(user, params)
    if not prop:
        return {"ok": False, "erro": "nenhuma propriedade encontrada"}

    cap = capacidade_pagamento(prop.id)
    f = cap["fatores"]

    partes = []
    for nome, rotulo in (
        ("receitas_periodo", "receitas"),
        ("despesas_periodo", "despesas"),
        ("saldo_periodo", "saldo"),
        ("custo_por_hectare_medio", "custo por hectare"),
    ):
        v = f.get(nome, {})
        valor = v.get("valor")
        if valor is None:
            partes.append(f"{rotulo}: não apurado ({v.get('motivo')})")
        else:
            partes.append(f"{rotulo}: R$ {valor:,.2f}")

    return _base(
        {
            "propriedade": prop.nome,
            "fatores": f,
            "decisao_de_credito": cap["decisao_de_credito"],
        },
        "Capacidade de pagamento de "
        + prop.nome
        + ": "
        + "; ".join(partes)
        + ". Isto são FACTORES observáveis, não uma decisão de crédito — a "
        "decisão é do banco, e o sistema não a toma.",
        "medido",
    )


# ---------------------------------------------------------------------------
# Rede de preços
# ---------------------------------------------------------------------------


def h_preco_referencia(user, params, ctx):
    """Preço de referência do produto, com a estrutura que o preço esconde."""
    from app.services.rede_precos import preco_referencia

    produto = params.get("produto")
    if not produto:
        return {
            "ok": False,
            "erro": "diga o produto: 'qual o preço da soja'",
        }

    uf = params.get("uf") or prop_uf(user, params)
    # O `user` vai **primeiro** e sem default: um preco de mercado que nao
    # filtre por posse diz a um produtor o preco de outro.
    r = preco_referencia(user, str(produto), uf=uf)

    if r["n_transacoes"] == 0:
        return _base(
            r,
            f"Não há transação de {produto} com quantidade e unidade"
            + (f" em {uf}" if uf else "")
            + ". Sem quantidade não há preço por unidade — importe a NF-e de "
            "venda para ter dado.",
            "sem_dado",
        )

    linhas = []
    for unidade, st in r["unidades"].items():
        linhas.append(
            f"{unidade}: mediana R$ {st['mediana']:,.2f} "
            f"(P25 R$ {st['p25']:,.2f}, P75 R$ {st['p75']:,.2f})"
            if st["p25"] is not None
            else f"{unidade}: mediana R$ {st['mediana']:,.2f}"
        )

    conc = r["concentracao_top1"]
    estrutura = (
        f" {r['n_transacoes']} transações em {r['n_fazendas']} fazenda(s), "
        f"{conc * 100:.0f}% da maior."
        if conc is not None
        else ""
    )

    return _base(
        r,
        f"Preço de {produto}: "
        + "; ".join(linhas)
        + "."
        + estrutura
        + (f" AVISO: {r['aviso']}" if r["aviso"] else "")
        + " A concentração importa mais que a mediana: é quem tem poder de "
        "negociação.",
        "medido" if r["e_preco_de_referencia"] else "medido_com_aviso",
    )


def prop_uf(user, params):
    prop = _prop(user, params)
    return prop.uf if prop else None


# ---------------------------------------------------------------------------
# ZARC
# ---------------------------------------------------------------------------


def h_zarc_safra(user, params, ctx):
    """A safra está dentro da janela ZARC? E o que fazer se não estiver."""
    from app.services.zarc import verificar_propriedade

    prop = _prop(user, params)
    if not prop:
        return {"ok": False, "erro": "nenhuma propriedade encontrada"}

    vereditos = verificar_propriedade(prop.id)
    if not vereditos:
        return _base(
            {"propriedade": prop.nome, "rastros": []},
            f"{prop.nome} não tem safras registadas, logo não há janela ZARC "
            "para verificar.",
            "sem_dado",
        )

    dentro = [v for v in vereditos if v["dentro_da_janela"] is True]
    fora = [v for v in vereditos if v["dentro_da_janela"] is False]
    sem = [v for v in vereditos if v["dentro_da_janela"] is None]

    partes = []
    for v in fora:
        partes.append(
            f"safra {v.get('ano')} ({v.get('cultura')}) fora da janela — "
            f"{v.get('dias_fora', '?')} dia(s)"
        )
    for v in sem:
        partes.append(
            f"Conhece a safra {v.get('ano')} ({v.get('cultura')}) sem ZARC "
            "carregado — não apurável"
        )

    if not partes:
        texto = f"Todas as {len(dentro)} safra(s) de {prop.nome} dentro da janela ZARC."
    else:
        texto = (
            f"{len(dentro)} de {len(vereditos)} safra(s) dentro da janela ZARC. "
            + "; ".join(partes)
        )

    return _base(
        {"propriedade": prop.nome, "rastros": vereditos},
        texto
        + " Uma safra sem ZARC não está 'fora' — está em desconhecimento, e isso é diferente.",
        "medido",
    )


# ---------------------------------------------------------------------------
# Classificação de CFOP
# ---------------------------------------------------------------------------


def h_classificar_cfop(user, params, ctx):
    """O que um CFOP faz no estoque e no financeiro."""
    from app.services.cfop import classificar

    cfop = params.get("cfop") or params.get("codigo")
    if not cfop:
        return {
            "ok": False,
            "erro": "diga o CFOP: 'o que é o CFOP 5102'",
        }

    cat, motivo = classificar(cfop)
    if cat is None:
        return _base(
            {"cfop": str(cfop), "motivo": motivo},
            f"CFOP {cfop}: {motivo}",
            "sem_dado",
        )

    efeitos = []
    if cat.classe == "entrada":
        efeitos.append("aumenta o estoque")
    elif cat.classe == "saida":
        efeitos.append("é venda — entra como receita, e NÃO como insumo")
    else:
        efeitos.append("é apuração — não gera lançamento")

    lanc = (
        f"lançamento de {cat.tipo_lancamento}/{cat.categoria}"
        if cat.tipo_lancamento
        else "sem lançamento"
    )

    return _base(
        cat.as_dict(),
        f"CFOP {cfop} ({cat.descricao}): {', '.join(efeitos)}. {lanc}.",
        "medido",
    )


# ---------------------------------------------------------------------------
# Reforma tributária
# ---------------------------------------------------------------------------


def h_ibs_cbs(user, params, ctx):
    """O imposto — ou, honestamente, que não está apurável."""
    from decimal import Decimal, InvalidOperation

    from app.services.reforma_tributaria import calcular_ibs_cbs

    bruto = params.get("valor") or params.get("base")
    if bruto in (None, ""):
        return {
            "ok": False,
            "erro": "diga o valor da base: 'quanto de IBS/CBS sobre 10 mil reais'",
        }
    try:
        base = Decimal(str(bruto).replace(".", "").replace(",", "."))
    except (InvalidOperation, ValueError):
        return {"ok": False, "erro": f"valor não é número: {bruto!r}"}

    r = calcular_ibs_cbs(base)

    if not r["apuravel"]:
        return _base(
            r,
            "Não é possível apurar IBS/CBS: "
            + str(r["motivo"])
            + f" Base informada: R$ {float(base):,.2f} — o valor existe, a "
            "alíquota é que ainda não foi carregada.",
            "sem_dado",
        )

    return _base(
        r,
        f"Sobre R$ {float(base):,.2f}: IBS R$ {r['ibs']:,.2f} + "
        f"CBS R$ {r['cbs']:,.2f} = R$ {r['total']:,.2f}. "
        f"Preço com imposto: R$ {r['preco_com_imposto']:,.2f}.",
        "medido",
    )


# ---------------------------------------------------------------------------
# Custo de produção
# ---------------------------------------------------------------------------


def h_custo_producao(user, params, ctx):
    """Custo por hectare e por unidade — com a área ausente dita como ausente."""
    from app.services.custo_producao import calcular_custo_producao

    prop = _prop(user, params)
    if not prop:
        return {"ok": False, "erro": "nenhuma propriedade encontrada"}

    safra_id = params.get("safra_id") or params.get("safra")
    if not safra_id:
        return {
            "ok": False,
            "erro": "diga a safra: 'custo por hectare da safra 2026'",
        }

    # `calcular_custo_producao(safra_id)` vai por ID, não por propriedade: a
    # safra já pertence a uma propriedade e voltar a passá-la seria uma chance
    # de as trocar. A tenancy foi assegurada pelo `_prop` acima.
    r = calcular_custo_producao(int(safra_id))

    ausentes = [k for k, v in r.items() if v is None]
    if not ausentes:
        texto = (
            f"Custo por hectare: R$ {r['custo_ha']:,.2f}. "
            f"Custo por {r['unidade_medida']}: R$ {r['custo_unidade']:,.4f}. "
            f"Total: R$ {r['custo_total']:,.2f}."
        )
        fonte = "medido"
    else:
        legiveis = {
            "area_total_ha": "área plantada",
            "producao_total": "produção",
            "custo_ha": "custo por hectare",
            "custo_unidade": "custo por unidade",
            "custo_total": "custo total",
        }
        texto = (
            "Não apurei: "
            + ", ".join(legiveis.get(a, a) for a in ausentes)
            + ". Sem área não há custo por hectare, e isso não é zero — é ausência."
        )
        fonte = "sem_dado"

    return _base(
        {"propriedade": prop.nome, "safra_id": int(safra_id), **r},
        texto,
        fonte,
    )
