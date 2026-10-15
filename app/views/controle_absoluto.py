from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from app.models import Cultura, Propriedade, Talhao


@login_required
def controle_absoluto_view(request):
    propriedades = Propriedade.objects.filter(user=request.user)
    talhoes = Talhao.objects.filter(propriedade__user=request.user).select_related(
        "propriedade", "cultura_atual"
    )
    # Cultura.talhao e ForeignKey (singular). "talhoes__" nao existe e fazia a
    # tela inteira estourar com FieldError.
    culturas = (
        Cultura.objects.filter(talhao__propriedade__user=request.user).distinct()
        | Cultura.objects.filter(safra__propriedade__user=request.user).distinct()
    )
    culturas = culturas.distinct().order_by("nome")[:50]

    # Custos por talhão
    from django.db.models import Q, Sum

    from app.models import CustoProducao, RastreabilidadeSafra

    custos_por_talhao = []
    for t in talhoes:
        custo = (
            CustoProducao.objects.filter(talhao=t).aggregate(total=Sum("custo_total"))[
                "total"
            ]
            or 0
        )
        custos_por_talhao.append(
            {
                "talhao": t,
                "custo": float(custo),
                "custo_por_ha": float(custo / t.area_hectare)
                if t.area_hectare and custo
                else 0,
            }
        )

    return render(
        request,
        "controle-absoluto.html",
        {
            "propriedades": propriedades,
            "talhoes": talhoes,
            "culturas": culturas,
            "custos_por_talhao": custos_por_talhao,
        },
    )
