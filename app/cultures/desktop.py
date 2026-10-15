"""Preferências da instalação local; nunca lidas pelo servidor web."""

import json

from django.conf import settings

from app.cultures.seletor import ids_validos


def culturas_da_instalacao():
    raiz = getattr(settings, "AMPLIAGRO_DESKTOP_DATA_DIR", None)
    if raiz is None:
        return None
    arquivo = raiz / "installation.json"
    if not arquivo.exists():
        return None
    dados = json.loads(arquivo.read_text(encoding="utf-8"))
    if dados.get("version") != 1 or not dados.get("acceptedAt"):
        return None
    return ids_validos(dados.get("culturas"))
