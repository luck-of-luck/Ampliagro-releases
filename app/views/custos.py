from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from app.hierarquia import hierarquia_required
from app.models import Propriedade


@login_required
@hierarquia_required("custos-producao")
def custos_producao_view(request):
    return render(request, "custos-producao.html", {})


@login_required
@hierarquia_required("orcamento-realizado")
def orcamento_realizado_view(request):
    """A tela do orcado x realizado.

    O dado vem de `/api/financeiro/custo-talhao/` (ver
    `app/api/views/custo_talhao_view.py`). A view passa `{}` de proposito: a
    conta e' feita em SQL no servico e levada ao browser ja em JSON, com o
    `Decimal` convertido na fronteira. Passar a tabela pelo contexto seria
    serializa-la duas vezes - uma para o HTML e outra para o fetch - e criaria
    uma segunda fonte de verdade que divergiria da API.

    O ano e' lido da query string e repassado. Fica no URL de proposito: quem
    abre "orcamento-realizado?ano=2026" pode voltar a esse numero amanha
        partindo do historico do navegador.
    """
    return render(request, "orcamento-realizado.html", {})


@login_required
@hierarquia_required("dre-view")
def dre_custo_view(request):
    # renomeado para não sobrescrever financeiro.dre_view (__init__.py: custos antes de financeiro)
    prop = Propriedade.objects.filter(user=request.user).first()
    return render(request, "dre.html", {"propriedade_id": prop.id if prop else None})


# compat alias (urls antigas)
dre_view = dre_custo_view


@login_required
@hierarquia_required("cadastro-centro-custo")
def centros_custo_view(request):
    return render(request, "centros-custo.html", {})
