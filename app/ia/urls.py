from django.urls import path

from app.ia import views as ia_views

urlpatterns = [
    path("intents/", ia_views.intents_catalogo, name="ia-intents"),
    path("sessao/", ia_views.sessao, name="ia-sessao"),
    path("executar/", ia_views.executar_intent, name="ia-executar"),
    path("evento/", ia_views.evento, name="ia-evento"),
    path("artefatos/", ia_views.artefatos, name="ia-artefatos"),
    path("imagem-estoque/", ia_views.imagem_estoque, name="ia-imagem-estoque"),
    path("chave/testar/", ia_views.testar_chave, name="ia-chave-testar"),
    path("ver-imagem/", ia_views.ver_imagem, name="ia-ver-imagem"),
    path("nuvem/", ia_views.conversa_nuvem, name="ia-nuvem"),
    path("confirmar-estoque/", ia_views.confirmar_estoque, name="ia-confirmar-estoque"),
    path("chave/", ia_views.chave_nuvem, name="ia-chave-nuvem"),
    path("diagnostico/", ia_views.diagnostico, name="ia-diagnostico"),
]
