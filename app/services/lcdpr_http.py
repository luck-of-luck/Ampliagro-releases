"""Contrato HTTP compartilhado pelas saídas do LCDPR."""
from django.http import HttpResponse, JsonResponse
from django.utils import timezone

from app.hierarquia import pode_ver_financeiro, propriedades_financeiras
from app.services.lcdpr_export import LCDPRDadosIncompletos, LCDPRExporter, diagnosticar_lcdpr, diagnosticar_consolidado, propriedades_do_contribuinte


def responder_lcdpr(request, *, diagnostico=False):
    resposta = _responder(request, diagnostico=diagnostico)
    resposta["Cache-Control"] = "private, no-store"
    return resposta


def _responder(request, *, diagnostico):
    if request.method != "GET":
        resposta = JsonResponse({"erro": "Use GET para consultar ou baixar o LCDPR."}, status=405)
        resposta["Allow"] = "GET"
        return resposta
    if not pode_ver_financeiro(request.user):
        return JsonResponse({"erro": "Sem permissão para dados financeiros."}, status=403)
    params = request.GET
    escopo = params.get("escopo", "propriedade")
    if escopo not in ("propriedade", "contribuinte"):
        return JsonResponse({"erro": "Escopo fiscal inválido."}, status=400)
    try:
        ano = int(params.get("ano", timezone.localdate().year))
        if not 2019 <= ano <= 9998:
            raise ValueError
        identificadores = [int(params[nome]) for nome in ("propriedade", "propriedade_id") if nome in params]
        if identificadores and (min(identificadores) <= 0 or len(set(identificadores)) != 1):
            raise ValueError
    except (ValueError, TypeError):
        return JsonResponse({"erro": "Informe propriedade válida e ano entre 2019 e 9998."}, status=400)
    propriedades = propriedades_financeiras(request.user).order_by("pk")
    if identificadores:
        propriedade = propriedades.filter(pk=identificadores[0]).first()
    else:
        candidatas = list(propriedades[:2])
        if len(candidatas) > 1:
            return JsonResponse({"erro": "Selecione a propriedade para o LCDPR.", "campo": "propriedade"}, status=400)
        propriedade = candidatas[0] if candidatas else None
    if propriedade is None:
        return JsonResponse({"erro": "Propriedade não encontrada."}, status=404)
    conjunto = propriedades_do_contribuinte(propriedade, propriedades) if escopo == "contribuinte" else None
    def obter_diagnostico():
        return (diagnosticar_consolidado(propriedade, conjunto, ano) if conjunto is not None
                else diagnosticar_lcdpr(propriedade, ano))
    if diagnostico:
        return JsonResponse(obter_diagnostico())
    try:
        conteudo = LCDPRExporter(propriedade, ano, propriedades=conjunto).gerar_arquivo()
    except LCDPRDadosIncompletos as erro:
        return JsonResponse({"erro": str(erro), "diagnostico": obter_diagnostico()}, status=400)
    resposta = HttpResponse(conteudo, content_type="text/plain; charset=utf-8")
    sufixo = "_consolidado" if conjunto is not None else ""
    resposta["Content-Disposition"] = f'attachment; filename="LCDPR_{propriedade.pk}_{ano}{sufixo}.txt"'
    return resposta
