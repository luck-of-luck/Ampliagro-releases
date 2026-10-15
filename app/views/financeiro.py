import json

from django import forms
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from app.hierarquia import hierarquia_required
from app.models import *
from app.services.custo_producao import calcular_custo_producao

from .utils import *


@login_required
@hierarquia_required("simulador-financeiro")
def simulador_financeiro_view(request):
    from app.models import Propriedade

    propriedades = Propriedade.objects.filter(user=request.user)
    return render(request, "simulador-financeiro.html", {"propriedades": propriedades})


@login_required
@hierarquia_required("simulador-colheita")
def simulador_colheita_view(request):
    from app.models import Propriedade

    propriedades = Propriedade.objects.filter(user=request.user)
    return render(request, "simulador-colheita.html", {"propriedades": propriedades})


@login_required
@hierarquia_required("simulador_lucro")
def simulador_lucro_view(request):
    """Simulador de lucro por talhão — requer login; pega talhões do usuário logado."""
    talhoes_qs = Talhao.objects.filter(propriedade__user=request.user).select_related(
        "propriedade", "cultura_atual"
    )

    talhoes_data = []
    for t in talhoes_qs:
        # `None`, não 380. Este valor estava HARDCODED: um talhão sem safra
        # registrada recebia "R$ 380/ha" — um número inventado que chegava ao
        # produtor como se fosse medido. É o mesmo defeito que
        # `custo_producao.py` tinha e que `user.py:190-208` já corrigiu.
        # Sem safra, não há custo por hectare: `None` é a resposta honesta.
        custo_ha = None
        # Buscar safra atual vinculada a este talhão (sem colheita = em andamento)
        safra = (
            Safra.objects.filter(talhoes=t, data_colheita__isnull=True)
            .order_by("-ano", "-data_plantio")
            .first()
        )
        if safra:
            resultado_custo = calcular_custo_producao(safra.id)
            # `custo_por_hectare` pode ser `None` quando a safra não tem área
            # registada — e `None > 0` levanta `TypeError` em Python 3. O `0`
            # do `get` só protegia a ausência da chave, não o valor nulo.
            custo_ha = resultado_custo.get("custo_por_hectare")

        talhoes_data.append(
            {
                "id": t.id,
                "nome": t.nome,
                "area_hectare": float(t.area_hectare),
                "propriedade": t.propriedade.nome if t.propriedade else "",
                "custo_ha": custo_ha,
            }
        )
    return render(request, "simulador-lucro.html", {"talhoes": talhoes_data})


@login_required
@hierarquia_required("dre-view")
def dre_view(request):
    """View do Demonstrativo de Resultado do Exercício"""
    prop = Propriedade.objects.filter(user=request.user).first()
    context = {"propriedade_id": prop.id if prop else None}
    return render(request, "financeiro/dre.html", context)


@login_required
@hierarquia_required("cashflow_view")
def cashflow_view(request):
    """View do Fluxo de Caixa Projetado"""
    prop = Propriedade.objects.filter(user=request.user).first()
    context = {"propriedade_id": prop.id if prop else None}
    return render(request, "financeiro/cashflow.html", context)


@login_required
@hierarquia_required("comparativo_safras_view")
def comparativo_safras_view(request):
    """View do Comparativo Safra vs Safra"""
    safras = (
        Safra.objects.filter(propriedade__user=request.user)
        .select_related("cultura", "talhao", "propriedade")
        .order_by("-ano")[:5]
    )
    # O template em disco chama-se comparativo-safras.html (hifen), nao
    # comparativo_safras.html. O nome errado estourava TemplateDoesNotExist.
    return render(request, "financeiro/comparativo-safras.html", {"safras": safras})


@login_required
def exportar_lcdpr_view(request):
    """
    Gera o arquivo TXT do Livro Caixa Digital do Produtor Rural (LCDPR)
    para download imediato.
    """
    import datetime

    from django.http import HttpResponse

    from app.services.lcdpr_export import LCDPRExporter

    propriedade_id = request.GET.get("propriedade_id")
    ano = request.GET.get("ano", datetime.date.today().year)

    if not propriedade_id:
        # Se não forneceu, pega a primeira
        propriedade = Propriedade.objects.filter(user=request.user).first()
    else:
        propriedade = Propriedade.objects.filter(
            user=request.user, id=propriedade_id
        ).first()

    if not propriedade:
        return HttpResponse(
            "Propriedade não encontrada ou você não tem acesso.", status=404
        )

    exporter = LCDPRExporter(propriedade, int(ano))
    conteudo_txt = exporter.gerar_arquivo()

    nome_arquivo = f"LCDPR_{propriedade.id}_{ano}.txt"
    response = HttpResponse(conteudo_txt, content_type="text/plain")
    response["Content-Disposition"] = f'attachment; filename="{nome_arquivo}"'
    return response
