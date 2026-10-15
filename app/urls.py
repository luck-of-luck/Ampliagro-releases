from django.contrib.auth.decorators import login_required
from django.http import FileResponse, HttpResponse
from django.shortcuts import render
from django.urls import path


def pwa_sw(request):
    import pathlib

    from django.conf import settings

    p = pathlib.Path(settings.BASE_DIR) / "app" / "static" / "js" / "pwa" / "sw.js"
    resp = HttpResponse(p.read_bytes(), content_type="application/javascript")
    resp["Service-Worker-Allowed"] = "/"
    resp["Cache-Control"] = "no-cache"
    return resp


def wellknown_dummy(request, path=None):
    return HttpResponse("", status=204, content_type="application/json")


def pwa_manifest(request):
    import pathlib

    from django.conf import settings

    p = pathlib.Path(settings.BASE_DIR) / "app" / "static" / "manifest.json"
    return HttpResponse(p.read_bytes(), content_type="application/manifest+json")


from app.views import (
    adicionar_funcionario_view,
    agenda_agricola_view,
    agenda_pecuaria_view,
    alertas_criticos_view,
    alertas_info_view,
    animais_gado_view,
    cadastro_animal_view,
    cadastro_apiario_view,
    cadastro_aquatico_view,
    cadastro_caminhao_view,
    cadastro_cultura_view,
    cadastro_estoque_view,
    cadastro_financeiro_view,
    cadastro_funcionario_view,
    cadastro_insumo_view,
    cadastro_maquinario_view,
    cadastro_mip_view,
    cadastro_propriedade_view,
    cadastro_receituario_view,
    cadastro_rota_view,
    cadastro_safra_view,
    cadastro_talhao_view,
    cadastro_vra_view,
    cashflow_view,
    centros_custo_view,
    comparativo_safras_view,
    compliance_view,
    culturas_propriedade_api,
    config_dia_view,
    config_noturno_view,
    config_page_view,
    config_sistema_view,
    custos_producao_view,
    dashboard_os_view,
    demo_login_view,
    dispositivos_view,
    dre_custo_view,
    dre_view,
    equipe_agenda_view,
    equipe_empregados_view,
    erro_report_view,
    estoque_geral_view,
    estoque_insumos_view,
    exportar_lcdpr_view,
    get_talhoes_api,
    guia_animal_view,
    guia_aquatica_view,
    guia_ferramentas_view,
    guia_sistemas_view,
    guia_vegetal_view,
    ia_registros_view,
    ia_web_search,
    index_view,
    limpar_flag_recuperacao,
    login_view,
    logistica_caminhao_view,
    logistica_rotas_view,
    logout_view,
    mapa_view,
    ndvi_view,
    onboarding_view,
    operario_criar_login,
    # Operário views
    operario_kanban_view,
    operario_perfil_view,
    operario_registrar_view,
    operario_remover_login,
    orcamento_realizado_view,
    perfil_config_view,
    # pitch_view: NÃO importar daqui — o canônico é app.views_pitch
    # (importado abaixo, junto com avaliador_login). Ter os dois virava
    # redefinição silenciosa (F811) e ninguém sabia qual rota usava.
    previsao_clima_view,
    previsao_safra_view,
    racoes_nutricao_view,
    rastreabilidade_view,
    registro_cafe_view,
    registro_cultura_sistemas_view,
    registro_cultura_view,
    resumo_gerencial_view,
    sensores_view,
    servidor_agenda_view,
    servidor_alertas_view,
    servidor_config_api,
    servidor_dashboard_view,
    servidor_estoque_view,
    setor_campo_view,
    setor_estoque_view,
    simulador_colheita_view,
    simulador_financeiro_view,
    simulador_lucro_view,
    spa_view,
    telemetria_view,
)
from app.views.controle_absoluto import controle_absoluto_view
from app.views.lgpd import lgpd_delete_data, lgpd_export_data, privacidade_view
from app.views.nfe_auto import lote_qr, nfe_import
from app.views.central_gestao import central_gestao
from app.views.theme import theme_api
from app.views_pitch import avaliador_login, pitch_view
from app.views_tarefas_associacao import tarefas_associacao_api, tarefas_associacao_view

urlpatterns = [
    path("login/", login_view, name="login"),
    path("logout/", logout_view, name="logout"),
    path(
        "limpar_flag_recuperacao/",
        limpar_flag_recuperacao,
        name="limpar_flag_recuperacao",
    ),
    path("demo/", demo_login_view, name="demo-login"),
    path("onboarding/", onboarding_view, name="onboarding"),
    path("", index_view, name="index_spa"),
    path("dashboard/", spa_view, name="dashboard-spa"),
    path("empregados/", spa_view, name="empregados-spa"),
    path("agenda/", spa_view, name="agenda-spa"),
    path("agenda/analises/", spa_view, name="agenda-analises-spa"),
    path("agenda/producao/", spa_view, name="agenda-producao-spa"),
    path("estoque/", spa_view, name="estoque-spa"),
    path("vendas/", spa_view, name="vendas-spa"),
    path("apiario/", spa_view, name="apiario-spa"),
    path("armazem/", spa_view, name="armazem-spa"),
    path("pecuaria/", spa_view, name="pecuaria-spa"),
    path("financeiro/", spa_view, name="financeiro-spa"),
    path("gestao/central/", central_gestao, name="central-gestao"),
    path("compras/", spa_view, name="compras-spa"),
    path("maquinarios/", spa_view, name="maquinarios-spa"),
    path("novidades/", spa_view, name="novidades-spa"),
    path("visao-geral/", spa_view, name="visao-geral-spa"),
    path("gestao/", spa_view, name="gestao-spa"),
    path("perfil/", spa_view, name="perfil-spa"),
    path("cadastro/cultura/", cadastro_cultura_view, name="cadastro-cultura"),
    path("cadastro/safra/", cadastro_safra_view, name="cadastro-safra"),
    path("cadastro/insumo/", cadastro_insumo_view, name="cadastro-insumo"),
    path(
        "cadastro/funcionario/", cadastro_funcionario_view, name="cadastro-funcionario"
    ),
    path(
        "funcionario/adicionar/",
        adicionar_funcionario_view,
        name="adicionar-funcionario",
    ),
    path("cadastro/animal/", cadastro_animal_view, name="cadastro-animal"),
    path("cadastro/talhao/", cadastro_talhao_view, name="cadastro-talhao"),
    path("cadastro/maquinario/", cadastro_maquinario_view, name="cadastro-maquinario"),
    path("cadastro/financeiro/", cadastro_financeiro_view, name="cadastro-financeiro"),
    path("cadastro/estoque/", cadastro_estoque_view, name="cadastro-estoque"),
    path("cadastro/apiario/", cadastro_apiario_view, name="cadastro-apiario"),
    path("cadastro/aquatico/", cadastro_aquatico_view, name="cadastro-aquatico"),
    path(
        "cadastro/propriedade/", cadastro_propriedade_view, name="cadastro-propriedade"
    ),
    path("cadastro/caminhao/", cadastro_caminhao_view, name="cadastro-caminhao"),
    path("cadastro/rota/", cadastro_rota_view, name="cadastro-rota"),
    # Estas tres eram `lambda r: render(r, ...)` soltas no urlpatterns, sem
    # `@login_required`. Serviam a pagina inteira a qualquer visitante
    # anonimo, enquanto as paginas irmas (`iot/sensores/`, `iot/dispositivos/`)
    # redirecionavam para o login. AnonymousUser e' um objeto valido para
    # `render`, entao nada reclamava — o unico sintoma era a pagina aparecer
    # para quem nao devia ver.
    #
    # O `@login_required` vai na rota, e nao dentro da lambda, para ficar
    # visivel na mesma linha que declara a rota. Ver o teste
    # `tests/test_iot_exige_login.py`.
    path(
        "iot/telemetria/",
        login_required(lambda r: render(r, "iot-telemetria.html")),
        name="iot-telemetria",
    ),
    path(
        "iot/alertas/",
        login_required(lambda r: render(r, "iot-alertas.html")),
        name="iot-alertas",
    ),
    path(
        "iot/comandos/",
        login_required(lambda r: render(r, "iot-comandos.html")),
        name="iot-comandos",
    ),
    path(
        "cadastro/receituario/", cadastro_receituario_view, name="cadastro-receituario"
    ),
    path("cadastro/vra/", cadastro_vra_view, name="cadastro-vra"),
    path("cadastro/mip/", cadastro_mip_view, name="cadastro-mip"),
    path("mapa/", mapa_view, name="mapa"),
    # Section pages
    path(
        "simulador/financeiro/", simulador_financeiro_view, name="simulador-financeiro"
    ),
    path("simulador/colheita/", simulador_colheita_view, name="simulador-colheita"),
    path("simulador-lucro/", simulador_lucro_view, name="simulador_lucro"),
    path("financeiro/dre/", dre_view, name="dre_view"),
    path("financeiro/cashflow/", cashflow_view, name="cashflow_view"),
    path("api/exportar-lcdpr/", exportar_lcdpr_view, name="exportar-lcdpr"),
    path(
        "financeiro/comparativo-safras/",
        comparativo_safras_view,
        name="comparativo_safras_view",
    ),
    path("agenda/agricola/", agenda_agricola_view, name="agenda-agricola"),
    path("agenda/pecuaria/", agenda_pecuaria_view, name="agenda-pecuaria"),
    path("setor/campo/", setor_campo_view, name="setor-campo"),
    path("setor/estoque/", setor_estoque_view, name="setor-estoque"),
    path("alertas/criticos/", alertas_criticos_view, name="alertas-criticos"),
    path("alertas/info/", alertas_info_view, name="alertas-info"),
    path("animais/gado/", animais_gado_view, name="animais-gado"),
    path("animais/racoes/", racoes_nutricao_view, name="racoes-nutricao"),
    path("dashboard/os/", dashboard_os_view, name="dashboard-os"),
    path("dashboard/resumo/", resumo_gerencial_view, name="resumo-gerencial"),
    path("previsao/clima/", previsao_clima_view, name="previsao-clima"),
    path("previsao/safra/", previsao_safra_view, name="previsao-safra"),
    path("iot/sensores/", sensores_view, name="sensores"),
    path("iot/dispositivos/", dispositivos_view, name="dispositivos"),
    path("telemetria/", telemetria_view, name="telemetria"),
    path("ia/registros/", ia_registros_view, name="ia-registros"),
    # Agronomia (BUILD 08 UI)
    path("agronomia/ndvi/", ndvi_view, name="ndvi-view"),
    path("agronomia/compliance/", compliance_view, name="compliance-view"),
    path("servidor/", servidor_dashboard_view, name="servidor-dashboard"),
    path("servidor/estoque/", servidor_estoque_view, name="servidor-estoque"),
    path("servidor/agenda/", servidor_agenda_view, name="servidor-agenda"),
    path("servidor/alertas/", servidor_alertas_view, name="servidor-alertas"),
    path("api/servidor/config/", servidor_config_api, name="servidor-config"),
    path("equipe/agenda/", equipe_agenda_view, name="equipe-agenda"),
    path("equipe/empregados/", equipe_empregados_view, name="equipe-empregados"),
    path("estoque/geral/", estoque_geral_view, name="estoque-geral"),
    path("estoque/insumos/", estoque_insumos_view, name="estoque-insumos"),
    path("logistica/caminhoes/", logistica_caminhao_view, name="logistica-caminhao"),
    path("logistica/rotas/", logistica_rotas_view, name="logistica-rotas"),
    path("perfil/config/", perfil_config_view, name="perfil-config"),
    # As culturas escolhidas, por propriedade. `name=` é o que o template usa
    # para montar o URL — sem reversing, o id da propriedade fica colado no
    # HTML e a rota passa a ter duasTruths.
    path(
        "perfil/culturas/<int:pk>/",
        culturas_propriedade_api,
        name="culturas-propriedade",
    ),
    path("config/dia/", config_dia_view, name="config-dia"),
    path("config/noturno/", config_noturno_view, name="config-noturno"),
    path("config/sistema/", config_sistema_view, name="config-sistema"),
    path("config/page/", config_page_view, name="config-page"),
    path("erro/", erro_report_view, name="erro-report"),
    path("avaliador/", avaliador_login, name="avaliador-login"),
    # Culture guide pages
    path("guias/vegetal/", guia_vegetal_view, name="guia-vegetal"),
    path("guias/vegetal/cafe/", registro_cafe_view, name="registro-cafe"),
    path("registro/cafe/", registro_cafe_view, name="registro-cafe-alias"),
    # Generico — qualquer cultura herda painel cafe (premium, fluido, sofisticado)
    path(
        "guias/vegetal/<slug:cultura_slug>/",
        registro_cultura_view,
        name="registro-cultura",
    ),
    # Detalhe por guia: redireciona para a guia correta conforme o grupo da cultura
    path(
        "guias/animal/<slug:cultura_slug>/",
        registro_cultura_view,
        name="registro-cultura-animal",
    ),
    path(
        "guias/aquatica/<slug:cultura_slug>/",
        registro_cultura_view,
        name="registro-cultura-aquatica",
    ),
    path(
        "registro/<slug:cultura_slug>/",
        registro_cultura_view,
        name="registro-cultura-alias",
    ),
    path("guias/animal/", guia_animal_view, name="guia-animal"),
    path("guias/aquatica/", guia_aquatica_view, name="guia-aquatica"),
    path("guias/sistemas/", guia_sistemas_view, name="guia-sistemas"),
    # MEDIDO 2026-10-06: abrir uma carta de "Outras Culturas" empurrava
    # `/guias/sistemas/<id>/` — e nao havia rota para ela. O painel abria por
    # JS, mas recarregar esse URL dava 404, e o link nao podia ser
    # partilhado nem guardado nos favoritos. `animal` e `aquatica` ja tinham
    # a sua; `sistemas` ficou de fora.
    #
    # E' a unica das tres cujas cartas NAO sao de uma cultura com `grupo`
    # animal/aquatica: sao culturas vegetais mostradas noutro separador. Por
    # isso nao redirecciona para a guia vegetal como as outras — quem abriu
    # estava em Sistemas, e e' para la que volta.
    path(
        "guias/sistemas/<slug:cultura_slug>/",
        registro_cultura_sistemas_view,
        name="registro-cultura-sistemas",
    ),
    path("guias/ferramentas/", guia_ferramentas_view, name="guia-ferramentas"),
    path(
        "api/talhoes-por-propriedade/", get_talhoes_api, name="talhoes-por-propriedade"
    ),
    path("api/ia/web-search/", ia_web_search, name="ia-web-search"),
    # Operário / Servidor Kanban (mesma view, hierarquia filtra)
    path("operario/kanban/", operario_kanban_view, name="operario-kanban"),
    path("servidor/kanban/", operario_kanban_view, name="servidor-kanban"),
    path("operario/perfil/", operario_perfil_view, name="operario-perfil"),
    path("operario/registrar/", operario_registrar_view, name="operario-registrar"),
    path(
        "operario/api/criar-login/", operario_criar_login, name="operario-criar-login"
    ),
    path(
        "operario/api/remover-login/",
        operario_remover_login,
        name="operario-remover-login",
    ),
    # Associação dedicada de tarefas (produtor + servidor)
    path("tarefas/associacao/", tarefas_associacao_view, name="tarefas-associacao"),
    path("api/tarefas/associar/", tarefas_associacao_api, name="api-tarefas-associar"),
    # Rastreabilidade & Custos (Plano v2.0)
    path("rastreabilidade/", rastreabilidade_view, name="rastreabilidade-lista"),
    path("custos/producao/", custos_producao_view, name="custos-producao"),
    path(
        "custos/orcado-realizado/",
        orcamento_realizado_view,
        name="orcamento-realizado",
    ),
    path("custos/dre/", dre_custo_view, name="dre-view"),
    path("custos/centros/", centros_custo_view, name="cadastro-centro-custo"),
    path("pitch/", pitch_view, name="pitch"),
    path("simulador/lucro/", simulador_lucro_view, name="simulador-lucro"),
    path("privacidade/", privacidade_view, name="privacidade"),
    path("lgpd/export/", lgpd_export_data, name="lgpd-export"),
    path("lgpd/delete/", lgpd_delete_data, name="lgpd-delete"),
    # `admin/tenant/` NAO vive aqui: ver o comentario em config/urls.py. Este
    # ficheiro e' incluido DEPOIS de `admin.site.urls`, e o catch-all do admin
    # do Django engolia a rota. Registada antes, em config/urls.py.
    path("api/nfe/import/", nfe_import, name="nfe-import"),
    path("api/lote/<int:lote_id>/qr/", lote_qr, name="lote-qr"),
    path("api/theme/", theme_api, name="api-theme"),
    path("controle/", controle_absoluto_view, name="controle-absoluto"),
    path("sw.js", pwa_sw, name="pwa-sw"),
    path(".well-known/<path:path>", wellknown_dummy, name="wellknown"),
    path("manifest.json", pwa_manifest, name="pwa-manifest"),
]
