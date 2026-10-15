from django.contrib import admin

from app.models import (
    Animal,
    ApiarioColmeia,
    AplicacaoInsumo,
    CentroCusto,
    Cultura,
    CustoProducao,
    DashboardUserState,
    EstoqueItem,
    Funcionario,
    Insumo,
    LancamentoDetalhado,
    LancamentoFinanceiro,
    Maquinario,
    MovimentoEstoque,
    PerfilUsuario,
    ProducaoAnimal,
    ProducaoApiario,
    Propriedade,
    RastreabilidadeSafra,
    RastroItem,
    Safra,
    Talhao,
    WidgetUsuario,
)

admin.site.register(Cultura)
admin.site.register(Propriedade)
admin.site.register(Talhao)
admin.site.register(Safra)
admin.site.register(Insumo)
admin.site.register(AplicacaoInsumo)
admin.site.register(Funcionario)
admin.site.register(Maquinario)
admin.site.register(LancamentoFinanceiro)
admin.site.register(Animal)
admin.site.register(ProducaoAnimal)
admin.site.register(EstoqueItem)
admin.site.register(ApiarioColmeia)
admin.site.register(ProducaoApiario)
admin.site.register(WidgetUsuario)
admin.site.register(PerfilUsuario)
admin.site.register(DashboardUserState)


@admin.register(RastroItem)
class RastroItemAdmin(admin.ModelAdmin):
    list_display = (
        "insumo",
        "propriedade",
        "numero_lote",
        "quantidade_recebida",
        "saldo",
        "data_validade",
        "vencido",
    )
    list_filter = ("propriedade", "data_validade")
    search_fields = ("numero_lote", "numero_serie", "nf_entrada", "insumo__nome")


@admin.register(MovimentoEstoque)
class MovimentoEstoqueAdmin(admin.ModelAdmin):
    list_display = (
        "rastro_item",
        "tipo",
        "quantidade",
        "data_movimento",
        "funcionario",
    )
    list_filter = ("tipo",)


@admin.register(RastreabilidadeSafra)
class RastreabilidadeSafraAdmin(admin.ModelAdmin):
    list_display = (
        "safra",
        "insumo_efetivo",
        "talhao_efetivo",
        "quantidade_aplicada",
        "custo_total",
        "data_aplicacao",
    )


@admin.register(CentroCusto)
class CentroCustoAdmin(admin.ModelAdmin):
    list_display = ("nome", "propriedade", "tipo", "ativo")
    list_filter = ("tipo", "ativo")


@admin.register(CustoProducao)
class CustoProducaoAdmin(admin.ModelAdmin):
    list_display = (
        "safra",
        "talhao",
        "custo_total",
        "custo_por_ha",
        "custo_por_saca",
        "margem",
    )
    readonly_fields = (
        "custo_total",
        "custo_por_ha",
        "custo_por_saca",
        "lucro",
        "margem",
    )


@admin.register(LancamentoDetalhado)
class LancamentoDetalhadoAdmin(admin.ModelAdmin):
    list_display = (
        "lancamento",
        "categoria_detalhada",
        "centro_custo",
        "safra",
        "valor_rateado",
    )
    list_filter = ("categoria_detalhada",)
