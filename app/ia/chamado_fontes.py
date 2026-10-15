"""As FONTES — onde os números dos blocos vêm, e nunca da IA.

O BURACO QUE ESTE MÓDULO FECHA
==============================
A primeira versão do Chamado deixava a IA escrever as *linhas* de uma tabela,
de um gráfico ou de uma planilha — e marcava o bloco como `medido` por ter
linhas. Medido, em rigor:

    fonte_dado = medido
    linhas     = [['Adubo', '1.234,56'], ['Semente', '900,00']]

As duas linhas saíram de um modelo de 1,7B. Não há consulta nenhuma por trás
delas. `1.234,56` é um número que a IA inventou, e está com o carimbo que o
produtor usa para decidir uma safra.

Isto não é um detalhe de estilo. É o que `paginas.py` chama, com razão:

    "Um número gerado não é um número pequeno: é um número que não dá erro. Uma
     balança que não está ligada devolve 50,4 sc/ha com a mesma confiança de uma
     balança ligada, e o produtor multiplica pela área dele."

Tinha ainda uma agravante que só apareceu quando testei com o modelo a escrever:
o `rastrear_numeros` que escrevi marcava o "18%" do TEXTO como sem apoio — e
tratava a TABELA inventada como evangelho. O validador era mais rigoroso com a
prosa do que com a malha.

A REGRA
=======
**A IA escolhe a FONTE. O servidor escreve os NÚMEROS.**

Não há linhas no pedido. A IA diz `fonte: "despesas-por-categoria"`, o servidor
consulta o banco, aplica o tenancy e devolve as linhas com a procedência. Uma
fonte desconhecida não é erro fatal: o bloco desce a `sem_dado` e diz porquê.

Isto também torna a peça REUTILIZÁVEL. Com números escritos à mão, a peça
descreve o passado — "a despesa foi 1.234,56". Com uma fonte, a peça pergunta ao
banco — "quanto foi a despesa" — e responde com o número de hoje. Um relatório
que envelhece mal é um relatório que o produtor deixa de abrir.

O TENANCY
=========
Toda a fonte entra por `_propriedades_do_usuario(user)` — as propriedades que o
utilizador PODE VER, que é o mesmo caminho do resto do sistema. `user` é o DONO,
não o acesso: um servidor ou um funcionário não é dono, é acessor, e
`filter(user=user)` devolver-lhe-ia uma fazenda vazia sem um único aviso.
"""

from __future__ import annotations

from typing import Any

from app.ia.palco_dados import _propriedades_do_usuario, _soma


def _n(valor: Any) -> float | None:
    """Decimal -> float, ou `None`.

    `None` e não `0`. "sem dado" e "zero" são coisas diferentes, e confundi-las é
    como um produtor descobre que a fazenda está a render e o painel diz que
    está tudo a zeros.
    """
    if valor is None or valor == "":
        return None
    try:
        return float(valor)
    except (TypeError, ValueError):
        return None


def _txt(valor) -> str:
    """Formata para a célula, e nunca deixa `None` dentro da lista.

    Uma célula vazia é `""`. `None` dentro de uma lista de linhas aparece em
    `JSON.stringify` como `null`, e o produtor lê "null" na coluna do custo — um
    erro do sistema com a cara de um dado.
    """
    n = _n(valor)
    return "" if n is None else f"{n:,.2f}"


def _base(user, prop=None, talhao: str = ""):
    """Os lançamentos, já com tenancy e filtro de talhão."""
    from app.models import LancamentoFinanceiro

    base = _propriedades_do_usuario(user)
    if prop is not None:
        base = base.filter(pk=getattr(prop, "pk", prop))
    qs = LancamentoFinanceiro.objects.filter(propriedade__in=base)
    if talhao:
        qs = qs.filter(talhao__nome__icontains=str(talhao).strip().lower())
    return qs


def _safras(user, prop=None, talhao: str = ""):
    from app.models import Safra

    base = _propriedades_do_usuario(user)
    if prop is not None:
        base = base.filter(pk=getattr(prop, "pk", prop))
    qs = Safra.objects.filter(propriedade__in=base)
    if talhao:
        qs = qs.filter(talhao__nome__icontains=str(talhao).strip().lower())
    return qs


def _janela(qs, filtros):
    """Aplica `de` e `ate`. Um filtro que ninguém pediu não apaga nada."""
    if filtros.get("de"):
        qs = qs.filter(data__gte=filtros["de"])
    if filtros.get("ate"):
        qs = qs.filter(data__lte=filtros["ate"])
    return qs


# --------------------------------------------------------------------------
# AS FONTES
# --------------------------------------------------------------------------


def f_despesas_por_categoria(user, *, prop=None, talhao="", **filtros) -> dict:
    """Despesas agrupadas por categoria. A fonte mais pedida, e a mais útil."""
    from django.db.models import Sum

    qs = _janela(_base(user, prop, talhao).filter(tipo="DESPESA"), filtros)
    if filtros.get("categoria"):
        qs = qs.filter(categoria__icontains=str(filtros["categoria"]))
    linhas = [
        [str(r.get("categoria") or "sem categoria"), _txt(r.get("total"))]
        for r in qs.values("categoria")
        .annotate(total=Sum("valor"))
        .order_by("-total")[:50]
    ]
    return {"colunas": ["categoria", "valor"], "linhas": linhas, "unidade": "R$"}


def f_receitas_despesas(user, *, prop=None, talhao="", **filtros) -> dict:
    """Um mês por linha, com entrada, saída e saldo lado a lado."""
    from django.db.models import Sum
    from django.db.models.functions import TruncMonth

    qs = _janela(_base(user, prop, talhao), filtros)
    meses: dict = {}
    for r in (
        qs.annotate(mes=TruncMonth("data"))
        .values("mes", "tipo")
        .annotate(total=Sum("valor"))
    ):
        chave = r["mes"].strftime("%Y-%m") if r.get("mes") else "?"
        f = meses.setdefault(chave, {"receita": 0.0, "despesa": 0.0})
        if str(r.get("tipo")).upper() == "RECEITA":
            f["receita"] += float(r.get("total") or 0)
        else:
            f["despesa"] += float(r.get("total") or 0)
    linhas = [
        [k, _txt(v["receita"]), _txt(v["despesa"]), _txt(v["receita"] - v["despesa"])]
        for k, v in sorted(meses.items())
    ]
    return {
        "colunas": ["mês", "receita", "despesa", "saldo"],
        "linhas": linhas,
        "unidade": "R$",
    }


def f_safras(user, *, prop=None, talhao="", **filtros) -> dict:
    """Safra a safra: ano, cultura, produção, área colhida e produtividade."""
    qs = _safras(user, prop, talhao)
    if filtros.get("cultura"):
        qs = qs.filter(cultura__nome__icontains=str(filtros["cultura"]))
    linhas = []
    for s in qs.select_related("cultura").order_by("-ano")[:50]:
        area = _n(s.area_colhida) or 0.0
        prod = _n(s.producao_total) or 0.0
        # A produtividade só existe quando a ÁREA foi medida. Dividir por área
        # zero dá um infinito, e um infinito com cara de sc/ha é pior que um "—".
        por_ha = f"{prod / area:,.2f}" if area > 0 else ""
        linhas.append(
            [
                str(s.ano or ""),
                str(getattr(s.cultura, "nome", "") or ""),
                _txt(prod),
                _txt(area),
                por_ha,
            ]
        )
    return {
        "colunas": ["ano", "cultura", "produção", "área colhida", "sc/ha"],
        "linhas": linhas,
        "unidade": "t e ha",
    }


def f_lancamentos(user, *, prop=None, talhao="", **filtros) -> dict:
    """Os lançamentos, um por linha. Para quando o produtor quer o detalhe."""
    qs = _janela(_base(user, prop, talhao), filtros)
    if filtros.get("tipo"):
        qs = qs.filter(tipo=str(filtros["tipo"]).upper())
    linhas = [
        [
            l.data.isoformat() if l.data else "",
            str(l.tipo or ""),
            str(l.categoria or ""),
            _txt(l.valor),
        ]
        for l in qs.select_related("talhao").order_by("-data")[:200]
    ]
    return {
        "colunas": ["data", "tipo", "categoria", "valor"],
        "linhas": linhas,
        "unidade": "R$",
    }


def f_saldo(user, *, prop=None, talhao="", **filtros) -> dict:
    """Entradas, saídas e saldo. Para o bloco `kpi`."""
    qs = _base(user, prop, talhao)
    receitas = _soma(qs.filter(tipo="RECEITA")) or 0.0
    despesas = _soma(qs.filter(tipo="DESPESA")) or 0.0
    return {
        "colunas": ["indicador", "valor"],
        "linhas": [
            ["entradas", _txt(receitas)],
            ["saídas", _txt(despesas)],
            ["saldo", _txt(receitas - despesas)],
        ],
        "unidade": "R$",
    }


def f_chuva_semana(user, *, prop=None, talhao="", **filtros) -> dict:
    """Chuva prevista dia a dia em mm. Para gráfico de colunas.

    `prop` pode vir vazio (peça montada sem contexto): resolve como os
    handlers, porque uma fonte que só funciona com prop dada é uma fonte
    que falha no caminho onde mais importa. Sem coordenadas ou sem
    resposta: linhas vazias — e o bloco desce a `sem_dado` com o motivo
    honesto, em vez de zeros que mentiriam "sem chuva".
    """
    dias = 7
    try:
        dias = max(1, min(int(filtros.get("dias") or 7), 14))
    except (TypeError, ValueError):
        dias = 7
    if prop is None:
        try:
            from app.ia.propriedade import resolver as _resolver

            prop = _resolver(user, {})
        except Exception:
            prop = None
    if prop is None:
        return {"colunas": ["dia", "mm"], "linhas": [], "unidade": "mm"}
    from app.ia.proativo import obter_previsao

    prev = obter_previsao(user, prop, dias=dias)
    if not prev.get("ok"):
        return {"colunas": ["dia", "mm"], "linhas": [], "unidade": "mm"}
    from app.ia.intents_chuva import serie_de

    linhas, _ausentes = serie_de(prev.get("dias"))
    return {"colunas": ["dia", "mm"], "linhas": linhas, "unidade": "mm"}


def f_resumo_safras(user, *, prop=None, talhao="", **filtros) -> dict:
    """Quantas safras e quantos hectares colhidos."""
    qs = _safras(user, prop, talhao)
    if filtros.get("cultura"):
        qs = qs.filter(cultura__nome__icontains=str(filtros["cultura"]))
    area = sum(_n(s.area_colhida) or 0.0 for s in qs.only("area_colhida"))
    return {
        "colunas": ["indicador", "valor"],
        "linhas": [
            ["safras registadas", str(qs.count())],
            ["área colhida (ha)", _txt(area)],
        ],
        "unidade": "ha",
    }


#: O REGISTO. O que a IA pode citar, e de onde sai cada coisa.
#:
#: Deriva-se daqui e não se escreve à mão nas descrições: a lista escrita à mão
#: diverge no primeiro dia em que uma fonte entra, e uma fonte que a IA não
#: conhece é uma fonte que a IA inventa.
FONTES: dict[str, dict[str, Any]] = {
    "despesas-por-categoria": {
        "descricao": "Despesas agrupadas por categoria, da maior para a menor.",
        "colunas": ["categoria", "valor"],
        "filtros": ["categoria", "de", "ate"],
        "calcular": f_despesas_por_categoria,
    },
    "receitas-despesas": {
        "descricao": "Um mês por linha: quanto entrou, quanto saiu e o saldo.",
        "colunas": ["mês", "receita", "despesa", "saldo"],
        "filtros": ["de", "ate"],
        "calcular": f_receitas_despesas,
    },
    "safras": {
        "descricao": "Safra a safra: ano, cultura, produção, área colhida e sc/ha.",
        "colunas": ["ano", "cultura", "produção", "área colhida", "sc/ha"],
        "filtros": ["cultura"],
        "calcular": f_safras,
    },
    "lancamentos": {
        "descricao": "Os lançamentos um a um, do mais recente para o mais antigo.",
        "colunas": ["data", "tipo", "categoria", "valor"],
        "filtros": ["tipo", "de", "ate"],
        "calcular": f_lancamentos,
    },
    "saldo": {
        "descricao": "Entradas, saídas e saldo, num número só.",
        "colunas": ["indicador", "valor"],
        "filtros": [],
        "calcular": f_saldo,
    },
    "resumo-safras": {
        "descricao": "Quantas safras e quantos hectares colhidos.",
        "colunas": ["indicador", "valor"],
        "filtros": ["cultura"],
        "calcular": f_resumo_safras,
    },
    "chuva-semana": {
        "descricao": "Chuva prevista dia a dia em mm, até 14 dias. Para gráfico de colunas.",
        "colunas": ["dia", "mm"],
        "filtros": ["dias"],
        # EXTERNA: responde de fetch (previsão), não de registo na base — por
        # isso `test_toda_fonte_responde` não a cobra linhas sem rede.
        "externa": True,
        "calcular": f_chuva_semana,
    },
}


def calcular(
    user, nome_fonte: str, *, prop=None, talhao: str = "", filtros=None
) -> dict:
    """Calcula a fonte. Devolve SEMPRE um dicionário com `ok`.

    Nunca levanta. Uma fonte que rebenta por um dado corrompido não pode levar
    o resto da peça — a mesma doutrina de `palco_dados.enriquece`.
    """
    spec = FONTES.get(str(nome_fonte or ""))
    if spec is None:
        return {
            "ok": False,
            "erro": f"fonte desconhecida: {nome_fonte!r}",
            "fontes_conhecidas": sorted(FONTES),
        }
    try:
        bruto = spec["calcular"](user, prop=prop, talhao=talhao, **(filtros or {}))
    except Exception as exc:  # noqa: BLE001 — o motivo VAI no bloco, não no log
        # A distinção importa e é o que o teste `test_toda_fonte_responde`
        # passa a exigir: uma FALHA DE CÓDIGO não pode sair daqui a dizer
        # "não há registo". O produtor lê o motivo e tem de perceber se
        # falta lançar uma despesa ou se o sistema está partido.
        return {
            "ok": False,
            "falhou": True,
            "erro": (
                "falha ao calcular esta fonte (o problema é do sistema, "
                f"não falta registo): {exc}"
            ),
        }
    return {
        "ok": True,
        "fonte": str(nome_fonte),
        "colunas": bruto.get("colunas") or spec["colunas"],
        "linhas": bruto.get("linhas") or [],
        "unidade": bruto.get("unidade", ""),
    }


def referencia_fontes() -> list[dict[str, Any]]:
    """O dicionário que o MCP publica: o que existe e que filtros aceita."""
    return [
        {
            "id": nome,
            "descricao": spec["descricao"],
            "colunas": list(spec["colunas"]),
            "filtros": list(spec.get("filtros", [])),
        }
        for nome, spec in sorted(FONTES.items())
    ]


def summarise_fontes() -> str:
    return (
        f"Fontes de dado: {len(FONTES)} ({', '.join(sorted(FONTES))}). "
        "Cite a fonte pelo id no campo `fonte` do bloco. NÃO escreva os "
        "números: um bloco sem fonte fica 'sem dado', e os números que você "
        "escrever são descartados — é o servidor que lê a base."
    )
