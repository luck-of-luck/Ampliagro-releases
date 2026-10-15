"""Rotina integrada de documentos, pagamentos e revisão fiscal."""

from datetime import date
from urllib.parse import urlencode

from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.http import HttpResponseBadRequest, HttpResponseForbidden
from django.shortcuts import get_object_or_404, render, redirect
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods
from app.forms_fiscal import ContribuinteFiscalForm, ContadorFiscalForm, ContrapartesFiscalFormSet, RevisaoLancamentoFiscalForm

from app.hierarquia import pode_ver_financeiro, propriedades_financeiras
from app.forms_importacao import ImportacaoFinanceiraCSVForm
from app.services.importacao_financeira import importar_lancamentos_csv
from app.models import ContaBancaria, LancamentoFinanceiro, NotaFiscalImportada
from app.services.integracoes_agro import catalogo_integracoes
from app.services.lcdpr_export import diagnosticar_lcdpr, diagnosticar_consolidado, propriedades_do_contribuinte


@login_required
@never_cache
@require_http_methods(["GET", "POST"])
def central_gestao(request):
    if not pode_ver_financeiro(request.user):
        return HttpResponseForbidden("Sem permissão para dados financeiros.", content_type="text/plain")
    escopo = request.GET.get("escopo", "propriedade")
    if escopo not in ("propriedade", "contribuinte"):
        return HttpResponseBadRequest("Escopo fiscal inválido.", content_type="text/plain")
    try:
        pagina = int(request.GET.get("pagina", 1))
        if pagina < 1:
            raise ValueError
    except (TypeError, ValueError):
        return HttpResponseBadRequest("Informe uma página inteira a partir de 1.", content_type="text/plain")
    try:
        ano = int(request.GET.get("ano", timezone.localdate().year))
        if not 2019 <= ano <= 9998:
            raise ValueError
        propriedade_id = request.GET.get("propriedade")
        if request.method == "POST" and propriedade_id is None:
            raise ValueError
        if propriedade_id is not None:
            propriedade_id = int(propriedade_id)
        lancamento_id = request.GET.get("lancamento")
        if lancamento_id is not None:
            lancamento_id = int(lancamento_id)
            if lancamento_id <= 0 or propriedade_id is None:
                raise ValueError
    except (TypeError, ValueError):
        return HttpResponseBadRequest("Informe propriedade válida e ano entre 2019 e 9998.", content_type="text/plain")

    propriedades = propriedades_financeiras(request.user).order_by("nome", "pk")
    propriedade = (
        get_object_or_404(propriedades, pk=propriedade_id)
        if propriedade_id is not None else propriedades.first()
    )
    contexto = {"propriedades": propriedades, "propriedade": propriedade, "ano": ano,
                "hoje": timezone.localdate(), "integracoes": catalogo_integracoes(), "escopo": escopo, "pagina": pagina}
    if request.method == "POST" and (not propriedade or propriedade.user_id != request.user.pk):
        return HttpResponseForbidden("Somente o proprietário pode alterar o cadastro fiscal.", content_type="text/plain")
    if propriedade:
        fiscal = propriedade.cadastro_fiscal if isinstance(propriedade.cadastro_fiscal, dict) else {}
        secao = request.POST.get("secao", "contribuinte") if request.method == "POST" else None
        if secao not in (None, "contribuinte", "contador", "contrapartes", "lancamento", "importacao_csv"):
            return HttpResponseBadRequest("Seção fiscal inválida.", content_type="text/plain")
        importacao = ImportacaoFinanceiraCSVForm(
            request.POST if secao == "importacao_csv" else None,
            request.FILES if secao == "importacao_csv" else None,
        )
        contexto["formulario_importacao"] = importacao
        if secao == "importacao_csv" and importacao.is_valid():
            arquivo = importacao.cleaned_data["arquivo"]
            try:
                resultado = importar_lancamentos_csv(
                    usuario=request.user, propriedade_id=propriedade.pk,
                    origem=importacao.cleaned_data["origem"], arquivo=arquivo.name,
                    conteudo=arquivo.read(),
                )
            except ValidationError as exc:
                importacao.add_error(None, exc)
            else:
                messages.success(request, f"CSV: {resultado['criados']} lançamento(s) criado(s); {resultado['existentes']} já importado(s). Confira o ano dos registros e revise pagamento e classificação fiscal.")
                return redirect(reverse("central-gestao") + "?" + urlencode({
                    "propriedade": propriedade.pk, "ano": ano, "escopo": escopo,
                }) + "#fiscal")
        if secao == "lancamento" and lancamento_id is None:
            return HttpResponseBadRequest("Selecione o lançamento para revisão.", content_type="text/plain")
        if lancamento_id is not None:
            lancamento = get_object_or_404(LancamentoFinanceiro, pk=lancamento_id, propriedade=propriedade)
            revisao = RevisaoLancamentoFiscalForm(
                request.POST if secao == "lancamento" else None,
                instance=lancamento, propriedade=propriedade, prefix="movimento",
            )
            if secao == "lancamento" and revisao.is_valid():
                revisao.save(commit=False).save(update_fields=list(revisao.Meta.fields))
                messages.success(request, f"Revisão do lançamento {lancamento.pk} salva. Confira o diagnóstico atualizado.")
                return redirect(reverse("central-gestao") + "?" + urlencode({
                    "propriedade": propriedade.pk, "ano": ano, "escopo": escopo, "pagina": pagina,
                }) + "#fiscal")
            contexto.update({"lancamento_revisao": lancamento, "formulario_lancamento": revisao})
        formulario = ContribuinteFiscalForm(
            request.POST if secao == "contribuinte" else None,
            initial=fiscal.get("contribuinte", {}),
        )
        contador = ContadorFiscalForm(request.POST if secao == "contador" else None,
                                    initial=fiscal.get("contador", {}), prefix="contador")
        contrapartes = ContrapartesFiscalFormSet(request.POST if secao == "contrapartes" else None,
                                               initial=fiscal.get("contrapartes", []), prefix="contrapartes")
        selecionado = {"contribuinte": formulario, "contador": contador, "contrapartes": contrapartes}.get(secao)
        if selecionado is not None and selecionado.is_valid():
            if secao == "contrapartes":
                valor = [{k: v for k, v in dados.items() if k != "DELETE"}
                         for dados in contrapartes.cleaned_data if dados and not dados.get("DELETE")]
            else:
                valor = selecionado.cleaned_data
            propriedade.cadastro_fiscal = {**fiscal, secao: valor}
            propriedade.save(update_fields=["cadastro_fiscal"])
            return redirect(reverse("central-gestao") + "?" + urlencode({"propriedade": propriedade.pk, "ano": ano, "escopo": escopo, "pagina": pagina}) + "#fiscal")
        contexto["formulario_fiscal"] = formulario
        contexto["formulario_contador"] = contador
        contexto["formulario_contrapartes"] = contrapartes
        inicio, fim = date(ano, 1, 1), date(ano + 1, 1, 1)
        lancamentos = LancamentoFinanceiro.objects.filter(propriedade=propriedade).filter(
            Q(data_pagamento__gte=inicio, data_pagamento__lt=fim) |
            Q(data__gte=inicio, data__lt=fim, pago=False) |
            Q(data__gte=inicio, data__lt=fim, pago=True, data_pagamento__isnull=True)
        ).select_related("conta_bancaria", "safra", "talhao", "linhafinanceiraimportada").order_by("-data", "-pk")
        pagina_movimentos = Paginator(lancamentos, 100).get_page(pagina)
        contexto.update({
            "diagnostico": (diagnosticar_consolidado(propriedade, propriedades_do_contribuinte(propriedade, propriedades), ano)
                            if escopo == "contribuinte" else diagnosticar_lcdpr(propriedade, ano)),
            "lancamentos": pagina_movimentos,
            "pagina_movimentos": pagina_movimentos,
            "pagina": pagina_movimentos.number,
            "total_lancamentos": pagina_movimentos.paginator.count,
            "contas": ContaBancaria.objects.filter(propriedade=propriedade, ativa=True).order_by("banco", "pk"),
            "notas": NotaFiscalImportada.objects.filter(propriedade=propriedade, emissao__gte=inicio, emissao__lt=fim).order_by("-importada_em")[:10],
            "cadastro_fiscal": getattr(propriedade, "cadastro_fiscal", {}) or {},
            "pode_editar_cadastro": propriedade.user_id == request.user.pk,
        })
    return render(request, "gestao/central.html", contexto,
                  status=400 if request.method == "POST" else 200)
