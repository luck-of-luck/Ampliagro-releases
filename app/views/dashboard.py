import json

from django import forms
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.text import slugify
from django.views.decorators.http import require_POST

from app.hierarquia import hierarquia_required
from app.models import *
from app.models.core import Cultura
from app.models.producao import RegistroProducao
from app.models.safra import Safra

from .utils import *


def culturas_do_produtor(user):
    """Slugs das culturas que ESTE produtor tem, e so as dele.

    O preset de entrada traz widgets de cultura por nome
    (`cultura-arroz_mercado_produtividade_grafico`). Para quem não planta
    arroz, esse widget não tem nada a mostrar — e o rótulo mente sobre o
    que a pessoa cultiva. Para o decidir, o template precisa de saber as
    culturas do produtor, não o catálogo inteiro.

    O catálogo (`Cultura.objects.all()`, ~700 entradas) é o mesmo para toda
    a gente e serve para o selector. Confundir as duas coisas é como um
    produtor de café acordou com um dashboard de arroz.
    """
    if not user or not user.is_authenticated:
        return []
    nomes = set()
    nomes.update(
        Safra.objects.filter(propriedade__user=user)
        .values_list("cultura__nome", flat=True)
        .distinct()
    )
    nomes.update(
        RegistroProducao.objects.filter(user=user)
        .values_list("cultura__nome", flat=True)
        .distinct()
    )
    return sorted({slugify(n) for n in nomes if n})


def _contexto_presets():
    """As duas listas de presets que o index.html consome.

    `PRESET_BLOCK_JSON` estava a ser usado pelo template e NUNCA era injetado:
    caía no `|default:"[]"` e o frontend trabalhava com uma blocklist vazia,
    enquanto o servidor limpava a lista verdadeira. Duas verdades, e a do
    navegador errada. `PRESET_SISTEMA_JSON` fecha o mesmo buraco para os presets
    de sistema — sem ele o `base-ia` é apagado como intruso no primeiro save.
    """
    from app.presets import PRESET_BASE_IA, PRESET_BLOCK, PRESETS_SISTEMA

    return {
        "PRESET_BLOCK_JSON": json.dumps(sorted(PRESET_BLOCK)),
        "PRESET_SISTEMA_JSON": json.dumps(sorted(PRESETS_SISTEMA)),
        "PRESET_BASE_IA": PRESET_BASE_IA,
    }


def index_view(request):
    """Renderiza a página principal da SPA com o novo navbar (acesso liberado)"""
    context = _contexto_presets()
    culturas = Cultura.objects.all()
    if culturas.exists():
        context["culturas"] = culturas
    context["culturas_do_produtor"] = json.dumps(culturas_do_produtor(request.user))
    response = render(request, "index.html", context)
    response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response["Pragma"] = "no-cache"
    return response


# Mesma tela, mas com sessao obrigatoria.
#
# `index_view` e' a entrada e fica aberta de proposito ("acesso liberado"): e' a
# porta de entrada do produto, e quem a ve anonimo ainda tem de se cadastrar.
#
# As OUTRAS 16 rotas da SPA (agenda, estoque, vendas, financeiro, perfil,
# gestao...) apontam para a MESMA view, e portanto serviam a casca completa do
# painel do produtor para qualquer visitante — inclusive com o link "Sair" na
# barra. Nenhum dado vazava (as APIs respondem 403 sem sessao), mas o visitante
# via um painel vazio sem explicacao e sem unico caminho de entrada, e o link de
# "Sair" nao levava a lugar nenhum, porque ja estava deslogado.
#
# Aqui a casca e' a mesma e a sessao e' exigida. A distincao fica onde se
# entende: o que e' entrada publica continua publico, o que e' aplicacao exige
# entrar.
spa_view = login_required(index_view)


@login_required
@hierarquia_required("dashboard-os")
def dashboard_os_view(request):
    from app.hierarquia import get_propriedade_optimizada
    from app.models import Propriedade

    prop = get_propriedade_optimizada(request.user)
    propriedades = Propriedade.objects.filter(user=request.user)
    # maquinários para OS (placeholder — modelo OS ainda não existe, mas passa propriedades)
    maquinarios = Maquinario.objects.filter(
        propriedade__user=request.user
    ).select_related("propriedade")[:20]
    return render(
        request,
        "dashboard-os.html",
        {"propriedades": propriedades, "propriedade": prop, "maquinarios": maquinarios},
    )


@login_required
@hierarquia_required("resumo-gerencial")
def resumo_gerencial_view(request):
    """Resumo gerencial — cards + 3 graficos, todos com dado REAL.

    Antes os graficos nao tinham o que receber: a view passava
    receita_total/despesa_total/lucro_liquido e o template lia
    receitas_meses/despesas_meses/meses_labels (inexistentes -> sempre "[]",
    barras vazias) e o doughnut de custos tinha [30,25,15,10,20] hardcoded,
    ou seja, um grafico de mentira. Alem disso o card "Despesas" lia
    `despesas` (a view passa `despesa_total`) e o card "ROI" lia `roi`, que
    nunca foi calculado. Todos os quatro foram corrigidos aqui.
    """
    from datetime import date

    from django.db.models import Q, Sum

    from app.models import LancamentoFinanceiro

    lancamentos = LancamentoFinanceiro.objects.filter(propriedade__user=request.user)

    # Serie de 12 meses (12-month rolling) terminada no mes corrente. Agrega por
    # (ano, mes) e preenche meses sem lancamento com 0 — sem isso o grafico pula
    # meses e a serie fica desalinhada com os labels.
    hoje = date.today()
    ano_ref, mes_ref = hoje.year, hoje.month
    inicio = date(ano_ref - 1, mes_ref, 1)  # 12 meses atras, mesmo dia 1
    # cards e graficos usam a MESMA janela: misturar card de vida toda com
    # grafico de 12 meses na mesma tela era parte da confusao original
    janela = lancamentos.filter(data__gte=inicio)
    agg = janela.aggregate(
        receita=Sum("valor", filter=Q(tipo="RECEITA")),
        despesa=Sum("valor", filter=Q(tipo="DESPESA")),
    )
    receita_total = agg["receita"] or 0
    despesa_total = agg["despesa"] or 0
    lucro_liquido = receita_total - despesa_total

    serie = janela.values("data__year", "data__month").annotate(
        receita=Sum("valor", filter=Q(tipo="RECEITA")),
        despesa=Sum("valor", filter=Q(tipo="DESPESA")),
    )
    por_mes = {(r["data__year"], r["data__month"]): r for r in serie}

    # 12 meses DO MAIS ANTIGO para o mais recente, terminando no mes corrente.
    # (Andar para tras a partir de (ano-1, mes+1) daria set/25..out/24 —
    #  invertia o periodo e o grafico mostrava o ano errado.)
    meses = []
    a, m = ano_ref, mes_ref
    for _ in range(12):
        meses.append((a, m))
        m -= 1
        if m == 0:
            a -= 1
            m = 12
    meses.reverse()

    CURTOS = [
        "",
        "jan",
        "fev",
        "mar",
        "abr",
        "mai",
        "jun",
        "jul",
        "ago",
        "set",
        "out",
        "nov",
        "dez",
    ]
    meses_labels = []
    receitas_meses = []
    despesas_meses = []
    for a, m in meses:
        meses_labels.append(f"{CURTOS[m]}/{str(a)[2:]}")
        linha = por_mes.get((a, m))
        receitas_meses.append(float(linha["receita"] or 0) if linha else 0.0)
        despesas_meses.append(float(linha["despesa"] or 0) if linha else 0.0)

    # Distribuicao de custos: soma real das DESPESAS por categoria (era fake).
    por_categoria = (
        lancamentos.filter(tipo="DESPESA", data__gte=inicio)
        .values("categoria")
        .annotate(total=Sum("valor"))
        .order_by("-total")
    )
    custos_labels = []
    custos_valores = []
    for linha in por_categoria:
        rotulo = dict(LancamentoFinanceiro._meta.get_field("categoria").choices).get(
            linha["categoria"], linha["categoria"] or "Sem categoria"
        )
        custos_labels.append(rotulo)
        custos_valores.append(float(linha["total"] or 0))

    # ROI: lucro sobre receita. Sem receita nao ha razao — None, e o template
    # mostra "—" em vez de um 0% inventado.
    roi = None
    if receita_total:
        roi = round(float(lucro_liquido) / float(receita_total) * 100, 1)

    return render(
        request,
        "resumo-gerencial.html",
        {
            "receita_total": float(receita_total),
            "despesa_total": float(despesa_total),
            "lucro_liquido": float(lucro_liquido),
            "roi": roi,
            "receitas_meses": receitas_meses,
            "despesas_meses": despesas_meses,
            "meses_labels": meses_labels,
            "custos_labels": custos_labels,
            "custos_valores": custos_valores,
            "tem_serie": any(receitas_meses) or any(despesas_meses),
            "tem_custos": bool(custos_valores),
            "periodo_meses": 12,
            "ultimos_lancamentos": lancamentos.select_related(
                "propriedade", "talhao", "safra"
            ).order_by("-data")[:10],
            "propriedades": Propriedade.objects.filter(user=request.user),
        },
    )


# pitch_view foi removido daqui: existiam DUAS definições (dashboard.py e
# views_pitch.py) e app/urls.py importava as duas — a última vencia (F811).
# O canônico passa a ser app.views_pitch.pitch_view.
