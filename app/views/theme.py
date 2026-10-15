from django.http import JsonResponse
from django.views.decorators.http import require_GET

# Mapa central — mesma fonte do ampliagro-global.css
THEME_LIGHT = {
    "--cor-fundo": "#fdfefe",
    "--cor-texto": "#1d2421",
    "--cor-primaria": "#0f9d6e",
    "--cor-secundaria": "#1d2421",
    "--cor-acento": "#3ec48f",
    "--cor-borda": "#e5e7eb",
    "--cor-hover": "rgba(15, 157, 110, 0.10)",
    "--cor-suave": "#f3f7f5",
    "--cor-texto-suave": "#5f6b66",
    "--cor-texto-fraco": "#8b9792",
    "--cor-sombra": "rgba(29, 36, 33, 0.12)",
    "--cor-fundo-navbar": "#fdfefe",
    "--cor-fundo-card": "#fdfefe",
    "--cor-fundo-card-aninhado": "#f3f7f5",
    "--cor-sucesso": "#0f9d6e",
    "--cor-alerta": "#c98a24",
    "--cor-erro": "#d93a3a",
    "--cor-cultura-graos": "#0f9d6e",
    "--cor-cultura-frutas": "#e67e22",
    "--dashboard-bg-from": "#ecfdf5",
    "--dashboard-bg-to": "#eef2ff",
}

THEME_DARK = {
    "--cor-fundo": "#0b0f0e",
    "--cor-texto": "#e9eeec",
    "--cor-primaria": "#3ec48f",
    "--cor-secundaria": "#0b0f0e",
    "--cor-acento": "#57d7a0",
    "--cor-borda": "#33413f",
    "--cor-hover": "rgba(62, 196, 143, 0.10)",
    "--cor-suave": "#131917",
    "--cor-texto-suave": "#8b9792",
    "--cor-texto-fraco": "#5f6b66",
    "--cor-sombra": "rgba(0, 0, 0, 0.5)",
    "--cor-fundo-navbar": "#131917",
    "--cor-fundo-card": "#151b19",
    "--cor-fundo-card-aninhado": "#1a211f",
    "--cor-sucesso": "#3ec48f",
    "--cor-alerta": "#e0a84e",
    "--cor-erro": "#ef6a6a",
    "--cor-cultura-graos": "#3ec48f",
    "--cor-cultura-frutas": "#f39c12",
    "--dashboard-bg-from": "rgba(15, 157, 110, .12)",
    "--dashboard-bg-to": "rgba(99, 102, 241, .08)",
}


@require_GET
def theme_api(request):
    """GET /api/theme/ — retorna mapa de cores para qualquer arquivo puxar via API.
    Query ?mode=claro|escuro|auto (default auto = ambos)."""
    mode = (request.GET.get("mode") or "auto").lower()
    if mode == "claro":
        return JsonResponse({"mode": "claro", "vars": THEME_LIGHT})
    if mode == "escuro":
        return JsonResponse({"mode": "escuro", "vars": THEME_DARK})
    return JsonResponse(
        {
            "light": THEME_LIGHT,
            "dark": THEME_DARK,
            "css": "/static/css/ampliagro-global.css",
        }
    )
