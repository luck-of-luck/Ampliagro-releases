"""
views.py — o receptor de eventos do dispositivo (BUILD 4).

Este é o ÚNICO ponto do AmplIA que aceita requisição anônima de fora. Tudo o
mais é sessão Django; aqui é um ESP32 sem navegador, sem cookie e sem login.

Duas decisões que definem a postura do arquivo:

1. **`csrf_exempt` é obrigatório aqui**, e não é uma brecha: o cliente não tem
   como ter token CSRF. O que substitui a proteção de CSRF é a autenticação por
   token no header — o CSRF existe para impedir que o *navegador do usuário*
   seja usado como proxy autenticado; um ESP32 não tem sessão para sequestrar.

2. **Nenhuma resposta diz se o token existe.** Tudo que não autenticou volta
   401 com o mesmo texto. Um 401 que distingue "token não existe" de "token
   revogado" é um oráculo de enumeração, e endpoint público é onde se testa
   oráculo.
"""

import json
import logging

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

logger = logging.getLogger(__name__)

#: Mesmo texto para token ausente, errado e revogado. Ver ponto 2 do docstring.
_NAO_AUTENTICADO = {"ok": False, "erro": "nao autorizado"}


@csrf_exempt
@require_POST
def evento(request):
    """POST /api/iot/dinamico/evento/

    Corpo: {"valor": 22.5}  (ou um único campo, que vira o valor)
    Header: Authorization: Bearer <token>
    """
    from app.ia.iot import receber_evento

    token = _token_do_request(request)
    if not token:
        return JsonResponse(_NAO_AUTENTICADO, status=401)

    # O corpo vem como bytes crus. Parsear com json.loads direto no body pode
    # levantar UnicodeDecodeError em payload binário, e uma exceção aqui é um
    # 500 que derruba o endpoint inteiro.
    try:
        payload = json.loads((request.body or b"{}").decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as e:
        return JsonResponse(
            {"ok": False, "erro": f"payload nao e JSON valido: {e}"[:200]},
            status=400,
        )

    if not isinstance(payload, dict):
        return JsonResponse(
            {"ok": False, "erro": "payload deve ser um objeto JSON"}, status=400
        )

    resultado = receber_evento(token, payload)

    if resultado.get("ok"):
        return JsonResponse(resultado, status=201)

    # Revogado e token inválido recebem o MESMO 401 e o MESMO texto. A diferença
    # está no `IotEvento`, que o produtor consulta, não no HTTP.
    if resultado.get("motivo") in ("token_invalido", "revogado"):
        return JsonResponse(_NAO_AUTENTICADO, status=401)

    if resultado.get("motivo") in ("payload_invalido", "excedido"):
        return JsonResponse(
            {"ok": False, "erro": resultado.get("erro", "payload invalido")[:200]},
            status=400,
        )

    # campo_invalido é 422: o pedido foi bem formado e autenticado, mas não
    # satisfaz o schema. 400 diria "arrume a requisição"; 422 diz "a requisição
    # está certa, o valor não é" — que é a informação que o firmware precisa.
    return JsonResponse(
        {
            "ok": False,
            "erro": resultado.get("erro", "valor fora do schema")[:300],
            "campos_validos": resultado.get("campos_validos", []),
        },
        status=422,
    )


def _token_do_request(request) -> str:
    """Extrai o token do header Authorization, ou da query string.

    A query string existe porque ESPClient/PubSub às vezes só aceita header em
    subscribe, não em publish — e o produtor não deveria trocar a lib do
    firmware por causa disso. Ela é a ÚNICA exceção ao header, e o token na
    query aparece em log de servidor, o que é o mesmo problema do tópico: por
    isso o modo seguro (token no header) é o recomendado no escopo C++.
    """
    auth = request.META.get("HTTP_AUTHORIZATION") or ""
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return (request.GET.get("token") or "").strip()
