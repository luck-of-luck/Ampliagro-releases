import json
import logging

from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

logger = logging.getLogger(__name__)

#: Únicas contas que o endpoint público pode CRIAR. Qualquer outro username
#: só entra se a senha já bater — nunca é redefinida por aqui.
USERNAMES_CRIAVEIS = frozenset({"avaliador"})


def pitch_view(request):
    """Landing page pública — /pitch/"""
    from app.guias.catalogo import CATALOGO, EXISTE, NAO_EXISTE, PARCIAL

    def por_estado(estado: str) -> int:
        return sum(
            1
            for classe in CATALOGO
            for item in classe["itens"]
            if item["estado"] == estado
        )

    return render(
        request,
        "pitch.html",
        {
            "n_catalogo": sum(len(classe["itens"]) for classe in CATALOGO),
            "n_existe": por_estado(EXISTE),
            "n_parcial": por_estado(PARCIAL),
            "n_ausente": por_estado(NAO_EXISTE),
        },
    )


@csrf_exempt
@require_http_methods(["POST"])
def avaliador_login(request):
    """Login rápido para avaliadores JOSIF/FEBRACE.

    Regras de segurança — este endpoint era takeover de conta anônimo:
    a versão anterior fazia ``set_password()`` em **conta existente**
    (qualquer visitante resetava a senha de qualquer usuário e entrava)
    e nascia com ``is_staff=True``. Agora:

    - a senha só é gravada na CRIAÇÃO da conta;
    - só ``USERNAMES_CRIAVEIS`` nasce por aqui;
    - conta nova é usuário comum (sem staff);
    - senha errada em conta existente → 401, sem alterar nada.
    """
    from django.contrib.auth import authenticate, login
    from django.contrib.auth.models import User

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "erro": "JSON inválido"}, status=400)

    username = str(data.get("username") or "").strip()
    password = str(data.get("password") or "")

    if not username or not password:
        return JsonResponse(
            {"ok": False, "erro": "Informe usuário e senha"}, status=400
        )

    user = User.objects.filter(username=username).first()

    if user is None:
        if username not in USERNAMES_CRIAVEIS:
            logger.warning("avaliador_login: criação recusada para %r", username)
            return JsonResponse({"ok": False, "erro": "Login indisponível"}, status=403)
        user = User.objects.create(username=username, email="avaliador@ampliagro.local")
        user.set_password(password)
        user.save(update_fields=["password"])
    # Conta existente: NUNCA alteramos a senha aqui — só autenticamos.

    auth_user = authenticate(request, username=username, password=password)
    if auth_user:
        login(request, auth_user)
        return JsonResponse({"ok": True, "redirect": "/"})

    return JsonResponse({"ok": False, "erro": "Falha no login"}, status=401)
