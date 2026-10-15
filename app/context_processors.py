def base_template(request):
    if request.headers.get("X-Partial") == "1":
        return {"base_template": "partial_base.html"}
    return {"base_template": "base.html"}


# ---------------------------------------------------------------------------
# A blocklist de presets, entregue ao frontend.
#
# O template lia `window._PRESET_BLOCK = {{ PRESET_BLOCK_JSON|default:"[]" }}`
# e NINGUÉM produzia essa variável — nem view, nem context processor, nem
# middleware. O `|default:[]` caía sempre, `window._PRESET_BLOCK` era sempre
# vazio, e as ~28 entradas de `app/presets.py` nunca eram aplicadas no
# frontend. A limpeza v13 no index.html filtrava só pelo prefixo `custom-`;
# o filtro por nome — que é o que ela se propõe a fazer — não acontecia.
#
# Esta função é a ponte. Ela é a MESMA fonte que o backend usa, então a
# duplicação que o docstring de app/presets.py proibia ("não duplique a lista
# no JS") deixa de existir.
# ---------------------------------------------------------------------------
def _presets_para_o_front() -> dict:
    import json as _json

    from app.presets import PRESET_BLOCK, PRESETS_SISTEMA

    return {
        "PRESET_BLOCK_JSON": _json.dumps(sorted(PRESET_BLOCK), ensure_ascii=False),
        "PRESETS_SISTEMA_JSON": _json.dumps(
            sorted(PRESETS_SISTEMA), ensure_ascii=False
        ),
    }


# ---------------------------------------------------------------------------
# Build stamp: identifica QUAL instalação está rodando.
#
# A máquina tem várias cópias do Ampliagro (worktrees, backup, OneDrive).
# "Meu navegador mostra diferente do meu" acontece quando cada aba aponta
# para uma cópia diferente. Expor commit + branch + estado sujo + nome da
# pasta torna isso diagnosticável em 1 segundo, sem abrir o terminal.
# ---------------------------------------------------------------------------
import os as _os
import subprocess as _subprocess
from pathlib import Path as _Path

_build_cache = None


def _git(args):
    from django.conf import settings

    base = _Path(getattr(settings, "BASE_DIR", _Path.cwd()))
    try:
        r = _subprocess.run(
            ["git", *args],
            cwd=str(base),
            capture_output=True,
            text=True,
            timeout=5,
            shell=False,
        )
    except (OSError, _subprocess.SubprocessError):
        return ""
    return r.stdout.strip() if r.returncode == 0 else ""


def _build_info():
    """(commit, branch, dirty, pasta) — cacheado por processo (1 git call só)."""
    global _build_cache
    if _build_cache is not None:
        return _build_cache
    from django.conf import settings

    base = _Path(getattr(settings, "BASE_DIR", _Path.cwd()))
    is_git = (base / ".git").exists()
    if not is_git:
        _build_cache = ("sem-git", "", "", base.name)
        return _build_cache
    commit = (_git(["rev-parse", "--short", "HEAD"]) or "desconhecido")[:7]
    branch = _git(["rev-parse", "--abbrev-ref", "HEAD"])
    dirty = "sujo" if _git(["status", "--porcelain"]) else "limpo"
    _build_cache = (commit, branch, dirty, base.name)
    return _build_cache


def ampliagro_build(request):
    """Contexto {{ AMPLIAGRO_BUILD }} — sempre presente, mesmo para anônimo."""
    from django.conf import settings

    commit, branch, dirty, pasta = _build_info()
    return {
        "AMPLIAGRO_BUILD": {
            "commit": commit,
            "branch": branch,
            "dirty": dirty,
            "pasta": pasta,
            # caminho completo só em DEBUG — não vazar layout de disco em produção
            "caminho": str(getattr(settings, "BASE_DIR", "")) if settings.DEBUG else "",
            "debug": bool(settings.DEBUG),
        }
    }


_vite_ativo_cache = None


def _vite_dev_ativo():
    """True se o dev-server Vite (:5173) está no ar. Evita 3x ERR_CONNECTION_REFUSED
    por página quando o frontend React não está rodando (só Django)."""
    global _vite_ativo_cache
    if _vite_ativo_cache is not None:
        return _vite_ativo_cache
    import socket

    from django.conf import settings as _settings

    try:
        cfg = getattr(_settings, "DJANGO_VITE", {}).get("default", {})
        host = cfg.get("dev_server_host", "localhost")
        port = cfg.get("dev_server_port", 5173)
        s = socket.create_connection((host, port), timeout=0.3)
        s.close()
        _vite_ativo_cache = True
    except OSError:
        _vite_ativo_cache = False
    return _vite_ativo_cache


def ampliagro_globals(request):
    """Variáveis globais incrementadas — tema, cultura, usuário, personalização.

    Disponível em todo template como {{ AMPLIAGRO_TEMA }}, {{ CULTURA_ATIVA }}, etc.
    Mantém padrão de cores e design, permite liberdade total de personalização.
    Usa cache para evitar queries redundantes a cada request.
    """
    from django.conf import settings
    from django.core.cache import cache

    user = request.user if request.user.is_authenticated else None

    if not user:
        return _default_context(settings)

    cache_key = f"ctx_globals_{user.id}"
    cached = cache.get(cache_key)

    # Cultura ativa vem da query string ou sessão, não cacheável — defensivo para RequestFactory/sem session (evita 500 ao clicar em Cadastrar Talhão)
    try:
        sess = getattr(request, "session", None)
        sess_val = sess.get("cultura_ativa") if sess is not None else None
    except Exception:
        sess_val = None
    cultura_ativa = request.GET.get("cultura") or sess_val or "cafe"

    if cached:
        cached["CULTURA_ATIVA"] = cultura_ativa
        # A blocklist entra AQUI TAMBÉM, e não só no caminho que constrói o
        # cache. Sem isto o menu fica intermitente: quem bate no cache recebe
        # o contexto sem PRESET_BLOCK_JSON e cai no `|default:"[]"`, quem não
        # bate recebe com a lista. Um defeito que depende de cache é um
        # defeito que alguém vai reportar como "às vezes o preset aparece".
        cached.update(_presets_para_o_front())
        return cached

    perfil = None
    tema = "claro"
    try:
        if hasattr(user, "perfil"):
            perfil = user.perfil
            tema = getattr(perfil, "tema", "claro") or "claro"
    except Exception:
        pass

    ctx = {
        "AMPLIAGRO_TEMA": tema,
        "AMPLIAGRO_VERSION": getattr(settings, "AMPLIAGRO_VERSION", "2.0.0"),
        "CULTURA_ATIVA": cultura_ativa,
        "USER_TIPO": getattr(perfil, "tipo_usuario", "anonimo")
        if perfil
        else "anonimo",
        "IS_PRODUTOR": getattr(perfil, "tipo_usuario", "") == "produtor",
        "SENTRY_DSN": getattr(settings, "SENTRY_DSN", ""),
        "SENTRY_ENVIRONMENT": getattr(settings, "SENTRY_ENVIRONMENT", "development"),
        "VITE_ATIVO": _vite_dev_ativo(),
        "CORES_SISTEMA": {
            "primaria": "#0f9d6e",
            "primaria_dark": "#3ec48f",
            "acento": "#3ec48f",
            "sucesso": "#0f9d6e",
            "alerta": "#c98a24",
            "erro": "#d93a3a",
        },
        "FLUIDEZ_CONFIG": {
            "transicao": "0.3s ease",
            "raio_grande": "28px",
            "raio_medio": "16px",
            "sombra_premium": "0 8px 32px rgba(15,157,110,0.12)",
        },
    }
    cache.set(cache_key, ctx, 300)  # 5 min cache
    # Fora do cache de propósito: PRESET_BLOCK é constante de módulo, e cacheá-lo
    # deixaria o menu servindo uma lista velha por até 5 minutos depois de
    # alguém editar app/presets.py. Uma lista pequena por request é barata;
    # um menu que mente sobre quais presets são fantasma não é.
    ctx.update(_presets_para_o_front())
    return ctx


def _default_context(settings):
    """Contexto padrão para usuários anônimos (sem DB query)."""
    ctx = {
        "AMPLIAGRO_TEMA": "claro",
        "AMPLIAGRO_VERSION": getattr(settings, "AMPLIAGRO_VERSION", "2.0.0"),
        "CULTURA_ATIVA": "cafe",
        "USER_TIPO": "anonimo",
        "IS_PRODUTOR": False,
        "SENTRY_DSN": getattr(settings, "SENTRY_DSN", ""),
        "SENTRY_ENVIRONMENT": getattr(settings, "SENTRY_ENVIRONMENT", "development"),
        "VITE_ATIVO": _vite_dev_ativo(),
        "CORES_SISTEMA": {
            "primaria": "#0f9d6e",
            "primaria_dark": "#3ec48f",
            "acento": "#3ec48f",
            "sucesso": "#0f9d6e",
            "alerta": "#c98a24",
            "erro": "#d93a3a",
        },
        "FLUIDEZ_CONFIG": {
            "transicao": "0.3s ease",
            "raio_grande": "28px",
            "raio_medio": "16px",
            "sombra_premium": "0 8px 32px rgba(15,157,110,0.12)",
        },
    }
    # Anônimo recebe a blocklist também. Sem isso o menu de quem não está
    # logado usaria a lista vazia e aceitaria presets fantasma — exatamente o
    # que a limpeza v13 existe para impedir.
    ctx.update(_presets_para_o_front())
    return ctx
