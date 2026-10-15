import json
import logging
import math
import random
import traceback
from collections import defaultdict
from datetime import date, datetime, timedelta

import requests
from django.conf import settings
from django.contrib.auth import authenticate, login
from django.contrib.auth.models import User
from django.core.cache import cache
from django.db import transaction
from django.db.models import Avg, Count, F, Q, Sum
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_date
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from app.api.serializers import *
from app.cultures.seletor import ids_validos
from app.hierarquia import *
from app.models import *
from app.presets import limpar_presets_bloqueados

from .utils import *  # noqa: F403

# Fix: import * não traz nomes com _ — importar explicitamente os helpers com _
from .utils import (  # noqa: F401 — nomes com _ não vêm no import *  # noqa: F401
    _IBGE_CACHE,
    _IBGE_CACHE_TTL,
    _WEATHER_CACHE,
    _WEATHER_CACHE_TTL,
    _gen_fallback_history,
    _gen_fallback_metrics,
    _get_real_weather,
    _owm_icon,
    _to_float,
)


class PerfilUsuarioViewSet(viewsets.ModelViewSet):
    serializer_class = PerfilUsuarioSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return PerfilUsuario.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class WidgetUsuarioViewSet(viewsets.ModelViewSet):
    serializer_class = WidgetUsuarioSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return WidgetUsuario.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


@extend_schema(responses=SPASimpleSerializer)
@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def dashboard_state(request):
    """Estado completo do dashboard por usuário: layout, preset ativo, presets custom."""
    if request.method == "GET":
        obj, _ = DashboardUserState.objects.get_or_create(user=request.user)
        state, removidos = limpar_presets_bloqueados(obj.state)
        if removidos:
            # Fantasmas antigos ainda gravados no banco são removidos na leitura
            # para que parem de reaparecer no menu/barra do dashboard.
            obj.state = state
            obj.save(update_fields=["state"])
            logger.info("presets fantasma removidos do estado: %s", removidos)
        return Response({"ok": True, "state": state})
    state = request.data.get("state", {})
    if not isinstance(state, dict):
        return Response(
            {"detail": "state inválido"}, status=status.HTTP_400_BAD_REQUEST
        )

    # A origem de cada preset tem de vir declarada pelo cliente, no mesmo
    # pacote da escrita (VISÃO §5.1.5). Um preset montado pelo utilizador e'
    # `declarado`. O vocabulario e' o de `app/validators.py`:
    # medido | declarado | sem_dado | suspect | simulado.
    #
    # Nao se aceita `medido` neste caminho: nada aqui mede alguma coisa. Aceitar
    # seria gravar a mesma mentira que o VISÃO §0.1 descreve -- um numero com a
    # mesma cara, so que agora traz etiqueta.
    FONTES = {"declarado", "sem_dado", "simulado", "suspect"}
    fde = state.get("presets_fonte_dado")
    if fde is not None and not isinstance(fde, dict):
        return Response(
            {"detail": "presets_fonte_dado inválido"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if isinstance(fde, dict):
        estado_final = {
            k: ("declarado" if v not in FONTES else v) for k, v in fde.items()
        }
        state["presets_fonte_dado"] = estado_final
    if "layout_fonte_dado" in state and state["layout_fonte_dado"] not in FONTES:
        state["layout_fonte_dado"] = "declarado"

    state, removidos = limpar_presets_bloqueados(state)
    if removidos:
        logger.info("presets fantasma descartados no save: %s", removidos)
    DashboardUserState.objects.update_or_create(
        user=request.user, defaults={"state": state}
    )
    return Response({"ok": True})


@extend_schema(responses=SPASimpleSerializer)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def perfil_data(request):
    props = get_propriedade_optimizada(request.user)
    perfis = PerfilUsuario.objects.filter(user=request.user).first()
    return Response(
        {
            "usuario": {
                "username": request.user.username,
                "email": request.user.email,
                "idioma": perfis.idioma if perfis else "pt-br",
                "tema": perfis.tema if perfis else "light",
            },
            "propriedade": {
                "nome": props.nome if props else "",
                "area_total": float(props.area_total) if props else 0,
                "uf": props.uf if props else "",
                "cidade": props.cidade if props else "",
                "bioma": props.bioma if props else "",
            }
            if props
            else {},
        }
    )


@extend_schema(responses=SPASimpleSerializer)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def dashboard_data(request):
    _ck = f"dash:{request.user.id}"
    _cached = cache.get(_ck)
    if _cached is not None:
        return Response(_cached)

    from app.painel_agregado import (
        agregar_safras,
        chart_data_agregado,
        escolher_propriedade_principal,
        financeiro_mensal_agregado,
    )

    # ─────────────────────────────────────────────────────────────────────────
    # TODAS as propriedades visíveis, não uma.
    #
    # Antes, `get_propriedade_optimizada()` (que faz `.first()`) decidia o
    # painel inteiro. Um produtor com duas fazendas via metade do negócio sem
    # qualquer aviso — números reais, errados, e nada na interface a dizer que
    # faltava a outra metade.
    #
    # Não existe "propriedade activa" em lado nenhum do sistema, portanto não
    # havia uma intenção de design a respeitar: era `.first()`. Sem ela, a
    # leitura honesta é o total do que o utilizador pode ver. Ver
    # app/painel_agregado.py para o porquê de cada escolha.
    # ─────────────────────────────────────────────────────────────────────────
    propriedades = list(propriedades_visiveis(request.user))
    if not propriedades:
        # `{}` com HTTP 200 é a pior resposta possível aqui: o front-end não
        # distingue "sem propriedade" de "todas as chaves a null", e cada KPI
        # caía no seu `|| 0`. Era esta a origem de um painel inteiro de zeros
        # para um produtor que ainda não cadastrou a fazenda — ele via zeros
        # em vez de "cadastre a sua propriedade".
        #
        # A resposta é nomeada e explícita. O `None` mantem-se: afirmar 0,0 ha
        # seria inventar uma medição que ninguém fez.
        return Response({"sem_propriedade": True})

    from datetime import date

    from django.db.models import Count, Q, Sum

    pids = [p.id for p in propriedades]
    lancamentos = LancamentoFinanceiro.objects.filter(propriedade_id__in=pids)
    safras_qs = Safra.objects.filter(propriedade_id__in=pids)

    total_talhoes = Talhao.objects.filter(propriedade_id__in=pids).count()
    safras_ativas = safras_qs.select_related("cultura", "propriedade").order_by(
        "-ano", "-id"
    )[:5]

    _agg = lancamentos.aggregate(
        total_receitas=Sum("valor", filter=Q(tipo="RECEITA")),
        total_despesas=Sum("valor", filter=Q(tipo="DESPESA")),
        total_lancamentos=Count("id"),
    )
    total_lancamentos = int(_agg["total_lancamentos"] or 0)
    total_receitas = float(_agg["total_receitas"] or 0)
    total_despesas = float(_agg["total_despesas"] or 0)
    saldo = total_receitas - total_despesas

    # A ÁREA É A DA FAZENDA, OU NÃO É NADA.
    #
    # `float(area_total) or 1.0` punha 1,0 no lugar de uma área zero. O `or`
    # existe para o cálculo não dividir por zero — e evita o crash. Mas o
    # `area_total` que ia para o JSON passava a ser esse 1,0, e o produtor via
    # "1 ha" numa fazenda que ninguém mediu.
    #
    # A conta que o produtor vê e a conta que o sistema usa não podem ser
    # coisas diferentes. Se a área não está medida, não há custo por hectare
    # que se possa afirmar — e "não sei" é uma resposta, enquanto "R$ 0,00/ha"
    # e R$ 12,00/ha são as mesmas frases para quem lê.
    #
    # O `roi` tinha o mesmo truque com `max(despesas, 1.0)`, e a mesma
    # consequência: um roi calculado contra um denominador que ninguém
    # registou. Um ROI sem despesa registrada é "não há roi para calcular".
    #
    # A área é a soma das propriedades visíveis: hectares somam-se. E o que
    # interessa para dividir é haver área medida — por isso `area_medida` conta
    # as propriedades COM área, não a soma, que dá o mesmo sinal.
    area_total = sum(float(p.area_total or 0) for p in propriedades)
    area_medida = area_total > 0
    props_sem_area = sum(1 for p in propriedades if not float(p.area_total or 0))

    # `custo_ha` é a DESPESA TOTAL sobre a SUPERFÍCIE DA FAZENDA. É uma
    # leitura de estrutura de custo, não de safra: "quanto custa manter esta
    # operação por hectare de terra", que é a pergunta de quem decide
    # alargar ou reduzir a área.
    #
    # A despesa é de TODOS os anos registados e a área é a área total, e as
    # duas coisas têm de ficar declaradas — porque o painel da IA tem um
    # `custo_por_ha` DIFERENTE, e que é o correto: despesa DO ANO da safra
    # sobre a área COLHIDA desse ano. Os dois números não divergem por
    # acidente; medem coisas diferentes, e cada um diz o que mede.
    #
    # O que já não pode acontecer é a mesma tela dar dois números para a
    # mesma pergunta sem dizer qual é qual. Por isso os dois campos
    # existem e cada um tem o seu nome.
    custo_ha = (
        round(total_despesas / area_total, 2)
        if total_despesas and area_medida
        else None
    )
    # A despesa do ano corrente, para um cartão que case com a safra em curso.
    # Fica aqui, e não mais abaixo, porque precisa de `hoje` — que é
    # declarado na secção do `chart_data` e chega tarde para este ponto.
    hoje = date.today()
    despesa_ano = float(
        lancamentos.filter(tipo="DESPESA", data__year=hoje.year).aggregate(
            s=Sum("valor")
        )["s"]
        or 0
    )
    roi = round((saldo / total_despesas) * 100, 1) if total_despesas else None

    safras_list = agregar_safras(safras_ativas)

    financeiro_mensal = financeiro_mensal_agregado(lancamentos)

    # chart_data: series reais por periodo.
    # Lancamentos nao possuem horario (data e DateField): "hoje" e o saldo do
    # dia e "semana" sao os saldos diarios reais. Nunca distribuir um total
    # mensal em horas ficticias.
    chart_data = chart_data_agregado(lancamentos, financeiro_mensal, hoje)

    # O modelo Maquinario nao possui OrdemServico/estado de OS. Portanto
    # "OS Pendentes" sao manutencoes vencidas (data <= hoje) de maquinarios
    # ativos. Maquinarios futuros/ativos sao apenas alertas de proxima manutencao.
    maquinarios = Maquinario.objects.filter(propriedade_id__in=pids)
    total_os = maquinarios.filter(ativo=True, proxima_manutencao__lte=hoje).count()
    total_alertas = maquinarios.filter(
        proxima_manutencao__isnull=False, ativo=True
    ).count()

    dias_calendario = [{"num": d, "destaque": d == hoje.day} for d in range(1, 32)]
    tarefas_list = []
    safras_para_plantio = (
        safras_qs.filter(data_plantio__gte=hoje)
        .select_related("cultura")
        .order_by("data_plantio")[:5]
    )
    for s in safras_para_plantio:
        tarefas_list.append(
            {
                "nome": f"Plantio {s.cultura.nome if s.cultura else ''} - {s.safra_nome or s.ano}",
                "feita": False,
                "tipo": "plantio",
            }
        )

    # O clima é meteorologia de UM sítio — a previsão de Brasília não é a
    # previsão de Três Lagoas. Agregar três municípios daria um número que não
    # corresponde a lado nenhum, e o painel deixaria de dizer algo verdadeiro
    # sobre o lugar onde se cultiva.
    #
    # Por isso o clima vem da propriedade principal (a de maior área, que é a
    # que domina o painel) e o payload diz QUAL é. Um produtor com várias
    # fazendas vê a previsão de uma delas, sabendo qual.
    propriedade_principal = escolher_propriedade_principal(propriedades)
    clima = _get_real_weather(propriedade_principal)
    clima_atual = (clima or {}).get("atual") or {}
    clima_icon = clima_atual.get("icone", "bi-sun") if clima else "bi-sun"
    clima_umidade = clima_atual.get("umidade", 0) if clima else 0
    clima_temp = clima_atual.get("temp", 0) if clima else 0

    alertas_novidades = _build_alertas_e_novidades(propriedades)
    total_alertas = len(alertas_novidades["alertas_list"])
    payload = {
        # `None`, e nao 0. Um `custo_ha: 0.0` afirma que a despesa por hectare
        # foi zero; o que aconteceu e' que nao ha hectares medidos para dividir.
        # O painel ja sabe mostrar "sem dado" — e e' isso que tem de mostrar.
        "roi": roi,
        "custo_ha": custo_ha,
        # A despesa do ANO CORRENTE, separada do total histórico. É o número
        # que casa com a safra em curso, e é o que o `custo_ha` de superfície
        # não é. Os dois vão no payload porque quem lê o painel precisa de
        # saber qual dos dois está a ver — e o valor sozinho não diz.
        "despesa_ano": round(despesa_ano, 2),
        "custo_ha_periodo": f"despesa de {hoje.year} sobre a área da fazenda",
        # A area que o produtor ve e a area que o calculo usou. Quando nao ha
        # medicao, a resposta e `area_medida: false` e nao um 1,0 de invencao.
        "area_total": area_total,
        "area_medida": area_medida,
        "alertas": total_alertas,
        "os_pendentes": total_os,
        "umidade": clima_umidade,
        "clima_icon": clima_icon,
        "temperatura": clima_temp,
        "clima_fonte": (clima or {}).get("fonte", "") if clima else "",
        "clima_descricao": clima_atual.get("descricao", "") if clima else "",
        "clima": clima if clima else {},
        "alertas_list": alertas_novidades["alertas_list"],
        "novidades": alertas_novidades["novidades"],
        "fluxo_caixa": round(saldo, 2),
        "sensor_status": "offline",
        "safras": safras_list,
        "tarefas": tarefas_list,
        "financeiro_mensal": financeiro_mensal,
        "dias": dias_calendario,
        "chart_data": chart_data,
        "propriedade": {
            "id": propriedade_principal.id,
            "nome_fazenda": propriedade_principal.nome,
            "cidade": propriedade_principal.cidade,
            "estado": propriedade_principal.uf,
            "area_total": area_total,
            "bioma": propriedade_principal.bioma,
        },
        # Quantas fazendas os números acima cobrem, e quais são. Sem isto, um
        # produtor com duas propriedades vê um total e não tem forma de saber
        # se é o todo — que é exatamente como o defeito antigo se escondia.
        "propriedades": [
            {
                "id": p.id,
                "nome": p.nome,
                "cidade": p.cidade,
                "uf": p.uf,
                "area_total": float(p.area_total or 0),
                "area_medida": bool(float(p.area_total or 0)),
            }
            for p in propriedades
        ],
        "total_propriedades": len(propriedades),
        "propriedades_sem_area": props_sem_area,
        "resumo": {
            "total_talhoes": total_talhoes,
            "total_funcionarios": Funcionario.objects.filter(
                propriedade_id__in=pids, ativo=True
            ).count(),
            "total_maquinarios": maquinarios.filter(ativo=True).count(),
            "total_animais": float(
                Animal.objects.filter(propriedade_id__in=pids).aggregate(
                    s=Sum("quantidade")
                )["s"]
                or 0
            ),
        },
        "financeiro": {
            "total_receitas": round(total_receitas, 2),
            "total_despesas": round(total_despesas, 2),
            "saldo": round(saldo, 2),
            "total_lancamentos": total_lancamentos,
        },
    }
    cache.set(_ck, payload, 30)
    return Response(payload)


@extend_schema(responses=SPASimpleSerializer)
@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def notificacoes_data(request):
    if request.method == "POST":
        data = request.data
        Notificacao.objects.create(
            user=request.user,
            titulo=data.get("titulo", ""),
            mensagem=data.get("mensagem", ""),
            nivel=data.get("nivel", "info"),
            link=data.get("link", ""),
        )
        return Response({"ok": True})
    notifs_base = Notificacao.objects.filter(user=request.user)
    nao_lidas = notifs_base.filter(lida=False).count()
    notifs = notifs_base[:50]
    props = get_propriedade_optimizada(request.user)
    dados = _build_alertas_e_novidades(props)
    return Response(
        {
            "notificacoes": NotificacaoSerializer(notifs, many=True).data,
            "nao_lidas": nao_lidas,
            "alertas": len(dados["alertas_list"]),
            "alertas_list": dados["alertas_list"],
            "novidades": dados["novidades"],
        }
    )


@extend_schema(responses=SPASimpleSerializer)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def notificacao_ler(request, pk):
    Notificacao.objects.filter(user=request.user, id=pk).update(lida=True)
    return Response({"ok": True})


@extend_schema(responses=SPASimpleSerializer)
@api_view(["GET", "PUT"])
@permission_classes([IsAuthenticated])
def alertas_config(request):
    """GET lista as 20 regras com config do usuário; PUT salva {regra, ativo, dias, limite}."""
    from app.models import REGRAS_ALERTA, AlertaConfig

    if request.method == "PUT":
        data = request.data
        regra = (data.get("regra") or "").strip()
        if regra not in REGRAS_ALERTA:
            return Response({"ok": False, "erro": "regra inválida"}, status=400)
        meta = REGRAS_ALERTA[regra]
        cfg, _ = AlertaConfig.objects.get_or_create(user=request.user, regra=regra)
        if "ativo" in data:
            cfg.ativo = bool(data["ativo"])
        if "dias" in data and meta["dias"] is not None:
            try:
                cfg.dias = (
                    max(0, int(data["dias"]))
                    if data["dias"] not in (None, "")
                    else None
                )
            except (TypeError, ValueError):
                pass
        if "limite" in data and meta["limite"] is not None:
            try:
                v = str(data["limite"]).replace(".", "").replace(",", ".")
                cfg.limite = float(v) if v not in ("", "None") else None
            except (TypeError, ValueError):
                pass
        cfg.save()
        return Response({"ok": True})
    atuais = {c.regra: c for c in AlertaConfig.objects.filter(user=request.user)}
    regras = []
    for chave, meta in REGRAS_ALERTA.items():
        c = atuais.get(chave)
        regras.append(
            {
                "regra": chave,
                "nome": meta["nome"],
                "descricao": meta["descricao"],
                "tem_dias": meta["dias"] is not None,
                "tem_limite": meta["limite"] is not None,
                "un_dias": meta["un_dias"],
                "un_limite": meta["un_limite"],
                "dias_padrao": meta["dias"],
                "limite_padrao": meta["limite"],
                "ativo": c.ativo if c else True,
                "dias": c.dias if c and c.dias is not None else meta["dias"],
                "limite": float(c.limite)
                if c and c.limite is not None
                else meta["limite"],
            }
        )
    return Response({"regras": regras})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def onboarding_save(request):
    from app.api.views.cultures import _chave_mercado_for_cultura
    from app.cultures.desktop import culturas_da_instalacao

    """Save onboarding wizard data: creates Propriedade + PerfilUsuario."""
    data = request.data
    user = request.user

    nome_fazenda = data.get("nome_fazenda", "").strip()
    estado = data.get("estado", "").strip()
    cidade = data.get("cidade", "").strip()
    documento = data.get("documento", "").strip()

    # A rota /api/onboarding/save/ resolve para ESTA funcao (app.api.views.user),
    # nao para a de app/views/auth.py. Tudo que o mapa envia precisa ser lido
    # aqui: antes documento, lat, lon e geometria eram aceitos pelo front e
    # descartados em silencio — o produtor desenhava a fazenda e nada gravava.
    lat = data.get("lat")
    lon = data.get("lon")
    geometria = data.get("geometria") or {}

    if not nome_fazenda:
        return Response(
            {"ok": False, "erro": "Informe o nome da propriedade"}, status=400
        )

    # Coordenada so entra se for plausivel: sem isso o mapa Mandaria NaN.
    try:
        lat_f = float(lat) if lat not in (None, "") else None
        lon_f = float(lon) if lon not in (None, "") else None
    except (TypeError, ValueError):
        lat_f = lon_f = None
    if lat_f is not None and not (-90 <= lat_f <= 90):
        lat_f = None
    if lon_f is not None and not (-180 <= lon_f <= 180):
        lon_f = None
    if lat_f is None or lon_f is None:
        lat_f = lon_f = None

    try:
        area_float = float(data.get("area", 0) or 0)
    except (ValueError, TypeError):
        area_float = 0

    if area_float <= 0:
        return Response(
            {"ok": False, "erro": "Informe a área total da propriedade"}, status=400
        )

    # Teto de sanidade. Medido no navegador: sem GPS o mapa abre em zoom 4 (o
    # pais inteiro) e um desenho de 16% da tela dava 162.987.290 ha — quase um
    # quinto do Brasil. area_total tem max_digits=10, ou seja estoura o campo em
    # ~1.6M ha. Sem este teto o produtor salva uma area sem sentido e o painel
    # inteiro passa a calcular errado.
    AREA_MAX_HA = 500000.0  # 5.000 km2 — maior fazenda do mundo (Madeira) ~0
    if area_float > AREA_MAX_HA:
        return Response(
            {
                "ok": False,
                "erro": (
                    f"A área desenhada dá {area_float:.0f} hectares, o que é maior que o "
                    "Brasil. Zoom out e redesenhe o contorno, ou escreva a "
                    "área real no campo."
                ),
            },
            status=400,
        )

    prop = Propriedade.objects.create(
        user=user,
        nome=nome_fazenda,
        area_total=area_float,
        uf=estado or "MT",
        cidade=cidade,
        cpf_cnpj=documento if documento else "",
        latitude=lat_f,
        longitude=lon_f,
        geometria=geometria if isinstance(geometria, dict) else {},
    )

    # As culturas que o produtor marcou no passo 3 do cadastro.
    #
    # Isto ja existia (a view guardava o que lhe mandassem), mas com duas
    # falhas que so a nova etapa do onboarding torna visiveis:
    #
    #  1. `culturas_ids` ia cru para o `id__in`. `data` e' um POST: pode ser
    #     uma string, um dicionario, ou 100 000 numeros. `id__in` com o que
    #     vier da' num `IN (...)` do tamanho do pedido.
    #  2. Sem filtro de `ativo`: dava para vincular a propriedade a uma
    #     cultura que ja nao existe no produto, e ela continuaria a contar
    #     como "cultura escolhida" para sempre.
    #
    # `ids_validos` fecha as duas (tecto + existencia + `ativo`) e devolve so
    # inteiros. O que nao passar e' ignorado em silencio de proposito: um id
    # invalido nao impede a fazenda de ser criada, porque quem manda isso e'
    # o proprio cadastro e nao ha' nada que ele possa fazer com um 400.
    #
    # `set()` e nao `add()` em ciclo: `add()` num ManyToMany e' um INSERT por
    # cultura, e o produtor pode marcar 40.
    #
    # `culturas_info` volta no JSON de resposta porque o dashboard le-a para
    # montar as opcoes culture-specific logo a seguir — e nao era para se
    # perder esse contrato.
    desktop_culturas = culturas_da_instalacao()
    culturas_ids = (
        desktop_culturas
        if desktop_culturas is not None
        else ids_validos(data.get("culturas"))
    )
    culturas_info = []
    if culturas_ids:
        culturas = list(Cultura.objects.filter(id__in=culturas_ids))
        prop.culturas.set(culturas)
        culturas_info = [
            {"id": c.id, "nome": c.nome, "chave_mercado": _chave_mercado_for_cultura(c)}
            for c in culturas
        ]

    # A marca de "foi perguntado" grava-se pela PRESENÇA da chave, e não pelo
    # conteúdo dela: `culturas: []` é uma resposta ("não produzo nada
    # disto"), e a ausência da chave é um cliente que não conhece o seletor
    # (API, importador, versão antiga da página).
    #
    # Se a marca fosse gravada sempre, um importador que manda só o nome da
    # fazenda marcareia a propriedade como respondida — e o filtro das guias
    # esvaziava-se sem o produtor ter visto pergunta nenhuma. Por isso é a
    # chave que conta.
    if "culturas" in data or desktop_culturas is not None:
        prop.culturas_escolhidas_em = timezone.now()
        prop.save(update_fields=["culturas_escolhidas_em"])

    PerfilUsuario.objects.get_or_create(
        user=user,
        defaults={
            "idioma": "pt-br",
            "tema": "light",
        },
    )
    # Inicializa o estado do dashboard com o preset base-ia
    # Este é o preset padrão que o produtor comum vê primeiro
    initial_state = {
        "layout": {},
        "active_preset": "base-ia",
        "presets_order": ["base-ia"],
        "presets": {
            "base-ia": {},  # Empty widgets - will be populated by frontend
        },
        "presets_meta": {},
    }
    obj = DashboardUserState.objects.get_or_create(user=user)[0]
    obj.state = initial_state
    obj.save()
    return Response({"ok": True, "redirect": "/dashboard/", "culturas": culturas_info})


@extend_schema(responses=SPASimpleSerializer)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def widget_data(request):
    """Unified endpoint: aggregated real data for all widget types. Cached per-user 30s. ?full=1 para payload completo."""
    is_full = request.GET.get("full") == "1"
    cache_key = f"widget_data:{request.user.id}:{1 if is_full else 0}"
    cached = cache.get(cache_key)
    if cached is not None:
        return Response(cached)
    props = get_propriedade_optimizada(request.user)
    if not props:
        return Response(
            {
                "safras": [],
                "financeiro": {},
                "estoque": [],
                "animais": [],
                "maquinarios": [],
                "talhoes": [],
                "insumos": [],
                "apiario": [],
                "funcionarios": [],
                "producao_animal": [],
                "aplicacoes": [],
            }
        )

    now = datetime.now()
    ano_atual = now.year

    # ── Safras ──
    safras_qs = Safra.objects.filter(propriedade=props)
    safras_por_ano = (
        safras_qs.values("ano")
        .annotate(
            total_area=Sum("area_plantada"),
            total_producao=Sum("producao_total"),
            media_produtividade=Avg("produtividade"),
            count=Count("id"),
        )
        .order_by("-ano")
    )

    safras_por_cultura = (
        safras_qs.values("cultura__nome")
        .annotate(
            total_producao=Sum("producao_total"),
            total_area=Sum("area_plantada"),
            count=Count("id"),
        )
        .order_by("-total_producao")
    )

    safras_recentes = safras_qs.select_related("cultura", "talhao").order_by("-ano")[
        :20
    ]
    safras_list = [
        {
            "id": s.id,
            "cultura": s.cultura.nome if s.cultura else "—",
            "talhao": s.talhao.nome if s.talhao else "—",
            "ano": s.ano,
            "area": float(s.area_plantada or 0),
            "producao": float(s.producao_total or 0),
            "produtividade": float(s.produtividade or 0),
            "receita": float(s.receita_estimada or 0),
            "data_plantio": s.data_plantio.isoformat() if s.data_plantio else None,
            "data_colheita": s.data_colheita.isoformat() if s.data_colheita else None,
        }
        for s in safras_recentes
    ]

    # ── Financeiro ──
    fin = LancamentoFinanceiro.objects.filter(propriedade=props)
    fin_aggr = fin.aggregate(
        total_receitas=Sum("valor", filter=Q(tipo="RECEITA")),
        total_despesas=Sum("valor", filter=Q(tipo="DESPESA")),
        receitas_pagas=Sum("valor", filter=Q(tipo="RECEITA", pago=True)),
        despesas_pagas=Sum("valor", filter=Q(tipo="DESPESA", pago=True)),
        count_receitas=Count("id", filter=Q(tipo="RECEITA")),
        count_despesas=Count("id", filter=Q(tipo="DESPESA")),
    )
    receitas = fin_aggr["total_receitas"] or 0
    despesas = fin_aggr["total_despesas"] or 0
    saldo = receitas - despesas

    fin_por_categoria = (
        fin.values("categoria", "tipo")
        .annotate(total=Sum("valor"), count=Count("id"))
        .order_by("-total")
    )

    fin_mensal = (
        fin.filter(data__year=ano_atual)
        .values("data__month")
        .annotate(
            receitas=Sum("valor", filter=Q(tipo="RECEITA")),
            despesas=Sum("valor", filter=Q(tipo="DESPESA")),
        )
        .order_by("data__month")
    )

    lancamentos_recentes = fin.select_related("talhao", "safra").order_by("-data")[:30]
    lancamentos_list = [
        {
            "id": l.id,
            "tipo": l.tipo,
            "categoria": l.categoria,
            "valor": float(l.valor),
            "data": l.data.isoformat(),
            "descricao": l.descricao or "",
            "pago": l.pago,
            "talhao": l.talhao.nome if l.talhao else None,
            "safra": str(l.safra) if l.safra else None,
        }
        for l in lancamentos_recentes
    ]

    # ── Estoque ──
    estoque_qs = EstoqueItem.objects.filter(propriedade=props)
    estoque_por_categoria = (
        estoque_qs.values("categoria")
        .annotate(
            total=Sum("quantidade"),
            count=Count("id"),
        )
        .order_by("categoria")
    )
    estoque_list = [
        {
            "id": e.id,
            "categoria": e.categoria,
            "nome": e.nome,
            "quantidade": float(e.quantidade or 0),
            "unidade": e.unidade,
            "local": e.local,
            "validade": e.data_validade.isoformat() if e.data_validade else None,
        }
        for e in estoque_qs.order_by("nome")
    ]

    # ── Animais ──
    animais_qs = Animal.objects.filter(propriedade=props)
    animais_por_especie = (
        animais_qs.values("especie", "tipo_producao")
        .annotate(
            total=Sum("quantidade"),
            count=Count("id"),
        )
        .order_by("especie")
    )
    animais_list = [
        {
            "id": a.id,
            "especie": a.especie,
            "tipo_producao": a.tipo_producao,
            "raca": a.raca,
            "quantidade": float(a.quantidade or 0),
            "peso_medio": float(a.peso_medio or 0),
        }
        for a in animais_qs.order_by("especie")
    ]
    total_animais = sum(a["quantidade"] for a in animais_list)

    # ── Producao Animal ──
    prod_animal = ProducaoAnimal.objects.filter(animal__propriedade=props)
    prod_animal_list = [
        {
            "id": p.id,
            "animal": str(p.animal),
            "data": p.data.isoformat(),
            "quantidade": float(p.quantidade_produzida or 0),
            "unidade": p.unidade,
            "valor": float(p.valor_estimado or 0),
        }
        for p in prod_animal.select_related("animal").order_by("-data")[:30]
    ]

    # ── Maquinarios ──
    maq_qs = Maquinario.objects.filter(propriedade=props)
    now_date = now.date()
    manutencao_pendente = maq_qs.filter(
        proxima_manutencao__lte=now_date, ativo=True
    ).count()
    maq_list = [
        {
            "id": m.id,
            "tipo": m.tipo,
            "nome": m.nome,
            "marca": m.marca,
            "modelo": m.modelo,
            "horas_uso": float(m.horas_uso or 0),
            "ultima_manutencao": m.ultima_manutencao.isoformat()
            if m.ultima_manutencao
            else None,
            "proxima_manutencao": m.proxima_manutencao.isoformat()
            if m.proxima_manutencao
            else None,
            "ativo": m.ativo,
        }
        for m in maq_qs.order_by("nome")
    ]

    # ── Talhoes ──
    talhao_qs = Talhao.objects.filter(propriedade=props)
    talhao_list = [
        {
            "id": t.id,
            "nome": t.nome,
            "area": float(t.area_hectare or 0),
            "cultura": t.cultura_atual.nome if t.cultura_atual else None,
            "tipo_solo": t.tipo_solo,
            "ativo": t.ativo,
        }
        for t in talhao_qs.select_related("cultura_atual").order_by("nome")
    ]
    area_total_talhoes = sum(t["area"] for t in talhao_list)

    # ── Insumos ──
    insumo_qs = Insumo.objects.filter(propriedade=props)
    insumo_list = [
        {
            "id": i.id,
            "categoria": i.categoria,
            "nome": i.nome,
            "quantidade": float(i.quantidade or 0),
            "unidade": i.unidade,
            "valor_unitario": float(i.valor_unitario or 0),
            "fornecedor": i.fornecedor,
        }
        for i in insumo_qs.order_by("nome")
    ]

    # ── Aplicacoes de Insumo ──
    aplicacoes = AplicacaoInsumo.objects.filter(insumo__propriedade=props)
    aplicacoes_list = [
        {
            "id": a.id,
            "insumo": a.insumo.nome,
            "talhao": a.talhao.nome if a.talhao else None,
            "data": a.data.isoformat() if a.data else None,
            "dose": float(a.dose or 0),
            "responsavel": a.responsavel,
        }
        for a in aplicacoes.select_related("insumo", "talhao").order_by("-data")[:30]
    ]

    # ── Apiario ──
    colmeias_qs = ApiarioColmeia.objects.filter(propriedade=props)
    colmeias_ativas = colmeias_qs.filter(ativa=True).count()
    colmeias_list = [
        {
            "id": c.id,
            "identificacao": c.identificacao,
            "tipo_abelha": c.tipo_abelha,
            "ativa": c.ativa,
        }
        for c in colmeias_qs.order_by("identificacao")
    ]

    # ── Funcionarios ──
    func_qs = Funcionario.objects.filter(propriedade=props)
    func_ativos = func_qs.filter(ativo=True).count()
    func_list = [
        {
            "id": f.id,
            "nome": f.nome,
            "cargo": f.cargo,
            "salario": float(f.salario or 0),
            "ativo": f.ativo,
        }
        for f in func_qs.order_by("nome")
    ]

    # ── Propriedade ──
    prop_info = {
        "id": props.id,
        "nome": props.nome,
        "area_total": float(props.area_total or 0),
        "uf": props.uf,
        "cidade": props.cidade,
        "bioma": props.bioma,
        "area_talhoes": area_total_talhoes,
    }

    payload = {
        "propriedade": prop_info,
        "safras": {
            "items": safras_list,
            "por_ano": list(safras_por_ano),
            "por_cultura": list(safras_por_cultura),
            "total_safras": safras_qs.count(),
        },
        "financeiro": {
            "receitas": float(receitas),
            "despesas": float(despesas),
            "saldo": float(saldo),
            "por_categoria": list(fin_por_categoria),
            "mensal": list(fin_mensal),
            "lancamentos": lancamentos_list,
        },
        "estoque": {
            "items": estoque_list,
            "por_categoria": list(estoque_por_categoria),
            "total_itens": len(estoque_list),
        },
        "animais": {
            "items": animais_list,
            "por_especie": list(animais_por_especie),
            "total_cabecas": total_animais,
        },
        "producao_animal": prod_animal_list,
        "maquinarios": {
            "items": maq_list,
            "total": len(maq_list),
            "manutencao_pendente": manutencao_pendente,
        },
        "talhoes": {
            "items": talhao_list,
            "total": len(talhao_list),
            "area_total": area_total_talhoes,
        },
        "insumos": {
            "items": insumo_list,
            "por_categoria": list(
                insumo_qs.values("categoria")
                .annotate(total=Sum("quantidade"))
                .order_by("categoria")
            ),
        },
        "aplicacoes": aplicacoes_list,
        "apiario": {
            "colmeias": colmeias_list,
            "ativas": colmeias_ativas,
            "total": len(colmeias_list),
        },
        "funcionarios": {
            "items": func_list,
            "total": len(func_list),
            "ativos": func_ativos,
        },
        "weather": _get_real_weather(props),
    }

    # ─────────────────────────────────────────────────────────────────────────
    # Lista `widgets`: o contrato que o `getWidgetDataFromAPI` do front consome.
    #
    # O JS pede `apiData.widgets[].id` e mapeia ids como `roi-analytics` e
    # `custo-hectare`. Essa lista NUNCA foi produzida por este endpoint — o
    # payload tinha `safras`, `financeiro`, `estoque`… e nada mais. O
    # resultado era `kpi-area` a mostrar 0 numa propriedade com 209 ha
    # registados, e o produtor a concluir que não tinha área.
    #
    # Tudo abaixo vem de valores JÁ calculados acima neste função. Não há uma
    # única constante nova: um número aqui ou é medido ou é `None`. Este é o
    # caminho que o comentário de `dashboard-desktop.js` descreve como o que já
    # foi removido uma vez — números plausíveis com cara de medidos. Não
    # voltamos a isso; liguei o contrato.
    #
    # `None` significa "sem dado" e é o que o front deve mostrar. Zero é uma
    # afirmação ("mediste zero") e só entra quando a fonte tem mesmo zero.
    # ─────────────────────────────────────────────────────────────────────────
    def _w(wid, valor, rotulo=None, unidade=None):
        """Monta uma entrada. `None` preserva a distinção sem dado / zero."""
        return {"id": wid, "valor": valor, "rotulo": rotulo, "unidade": unidade}

    # Área: soma das safras do ano corrente. Sem safras, cai na área da
    # propriedade desenhada no onboarding — que é um registo real.
    _area_safras = sum(
        float(a.get("total_area") or 0)
        for a in safras_por_ano
        if a.get("ano") == ano_atual
    )
    _area_total = _area_safras or float(props.area_total or 0) or None

    _custo_ha = None
    if despesas and _area_total:
        _custo_ha = round(float(despesas) / float(_area_total), 2)

    # Produtividade média (kg/ha) das safras do ano. Vem da agregação que
    # já existe acima — não é um número novo, é o mesmo que a lista de
    # safras devolve, agregado.
    _prod_media = next(
        (
            float(a.get("media_produtividade") or 0)
            for a in safras_por_ano
            if a.get("ano") == ano_atual and a.get("media_produtividade")
        ),
        None,
    )

    # ROI: (receita - despesa) / despesa. Só existe se houver despesa.
    _roi = None
    if despesas:
        _roi = round(((float(receitas) - float(despesas)) / float(despesas)) * 100, 1)

    _manut_pendentes = (
        Maquinario.objects.filter(propriedade=props)
        .exclude(proxima_manutencao__isnull=True)
        .filter(proxima_manutencao__lt=now)
        .count()
    )

    # Clima: a fonte é `_get_real_weather`, que aninha em `weather.atual`
    # (medido: {"dia","icone","temp","umidade","chuva_mm","descricao"}).
    _clima = None
    _weather = payload.get("weather") if isinstance(payload, dict) else None
    if isinstance(_weather, dict):
        _atual = _weather.get("atual")
        if isinstance(_atual, dict):
            for _k in ("temp", "temperatura", "temperatura_atual"):
                if _atual.get(_k) is not None:
                    _clima = _atual[_k]
                    break

    widgets = [
        _w("area-plantada", _area_total, "Área", "ha"),
        _w("custo-hectare", _custo_ha, "Custo por hectare", "R$/ha"),
        _w("roi-analytics", _roi, "ROI", "%"),
        _w(
            "fluxo-caixa",
            float(saldo) if (receitas or despesas) else None,
            "Saldo",
            "R$",
        ),
        _w("total-receitas", float(receitas) if receitas else None, "Receitas", "R$"),
        _w("total-despesas", float(despesas) if despesas else None, "Despesas", "R$"),
        _w(
            "manutencoes",
            _manut_pendentes if _manut_pendentes else None,
            "Revisões vencidas",
        ),
        _w("total-safras", len(safras_list) if safras_list else None, "Safras"),
        _w("produtividade-media", _prod_media, "Produtividade", "kg/ha"),
        _w("clima-previsao", _clima, "Clima", "°C"),
    ]
    # Só entra o que tem fonte. Sem dado continua ausente, nunca zero.
    widgets = [x for x in widgets if x["valor"] is not None]
    payload["widgets"] = widgets

    # `kpi-sensores` no front lê `apiData.sensores[0].valor` — a leitura mais
    # recente. A leitura liga-se à estação (EstacaoMeteo), não à propriedade,
    # por isso o caminho é: propriedade -> estacoes -> leituras.
    _sens = []
    try:
        _leitura = (
            LeituraSensor.objects.filter(estacao__propriedade=props, qualidade="good")
            .order_by("-timestamp")
            .first()
        )
        if _leitura is not None:
            _sens = [
                {
                    "tipo": _leitura.tipo,
                    "valor": float(_leitura.valor),
                    "unidade": _leitura.unidade,
                    "timestamp": _leitura.timestamp.isoformat(),
                }
            ]
    except Exception:  # noqa: BLE001 — sensores não podem derrubar o painel
        _sens = []
    payload["sensores"] = _sens

    if not is_full:
        # payload enxuto 180KB vs 1.2MB — evita timeout em 4G
        for _k in ("estoque", "animais", "maquinarios", "talhoes", "insumos"):
            if (
                _k in payload
                and isinstance(payload[_k], dict)
                and "items" in payload[_k]
            ):
                payload[_k]["items"] = payload[_k]["items"][:20]
        if "producao_animal" in payload:
            payload["producao_animal"] = payload["producao_animal"][:20]
        if "aplicacoes" in payload:
            payload["aplicacoes"] = payload["aplicacoes"][:20]
        if (
            "funcionarios" in payload
            and isinstance(payload["funcionarios"], dict)
            and "items" in payload["funcionarios"]
        ):
            payload["funcionarios"]["items"] = payload["funcionarios"]["items"][:20]
        if "safras" in payload and "items" in payload["safras"]:
            payload["safras"]["items"] = payload["safras"]["items"][:20]
        if (
            "financeiro" in payload
            and isinstance(payload["financeiro"], dict)
            and "lancamentos" in payload["financeiro"]
        ):
            payload["financeiro"]["lancamentos"] = payload["financeiro"]["lancamentos"][
                :20
            ]
    cache.set(cache_key, payload, 30)
    return Response(payload)


@extend_schema(responses=SPASimpleSerializer)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def widgets_layout_sync(request):
    widgets = request.data.get("widgets", {})
    if isinstance(widgets, str):
        try:
            widgets = json.loads(widgets)
        except Exception:
            return Response(
                {"detail": "widgets inválido"}, status=status.HTTP_400_BAD_REQUEST
            )
    if not isinstance(widgets, dict):
        return Response(
            {"detail": "widgets inválido"}, status=status.HTTP_400_BAD_REQUEST
        )

    saved = 0

    def _do_sync():
        nonlocal saved
        for tipo_widget, cfg in widgets.items():
            if not isinstance(cfg, dict):
                continue
            WidgetUsuario.objects.update_or_create(
                user=request.user,
                tipo_widget=tipo_widget,
                defaults={
                    "posicao_x": int(cfg.get("gridX", 0)),
                    "posicao_y": int(cfg.get("gridY", 0)),
                    "tamanho_w": int(cfg.get("gridW", 1)),
                    "tamanho_h": int(cfg.get("gridH", 1)),
                    "config": cfg,
                },
            )
            saved += 1

    with transaction.atomic():
        _do_sync()
    return Response({"ok": True, "saved": saved})


@extend_schema(responses=SPASimpleSerializer)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def novidades_data(request):
    props = get_propriedade_optimizada(request.user)
    if not props:
        return Response({"total_alertas": 0, "novidades": []})
    dados = _build_alertas_e_novidades(props)
    return Response(
        {
            "total_alertas": len(dados["alertas_list"]),
            "novidades": dados["novidades"],
        }
    )


def _build_alertas_e_novidades(propriedades):
    """Monta listas reais de alertas e novidades para os widgets KPI.

    `propriedades` é uma LISTA. O painel deixou de escolher uma propriedade ao
    acaso (ver `dashboard_data`), e um alerta de manutenção que existe na
    segunda fazenda não pode desaparecer só porque a base de dados devolveu
    primeiro a primeira.

    Aceita também um `Propriedade` solto, para não partir os outros chamadores
    — mas nesse caso agrega-se a lista de um elemento.
    """
    from datetime import date

    from app.painel_agregado import escolher_propriedade_principal

    if isinstance(propriedades, Propriedade):
        propriedades = [propriedades]
    else:
        propriedades = list(propriedades or [])
    if not propriedades:
        return {"alertas_list": [], "novidades": []}
    pids = [p.id for p in propriedades]
    hoje = date.today()
    trinta_dias = hoje + timedelta(days=30)

    alertas_list = []
    novidades = []

    # ── Maquinários: manutenção vencida ou nos próximos 30 dias
    maqs = Maquinario.objects.filter(
        propriedade_id__in=pids, ativo=True, proxima_manutencao__isnull=False
    ).order_by("proxima_manutencao")
    for m in maqs:
        if m.proxima_manutencao > trinta_dias:
            continue
        vencida = m.proxima_manutencao < hoje
        alertas_list.append(
            {
                "tipo": "maquinario",
                "msg": f"Manutenção{' atrasada' if vencida else ''}: {m.nome} em {m.proxima_manutencao.strftime('%d/%m')}",
                "icone": "bi-tools",
                "nivel": "critical" if vencida else "warning",
                "data": m.proxima_manutencao.isoformat(),
            }
        )

    # ── Estoque: vencidos (alerta) e validade próxima (novidade)
    estoque = EstoqueItem.objects.filter(
        propriedade_id__in=pids, data_validade__isnull=False
    ).order_by("data_validade")
    for e in estoque:
        if e.data_validade <= hoje:
            alertas_list.append(
                {
                    "tipo": "estoque",
                    "msg": f"Vencido: {e.nome} ({e.quantidade} {e.unidade})",
                    "icone": "bi-exclamation-triangle",
                    "nivel": "critical",
                    "data": e.data_validade.isoformat(),
                }
            )
        elif e.data_validade <= trinta_dias:
            novidades.append(
                {
                    "tipo": "estoque",
                    "msg": f"Validade próxima: {e.nome} em {e.data_validade.strftime('%d/%m')}",
                    "icone": "bi-hourglass-split",
                    "nivel": "info",
                    "data": e.data_validade.isoformat(),
                }
            )

    # ── Colmeias inativas
    for c in ApiarioColmeia.objects.filter(propriedade_id__in=pids, ativa=False):
        alertas_list.append(
            {
                "tipo": "colmeia",
                "msg": f"Colmeia inativa: {c.identificacao}",
                "icone": "bi-flower1",
                "nivel": "info",
                "data": c.data_instalacao.isoformat(),
            }
        )

    # ── Safras: plantio atrasado (alerta) / próximo (novidade)
    #
    # O QUE ESTA CONDIÇÃO JÁ FEZ, E NÃO PODE VOLTAR A FAZER
    # =======================================================
    # A regra era `if s.data_plantio < hoje` — e isso é verdade para TODA
    # safra cujo plantio já passou, o que inclui as safras de anos
    # anteriores. Na Fazenda Modelo (hoje = out/2026) o painel abria com
    # "Plantio atrasado: Soja (2024-10-15)" e "Plantio atrasado: Milho
    # (2025-02-28)": dois anos de aviso, todos os dias, para um produtor que
    # já não pode fazer nada com eles.
    #
    # E não era aviso: era mentira. A safra de 2024 foi colhida. Um "atraso"
    # sem ação possível é ruído — e ruído treina o olho a ignorar os alertas
    # que importam, que é o pior resultado que um sistema de alertas pode ter.
    #
    # O plantio só está atrasado se a safra AINDA estiver de pé. O fim da
    # safra é `data_colheita`; sem ele, o que decide é o ano — um plantio de
    # 2024 sem colheita registada é um esquecimento do produtor, e merece ser
    # pedido, não gritado todos os dias.
    safras = Safra.objects.filter(propriedade_id__in=pids).select_related("cultura")
    # Duas passagens, e a segunda só existe por causa de uma palavra que o
    # produtor teria de adivinhar.
    #
    # O aviso dizia "Plantio atrasado: Milho (há 61 dias)". Numa fazenda com
    # DUAS safras de milho em curso, saem dois avisos assim — e o produtor tem
    # duas lavouras diferentes para escolher e nenhuma delas nomeada. Ele sabe que
    # uma está mais atrasada que a outra; não sabe qual. O aviso diz o que
    # está errado mas não o que fazer, que é a diferença entre um dado e uma
    # acção.
    #
    # Só se descobre que a cultura repete depois de percorrer todas as safras,
    # por isso primeiro se recolhe quem está atrasado, e só então se escreve a
    # lista. O custo é uma passagem a mais sobre safras que já estavam em
    # memória.
    atrasadas = []
    for s in safras.filter(data_plantio__isnull=False).order_by("data_plantio")[:10]:
        if s.data_plantio >= hoje:
            # Plantio por vir. "Atrasado" para um plantio de amanhã seria
            # absurdo, e era o que a condição anterior podia dizer.
            if s.data_plantio <= trinta_dias:
                novidades.append(
                    {
                        "tipo": "safra",
                        "msg": f"Plantio: {s.cultura.nome if s.cultura else (s.safra_nome or s.ano)} em {s.data_plantio.strftime('%d/%m')}",
                        "icone": "bi-calendar-check",
                        "nivel": "info",
                        "data": s.data_plantio.isoformat(),
                    }
                )
            continue

        # Plantio no passado. A pergunta que decide é: a safra ainda existe?
        if s.data_colheita is not None:
            continue
        # Sem data de colheita: só é atraso se for a safra do ano corrente.
        if s.ano is not None and s.ano < hoje.year:
            continue

        atrasadas.append((s, (hoje - s.data_plantio).days))

    # Quantas safras atrasadas há por cultura. Com uma só, o nome da cultura
    # identifica a safra e o aviso fica curto. Com mais, só ele não identifica.
    por_cultura = {}
    for s, _dias in atrasadas:
        chave = s.cultura.nome if s.cultura else "(sem cultura)"
        por_cultura[chave] = por_cultura.get(chave, 0) + 1

    for s, dias in atrasadas:
        cultura = s.cultura.nome if s.cultura else (s.safra_nome or s.ano)
        repetida = por_cultura[cultura] > 1
        # Com várias, o nome da safra entra para o aviso dizer QUAL. Sem ele,
        # "Milho" sozinho obriga o produtor a abrir safras uma a uma.
        rotulo = (
            f"{cultura} — {s.safra_nome}"
            if repetida and s.safra_nome and s.safra_nome != cultura
            else cultura
        )
        alertas_list.append(
            {
                "tipo": "safra",
                "msg": (
                    f"Plantio atrasado: {rotulo} (há {dias} dias)"
                    if dias >= 1
                    else f"Plantio atrasado: {rotulo}"
                ),
                "icone": "bi-calendar-x",
                # Um atraso de duas semanas é rotina de calendário; um de
                # três meses é uma safra que se perdeu. O mesmo nível para os
                # dois treinava o olho a não distinguir.
                "nivel": "warning" if dias <= 60 else "critical",
                "data": s.data_plantio.isoformat(),
            }
        )

    total_safras = safras.count()
    if total_safras:
        novidades.append(
            {
                "tipo": "safra",
                "msg": f"{total_safras} safras registradas",
                "icone": "bi-flower1",
                "nivel": "info",
                "data": None,
            }
        )

    colmeias_ativas = ApiarioColmeia.objects.filter(
        propriedade_id__in=pids, ativa=True
    ).count()
    if colmeias_ativas:
        novidades.append(
            {
                "tipo": "colmeia",
                "msg": f"{colmeias_ativas} colmeias ativas",
                "icone": "bi-flower1",
                "nivel": "info",
                "data": None,
            }
        )

    # ── Clima severo na previsão (apenas fontes reais, não o fallback simulado)
    # O clima é meteorologia de UM sítio: usa a propriedade principal, que é a
    # que o painel diz representar. Ver `escolher_propriedade_principal`.
    #
    # `open-meteo` entrou na lista porque passou a ser a fonte real do
    # sistema. Sem esta linha, a previsão que o produtor lê no topo do painel
    # vinha do Open-Meteo e a tempestade — que dispara alertas de pulverização
    # e de colheita — nunca era traduzida em alerta nenhum.
    clima = _get_real_weather(escolher_propriedade_principal(propriedades))
    if clima and clima.get("fonte") in ("inmet", "openweathermap", "open-meteo"):
        icones = [p.get("icone", "") for p in (clima.get("previsao") or [])]
        if any("lightning" in ic for ic in icones):
            alertas_list.append(
                {
                    "tipo": "clima",
                    "msg": "Tempestades previstas nos próximos dias",
                    "icone": "bi-cloud-lightning-rain",
                    "nivel": "warning",
                    "data": None,
                }
            )
        elif any("rain" in ic for ic in icones):
            novidades.append(
                {
                    "tipo": "clima",
                    "msg": "Chuva prevista nos próximos dias",
                    "icone": "bi-cloud-rain",
                    "nivel": "info",
                    "data": None,
                }
            )

    prioridade = {"critical": 0, "warning": 1, "info": 2}

    # ── IA Alerta Proativo ──
    try:
        from app.models import IAAlertaProativo

        ia_alertas = IAAlertaProativo.objects.filter(
            propriedade__in=propriedades,
            criado_em__gte=hoje - timedelta(days=3),
            estado__in=("novo", "visto"),
        ).order_by("-criado_em")[:10]

        for a in ia_alertas:
            nivel_ui = "warning"
            if a.nivel == 0:
                nivel_ui = "critical"
            elif a.nivel == 2:
                nivel_ui = "info"

            item = {
                "tipo": "ia_proativo",
                "msg": f"✨ {a.titulo}",
                "icone": "bi-robot",
                "nivel": nivel_ui,
                "data": a.criado_em.isoformat(),
            }
            if nivel_ui == "info":
                novidades.append(item)
            else:
                alertas_list.append(item)
    except Exception as exc:
        # MEDIDO 2026-10-05: era `pass`, e devolve
        # `{"alertas_list": [], "novidades": []}`.
        #
        # ISTO E' A MENTIRA DO "SEM DADO" COM ROUPA NOVA.
        #
        # Um `alertas_list: []` diz ao produtor "nao tens alertas". Se o
        # que aconteceu foi um `OperationalError` — uma coluna em falta
        # a meio de uma migracao — o que verdade e' "o sistema nao
        # conseguiu ler os teus alertas". Sao coisas completamente
        # diferentes, e o produtor decide diferente com elas: a primeira
        # deixa-o descansado, a segunda obriga-o a telefonar.
        #
        # E' a MESMA classe de bug do painel que dizia "sem dado" sem
        # nenhuma fetch ter acontecido (a guarda lia um cookie HTTP-only e
        # era `false` para toda a gente), e da guia que anunciava "IoT: 4"
        # com 8 dispositivos na base.
        #
        # O `[]` e' a forma mais facil de dizer "zero", e por isso e' a
        # mais perigosa.
        import logging

        logging.getLogger(__name__).error(
            "alertas: a leitura de alertas/novidades falhou (%s). A lista "
            "vai sair VAZIA — e isso vai aparecer ao produtor como "
            "'nao tens alertas'. A correccao e' na base, nunca devolver "
            "uma lista vazia como se fosse uma medicao.",
            type(exc).__name__,
            exc_info=True,
        )

    alertas_list.sort(key=lambda a: prioridade.get(a["nivel"], 3))
    return {"alertas_list": alertas_list[:15], "novidades": novidades[:15]}


class FuncionarioViewSet(viewsets.ModelViewSet):
    filterset_fields = ["cargo", "propriedade"]
    search_fields = ["nome"]
    ordering_fields = ["nome"]
    serializer_class = FuncionarioSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Funcionario.objects.filter(
            propriedade__user=self.request.user
        ).select_related("propriedade", "user")

    def perform_create(self, serializer):
        prop = serializer.validated_data.get("propriedade")
        if prop and prop.user != self.request.user:
            raise PermissionDenied("Esta propriedade não pertence ao seu usuário")
        serializer.save()


class OperarioRegistroViewSet(viewsets.ModelViewSet):
    """ViewSet para registrar operários com login"""

    serializer_class = OperarioRegistroSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Funcionario.objects.filter(propriedade__user=self.request.user)

    def perform_create(self, serializer):
        prop = serializer.validated_data.get("propriedade")
        if prop and prop.user != self.request.user:
            raise PermissionDenied("Esta propriedade não pertence ao seu usuário")
        serializer.save()

    @action(detail=True, methods=["post"])
    def remover_login(self, request, pk=None):
        """Remove o login de um funcionário"""
        funcionario = self.get_object()
        if funcionario.user:
            user = funcionario.user
            funcionario.user = None
            funcionario.save()
            user.delete()
            return Response({"ok": True, "message": "Login removido com sucesso"})
        return Response(
            {"ok": False, "erro": "Funcionário não possui login"},
            status=status.HTTP_400_BAD_REQUEST,
        )
