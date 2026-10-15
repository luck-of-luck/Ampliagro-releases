"""Ponte local para os viewsets do produto: mesmos serializers e permissões."""

import json
import re
from io import BytesIO
from urllib.parse import urlencode

from django.core.handlers.wsgi import WSGIRequest
from django.db import transaction
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import APIException, PermissionDenied, ValidationError
from rest_framework.pagination import LimitOffsetPagination

_SEGREDO = re.compile(
    r"password|senha|secret|token|api_key|chave_api|credential|credencial", re.I
)
_RESERVADOS = {"user", "user_id", "is_staff", "is_superuser", "groups", "permissions"}
_INFRA = {"push-subscriptions", "erros"}


def _limpar(valor):
    if isinstance(valor, dict):
        return {k: _limpar(v) for k, v in valor.items() if not _SEGREDO.search(str(k))}
    if isinstance(valor, (list, tuple)):
        return [_limpar(v) for v in valor]
    return valor


def _validar_campos(valor):
    if isinstance(valor, dict):
        for chave, item in valor.items():
            if chave in _RESERVADOS or _SEGREDO.search(str(chave)):
                raise ValidationError(f"Campo reservado: {chave}.")
            _validar_campos(item)
    elif isinstance(valor, list):
        for item in valor:
            _validar_campos(item)


class AutenticacaoInterna(BaseAuthentication):
    def authenticate(self, request):
        # Esta classe só é passada à view criada abaixo, nunca às rotas HTTP.
        user = getattr(request._request, "_copiloto_user", None)
        if user is None or not user.is_authenticated or not user.is_active:
            raise PermissionDenied("Usuário ativo obrigatório.")
        return user, None


class PaginaCopiloto(LimitOffsetPagination):
    default_limit = 20
    max_limit = 50


def registro_recursos():
    from app.api.urls import router

    return {
        prefixo: view
        for prefixo, view, _ in router.registry
        if prefixo not in _INFRA and re.fullmatch(r"[a-z0-9-]+", prefixo)
    }


def _request(user, metodo, recurso, dados=None, filtros=None):
    corpo = json.dumps(dados or {}, ensure_ascii=False).encode("utf-8")
    request = WSGIRequest(
        {
            "REQUEST_METHOD": metodo,
            "PATH_INFO": f"/api/{recurso}/",
            "QUERY_STRING": urlencode(filtros or {}),
            "SERVER_NAME": "localhost",
            "SERVER_PORT": "80",
            "SERVER_PROTOCOL": "HTTP/1.1",
            "wsgi.url_scheme": "http",
            "wsgi.input": BytesIO(corpo),
            "CONTENT_TYPE": "application/json",
            "CONTENT_LENGTH": str(len(corpo)),
        }
    )
    request._copiloto_user = user
    return request


def _view(user, recurso, action="list", filtros=None):
    classe = registro_recursos().get(recurso)
    if classe is None:
        raise ValidationError("Recurso desconhecido. Consulte recursos_catalogo.")
    view = classe(
        authentication_classes=[AutenticacaoInterna], pagination_class=PaginaCopiloto
    )
    view.args, view.kwargs, view.format_kwarg = (), {}, None
    view.action_map = {"get": action}
    request = view.initialize_request(_request(user, "GET", recurso, filtros=filtros))
    view.request = request
    view.initial(request)
    return view


def catalogo(user, recurso=None, filtros=None):
    if not recurso:
        return {"recursos": sorted(registro_recursos()), "limite_por_pagina": 50}
    view = _view(user, recurso, filtros=filtros)
    serializer = view.get_serializer()
    campos = {}
    for nome, campo in serializer.fields.items():
        if nome in _RESERVADOS or _SEGREDO.search(nome) or campo.write_only:
            continue
        campos[nome] = {
            "tipo": type(campo).__name__,
            "rotulo": str(campo.label or nome),
            "somente_leitura": campo.read_only,
            "obrigatorio": campo.required,
            "aceita_nulo": campo.allow_null,
        }
        if getattr(campo, "choices", None):
            campos[nome]["opcoes"] = list(campo.choices)[:100]
    return {
        "recurso": recurso,
        "campos": campos,
        "operacoes": [
            a
            for a in ("list", "retrieve", "partial_update", "destroy")
            if hasattr(view, a)
        ],
    }


def operar(user, recurso, operacao, *, identificador=None, dados=None, filtros=None):
    """Despacha em memória; nenhum HTTP, modelo ou shell é gerado pela IA."""
    acoes = {
        "listar": ("get", "list"),
        "ler": ("get", "retrieve"),
        "editar": ("patch", "partial_update"),
        "excluir": ("delete", "destroy"),
    }
    if operacao not in acoes:
        raise ValidationError("Operação desconhecida.")
    if operacao != "listar" and (type(identificador) is not int or identificador <= 0):
        raise ValidationError("Informe o id inteiro positivo do registro.")
    if filtros is not None and (not isinstance(filtros, dict) or len(filtros) > 15):
        raise ValidationError("Filtros devem ser um objeto de até 15 campos.")
    classe = registro_recursos().get(recurso)
    if classe is None:
        raise ValidationError("Recurso desconhecido. Consulte recursos_catalogo.")
    metodo, acao = acoes[operacao]
    if not hasattr(classe, acao):
        raise ValidationError("Operação indisponível neste recurso.")
    if operacao == "editar":
        if not isinstance(dados, dict) or not dados or len(json.dumps(dados)) > 32000:
            raise ValidationError(
                "Informe um objeto de campos não vazio, com até 32 KB."
            )
        _validar_campos(dados)
        view = _view(user, recurso, action="partial_update", filtros=filtros)
        campos = view.get_serializer().fields
        invalidos = [
            k
            for k in dados
            if k not in campos or campos[k].read_only or campos[k].write_only
        ]
        if invalidos:
            raise ValidationError({"campos_nao_editaveis": invalidos})
    request = _request(user, metodo.upper(), recurso, dados, filtros)
    endpoint = classe.as_view(
        {metodo: acao},
        authentication_classes=[AutenticacaoInterna],
        pagination_class=PaginaCopiloto,
    )
    with transaction.atomic():
        resposta = endpoint(request, **({"pk": identificador} if identificador else {}))
        if resposta.status_code >= 400:
            transaction.set_rollback(True)
            return {
                "ok": False,
                "erro": _limpar(resposta.data),
                "status": resposta.status_code,
            }
        if operacao == "editar":
            # Impede uma alteração de relacionamento de retirar o objeto do escopo.
            # O rollback também desfaz efeitos de signals/perform_update no banco.
            verificacao = _view(user, recurso, filtros=filtros)
            if not verificacao.get_queryset().filter(pk=identificador).exists():
                raise PermissionDenied(
                    "A alteração retiraria o registro do seu escopo."
                )
        return {
            "ok": True,
            "resposta": f"{recurso}: {operacao} concluído.",
            "dados": {
                "recurso": recurso,
                "id": identificador,
                "resultado": _limpar(getattr(resposta, "data", None)),
            },
        }


def executar_seguro(funcao, *args, **kwargs):
    try:
        return funcao(*args, **kwargs)
    except APIException as exc:
        return {"ok": False, "erro": _limpar(exc.detail), "status": exc.status_code}
