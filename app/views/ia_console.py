from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count, Q
from django.shortcuts import render

from app.models import IAEvento, IAExecucao


@login_required
def ia_registros_view(request):
    """Console de registros-teste da IA: toda interação + tudo que ela fez."""
    qs = (
        IAExecucao.objects.filter(user=request.user)
        .select_related("artefato")
        .prefetch_related("eventos")
        .order_by("-criado_em")
    )
    f_intent = (request.GET.get("intent") or "").strip()
    f_ok = request.GET.get("ok") or ""
    f_q = (request.GET.get("q") or "").strip()
    if f_intent:
        qs = qs.filter(intent=f_intent)
    if f_ok == "1":
        qs = qs.filter(ok=True)
    elif f_ok == "0":
        qs = qs.filter(ok=False)
    if f_q:
        qs = qs.filter(Q(entrada__icontains=f_q) | Q(resposta__icontains=f_q))
    execucoes = list(qs[:100])

    ev = IAEvento.objects.filter(user=request.user).order_by("-criado_em")
    f_tipo = (request.GET.get("tipo") or "").strip()
    if f_tipo:
        ev = ev.filter(tipo=f_tipo)
    if f_q:
        ev = ev.filter(Q(resumo__icontains=f_q) | Q(dados__icontains=f_q))
    eventos = list(ev[:100])

    base = IAExecucao.objects.filter(user=request.user)
    stats = {
        "total": base.count(),
        "ok": base.filter(ok=True).count(),
        "ms_medio": round(base.aggregate(m=Avg("duracao_ms"))["m"] or 0),
        "satisfeito": base.filter(satisfeito=True).count(),
        "insatisfeito": base.filter(satisfeito=False).count(),
    }
    intents = list(base.values("intent").annotate(n=Count("id")).order_by("-n"))
    return render(
        request,
        "ia-registros.html",
        {
            "execucoes": execucoes,
            "eventos": eventos,
            "stats": stats,
            "intents": intents,
            "f_intent": f_intent,
            "f_ok": f_ok,
            "f_q": f_q,
            "f_tipo": f_tipo,
            "tipos_evento": IAEvento.TIPOS,
        },
    )
