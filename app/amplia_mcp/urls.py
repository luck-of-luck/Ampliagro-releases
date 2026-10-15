from django.urls import path

from app.amplia_mcp import views as mcp_views
from app.api.views import amplia_palco as palco_views

app_name = "amplia_mcp"

urlpatterns = [
    # nome sem prefixo /api/amplia porque o include ja o traz
    path("tools/", mcp_views.tools, name="tools"),
    path("exec/", mcp_views.exec, name="exec"),
    path("contexto/", mcp_views.ctx, name="contexto"),
    # O vocabulario que o modelo local le. `/tools/` e' o catalogo completo —
    # 34 KB, ~8 700 tokens medidos — e nao cabe na janela de 4 096 do SmolLM2
    # de 1,7 B que roda na aba. Este e' o texto derivado que cabe, e e'
    # derivado a cada chamada: um intent novo aparece aqui sem ninguem
    # editar nada. Ver FILA #27.
    path("vocabulario/", mcp_views.vocabulario_view, name="vocabulario"),
    # As duas surfaces que faltavam, todas de LEITURA e todas derivadas do
    # codigo — nenhum destino novo, nenhuma segunda lista de verdade:
    #
    #   skills/       as especialidades de dominio (campo, financas, IoT) e
    #                 os intents que cada uma cobre. Viviam em
    #                 `app/ia/skills/*.md` desde o BUILD 16 e nao tinham
    #                 porta nenhuma fora da aba do browser. Hoje dizem, com
    #                 honestidade, que 15 dos 15 handlers declarados nao
    #                 existem (FILA #43).
    #   diagnostico/  a aritmetica da propria camada, com os invariantes do
    #                 contrato. Para uma IA (ou um humano) descobrir que o
    #                 caminho esta inteiro sem abrir ficheiros.
    path("skills/", mcp_views.skills_view, name="skills"),
    path("diagnostico/", mcp_views.diagnostico, name="diagnostico"),
    # ingestao: so leitura, devolve sinais. Nao executa nada.
    path(
        "ingestao/audio/sinais/",
        mcp_views.audio_sinais,
        name="audio_sinais",
    ),
    # Motor proativo: a fila que entrega o cenario ao modelo do navegador.
    # `pendente` entrega UM cenario e toma o lease; `devolver` devolve sem
    # alerta, para o cenario voltar a fila.
    path(
        "proativo/pendente/",
        mcp_views.proativo_pendente,
        name="proativo_pendente",
    ),
    path(
        "proativo/devolver/",
        mcp_views.proativo_devolver,
        name="proativo_devolver",
    ),
    # A outra metade do motor: o produtor LENDO o que o motor pensou.
    # `alertas` traz o raciocinio (evidencia) junto do aviso; `visto` fecha.
    path(
        "alertas/pendentes/",
        mcp_views.proativo_alertas,
        name="proativo_alertas",
    ),
    path(
        "alertas/visto/",
        mcp_views.proativo_alerta_visto,
        name="proativo_alerta_visto",
    ),
    # BUILD 5 — o palco "Amplia": a mesa de operação que a IA monta.
    #
    # As vistas vivem em `app/api/views/amplia_palco.py` e NÃO aqui. Este
    # ficheiro é pequeno e é meu; `app/api/urls.py` e `app/api/views/user.py`
    # estão a ser editados por outra sessão, e tocar neles seria uma colisão.
    # O registo é feito aqui só para fixar o prefixo `/api/amplia/` sem tocar
    # num único byte do registo partilhado.
    path(
        "palco/render/",
        palco_views.palco_render,
        name="palco_render",
    ),
    path(
        "palco/avaliar/",
        palco_views.palco_avaliar,
        name="palco_avaliar",
    ),
    path(
        "palco/clonar/",
        palco_views.palco_clonar,
        name="palco_clonar",
    ),
    path(
        "palco/info/",
        palco_views.palco_info,
        name="palco_info",
    ),
    # O Chamado Amplia — a peça que a IA escreve. `GET` só: a escrita passa por
    # `sandbox.executar`, que é o caminho único que audita e que confirma com o
    # produtor. Um POST de escrita aqui seria o segundo caminho que esta camada
    # existe para não ter.
    path(
        "palco/chamado/",
        palco_views.palco_chamado,
        name="palco_chamado",
    ),
]
