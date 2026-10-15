from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    CultivarViewSet,
    LoteSementeViewSet,
    EnsaioCultivarViewSet,
    FaixaEnsaioViewSet,
    ViveiroViewSet,
    LoteMudaViewSet,
    MixPastagemViewSet,
    AlertaTelemetriaViewSet,
    AnimalIndividualViewSet,
    AnimalViewSet,
    ApiarioColmeiaViewSet,
    AplicacaoInsumoViewSet,
    AtividadePlanejadaViewSet,
    CentroCustoViewSet,
    CulturaViewSet,
    CustoProducaoViewSet,
    DespescaViewSet,
    ErroReportViewSet,
    EstacaoMeteoViewSet,
    EstagioCulturaViewSet,
    EstoqueItemViewSet,
    EventoSanitarioViewSet,
    FotoViewSet,
    FuncionarioViewSet,
    InsumoViewSet,
    InventarioItemViewSet,
    InventarioViewSet,
    LancamentoDetalhadoViewSet,
    LancamentoFinanceiroViewSet,
    LeituraSensorViewSet,
    LoteAquaticoViewSet,
    MaquinarioViewSet,
    MovimentacaoEstoqueViewSet,
    MovimentoEstoqueViewSet,
    NotaViewSet,
    OperarioRegistroViewSet,
    OrdemCompraViewSet,
    PerfilUsuarioViewSet,
    PesagemViewSet,
    PiqueteViewSet,
    PlanoSafraViewSet,
    ProducaoAnimalViewSet,
    ProducaoApiarioViewSet,
    PropriedadeViewSet,
    ProtocoloSanitarioViewSet,
    RacaoViewSet,
    RastreabilidadeSafraViewSet,
    RastreabilidadeSafraViewSet2,
    RastroItemViewSet,
    RastroItemViewSet2,
    ReceituarioViewSet,
    RegistroProducaoViewSet,
    RegraAlertaViewSet2,
    RelatorioGeradoViewSet,
    RelatorioTemplateViewSet,
    SafraViewSet,
    TalhaoGeometriaViewSet,
    TalhaoViewSet,
    TarefaEstagioViewSet,
    TelemetryDataViewSet,
    WidgetUsuarioViewSet,
    agenda_analises_data,
    agenda_data,
    agenda_producao_data,
    alertas_config,
    apiario_data,
    armazem_data,
    busca_geral_data,
    caminhoes_data,
    cashflow_data,
    commodities_data,
    comparativo_safras_data,
    compras_data,
    contexto_ia_data,
    cotacoes_data,
    custo_producao_data,
    dashboard_data,
    dashboard_state,
    dispositivos_data,
    dre_data,
    estoque_data,
    export_dashboard_csv,
    export_dashboard_excel,
    financeiro_data,
    funcionarios_data,
    gerar_relatorio,
    gestao_data,
    healthz,
    ibge_proxy_data,
    ibge_ufs,
    lcdpr_download,
    lcdpr_diagnostico_api,
    lcdpr_gerar_arquivo,
    leituras_sensor_data,
    maquinarios_data,
    notificacao_ler,
    notificacoes_data,
    novidades_data,
    onboarding_save,
    pecuaria_data,
    perfil_data,
    previsao_clima_data,
    previsao_safra_data,
    relatorio_status,
    rotas_data,
    salvar_geometria,
    sensores_data,
    simulacao_data,
    talhoes_geometria_fc,
    vendas_data,
    visao_geral_data,
    weather_forecast,
    weather_integracao,
    widget_data,
    widgets_layout_sync,
)
from .views.agronomia import (
    clima_historico_data,
    clima_previsao_data,
    compliance_ambiental_data,
    ndvi_heatmap,
    ndvi_talhao_data,
)
from .views.credito import CapacidadePagamentoViewSet
from .views.financeiro_banco import (
    ConciliacaoBancariaViewSet,
    ContaBancariaViewSet,
    MovimentacaoBancariaViewSet,
    NotificacaoTemplateViewSet,
    ParcelamentoViewSet,
    PushSubscriptionViewSet,
)
from .views.mip import MonitoramentoPragaViewSet
from .views.vra import PrescricaoVRAViewSet, ZARCViewSet

# Caderno de Campo. O import fica aqui, e nao dentro de `from .views import *`,
# porque `app/api/views/__init__.py` não o reexporta — e essa omissão é
# exactamente o que mantinha o Caderno como feature fantasma: modelo, migration
# e viewset existiam, e o POST do `pwa/sync.js` levava 404 na mesma.
#
# Houve uma versao deste ficheiro com o mesmo import duplicado: nao dava erro,
# e era por isso que era pior — duas linhas para apagar, e nada que o dissesse.
from .views.caderno import nota_create, nota_fotos, nota_voice
from .views.custo_talhao_view import custo_por_talhao_data
from .views.experimento import ExperimentoViewSet, MedicaoExperimentalViewSet
from .views.financeiro_banco import (
    ConciliacaoBancariaViewSet,
    ContaBancariaViewSet,
    MovimentacaoBancariaViewSet,
    NotificacaoTemplateViewSet,
    ParcelamentoViewSet,
    PushSubscriptionViewSet,
)
from .views.mip import MonitoramentoPragaViewSet
from .views.vra import PrescricaoVRAViewSet, ZARCViewSet

router = DefaultRouter()

router.register(r"culturas", CulturaViewSet)
router.register(r"propriedades", PropriedadeViewSet, basename="propriedade")
router.register(r"talhoes", TalhaoViewSet, basename="talhao")
router.register(r"safras", SafraViewSet, basename="safra")
router.register(r"insumos", InsumoViewSet, basename="insumo")
router.register(
    r"aplicacoes-insumo", AplicacaoInsumoViewSet, basename="aplicacao-insumo"
)
router.register(r"funcionarios", FuncionarioViewSet, basename="funcionario")
router.register(r"operarios", OperarioRegistroViewSet, basename="operario")
router.register(r"maquinarios", MaquinarioViewSet, basename="maquinario")
router.register(r"lancamentos", LancamentoFinanceiroViewSet, basename="lancamento")
router.register(r"animais", AnimalViewSet, basename="animal")
router.register(r"producao-animal", ProducaoAnimalViewSet, basename="producao-animal")
router.register(r"racoes", RacaoViewSet, basename="racao")
router.register(r"lotes-aquaticos", LoteAquaticoViewSet, basename="lote-aquatico")
router.register(r"despescas", DespescaViewSet, basename="despesca")
router.register(r"estoque", EstoqueItemViewSet, basename="estoque")
router.register(r"colmeias", ApiarioColmeiaViewSet, basename="colmeia")
router.register(
    r"producao-apiario", ProducaoApiarioViewSet, basename="producao-apiario"
)
router.register(r"widgets-usuario", WidgetUsuarioViewSet, basename="widgets-usuario")
router.register(r"perfis-usuario", PerfilUsuarioViewSet, basename="perfil-usuario")
router.register(r"estacoes-meteo", EstacaoMeteoViewSet, basename="estacao-meteo")
router.register(r"leituras-sensor", LeituraSensorViewSet, basename="leitura-sensor")
router.register(
    r"talhoes-geometria", TalhaoGeometriaViewSet, basename="talhao-geometria"
)
router.register(
    r"relatorios-template", RelatorioTemplateViewSet, basename="relatorio-template"
)
router.register(
    r"relatorios-gerados", RelatorioGeradoViewSet, basename="relatorio-gerado"
)
router.register(
    r"registros-producao", RegistroProducaoViewSet, basename="registro-producao"
)
router.register(r"erros", ErroReportViewSet, basename="erro-report")
router.register(r"caderno/notas", NotaViewSet, basename="caderno-nota")
router.register(r"caderno/fotos", FotoViewSet, basename="caderno-foto")
router.register(r"estagios-cultura", EstagioCulturaViewSet, basename="estagio-cultura")
router.register(r"tarefas-estagio", TarefaEstagioViewSet, basename="tarefa-estagio")
router.register(r"rastros", RastroItemViewSet, basename="rastro")
router.register(
    r"movimentos-estoque", MovimentoEstoqueViewSet, basename="movimento-estoque"
)
router.register(r"rastro-safra", RastreabilidadeSafraViewSet, basename="rastro-safra")
router.register(r"prescricoes-vra", PrescricaoVRAViewSet, basename="prescricao-vra")
router.register(r"experimentos", ExperimentoViewSet, basename="experimento")
router.register(
    r"medicoes-experimentais",
    MedicaoExperimentalViewSet,
    basename="medicao-experimental",
)
router.register(
    r"monitoramentos-praga", MonitoramentoPragaViewSet, basename="monitoramento-praga"
)
router.register(r"zarc", ZARCViewSet, basename="zarc")
router.register(r"centros-custo", CentroCustoViewSet, basename="centro-custo")
router.register(r"custos-producao", CustoProducaoViewSet, basename="custo-producao")
# Aliases: JS chama por estes nomes (mesmo viewset, segunda rota)
router.register(
    r"custo-producao", CustoProducaoViewSet, basename="custo-producao-alias"
)
router.register(r"rastro-itens", RastroItemViewSet, basename="rastro-itens-alias")
router.register(
    r"rastreabilidade", RastreabilidadeSafraViewSet, basename="rastreabilidade-alias"
)
router.register(
    r"relatorio-templates",
    RelatorioTemplateViewSet,
    basename="relatorio-templates-alias",
)
# Viewsets mecânicos (app/api/views/faltantes.py) — endpoints que o JS chama
router.register(
    r"alertas-telemetria", AlertaTelemetriaViewSet, basename="alerta-telemetria"
)
router.register(
    r"animais-individuais", AnimalIndividualViewSet, basename="animal-individual"
)
router.register(
    r"eventos-sanitarios", EventoSanitarioViewSet, basename="evento-sanitario"
)
router.register(r"inventarios", InventarioViewSet, basename="inventario")
router.register(r"inventario-itens", InventarioItemViewSet, basename="inventario-item")
router.register(
    r"movimentacoes-estoque",
    MovimentacaoEstoqueViewSet,
    basename="movimentacao-estoque",
)
router.register(r"ordens-compra", OrdemCompraViewSet, basename="ordem-compra")
router.register(r"pesagens", PesagemViewSet, basename="pesagem")
router.register(r"piquetes", PiqueteViewSet, basename="piquete")
router.register(r"atividades", AtividadePlanejadaViewSet, basename="atividade")
router.register(r"planos-safra", PlanoSafraViewSet, basename="plano-safra")
router.register(
    r"protocolos-sanitarios", ProtocoloSanitarioViewSet, basename="protocolo-sanitario"
)
router.register(r"receituarios", ReceituarioViewSet, basename="receituario")
router.register(r"regras-alerta", RegraAlertaViewSet2, basename="regra-alerta")
router.register(r"telemetria", TelemetryDataViewSet, basename="telemetria")
router.register(
    r"lancamentos-detalhados",
    LancamentoDetalhadoViewSet,
    basename="lancamento-detalhado",
)
router.register(r"contas-bancarias", ContaBancariaViewSet, basename="conta-bancaria")
router.register(
    r"movimentacoes-bancarias",
    MovimentacaoBancariaViewSet,
    basename="movimentacao-bancaria",
)
router.register(r"parcelamentos", ParcelamentoViewSet, basename="parcelamento")
router.register(
    r"conciliacoes-bancarias",
    ConciliacaoBancariaViewSet,
    basename="conciliacao-bancaria",
)
router.register(
    r"push-subscriptions", PushSubscriptionViewSet, basename="push-subscription"
)
router.register(
    r"notificacao-templates",
    NotificacaoTemplateViewSet,
    basename="notificacao-template",
)
# G-01..G-06 plano-correcao
router.register(r"cultivares", CultivarViewSet, basename="cultivar")
router.register(r"lotes-semente", LoteSementeViewSet, basename="lotesemente")
router.register(r"ensaios-cultivar", EnsaioCultivarViewSet, basename="ensaiocultivar")
router.register(r"faixas-ensaio", FaixaEnsaioViewSet, basename="faixaensaio")
router.register(r"viveiros", ViveiroViewSet, basename="viveiro")
router.register(r"lotes-muda", LoteMudaViewSet, basename="lotemuda")
router.register(r"mixes-pastagem", MixPastagemViewSet, basename="mixpastagem")

# Dados de crédito rural (item nº 1 do plano, §21.3). Read-only e NÃO decide
# crédito: entrega fatores observáveis com a fonte de cada um, e a decisão é
# da instituição financeira. Ver `app/api/views/credito.py`.
router.register(
    r"credito",
    CapacidadePagamentoViewSet,
    basename="capacidade-pagamento",
)

urlpatterns = [
    path("healthz/", healthz, name="api-healthz"),
    path("dashboard/", dashboard_data, name="api-dashboard"),
    path("dashboard-state/", dashboard_state, name="api-dashboard-state"),
    path("widgets-layout-sync/", widgets_layout_sync, name="widgets-layout-sync"),
    # `/api/estoque/` e `/api/maquinarios/` NAO sao registados aqui de
    # propósito: pertencem ao router, aos ViewSets CRUD.
    #
    # Estas duas `path()` já ocupavam os mesmos caminhos e vinham DEPOIS do
    # `router.register()` (linhas 148 e 141). Em Django a última registo ganha,
    # e estas vinham depois — logo `/api/estoque/` resolvia para
    # `estoque_data`, que é `@api_view(["GET"])`, e o `EstoqueItemViewSet`
    # ficava INALCANÇAVEL. O mesmo em maquinarios.
    #
    # O estrago era real, nos dois sentidos:
    #   - `cadastro-estoque.html:191` faz POST `/api/estoque/`  -> 405
    #   - `cadastro-estoque.html:200` faz DELETE `/api/estoque/{id}/` -> 405
    #   - `cadastro-maquinario.html:257` faz POST `/api/maquinarios/` -> 405
    #   - `estoque-geral.html:115` faz `itens.forEach` sobre a resposta, mas
    #     `estoque_data` devolve um OBJECTO `{itens, ...}`, nao um array
    #
    # Ou seja: o cadastro de estoque e de maquinas estava partido, e as
    # paginas de lista também. O ViewSet sombreado e' exactamente o que o
    # frontend espera.
    #
    # O agregado continua disponivel, no nome que a casa ja usa para isto:
    # `funcionarios-resumo/` (linha 264) ao lado de `/api/funcionarios/`.
    path("estoque-resumo/", estoque_data, name="api-estoque-resumo"),
    path("financeiro/", financeiro_data, name="api-financeiro"),
    path("funcionarios-resumo/", funcionarios_data, name="api-funcionarios-resumo"),
    path("gestao/", gestao_data, name="api-gestao"),
    path("visao-geral/", visao_geral_data, name="api-visao-geral"),
    path("pecuaria/", pecuaria_data, name="api-pecuaria"),
    path("armazem/", armazem_data, name="api-armazem"),
    path("compras/", compras_data, name="api-compras"),
    path("novidades/", novidades_data, name="api-novidades"),
    path("perfil/", perfil_data, name="api-perfil"),
    path("agenda/", agenda_data, name="api-agenda"),
    path("agenda-analises/", agenda_analises_data, name="api-agenda-analises"),
    # Caderno de Campo. O `pwa/sync.js` chamava estas tres rotas e nenhuma
    # existia: a nota de campo ficava no IndexedDB do aparelho e nunca
    # chegava ao servidor. `notas/` grava; `fotos/` e `voice/` devolvem 501
    # com a lista do que falta, em vez de 404 que a app nao distingue de
    # "feature inexistente". Ver `app/api/views/caderno.py`.
    path("caderno/notas/", nota_create, name="api-caderno-notas"),
    path("caderno/fotos/", nota_fotos, name="api-caderno-fotos"),
    path("caderno/voice/", nota_voice, name="api-caderno-voice"),
    path("agenda-producao/", agenda_producao_data, name="api-agenda-producao"),
    path("vendas/", vendas_data, name="api-vendas"),
    path("apiario/", apiario_data, name="api-apiario"),
    # Ver a nota em `estoque-resumo/`: `/api/maquinarios/` pertence ao router
    # (`MaquinarioViewSet`, registo na linha 141) e esta `path()` sombreava-o.
    # O agregado passa a `maquinarios-resumo/`, como `funcionarios-resumo/`.
    path("maquinarios-resumo/", maquinarios_data, name="api-maquinarios-resumo"),
    path("commodities/", commodities_data, name="api-commodities"),
    path("weather/", weather_forecast, name="api-weather"),
    path("widget-data/", widget_data, name="api-widget-data"),
    path("weather-integracao/", weather_integracao, name="api-weather-integracao"),
    path("leituras-sensor/", leituras_sensor_data, name="api-leituras-sensor"),
    path("export/csv/", export_dashboard_csv, name="api-export-csv"),
    path("export/excel/", export_dashboard_excel, name="api-export-excel"),
    path("notificacoes/", notificacoes_data, name="api-notificacoes"),
    path("notificacao/<int:pk>/ler/", notificacao_ler, name="api-notificacao-ler"),
    path("alertas-config/", alertas_config, name="api-alertas-config"),
    path("onboarding/save/", onboarding_save, name="api-onboarding-save"),
    path("relatorio/gerar/", gerar_relatorio, name="api-relatorio-gerar"),
    path("relatorio/<int:pk>/status/", relatorio_status, name="api-relatorio-status"),
    path("ibge-proxy/", ibge_proxy_data, name="api-ibge-proxy"),
    path("spa/ibge/ufs/", ibge_ufs, name="api_ibge_ufs"),
    path("spa/ibge/proxy/", ibge_proxy_data, name="api_ibge_proxy_data"),
    path("financeiro/dre/", dre_data, name="api_dre_data"),
    path("financeiro/cashflow/", cashflow_data, name="api_cashflow_data"),
    path("simulacao/", simulacao_data, name="api-simulacao"),
    path("financeiro/lcdpr/download/", lcdpr_download, name="api_lcdpr_download"),
    path("financeiro/lcdpr/gerar/", lcdpr_gerar_arquivo, name="api_lcdpr_gerar"),
    path(
        "financeiro/lcdpr/diagnostico/",
        lcdpr_diagnostico_api,
        name="api_lcdpr_diagnostico",
    ),
    path(
        "financeiro/custo-producao/",
        custo_producao_data,
        name="api_custo_producao_data",
    ),
    # Orcado x realizado POR TALHAO. Nao confundir com o `custo-producao`
    # acima: aquele e' por SAFRA e le a tabela `CustoProducao`; este le
    # `LancamentoFinanceiro` direto e e' o unico que responde "gastei mais
    # do que orcei, e onde".
    #
    # `custo-talhao` e nao `custo-por-talhao` para nao colidir com o router
    # `talhoes` nem com nenhum `path("custo...", ...)`. A URL e' longa de
    # proposito: uma rota curta e' uma rota que um dia sombrea outra, que e'
    # o que aconteceu com `estoque/` e custou uma tarde.
    path(
        "financeiro/custo-talhao/",
        custo_por_talhao_data,
        name="api_custo_por_talhao",
    ),
    path(
        "financeiro/comparativo-safras/",
        comparativo_safras_data,
        name="api_comparativo_safras_data",
    ),
    path("financeiro/cotacoes/", cotacoes_data, name="api_cotacoes_data"),
    # Agronomia (BUILD 08)
    path(
        "agronomia/clima/previsao/", clima_previsao_data, name="api_clima_previsao_data"
    ),
    path(
        "agronomia/clima/historico/",
        clima_historico_data,
        name="api_clima_historico_data",
    ),
    path("agronomia/ndvi/", ndvi_talhao_data, name="api_ndvi_talhao_data"),
    path(
        "talhao/<int:talhao_id>/ndvi-heatmap/",
        ndvi_heatmap,
        name="api_ndvi_heatmap",
    ),
    path(
        "agronomia/compliance/",
        compliance_ambiental_data,
        name="api_compliance_ambiental_data",
    ),
    path("ibge-ufs/", ibge_ufs, name="api-ibge-ufs"),
    path("busca-geral/", busca_geral_data, name="api-busca-geral"),
    path("contexto-ia/", contexto_ia_data, name="api-contexto-ia"),
    path("caminhoes/", caminhoes_data, name="api-caminhoes"),
    path("rotas/", rotas_data, name="api-rotas"),
    path("dispositivos/", dispositivos_data, name="api-dispositivos"),
    path("previsao-clima/", previsao_clima_data, name="api-previsao-clima"),
    path("previsao-safra/", previsao_safra_data, name="api-previsao-safra"),
    path("sensores/", sensores_data, name="api-sensores"),
    path(
        "talhoes-geometria-fc/", talhoes_geometria_fc, name="api-talhoes-geometria-fc"
    ),
    path("salvar-geometria/", salvar_geometria, name="api-salvar-geometria"),
    # O Caderno de Campo e' registado mais acima, em `:303`, junto das rotas de
    # painel. Nao se repete aqui: duas `path()` com o mesmo `name` fazem o
    # `reverse()` resolver para a ultima, e esse "funciona" e' a razao pela qual
    # a duplicacao nao dava erro — dava apenas um segundo sitio onde mexer.
    path("", include(router.urls)),
    path(
        "top-globais/<str:widget_id>/",
        __import__(
            "app.api.views.top_globais", fromlist=["top_globais_widget"]
        ).top_globais_widget,
        name="api-top-globais-widget",
    ),
    path(
        "top-globais/",
        __import__(
            "app.api.views.top_globais", fromlist=["public_top_globais_list"]
        ).public_top_globais_list,
        name="api-top-globais-list",
    ),
]
