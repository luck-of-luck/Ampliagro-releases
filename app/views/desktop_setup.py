"""Configuração exclusiva do runtime local, autenticada pelo processo Electron."""

import hashlib
import json
import os
import secrets
import tempfile
from pathlib import Path

from django.conf import settings
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from app.cultures.seletor import MAXIMO_CULTURAS, ids_validos, opcoes_para_seletor
from app.models import Cultura


def _gravar_atomico(destino, conteudo):
    destino.parent.mkdir(parents=True, exist_ok=True)
    fd, temporario = tempfile.mkstemp(dir=destino.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as arquivo:
            json.dump(conteudo, arquivo, ensure_ascii=False, sort_keys=True)
            arquivo.flush()
            os.fsync(arquivo.fileno())
        os.replace(temporario, destino)
    finally:
        Path(temporario).unlink(missing_ok=True)


@csrf_exempt
@require_http_methods(["GET", "POST"])
def desktop_setup(request):
    # Uma página web não conhece este segredo aleatório, mantido fora do renderer.
    token = os.environ.get("AMPLIAGRO_SETUP_TOKEN", "")
    raiz = getattr(settings, "AMPLIAGRO_DESKTOP_DATA_DIR", None)
    if (
        raiz is None
        or not token
        or not secrets.compare_digest(
            request.headers.get("X-Ampliagro-Setup", ""), token
        )
    ):
        return JsonResponse({"erro": "Não encontrado"}, status=404)
    destino = raiz / "installation.json"
    if request.method == "GET":
        saved = (
            json.loads(destino.read_text(encoding="utf-8"))
            if destino.exists()
            else None
        )
        return JsonResponse({"grupos": opcoes_para_seletor(), "installation": saved})
    try:
        if len(request.body) > 16000:
            raise ValueError("Seleção muito grande")
        dados = json.loads(request.body)
        if not isinstance(dados, dict):
            raise ValueError("Configuração inválida")
        termos = os.environ.get("AMPLIAGRO_TERMS_HASH", "")
        if (
            not termos
            or dados.get("termsHash") != termos
            or dados.get("accepted") is not True
        ):
            raise ValueError("Leia e aceite os termos desta versão")
        if dados.get("mode") not in ("local", "cloud"):
            raise ValueError("Escolha o modo de uso")
        if dados["mode"] == "cloud" and not os.environ.get("AMPLIAGRO_WEB_URL"):
            raise ValueError("O servidor web ainda não está disponível")
        recebidos = dados.get("culturas")
        if (
            not isinstance(recebidos, list)
            or not 1 <= len(recebidos) <= MAXIMO_CULTURAS
        ):
            raise ValueError(f"Escolha de 1 a {MAXIMO_CULTURAS} culturas")
        if any(
            not isinstance(item, int) or isinstance(item, bool) for item in recebidos
        ):
            raise ValueError("Identificadores de cultura inválidos")
        ids = ids_validos(recebidos)
        if len(ids) != len(set(recebidos)):
            raise ValueError(
                "Uma cultura não está mais disponível. Atualize o catálogo"
            )
    except (ValueError, TypeError) as erro:
        return JsonResponse({"erro": str(erro)}, status=400)

    # Materializa somente os perfis escolhidos. O catálogo de nomes continua
    # disponível para permitir novas escolhas; não se apaga o banco compartilhado.
    perfis = []
    for cultura in Cultura.objects.filter(pk__in=ids).values():
        payload = json.dumps(cultura, ensure_ascii=False, sort_keys=True).encode(
            "utf-8"
        )
        _gravar_atomico(raiz / "culturas" / f"{cultura['id']}.json", cultura)
        perfis.append(
            {"id": cultura["id"], "sha256": hashlib.sha256(payload).hexdigest()}
        )
    config = {
        "version": 1,
        "mode": dados["mode"],
        "culturas": ids,
        "profiles": perfis,
        "termsHash": termos,
        "acceptedAt": timezone.now().isoformat(),
    }
    # Só conclui depois de todos os perfis terem sido gravados com sucesso.
    _gravar_atomico(destino, config)
    return JsonResponse({"ok": True, "installation": config})
