import json
import logging

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

from .utils import *

logger = logging.getLogger(__name__)


# NOTA DE REVOGACAO — `get_talhoes_api` NAO verifica `ativo_servidor`, de proposito.
# A rota nao e' de servidor: registada como `api/talhoes-por-propriedade/`
# (app/urls.py) e consumida por cadastro-safra, cadastro-financeiro e
# agronomia/ndvi — paginas de produtor, agronomo e administrativo. E o proprio
# queryset ja nao entrega dado de fazenda a um servidor: filtra
# `propriedade__user=request.user`, e um servidor nunca e' dono da propriedade
# (e' `propriedade_vinculada`), portanto recebe `[]`. Aplicar aqui um portao
# de servidor alargaria a revogacao a paginas que nao tem nada com ela — e
# negaria quem tem perfil mas nao tem `PerfilUsuario`, que o `kanban_allowed`
# trata como "sem tipo declarado".
@login_required
def get_talhoes_api(request):
    propriedade_id = request.GET.get("propriedade_id")
    if not propriedade_id:
        return JsonResponse([], safe=False)
    talhoes = Talhao.objects.filter(
        propriedade_id=propriedade_id, propriedade__user=request.user
    )
    data = [
        {"id": t.id, "nome": t.nome, "area_hectare": str(t.area_hectare)}
        for t in talhoes
    ]
    return JsonResponse(data, safe=False)


@login_required
def servidor_config_api(request):
    """Retorna JSON da config do servidor logado — usado pelo servidor.js para modificar a página."""

    # REVOGACAO. `@login_required` prova que ha sessao, NAO que a sessao ainda
    # e' valida: o produtor pode ter desligado o servidor depois do login
    # (`perfil.ativo_servidor = False`, em lgpd.py). Sem esta passagem, um
    # servidor desligado com sessao aberta recebia HTTP 200 com o nome da
    # propriedade, o id e a config do dashboard.
    #
    # Usa-se `kanban_allowed` (utils.py) em vez de reescrever
    # `if not perfil.ativo_servidor`: e' o portao unico que ja le esse campo, e
    # a razao de ele existir e' exactamente a razao desta linha — uma condicao
    # escrita a mao e' uma condicao para se esquecer de actualizar. As rotas
    # HTML de /servidor/ passam por `_perfil_e_propriedade` (servidor.py) ou pelo
    # dashboard; esta passa pelo mesmo portao. Um sitio de verdade.
    if not kanban_allowed(request.user):
        # Mesmo contrato do `servidor_dashboard_view`: encerrar a sessao E dizer
        # "desativado". Recusar no ecra sem fechar a porta nao e' revogar.
        logout(request)
        return JsonResponse({"error": "Servidor desativado pelo produtor."}, status=403)

    try:
        perfil = request.user.perfil
        config = perfil.get_dashboard_config()
        return JsonResponse(
            {
                "area": perfil.area_servidor,
                "tipo": perfil.tipo_usuario,
                "propriedade": perfil.propriedade_vinculada.nome
                if perfil.propriedade_vinculada
                else None,
                "propriedade_id": perfil.propriedade_vinculada_id,
                "config": config,
            }
        )
    except Exception:
        # A excecao nao vai para o cliente. A versao anterior devolvia a
        # mensagem da excecao em JSON — nomes de tabela/coluna, valores e
        # fragmento de traceback: mapa do esquema para quem so precisa de um
        # HTTP 200. Fica no log do servidor, com traceback, e o cliente recebe
        # so "erro interno".
        logger.exception("servidor_config_api falhou (user_id=%s)", request.user.pk)
        return JsonResponse({"error": "erro interno"}, status=400)
