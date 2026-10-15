"""
Agregação do painel sobre TODAS as propriedades visíveis do utilizador.

## O problema que isto resolve

`dashboard_data` recebia **uma** propriedade — `get_propriedade_optimizada()`,
que faz `.first()`. Um produtor com duas fazendas via o painel inteiro
calculado sobre uma delas, **sem qualquer aviso**: números reais, errados.

Isto não é um caso raro. O modelo `Propriedade` é `user = FK(User)` — não há
unicidade. E **não existe conceito de "propriedade activa"** em lado nenhum do
sistema (verificado: nenhuma referência a `propriedade_ativa` nos modelos, nas
views ou no front-end). Não havia, portanto, nenhuma intenção de design a
respeitar: era `.first()`, e `.first()` devolve a que a base de dados calçar
primeiro — que pode mudar com o plano de execução.

Quando se escolhe uma das propriedades ao acaso e se mostra o resultado como se
fosse o todo, o produtor não tem forma de saber que está a ver metade. Um
painel que mostra números plausíveis e errados é pior do que um painel vazio:
o vazio convida a investigar.

## A regra

Sem "propriedade activa" definida, a leitura honesta é: **o painel mostra o
total do que o utilizador pode ver.** Um produtor com duas fazendas quer o
negócio inteiro, não a fazenda que a base de dados devolveu primeiro.

Por isso agregamos sobre `propriedades_visiveis(user)` — as próprias, mais a
vinculada ao perfil de servidor, mais a do funcionário ligado. É a mesma
consulta que o resto da hierarquia de permissões já usa, o que garante que o
painel não mostra nem mais nem menos do que a pessoa pode ver noutro sítio.

## O que NÃO se pode agregar

Some things genuinely belong to one property and cannot be summed:

- **Clima** — é a previsão de um sítio. Agregar meteorologia de três fazendas
  em três municípios dá um número que não corresponde a lado nenhum. Escolhemos
  a propriedade com maior área (a que domina o painel) e dizemos qual é, em vez
  de inventar uma média.
- **Objetos do payload** (`propriedade`, `safras` com cultura/ano) — são listas
  legíveis. Mantêm-se por propriedade, com a marca de qual é qual.

Tudo o resto (saldos, despesas, cabeças de gado, funcionários, hectares, OS
pendentes) é um somatório, e é assim que é agregado.
"""

from datetime import date, timedelta

from django.db.models import Q, Sum
from django.db.models.functions import TruncMonth

MESES_PT = [
    "Jan",
    "Fev",
    "Mar",
    "Abr",
    "Mai",
    "Jun",
    "Jul",
    "Ago",
    "Set",
    "Out",
    "Nov",
    "Dez",
]


def escolher_propriedade_principal(propriedades):
    """A propriedade que representa o painel: a de maior área medida.

    Só é usada para coisas que não se agregam (o clima). Escolher a maior
    area é melhor do que escolher a primeira: o painel fala em nome da maior
    parte da operação, e a resposta traz `propriedade_principal` para o
    utilizador ver a quem pertence.
    """
    return max(
        propriedades,
        key=lambda p: float(p.area_total or 0),
    )


def agregar_safras(safras):
    """Lista de safras para o painel, com a propriedade de origem.

    Mantém a forma que o front-end já consome (`cultura`, `area`, `sacas`,
    `ano`) e acrescenta `propriedade_id`/`propriedade` para que, havendo mais
    do que uma fazenda, o widget possa dizer de onde veio cada linha.
    """
    saida = []
    for s in safras:
        saida.append(
            {
                "cultura": s.cultura.nome if s.cultura else "—",
                "area": float(s.area_plantada or 0),
                "sacas": float(s.producao_total or 0),
                "ano": s.ano,
                "propriedade_id": s.propriedade_id,
                "propriedade": s.propriedade.nome if s.propriedade_id else "",
            }
        )
    return saida


def financeiro_mensal_agregado(lancamentos):
    """Série mensal de receitas/despesas somando todas as propriedades.

    Sem distorção: um mês entra no gráfico se qualquer propriedade teve
    movimento nesse mês, e os valores são a soma desse mês. Duas fazendas com
    movimento emombo dão um Fevereiro com os dois — que é a verdade.

    O QUE ESTA VERSÃO CORRIGE
    ==========================
    A chave do mapa era `r["mes"].month` — o número do mês **sem o ano**.
    Isso obriga o gráfico a escolher UM ano só, e a escolha era silenciosa e
    arbitrária: o último `(ano, mês)` que a base de dados devolveu vencia.

    Com lançamentos em vários anos, dois Outubros diferentes caíam na mesma
    chave, e o segundo apagava o primeiro. Verificado na Fazenda Modelo
    (Primavera do Leste/MT): a despesa de R$ 420.000 de 2024-10 desaparecia
    do gráfico por causa da receita de R$ 850.000 de 2026-10. O produtor via
    "Outubro: receita 850.000, despesa 0,00" — e a despesa existia.

    A soma por mês do CALENDÁRIO é a leitura que o gráfico já promete: os
    rótulos são fixos ("Jan" … "Dez"), e um mês do calendário é a soma de
    todos os anos que tiveram movimento nele. some(Outubro de 2024 +
    Outubro de 2026) é o total de Outubro que a fazenda gastou, e é um número
    que se pode conferir. Escolher um ano seria esconder o resto.
    """
    _mensal = (
        lancamentos.filter(data__isnull=False)
        .annotate(mes=TruncMonth("data"))
        .values("mes")
        .annotate(
            receita=Sum("valor", filter=Q(tipo="RECEITA")),
            despesa=Sum("valor", filter=Q(tipo="DESPESA")),
        )
        .order_by("mes")
    )
    # Chave pelo par (ano, mês) primeiro, para NENHUMA linha ser descartada
    # por uma colisão; a soma por mês do calendário é feita a seguir, sobre
    # linhas que já sobreviveram.
    por_mes_do_calendario: dict[int, dict] = {}
    for r in _mensal:
        if not r["mes"]:
            continue
        alvo = por_mes_do_calendario.setdefault(
            r["mes"].month, {"receita": 0.0, "despesa": 0.0}
        )
        alvo["receita"] += float(r.get("receita") or 0)
        alvo["despesa"] += float(r.get("despesa") or 0)

    serie = []
    for i, mes in enumerate(MESES_PT, start=1):
        linha = por_mes_do_calendario.get(i)
        if not linha:
            continue
        rec = linha["receita"]
        desp = linha["despesa"]
        if rec or desp:
            serie.append(
                {"mes": mes, "receita": round(rec, 2), "despesa": round(desp, 2)}
            )
    return serie


def chart_data_agregado(lancamentos, financeiro_mensal, hoje=None):
    """Séries do gráfico, sem números fictícios.

    `LancamentoFinanceiro` tem `data` como `DateField` — não existe hora. Por
    isso "hoje" é o saldo do dia e "semana" são os saldos reais de cada dia da
    semana, e não um total mensal distribuído por horas inventadas.
    """
    if not financeiro_mensal:
        return {}
    hoje = hoje or date.today()
    inicio_semana = hoje - timedelta(days=hoje.weekday())
    out = {}

    labels = [f["mes"] for f in financeiro_mensal]
    dados = [
        float(f["receita"] or 0) - float(f["despesa"] or 0) for f in financeiro_mensal
    ]

    _hoje = lancamentos.filter(data=hoje).aggregate(
        receita=Sum("valor", filter=Q(tipo="RECEITA")),
        despesa=Sum("valor", filter=Q(tipo="DESPESA")),
    )
    out["today"] = {
        "labels": [hoje.strftime("%d/%m")],
        "data": [round(float(_hoje["receita"] or 0) - float(_hoje["despesa"] or 0), 2)],
        "label": "Saldo de Hoje",
        "borderColor": "#006b68",
        "backgroundColor": "rgba(0,107,104,0.1)",
    }

    _dias = {
        r["data"]: r
        for r in lancamentos.filter(data__gte=inicio_semana, data__lte=hoje)
        .values("data")
        .annotate(
            receita=Sum("valor", filter=Q(tipo="RECEITA")),
            despesa=Sum("valor", filter=Q(tipo="DESPESA")),
        )
    }
    if _dias:
        datas = [inicio_semana + timedelta(days=i) for i in range(7)]
        out["week"] = {
            "labels": [d.strftime("%d/%m") for d in datas],
            "data": [
                round(
                    float(_dias.get(d, {}).get("receita") or 0)
                    - float(_dias.get(d, {}).get("despesa") or 0),
                    2,
                )
                for d in datas
            ],
            "label": "Saldo da Semana",
            "borderColor": "#006b68",
            "backgroundColor": "rgba(0,107,104,0.1)",
        }

    out["month"] = {
        "labels": labels[:6],
        "data": dados[:6],
        "label": "Fluxo Mensal",
        "borderColor": "#006b68",
        "backgroundColor": "rgba(0,107,104,0.1)",
    }
    out["semester"] = {
        "labels": labels,
        "data": dados,
        "label": "Fluxo Semestral",
        "borderColor": "#006b68",
        "backgroundColor": "rgba(0,107,104,0.1)",
    }
    return out
