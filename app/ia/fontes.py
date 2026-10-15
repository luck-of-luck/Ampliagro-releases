"""Allowlist de fontes da IA local.

A IA NUNCA pesquisa "por qualquer canto da internet". Destinos permitidos:
  1. APIs padrão do sistema (Open-Meteo previsão + geocodificação).
  2. Fontes que o USUÁRIO cadastrou e ativou (FonteDadosExterna).
Todo o resto é bloqueado — e a tentativa é registrada na execução.
"""

from urllib.parse import urlparse

import requests

_SESSAO = requests.Session()  # reusa conexão TCP (latência menor)
_SESSAO.headers.update({"User-Agent": "AmpliagroIA/1.0"})

# APIs padrão do sistema (usadas pelo próprio backend: clima, geocode)
FONTES_PADRAO = {
    "open_meteo": ["api.open-meteo.com", "geocoding-api.open-meteo.com"],
}

# Hosts fixos por tipo de fonte cadastrável (sem config de URL pelo usuário)
FONTES_POR_TIPO = {
    "OPEN_METEO": ["api.open-meteo.com", "geocoding-api.open-meteo.com"],
    "INMET": ["apitempo.inmet.gov.br"],
    "NASA_POWER": ["power.larc.nasa.gov"],
    "SENTINEL": ["dataspace.copernicus.eu"],
    # CHIRPSTACK/TTN: só o base_url que o usuário registrou no config
    "CHIRPSTACK": [],
    "TTN": [],
}


class FonteBloqueada(Exception):
    pass


def fontes_ativas(user, propriedade=None):
    """Fontes externas ATIVAS do usuário (opcionalmente da propriedade)."""
    from django.db.models import Q

    from app.models import FonteDadosExterna

    qs = FonteDadosExterna.objects.filter(ativo=True, propriedade__user=user)
    if propriedade is not None:
        # inclui globais (propriedade=NULL) + as da propriedade específica
        qs = qs.filter(Q(propriedade=propriedade) | Q(propriedade__isnull=True))
    return list(qs)


def hosts_permitidos(user, propriedade=None):
    """Conjunto de hosts que a IA pode acessar nesta execução."""
    hosts = set()
    for lista in FONTES_PADRAO.values():
        hosts.update(h.lower() for h in lista)
    for f in fontes_ativas(user, propriedade):
        for h in FONTES_POR_TIPO.get(f.tipo, []):
            hosts.add(h.lower())
        base = (f.config or {}).get("base_url") or ""
        try:
            host = urlparse(base).hostname if base else None
        except Exception:
            host = None
        if host:
            hosts.add(host.lower())
    return hosts


def fetch_permitido(url, user, propriedade=None, timeout=8, params=None):
    """GET auditado: só sai se o host estiver na allowlist. Retorna (json, fonte_nome)."""
    host = (urlparse(url).hostname or "").lower()
    permitidos = hosts_permitidos(user, propriedade)
    if host not in permitidos:
        raise FonteBloqueada(
            f"host '{host}' fora da allowlist — a IA só usa APIs padrão e fontes cadastradas"
        )
    r = _SESSAO.get(url, params=params, timeout=timeout)
    r.raise_for_status()
    return r.json(), host
