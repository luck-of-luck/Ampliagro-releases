"""Os números da mesa — reais, do banco, e tenancy-safe.

A REGRA ÚNICA DESTE MÓDULO
=========================
**Um número que não sai do banco não entra na mesa.** Nem zero, nem um
placeholder, nem um "-". Uma mesa com um card a menos é uma mesa menor; uma
mesa com um número inventado é uma mentira, e o produtor age em cima dela.

Esta regra é o oposto do `getWidgetDataFromAPI` do dashboard, que cai para
"R$ 450" e "28°C" quando não sabe. Esse fallback faz a tela parecer viva
enquanto mente, e é exactamente o que transformaria a IA numa brincadeira.

ONDE ESTES NÚMEROS VÊM
======================
`LancamentoFinanceiro` (DESPESA / RECEITA) e `Safra` (área, produção) — os
mesmos modelos que o resto do produto já usa. Nenhum número sai de um segundo
cálculo: é o mesmo que o produtor vê no dashboard dele, calculado do mesmo
lado do servidor.

O TENANCY, AQUI TAMBÉM
======================
Toda a agregação entra por `Propriedade.objects.filter(user=user)`. Uma mesa
de operação com a despesa do vizinho não é um erro de aspecto: é o defeito
que destrói a confiança no produto, e o produtor não tem como desconfiar de um
número que parece normal.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.db.models import Count, Sum
from django.db.models.functions import TruncYear

from app.ia.palco import CATALOGO_IA
from app.ia.proveniencia import Estado, Medido, serializar_tudo

#: Um `Decimal` straight para o JSON vira string, e um float arredonda dinheiro
#: a Errado. Duas casas na moeda estrita, uma na produção/ha.
CENTAVOS = Decimal("0.01")


#: Que campo de cada widget e' o NÚMERO, e qual e' dinheiro, e qual e' área.
#:
#: Vem do `_calcula` de cada tipo, e e' a unica fonte. Antes o frontend
#: adivinhavam pelo NOME da chave ("custo" e' dinheiro, "area" e' hectares) e o
#: `referencia_widgets` publicava um `campos: []` que nenhuma entrada do
#: catálogo preenchia — o dicionario que a IA lia prometia campos e nao
#: entregava nenhum, para os 17.
CAMPOS_POR_WIDGET: dict[str, tuple[str, ...]] = {
    "kpi-custo": ("custo_total", "custo_por_ha", "area_colhida"),
    "kpi-caixa": ("entradas", "saidas", "saldo"),
    "kpi-roi": ("receita_total", "custo_total", "roi"),
    "kpi-produtividade": ("producao_total", "area_colhida_periodo", "produtividade_ha"),
    "kpi-area": ("area_plantada", "area_colhida", "area_downtime"),
    "chart-safras": ("series",),
    "table-financeiro": ("linhas",),
    "kpi-alertas": ("criticos", "atencao", "informativos"),
}


def _n(valor: Any) -> float | None:
    """Decimal -> float para o JSON, ou None quando não há número.

    None e não 0: "sem dado" e "zero" são coisas diferentes, e confundi-las
    é como um produtor descobre que a fazenda está a render e o painel diz
    que está tudo a zeros.
    """
    if valor is None or valor == "":
        return None
    try:
        return float(valor)
    except (TypeError, ValueError):
        return None


def _soma(queryset, campo="valor"):
    """Soma de um aggregate, em None quando não há linhas."""
    agg = queryset.aggregate(total=Sum(campo))
    return _n(agg.get("total"))


def enriquece(user, widgets: list[dict], *, prop=None, talhao: str = "") -> list[dict]:
    """Devolve os widgets com `config` preenchido a partir do banco.

    Não levanta. Um widget cujo cálculo parte de um dado corrompido não pode
    impedir os outros de aparecerem — o mesmo princípio da varredura proativa:
    uma falha isolada não pode virar cessação silenciosa de tudo o resto.
    """
    try:
        from app.models import LancamentoFinanceiro, Propriedade, Safra
    except Exception:  # pragma: no cover - modelos indisponiveis
        return widgets

    base = _propriedades_do_usuario(user)
    if prop is not None:
        base = base.filter(pk=getattr(prop, "pk", prop))

    talhao_txt = str(talhao or "").strip().lower()
    safras = Safra.objects.filter(propriedade__in=base)
    if talhao_txt:
        safras = safras.filter(talhao__nome__icontains=talhao_txt)

    financeiro = LancamentoFinanceiro.objects.filter(propriedade__in=base)
    if talhao_txt:
        financeiro = financeiro.filter(talhao__nome__icontains=talhao_txt)

    despesas = financeiro.filter(tipo="DESPESA")
    receitas = financeiro.filter(tipo="RECEITA")

    for w in widgets:
        tipo = w.get("tipo")
        # SÓ os widgets de SERVIDOR são preenchidos aqui.
        #
        # Um widget `top_globais` já chega com o valor que o cliente buscou no
        # endpoint dele. Sobrescrever isso com `_calcula` — que para eles cai
        # no `return {}` do fim — apagava o número e deixava um cartão vazio
        # sem qualquer aviso. Hoje nenhum MODELOS cita um simulado, o que
        # tornava o problema LATENTE; no dia em que um citasse, o valor
        # desaparecia em silêncio.
        #
        # Um módulo que mexe no que outro módulo respondeu é um módulo que
        # mente por omissão. Este só toca no que é dele.
        if tipo not in CATALOGO_IA or CATALOGO_IA[tipo].get("fonte") != "servidor":
            continue
        try:
            cru = _calcula(
                tipo, user, safras, despesas, receitas, financeiro, talhao_txt
            )
            # O número entra no mundo aqui, e entra embrulhado. `_calcula`
            # devolve crus porque a aritmética não tem nada a ver com
            # proveniência; a honestidade é posta no bordo.
            w["config"] = _proveniencia(
                tipo, cru, _nome_da_propriedade(prop or _unica_propriedade(user))
            )
        except Exception:  # noqa: BLE001
            # Card sem número é melhor do que card com número errado, e melhor
            # ainda do produtor não ver a mesa nenhuma.
            w["config"] = {"fonte_dado": "sem_dado", "motivo": "Falha ao calcular."}
    return widgets


def _nome_da_propriedade(prop) -> str:
    """O nome, para a fonte ser auditável por uma pessoa.

    A pergunta que a fonte tem de responder é "isto foi lido de onde?", e um
    id não responde — ninguém sabe a que fazenda o `18` corresponde dentro de
    seis meses.
    """
    if prop is None:
        return ""
    nome = getattr(prop, "nome", "")
    return str(nome or f"propriedade {getattr(prop, 'pk', '?')}")


def _propriedades_do_usuario(user):
    """As propriedades que o utilizador PODE ver — a mesma do resto do sistema.

    O O QUÊ
    =======
    Este módulo usava `Propriedade.objects.filter(user=user)`, e o próprio
    cabeçalho do ficheiro afirmava ser "tenancy-safe". Não era: `user` é
    apenas o DONO, e um servidor ou um funcionário não é dono — é
    ACESSOR. A propriedade dele entra por `PerfilUsuario.propriedade_vinculada`
    ou por `Funcionario.propriedade`.

    O defeito, verificado no ambiente real com o servidor `mecanico.demo`
    (vinculado à Fazenda Modelo, id 14):

        propriedades_visiveis(servidor)  -> [(14, 'Fazenda Modelo')]   ✅
        o_que_existe(servidor)           -> tudo False               ❌
        kpi-caixa(servidor)              -> sem_dado                 ❌

    Um técnico que vê a fazenda no resto do sistema — e que a propósito foi
    ligado a ela — via um painel vazio, sem um aviso. A tela dizia "sem
    dado" com a mesma cara com que diria "não há lançamentos", e as duas
    coisas são mentira: havia lançamentos, e ele tinha permissão para os ver.

    Por que `propriedades_visiveis` e não um `user__in=[...]` próprio
    ====================================================================
    Porque `app/hierarquia.py::propriedades_visiveis` é a consulta que o
    resto da hierarquia de permissões já usa. Duas fontes de verdade para
    "o que esta pessoa vê" é exactamente o que produz divergência: a
    hierarquia ganha um caminho novo, este fica desatualizado, e a falha é
    silenciosa porque os dois devolvem "sem dados" com a mesma forma.
    """
    from app.hierarquia import propriedades_visiveis

    return propriedades_visiveis(user)


def _area_dos_talhoes(safras_do_ano) -> float | None:
    """Soma da área dos talhões em que as safras desse ano estão plantadas.

    Serve para CONFERIR a soma das safras, não para a substituir. As duas
    medidas são do mesmo terreno e vêm de cadastros diferentes; quando
    divergem, uma está errada, e a pergunta é qual — e isso é trabalho de
    quem conhece a fazenda, não uma conta.

    Devolve `None` quando nenhuma das safras tem talhão ligado: uma safra sem
    talhão não tem contra-o-que conferir, e devolver 0 diria "a área dos
    talhões é zero", que é uma afirmação.
    """
    from app.models import Talhao

    ids = {s.talhao_id for s in safras_do_ano if getattr(s, "talhao_id", None)}
    if not ids:
        return None
    total = 0.0
    for area in Talhao.objects.filter(id__in=ids).values_list(
        "area_hectare", flat=True
    ):
        total += float(area or 0)
    return total or None


def _calcula(tipo, user, safras, despesas, receitas, financeiro, talhao_txt) -> dict:
    if tipo == "kpi-custo":
        # O DENOMINADOR É A ÁREA DA SAFRA, E A DESPESA É DO MESMO PERÍODO
        # =================================================================
        # A conta antiga era `_soma(despesas) / _soma(safras, "area_colhida")`:
        # o numerador eram TODOS os lançamentos de todos os anos, e o
        # denominador a área colhida de todos os anos também. Verificado na
        # Fazenda Modelo: R$ 420.000 de despesa (de 2024, uma única nota de
        # insumo) divididos por 2.381,94 ha de área colhida de 2024+2025+2026
        # davam R$ 176,33/ha — enquanto `/api/dashboard` dizia R$ 338,71/ha
        # para a MESMA propriedade no MESMO dia.
        #
        # Dois ecrãs com dois números para o mesmo dado não é "duas fontes
        # legítimas": é uma delas errada, e o produtor não tem como saber
        # qual. A conta tem de responder a uma pergunta — "quanto custa
        # produzir por hectare?" — e essa pergunta tem um período.
        #
        # Duas medidas são possíveis, e são coisas diferentes:
        #
        #  * `custo_por_ha_colhida` — despesa do ano ÷ área COLHIDA desse ano.
        #    É o custo real de quem colheu, e é o que interessa a quem já
        #    vendeu.
        #  * `custo_por_ha_plantada` — despesa do ano ÷ área PLANTADA desse
        #    ano. É o custo de quem investiu, e é o que interessa a quem
        #    ainda vai colher.
        #
        # As duas saem, com o nome a dizer qual é qual. Um número só sem
        # nome é o defeito outra vez: "R$ 176/ha" e "R$ 338/ha" são ambos
        # verdadeiros em Measurements diferentes, e quem lê não sabe qual
        # está a ver.
        #
        # E o período vai NO CARTÃO, pelo mesmo motivo: um custo por hectare
        # sem o ano a que se refere é um número que não pode ser conferido
        # contra nada.
        custo_total = _soma(despesas)
        if custo_total is None:
            return {}

        # A despesa por ano. `TruncYear` devolve uma DATA (1 de janeiro do
        # ano), e não o número do ano — e comparar `date(2026,1,1)` com `2026`
        # dá sempre falso, que é o que fazia o cartão cair no total geral.
        # A chave é o `.year` da data truncada.
        custo_por_ano = {
            r["ano"].year: float(r["total"] or 0)
            for r in despesas.filter(data__isnull=False)
            .annotate(ano=TruncYear("data"))
            .values("ano")
            .annotate(total=Sum("valor"))
            if r["ano"]
        }

        ano_ref = (
            safras.exclude(ano=None)
            .order_by("-ano")
            .values_list("ano", flat=True)
            .first()
        )
        do_ano = safras.filter(ano=ano_ref) if ano_ref is not None else safras.none()

        colhida = _soma(do_ano, "area_colhida")
        plantada = _soma(do_ano, "area_plantada")
        custo_ano = custo_por_ano.get(ano_ref) if ano_ref is not None else None
        if custo_ano is None:
            # Sem despesa datada no ano da safra, o total continua a ser a
            # verdade — mas o cartão tem de dizer que não conseguiu casar os
            # dois, em vez de apresentar uma divisão que não é de nenhum ano.
            custo_ano = custo_total

        return {
            "custo_total": custo_total,
            "custo_por_ha": _ratio(custo_ano, colhida),
            "custo_por_ha_colhida": _ratio(custo_ano, colhida),
            "custo_por_ha_plantada": _ratio(custo_ano, plantada),
            "area_colhida": colhida,
            "area_plantada": plantada,
            "custo_do_ano": custo_ano,
            # O ano a que a despesa pertence. Sem ele, o número não pode ser
            # conferido contra o lançamento que o originou.
            "ano": ano_ref,
            "periodo": (
                f"despesa de {ano_ref} sobre a safra de {ano_ref}"
                if ano_ref is not None
                else "tudo o que está registado"
            ),
        }

    if tipo == "kpi-caixa":
        entradas = _soma(receitas)
        saidas = _soma(despesas)
        if entradas is None and saidas is None:
            return {}
        return {
            "entradas": entradas,
            "saidas": saidas,
            "saldo": _diferenca(entradas, saidas),
        }

    if tipo == "kpi-roi":
        receita = _soma(receitas)
        custo = _soma(despesas)
        if not custo:
            # Sem despesa o ROI é infinito, e um "infinito" numa tela é pior
            # que uma ausência. O produtor não precisa de ROI na safra em que
            # não gastou nada.
            return {"receita_total": receita} if receita is not None else {}
        return {
            "receita_total": receita,
            "custo_total": custo,
            "roi_pct": _ratio(_diferenca(receita, custo), custo, vezes=100),
        }

    if tipo == "kpi-produtividade":
        # Aqui a ÁREA SOMA-SE, e é a soma que está certa.
        #
        # Contrasta com o `kpi-area`, onde a soma estava errada. A diferença
        # é o que se está a medir: aqui é produção POR hectare ao longo de
        # vários anos, e (soma das produções) ÷ (soma das áreas) é a média
        # ponderada correcta. Somar 62.000 + 58.000 kg e dividir por 228 + 228
        # hectares dá a produtividade média de quem colheu, que é uma pergunta
        # com resposta.
        #
        # Em `kpi-area` a pergunta é outra — "quanto terreno tenho?" — e
        # responder 630 ha a alguém com 210 ha é apenas errado.
        #
        # O mesmo nome de campo nos dois widgets, com significados diferentes,
        # é a incoerência que o produtor não tem como resolver: vê "228 ha" no
        # cartão de área e "456 ha" no de produtividade, e nenhum dos dois
        # lies — mas nenhum dos dois explica-se.
        producao = _soma(safras, "producao_total")
        area = _soma(safras, "area_colhida")
        if producao is None and area is None:
            return {}
        anos = list(
            safras.exclude(area_colhida=None)
            .exclude(area_colhida=0)
            .values_list("ano", flat=True)
            .distinct()
            .order_by("ano")
        )
        return {
            "producao_total": producao,
            # O nome diz o que é: área SOMADA no período, não a área da
            # fazenda. `area_colhida` aqui e `area_colhida` no `kpi-area` são
            # coisas diferentes, e dizer isso no nome é o que impede o produtor
            # de os ler como o mesmo número.
            "area_colhida_periodo": area,
            "produtividade_ha": _ratio(producao, area),
            "anos": anos,
            "anos_contagem": len(anos),
        }

    if tipo == "kpi-area":
        # A ÁREA NÃO SE SOMA ENTRE ANOS.
        #
        # `_soma(safras, "area_plantada")` somava a área de TODAS as safras. Um
        # produtor com 210 ha de café e três anos registados via 630 ha
        # plantados — e `area_downtime` passava a ser uma métrica inventada
        # (630 − 456 = 174 ha "em downtime") que não existe em lado nenhum.
        #
        # Terreno não se acumula: a mesma terra, três vezes, é a mesma terra.
        # A área de uma safra é a área DAQUELE ano, e a do produtor é a
        # superfície, não a soma das superfícies que ele usou.
        #
        # Isto só aparece com mais de uma safra. Um teste com um ano só passa,
        # e é por isso que só uma persona com histórico real o apanha.
        #
        # A produção, ao contrário, SOMA-SE: 62.000 + 58.500 são 120.500
        # colheitas colhidas em dois anos. Por isso a área não e a produção
        # levam tratamento diferente — e por isso as duas somas não podem
        # estar na mesma linha de código a céu aberto.
        #
        # `.order_by("-ano").first()` era a terceira via, e a pior das três: não
        # somava o ano, devolvia UMA linha. O `.first()` sem desempate deixa o
        # SQLite escolher, e a escolha muda com o plano de execução — o mesmo
        # cartão respondia 45.000 ha por um caminho do código e 180 ha por
        # outro, no mesmo banco e para o mesmo produtor. E o que devolvia não
        # era "a área da fazenda": era a área de um talhão qualquer.
        #
        # A área de um ano é a SOMA das safras desse ano. E o ano é o mais
        # recente que existe. `Safra.ano` é `IntegerField()` sem `null=True`, o
        # que o torna NOT NULL no banco: não há ano em branco para ordenar.
        ano = safras.order_by("-ano").values_list("ano", flat=True).first()
        if ano is None:
            return {}
        do_ano = safras.filter(ano=ano)
        safras_do_ano = list(do_ano)
        if not safras_do_ano:
            return {}
        plantada = _soma(do_ano, "area_plantada")
        colhida = _soma(do_ano, "area_colhida")
        if plantada is None and colhida is None:
            return {}
        downtime = (
            round(max(0.0, plantada - colhida), 2)
            if plantada is not None and colhida is not None
            else None
        )
        # A área dos TALHÕES é OUTRA medida do mesmo terreno. Quando não bate
        # com a soma das safras, uma das duas está errada — e o produtor não
        # tem como saber qual. Sem esta conferência, "1.636 ha" e "3.047 ha"
        # viviam lado a lado em ecrãs diferentes sem que ninguém notasse.
        #
        # O critério é 5% (e nunca menos que 1 ha): abaixo disso é arredondamento
        # de centésimos, acima disso são dois cadastros que não falam a mesma
        # língua. A fazenda modelo tem 1.240 ha declaradas e 3.132 ha de
        # talhões — nem 5% nem 50%: a divergência que este cartão tem de
        # gritar é a que ninguém está a ver.
        area_talhoes = _area_dos_talhoes(do_ano)
        divergencia = None
        if area_talhoes and plantada:
            dif = area_talhoes - plantada
            if abs(dif) > max(1.0, 0.05 * plantada):
                divergencia = {
                    "area_safras": round(plantada, 2),
                    "area_talhoes": round(area_talhoes, 2),
                    "diferenca_ha": round(dif, 2),
                    "aviso": (
                        f"A soma das safras de {ano} dá {plantada:,.2f} ha e a "
                        f"área dos talhões dá {area_talhoes:,.2f} ha. Uma das "
                        "duas está errada — reveja o cadastro das safras e "
                        "dos talhões."
                    ),
                }
        return {
            "area_plantada": plantada,
            "area_colhida": colhida,
            "area_downtime": downtime,
            # De que safra é este número. Sem o ano, "210 ha" não quer dizer
            # nada: pode ser a área deste ano, ou a de há três, e o produtor
            # não tem como saber qual está a ler.
            "ano": ano,
            # Quantas safras entraram na soma. Um total sem a contagem não é
            # auditável: "1.636 ha" de uma safra ou de dez são coisas muito
            # diferentes para quem vai conferir, e uma safra com área a zero
            # que fica de fora do total tem de ser visível como linha, não
            # como silêncio.
            "safras_no_ano": len(safras_do_ano),
            "safras_sem_area": sum(
                1
                for s in safras_do_ano
                if not float(getattr(s, "area_plantada", 0) or 0)
            ),
            "area_talhoes": round(area_talhoes, 2) if area_talhoes else None,
            "divergencia_area": divergencia,
        }

    if tipo == "chart-safras":
        linhas = (
            safras.values("ano")
            .annotate(producao=Sum("producao_total"), area=Sum("area_colhida"))
            .order_by("ano")
        )
        serie = [
            {
                "ano": l["ano"],
                "producao": _n(l["producao"]),
                "area": _n(l["area"]),
                "produtividade": _ratio(_n(l["producao"]), _n(l["area"])),
            }
            for l in linhas
            if l["ano"] is not None
        ]
        if not serie:
            return {}
        return {"periodo": "ano", "series": serie}

    if tipo == "table-financeiro":
        linhas = (
            financeiro.values("categoria", "tipo")
            .annotate(n=Count("id"), total=Sum("valor"))
            .order_by("-total")
        )
        tabela = [
            {
                "categoria": l["categoria"] or "(sem categoria)",
                "tipo": l["tipo"],
                "lancamentos": l["n"],
                "total": _n(l["total"]),
            }
            for l in linhas[:12]
        ]
        if not tabela:
            return {}
        return {
            "colunas": ["categoria", "tipo", "lancamentos", "total"],
            "linhas": tabela,
        }

    if tipo == "kpi-alertas":
        # CONTAGEM POR SEVERIDADE, e nao "quantos tem no total".
        #
        # O total não diz ao produtor o que fazer. "Tem 4 alertas" e uma frase
        # que obriga a ir ver; "2 criticos, 1 atenção, 1 informativo" diz que
        # dois estão a queimar. E a severidade é o que o desenho original
        # previa — o frontend já tem os rótulos prontos para os três.
        #
        # Isto estavaPartido desde que nasceu: pedia um `dict` a uma função que
        # devolve um `int`, e `isinstance(3, dict)` é False para sempre. Um
        # `isinstance` que nunca é verdade não avisa — devolve o caminho vazio,
        # e um caminho vazio parece uma conta sem alertas.
        try:
            from app.models import IAAlertaProativo

            qs = IAAlertaProativo.objects.filter(user=user, estado="novo")
            if not qs.exists():
                return {}
            return {
                "criticos": qs.filter(nivel=0).count(),
                "atencao": qs.filter(nivel=1).count(),
                "informativos": qs.filter(nivel=2).count(),
            }
        except Exception:  # noqa: BLE001
            # O modelo pode não existir numa instalação mais magra. Um cartão
            # a menos é melhor do que a mesa inteira a cair.
            return {}

    # Widget sem cálculo próprio: fica vazio, e a tela diz que não há dado.
    return {}


def _ratio(numerador, denominador, *, vezes: float = 1.0):
    """Divisão que não mente.

    Devolve None quando o denominador é zero ou falta. Um `0` aqui seria lido
    como "a produtividade é zero", que é uma afirmação; None é "não há como
    saber", que é a verdade.
    """
    if numerador is None or denominador in (None, 0):
        return None
    return round(numerador / denominador * vezes, 2)


def _diferenca(a, b):
    if a is None and b is None:
        return None
    return round((a or 0) - (b or 0), 2)


#: De ONDE vem o número de cada widget, por nome de modelo e não por URL.
#:
#: A fonte tem de responder a "isto foi lido de onde?" dentro de seis meses,
#: quando já ninguém se lembra. "api" não responde. "LancamentoFinanceiro da
#: propriedade Sítio Santa Clara" responde, e é auditável.
FONTE_POR_WIDGET: dict[str, str] = {
    "kpi-custo": "LancamentoFinanceiro",
    "kpi-caixa": "LancamentoFinanceiro",
    "kpi-roi": "LancamentoFinanceiro",
    "table-financeiro": "LancamentoFinanceiro",
    "kpi-produtividade": "Safra",
    "kpi-area": "Safra",
    "chart-safras": "Safra",
    "kpi-alertas": "IAAlertaProativo",
}

#: Campos que são METADADOS, não medidas. A somar as áreas de dois anos dá
#: uma média por hectare que é uma resposta certa; a área da fazenda não é
#: essa, e somá-la dá 630 ha a quem tem 210. O mesmo nome de campo nos dois
#: widgets, com sentidos diferentes, é o que o produtor não consegue resolver
#: quando olha para os dois cartões lado a lado.
_NAO_E_MEDIDA = {
    "periodo",
    "ano",
    "anos",
    "anos_contagem",
    "colunas",
    "series",
    "linhas",
}


def _proveniencia(tipo: str, config: dict, prop_nome: str) -> dict:
    """Passa um config cru pelos embrulhos, e devolve o mesmo formato.

    O formato do JSON não muda — é o `{custo_por_ha: 418.57, fonte_dado:
    "medido"}` que o frontend já sabe ler. O que muda é o caminho: um número
    só chega aqui embrulhado, e o embrulho não tem forma de existir sem a
    fonte.

    `_calcula` continua a devolver números crus porque a aritmética não tem
    nada a ver com proveniência, e embrulhar cada `return` seria transformar
    contas honestas em código verboso. A honestidade é posta no BORDE, onde
    o número entra no mundo — e o teste `tests_proveniencia_tipo.py` mede
    se o caminho todo o respeita.
    """
    fonte_base = FONTE_POR_WIDGET.get(tipo, "consulta ao banco")
    fonte = f"{fonte_base} de {prop_nome}" if prop_nome else fonte_base

    embrulhos: dict[str, Any] = {}
    for chave, valor in config.items():
        if chave in _NAO_E_MEDIDA:
            # sai tal e qual: é rótulo, lista ou ano, e embrulhar um `ano`
            # em `Medido` seria a mesma mentira de embrulhar o que não é
            # medida.
            #
            # RECONSTRUÍDO, não descripto. A palavra original estava
            # corrompida (CJK) e não há forma de a recuperar. "mentira" é a
            # palavra do próprio projecto para isto — "aqui o vazio enche-se
            # de mentira" — e a frase fica correcta com ela. Se alguém
            # lembrar a original, é trocar uma palavra e nada mais.
            embrulhos[chave] = valor
        elif isinstance(valor, (int, float, Decimal)) and not isinstance(valor, bool):
            embrulhos[chave] = Medido(valor, fonte)
        else:
            embrulhos[chave] = valor

    saida = serializar_tudo(embrulhos)
    # Um widget que não tem NENHUM número não é "medido": é uma tela vazia, e
    # tem de dizer isso.
    #
    # E a pergunta tem de olhar PARA DENTRO das listas. Um `chart-safras` com
    # cinco anos de produção tem uma lista de séries no topo e zero números ao
    # nível do config — e a primeira versão deste código declarava-o
    # `sem_dado` com as séries cheias na tela. Um gráfico com dados que diz
    # "sem dado" é a pior das duas metades: o produtor vê a curva e a legenda
    # a dizer que não há nada.
    if _tem_medicao(config):
        saida["fonte_dado"] = Estado.MEDIDO
        # A fonte escreve-se ao nível do CONFIG, e não por chave.
        #
        # Um `chart-safras` tem uma lista de séries e zero números no topo: os
        # números estão dentro dos dicionários da lista, e cada um já foi
        # embrulhado com a sua fonte. Sem esta linha, o config fica `medido`
        # e sem `fonte` — que é o que o frontend lê, e é um número que
        # ninguém sabe de onde veio.
        saida["fonte"] = fonte
    else:
        saida["fonte_dado"] = Estado.SEM_DADO
        saida.pop("fonte", None)
        saida.setdefault("motivo", "Nenhuma medição disponível para este dado.")
    return saida


def _tem_medicao(valor) -> bool:
    """Há algum número medido, a qualquer profundidade?"""
    if isinstance(valor, bool):
        return False
    if isinstance(valor, (int, float, Decimal)):
        return True
    if isinstance(valor, (list, tuple)):
        return any(_tem_medicao(v) for v in valor)
    if isinstance(valor, dict):
        return any(_tem_medicao(v) for v in valor.values())
    return False


def _unica_propriedade(user):
    """A propriedade do produtor, quando a tela nao passou uma.

    A fonte de um numero tem de responder a "isto foi lido de onde?". Um nome
    de modelo responde a parte -- `LancamentoFinanceiro` -- mas nao diz de
    QUEM. Num sistema com mil produtores, "LancamentoFinanceiro" e' tao
    inutil como "a API": sao as contas de toda a gente.

    Com varias propriedades nao se inventa uma: devolve `None` e a fonte fica
    pelo modelo, que e' o que se sabe de facto. Inventar um nome seria
    fabricar proveniencia -- exactamente o que este modulo existe para
    impedir.

    A consulta e' `propriedades_visiveis`, e nao `filter(user=user)`: um
    servidor tem uma unica propriedade visivel — a que lhe linkedaram — e
    sem esta correccao a fonte do numero dele ficava sem nome, que e' a
    unica informacao que o produtor tem para desconfiar do numero.
    """
    qs = _propriedades_do_usuario(user)
    return qs.first() if qs.count() == 1 else None
