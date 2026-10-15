from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from app.hierarquia import hierarquia_required
from app.models import Propriedade


@login_required
@hierarquia_required("rastreabilidade-lista")
def rastreabilidade_view(request):
    propriedades = Propriedade.objects.filter(user=request.user)
    return render(request, "rastreabilidade.html", {"propriedades": propriedades})
