from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.generic.base import RedirectView, TemplateView
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from app.views.admin_tenant import tenant_switcher
from app.views.desktop_setup import desktop_setup
from app.views.health_dashboard import health_dashboard, healthz_detailed

# Static files MUST come first in DEBUG mode to avoid being caught by catch-all routes
urlpatterns = static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

urlpatterns += [
    path("desktop/setup/", desktop_setup, name="desktop-setup"),
    # `/robots.txt` nao existia. Num ERP de uso privado isso e' uma omissao
    # e nao uma escolha: nao ha nada a indexar, e um motor de busca que
    # encontra o painel de um produtor vee o login, a estrutura de rotas e o
    # nome das entidades. `Disallow: /` e' o que diz a verdade sobre o
    # produto. O template esta em app/templates/robots.txt.
    path(
        "robots.txt",
        TemplateView.as_view(template_name="robots.txt", content_type="text/plain"),
        name="robots",
    ),
    # O tenant_switcher fica AQUI, e nao em app/urls.py, por uma razao concreta:
    # `admin.site.urls` (linha seguinte) tem um catch-all que engole
    # /admin/<qualquer-coisa>/. Como app.urls e' incluido depois, a rota
    # `admin/tenant/` ficava registada mas INALCANCAVEL — o Django resolvia-a
    # para `AdminSite.catch_all_view` e devolvia 404. A funcao era codigo morto.
    #
    # Registar antes do admin preserva o URL que o autor pretendia.
    path("admin/tenant/", tenant_switcher, name="tenant-switcher"),
    path("admin/", admin.site.urls),
    path("accounts/", include("allauth.urls")),  # P9.2 SSO Google
    path("health/", include("health_check.urls")),
    path("healthz", healthz_detailed, name="healthz"),
    path("healthz/", healthz_detailed),
    path("health/dashboard/", health_dashboard, name="health-dashboard"),
    path("api/", include("app.api.urls")),  # Endpoints REST da API
    path("api/iot/", include("app.iot.urls")),  # Telemetria / IoT
    path("api/ia/", include("app.ia.urls")),  # IA local sandbox + artifactory
    # BUILD 0 da AmplIA: as tools que a IA local (WebLLM) chama.
    # Executam SOMENTE via sandbox.executar(via='mcp') — ver app/amplia_mcp.
    path("api/amplia/", include("app.amplia_mcp.urls")),
    path("", include("app.urls")),  # CONEXÃO CRÍTICA: Vincula a página inicial da SPA
    # Swagger
    path(
        "favicon.ico", RedirectView.as_view(url=settings.STATIC_URL + "img/ampliagro-logo.svg?v=brand-1", permanent=False)
    ),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
]
