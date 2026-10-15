import logging

from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from app.models import Propriedade

logger = logging.getLogger(__name__)


@staff_member_required
def tenant_switcher(request):
    """P9.3: Admin ve todas as propriedades e fixa o tenant na sessao.

    O QUE ESTE PORTAO FAZ: `@staff_member_required`. So staff Django chega
    aqui. Antes desta nota, o docstring dizia "para debug" e nao havia gate
    nenhum — a accao privilegiada corria em producao.

    O QUE NAO FAZ: nao ha `settings.DEBUG` a travar. Deliberado — um switch de
    tenant e' uma ferramenta de ADMINISTRACAO, nao de desenvolvimento, e
    gate-a-la por DEBUG tira-lhe a razao de existir em ambiente de
    homogeneous. O que o torna seguro e' o `@staff_member_required` mais o
    registo em baixo, nao o modo de execucao.

    O QUE LHE FALTAVA: registo. Trocar de tenant muda o que o staff ve, e era
    uma accao silenciosa. `django-auditlog` esta instalado no projecto e nao era
    usado aqui. Agora ha uma linha em `logger.warning`, com quem e' para que
    tenant.
    """
    propriedades = (
        Propriedade.objects.select_related("user").all().order_by("nome")[:100]
    )
    current = request.session.get("tenant_id")
    if request.method == "POST":
        tid = request.POST.get("tenant_id")
        if tid == "":
            request.session.pop("tenant_id", None)
            logger.warning("tenant_limpo", extra={"staff_id": request.user.pk})
        elif tid and tid.isdigit() and Propriedade.objects.filter(id=tid).exists():
            request.session["tenant_id"] = int(tid)
            # accao privilegiada e mudavel: registar SEMPRE, com quem e' e para
            # que. antes isto era silencioso.
            logger.warning(
                "tenant_trocado",
                extra={
                    "staff_id": request.user.pk,
                    "staff": request.user.get_username(),
                    "tenant_id": int(tid),
                },
            )
        # `tid` invalido nao muda nada e nao parte: o `isdigit()` evita que o
        # filter do Django levante ValueError com texto. Um 302 de volta ao
        # switcher e' a resposta a um erro de digitacao — um 500 diria ao staff
        # que o Ampliagro esta partido, e nao e' verdade.
        return redirect("tenant-switcher")
    return render(
        request,
        "admin-tenant-switcher.html",
        {"propriedades": propriedades, "current": current},
    )
