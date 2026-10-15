"""Views LCDPR 1.3 — Páginas web que seguem o padrão visual do LCDPR."""

from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from app.hierarquia import pode_ver_financeiro, propriedades_financeiras
from app.services.lcdpr_export import (
    LCDPRDadosIncompletos,
    LCDPRExporter,
    diagnosticar_lcdpr,
    diagnosticar_consolidado,
    propriedades_do_contribuinte,
)
from app.services.lcdpr_http import responder_lcdpr


@login_required
@require_http_methods(["GET"])
def lcdpr_download_page(request):
    """Página web para download do LCDPR com interface visual LCDPR 1.3."""
    if not request.user.has_perm("financeiro.view_lcdpr"):
        return JsonResponse({"erro": "Sem permissão para acessar o LCDPR."}, status=403)

    propriedades = request.user.propriedades.all().order_by("nome")

    context = {
        "propriedades": propriedades,
        "ano_atual": timezone.localdate().year,
    }
    return render(request, "lcdpr/download.html", context)


@login_required
@require_http_methods(["GET"])
def lcdpr_diagnostico_page(request):
    """Página de diagnóstico do LCDPR com interface visual."""
    if not request.user.has_perm("financeiro.view_lcdpr"):
        return JsonResponse({"erro": "Sem permissão para acessar o LCDPR."}, status=403)

    propriedades = request.user.propriedades.all().order_by("nome")

    context = {
        "propriedades": propriedades,
        "ano_atual": timezone.localdate().year,
    }
    return render(request, "lcdpr/diagnostico.html", context)


@csrf_exempt
@login_required
@require_http_methods(["POST"])
def lcdpr_gerar_arquivo(request):
    """Endpoint para gerar o arquivo LCDPR via POST (formulário web)."""
    if not request.user.has_perm("financeiro.view_lcdpr"):
        return JsonResponse({"erro": "Sem permissão para gerar LCDPR."}, status=403)

    # Reutiliza a lógica do responder_lcdpr mas via POST
    from app.services.lcdpr_http import _responder
    from django.http import HttpRequest

    # Converte POST para GET-like para reutilizar _responder
    request.GET = request.POST
    return _responder(request, diagnostico=False)


@login_required
@require_http_methods(["GET"])
def lcdpr_diagnostico_api(request):
    """API de diagnóstico do LCDPR (reutiliza lcdpr_download com diagnostico=1)."""
    return responder_lcdpr(request, diagnostico=True)
