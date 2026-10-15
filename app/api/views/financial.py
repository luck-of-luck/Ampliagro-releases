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
from app.hierarquia import *
from app.models import *
from app.services.cashflow import projetar_fluxo_caixa
from app.services.cotacoes import CotacoesService
from app.services.custo_producao import calcular_custo_producao
from app.services.dre import gerar_dre
from app.services.lcdpr_http import responder_lcdpr

from .utils import *


class LancamentoFinanceiroViewSet(viewsets.ModelViewSet):
    filterset_fields = ["tipo", "categoria", "propriedade"]
    search_fields = ["descricao"]
    ordering_fields = ["data", "valor"]
    serializer_class = LancamentoFinanceiroSerializer
    permission_classes = [IsAuthenticated, PodeVerFinanceiro]

    def get_queryset(self):
        return LancamentoFinanceiro.objects.filter(
            propriedade__in=propriedades_financeiras(self.request.user)
        ).select_related("talhao", "safra")

    def perform_create(self, serializer):
        prop = serializer.validated_data.get("propriedade")
        props = propriedades_financeiras(self.request.user)
        if prop and not props.filter(id=prop.id).exists():
            raise PermissionDenied("Esta propriedade não pertence ao seu usuário")
        serializer.save()


@extend_schema(responses=SPASimpleSerializer)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def simulacao_data(request):
    """Motor de simulação: {tipo, params}. Tipos: lucro, cenarios, equilibrio,
    sensibilidade, montecarlo, financiamento, ranking."""
    from app.services import simulacao as sim

    tipo = (request.data.get("tipo") or "lucro").strip().lower()
    p = request.data.get("params") or {}
    try:
        if tipo == "lucro":
            out = sim.simular_lucro(
                p.get("area_ha"),
                p.get("produtividade_sc_ha"),
                p.get("preco_sc"),
                p.get("custo_ha"),
            )
        elif tipo == "cenarios":
            out = sim.cenarios(p)
        elif tipo == "equilibrio":
            out = sim.ponto_equilibrio(p.get("custo_ha"), p.get("preco_sc"))
        elif tipo == "sensibilidade":
            out = sim.sensibilidade(
                p.get("base") or {}, p.get("variavel"), p.get("valores") or []
            )
        elif tipo == "montecarlo":
            out = sim.monte_carlo(p, n=min(int(p.get("n", 1000)), 5000))
        elif tipo == "financiamento":
            out = sim.financiamento(
                p.get("valor"), p.get("taxa_mes_pct"), p.get("meses"), p.get("sistema")
            )
        elif tipo == "ranking":
            out = sim.ranking_culturas(p.get("area_ha"), p.get("opcoes"))
        elif tipo == "hedge":
            from app.services.hedge import hedge_recomendado, simular_com_hedge

            if "preco_trava" in p:
                out = simular_com_hedge(
                    p.get("base") or p, p.get("preco_trava"), p.get("pct_travado", 0.5)
                )
            else:
                out = hedge_recomendado(
                    p.get("preco_chicago_atual") or p.get("preco_sc"),
                    p.get("preco_trava"),
                    p.get("area_ha"),
                    p.get("produtividade_sc_ha"),
                    p.get("pct_travado", 0.5),
                )
        elif tipo == "ruminante":
            from app.services.ruminante import ph_rumen, recomendar_dieta, simular_ganho

            if "peso_kg" in p:
                out = simular_ganho(
                    p.get("peso_kg"),
                    p.get("dias", 60),
                    p.get("ganho_kg_d_base", 1.6),
                    p.get("fibra_pct", 35),
                    p.get("amido_pct", 30),
                    p.get("tamponante", False),
                )
            elif "fibra_pct" in p:
                out = {
                    "ph": ph_rumen(
                        p.get("fibra_pct"),
                        p.get("amido_pct"),
                        p.get("tamponante", False),
                    ),
                    "recomendacao": recomendar_dieta(
                        ph_rumen(
                            p.get("fibra_pct"),
                            p.get("amido_pct"),
                            p.get("tamponante", False),
                        )
                    ),
                }
            else:
                return Response(
                    {
                        "ok": False,
                        "erro": "informe peso_kg+dias ou fibra_pct+amido_pct",
                    },
                    status=400,
                )
        elif tipo == "avicultura":
            from app.services.avicultura import (
                big_brother_previsao,
                lotes_por_ano,
                moba_descarte,
            )

            sub = (p.get("sub") or "lotes").lower()
            if sub == "bigbrother":
                out = big_brother_previsao(
                    p.get("peso_dia35", 2.37), p.get("balancas", 12)
                )
            elif sub == "moba":
                out = moba_descarte(p.get("aves", 100000), p.get("descarte_pct", 9.5))
            else:
                out = lotes_por_ano(
                    p.get("dias_engorda", 42),
                    p.get("dias_vazio", 15),
                    tipo=p.get("tipo", "lego"),
                )
        else:
            return Response({"ok": False, "erro": "tipo inválido"}, status=400)
    except (ValueError, TypeError) as e:
        return Response({"ok": False, "erro": str(e)}, status=400)

    # Este endpoint e' um SIMULADOR, e simular e' o que ele diz que faz —
    # por isso os defaults nao sao um defeito. O que era defeito e' o
    # resultado sair sem dizer QUAIS inputs foram assumidos: o produtor via
    # um ganho de 1,6 kg/dia e não sabia se aquilo era um valor que ele
    # passou, um valor de tabela, ou um número que alguém escreveu à mão
    # como default.
    #
    # "Simulei com 1,6" e "simulei, e assumi 1,6 porque não me disseste
    # outro" são respostas diferentes, e a segunda é a que deixa alguém
    # decidir se aceita o resultado.
    #
    # `_defaults` lista os defaults que este `tipo` usa. Um default que
    # entra na conta tem de sair nomeado.
    _defaults = _defaults_do_simulador(p)
    resposta = {"ok": True, "tipo": tipo, "resultado": out}
    if _defaults:
        resposta["assumidos"] = _defaults
        resposta["aviso"] = (
            "Simulação com valores por omissão. "
            f"{len(_defaults)} campo(s) não foram enviados e entraram com "
            "o valor de tabela — o resultado depende deles."
        )
    return Response(resposta)


def _defaults_do_simulador(p):
    """Campos que o simulador encheu sozinho, e com que valor.

    A lista sai da MESMA fonte que enche o default. Se alguém acrescentar
    um `p.get("x", 1)` aqui e esquecer esta função, o default continua a
    entrar em silêncio — por isso o teste da equipa verifica que a lista
    cobre os defaults que estão no código.
    """
    ASSUMIDOS = {
        "ganho_kg_d_base": 1.6,
        "fibra_pct": 35,
        "amido_pct": 30,
        "pct_travado": 0.5,
        "peso_dia35": 2.37,
        "balancas": 12,
        "aves": 100000,
        "descarte_pct": 9.5,
        "dias_engorda": 42,
        "dias_vazio": 15,
        "dias": 60,
    }
    return {
        campo: valor
        for campo, valor in ASSUMIDOS.items()
        if p.get(campo) is None and valor is not None
    }


@extend_schema(responses=SPASimpleSerializer)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def financeiro_data(request):
    props = get_propriedade_optimizada(request.user)
    if not props and pode_ver_financeiro(request.user):
        props = propriedades_financeiras(request.user).first()
    if not props:
        return Response({"lancamentos": [], "resumo": {}})
    lancs = (
        LancamentoFinanceiro.objects.filter(propriedade=props)
        .select_related("talhao", "safra")
        .order_by("-data")[:50]
    )
    receitas = sum(float(l.valor) for l in lancs if l.tipo == "RECEITA")
    despesas = sum(float(l.valor) for l in lancs if l.tipo == "DESPESA")
    return Response(
        {
            "lancamentos": LancamentoFinanceiroSerializer(lancs, many=True).data,
            "resumo": {
                "receitas": receitas,
                "despesas": despesas,
                "saldo": receitas - despesas,
            },
        }
    )


@extend_schema(responses=SPASimpleSerializer)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def compras_data(request):
    props = get_propriedade_optimizada(request.user)
    if not props:
        return Response({"solicitacoes": []})
    despesas = LancamentoFinanceiro.objects.filter(
        propriedade=props, tipo="DESPESA"
    ).order_by("-data")[:20]
    return Response(
        {
            "solicitacoes": LancamentoFinanceiroSerializer(despesas, many=True).data,
        }
    )


@extend_schema(responses=SPASimpleSerializer)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def vendas_data(request):
    props = get_propriedade_optimizada(request.user)
    if not props:
        return Response({"itens": []})
    receitas = (
        LancamentoFinanceiro.objects.filter(propriedade=props, tipo="RECEITA")
        .select_related("talhao", "safra")
        .order_by("-data")[:30]
    )
    return Response(
        {
            "itens": LancamentoFinanceiroSerializer(receitas, many=True).data,
            "total": sum(float(r.valor) for r in receitas),
        }
    )


@extend_schema(
    parameters=[
        OpenApiParameter(
            name="propriedade_id",
            type=int,
            location=OpenApiParameter.QUERY,
            description="ID da propriedade",
        ),
        OpenApiParameter(
            name="de",
            type=str,
            location=OpenApiParameter.QUERY,
            description="Data início (YYYY-MM-DD)",
        ),
        OpenApiParameter(
            name="ate",
            type=str,
            location=OpenApiParameter.QUERY,
            description="Data fim (YYYY-MM-DD)",
        ),
    ]
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def dre_data(request):
    _ck = f"dre:{request.user.id}:{request.GET.get('propriedade_id', '')}:{request.GET.get('de', '')}:{request.GET.get('ate', '')}"
    _cached = cache.get(_ck)
    if _cached is not None:
        return Response(_cached)
    prop_id = request.GET.get("propriedade_id")

    if not prop_id:
        prop = get_propriedade_optimizada(request.user)
        if not prop:
            return Response(
                {"error": "Propriedade não encontrada"},
                status=status.HTTP_404_NOT_FOUND,
            )
        prop_id = prop.id
    else:
        # Check permissions
        prop = get_object_or_404(Propriedade, id=prop_id, user=request.user)

    de = request.GET.get("de")
    ate = request.GET.get("ate")

    # Default to current year if not provided
    if not de:
        de = f"{timezone.now().year}-01-01"
    if not ate:
        ate = f"{timezone.now().year}-12-31"

    data_inicio = parse_date(de)
    data_fim = parse_date(ate)

    if not data_inicio or not data_fim:
        return Response(
            {"error": "Formato de data inválido. Use YYYY-MM-DD."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        dre = gerar_dre(prop_id, data_inicio, data_fim)
        payload = {"dre": dre}
        cache.set(_ck, payload, 60)
        return Response(payload)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@extend_schema(
    parameters=[
        OpenApiParameter(
            name="propriedade_id",
            type=int,
            location=OpenApiParameter.QUERY,
            description="ID da propriedade",
        ),
        OpenApiParameter(
            name="meses",
            type=int,
            location=OpenApiParameter.QUERY,
            description="Número de meses para projetar",
        ),
    ]
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def cashflow_data(request):
    _ck = f"cashflow:{request.user.id}:{request.GET.get('propriedade_id', '')}:{request.GET.get('meses', '12')}"
    _cached = cache.get(_ck)
    if _cached is not None:
        return Response(_cached)
    prop_id = request.GET.get("propriedade_id")
    meses = int(request.GET.get("meses", 12))

    if not prop_id:
        prop = get_propriedade_optimizada(request.user)
        if not prop:
            return Response(
                {"error": "Propriedade não encontrada"},
                status=status.HTTP_404_NOT_FOUND,
            )
        prop_id = prop.id
    else:
        prop = get_object_or_404(Propriedade, id=prop_id, user=request.user)

    try:
        fluxo = projetar_fluxo_caixa(prop_id, meses)
        payload = {"fluxo": fluxo}
        cache.set(_ck, payload, 60)
        return Response(payload)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@extend_schema(
    parameters=[
        OpenApiParameter(
            name="propriedade_id",
            type=int,
            location=OpenApiParameter.QUERY,
            description="ID da propriedade",
        ),
        OpenApiParameter(
            name="ano",
            type=int,
            location=OpenApiParameter.QUERY,
            description="Ano base do LCDPR",
        ),
    ]
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def lcdpr_download(request):
    from app.services.lcdpr_http import responder_lcdpr

    return responder_lcdpr(request)


@extend_schema(
    parameters=[
        OpenApiParameter(
            name="safra_id",
            type=int,
            location=OpenApiParameter.QUERY,
            description="ID da safra",
        ),
    ]
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def custo_producao_data(request):
    safra_id = request.GET.get("safra_id")
    if not safra_id:
        return Response(
            {"error": "safra_id é obrigatório"}, status=status.HTTP_400_BAD_REQUEST
        )
    _ck = f"custo:{request.user.id}:{safra_id}"
    _cached = cache.get(_ck)
    if _cached is not None:
        return Response(_cached)
    try:
        # Check permissions
        safra = get_object_or_404(Safra, id=safra_id, propriedade__user=request.user)
        resultado = calcular_custo_producao(safra.id)
        cache.set(_ck, resultado, 60)
        return Response(resultado)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@extend_schema(
    parameters=[
        OpenApiParameter(
            name="propriedade_id",
            type=int,
            location=OpenApiParameter.QUERY,
            description="ID da propriedade",
        ),
    ]
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def comparativo_safras_data(request):
    """Retorna dados de 2 ou mais safras para comparação (Receita, Custo, Margem)"""
    _ck = f"comp:{request.user.id}"
    _cached = cache.get(_ck)
    if _cached is not None:
        return Response(_cached)
    prop_id = request.GET.get("propriedade_id")

    if not prop_id:
        prop = get_propriedade_optimizada(request.user)
        if not prop:
            return Response(
                {"error": "Propriedade não encontrada"},
                status=status.HTTP_404_NOT_FOUND,
            )
        prop_id = prop.id
    else:
        prop = get_object_or_404(Propriedade, id=prop_id, user=request.user)

    try:
        # Busca ultimas 3 safras concluídas ou em andamento
        # `Safra` nao tem `data_inicio`: os campos de calendario do modelo sao
        # `data_plantio` e `data_colheita`. Ordenar por `-data_inicio` levantava
        # FieldError e a tela inteira de comparativo respondia 500.
        safras = Safra.objects.filter(propriedade=prop).order_by("-data_plantio")[:3]
        safras_comparativo = []

        for s in reversed(safras):
            custos = calcular_custo_producao(s.id)
            receitas = (
                LancamentoFinanceiro.objects.filter(safra=s, tipo="RECEITA").aggregate(
                    total=Sum("valor")
                )["total"]
                or 0
            )

            custo_total = custos.get("custo_total", 0)
            lucro = float(receitas) - custo_total
            margem = (lucro / float(receitas) * 100) if float(receitas) > 0 else 0

            # `Safra` nao tem campo `nome` - o rotulo da safra e'
            # `safra_nome`, e a cultura vem do relacao `cultura`.
            # `s.nome` levantava AttributeError e derrubava o comparativo.
            rotulo_safra = s.safra_nome or (s.cultura.nome if s.cultura else "Sem nome")
            safras_comparativo.append(
                {
                    "id": s.id,
                    "nome": f"{rotulo_safra} ({s.cultura.nome if s.cultura else 'Sem Cultura'})",
                    "ano": s.ano,
                    "receita": float(receitas),
                    "custo": custo_total,
                    "lucro": lucro,
                    "margem": round(margem, 2),
                }
            )

        payload = {"comparativo": safras_comparativo}
        cache.set(_ck, payload, 60)
        return Response(payload)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@extend_schema(responses=SPASimpleSerializer)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def cotacoes_data(request):
    """Retorna cotações agrícolas cacheadas"""
    try:
        dados = CotacoesService.get_cotacoes()
        return Response(dados)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ==========================================================================
# LCDPR 1.3 Views — Páginas web com padrão visual LCDPR
# ==========================================================================
@extend_schema(
    parameters=[
        OpenApiParameter(
            name="ano",
            type=int,
            location=OpenApiParameter.QUERY,
            description="Ano base do LCDPR",
        ),
        OpenApiParameter(
            name="escopo",
            type=str,
            location=OpenApiParameter.QUERY,
            description="Escopo: propriedade ou contribuinte",
        ),
    ]
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def lcdpr_diagnostico_api(request):
    """API de diagnóstico do LCDPR — retorna JSON com pendências e avisos."""
    return responder_lcdpr(request, diagnostico=True)


@extend_schema(
    request=None,
    responses={
        200: {"description": "Arquivo LCDPR .txt", "content": {"text/plain": {}}}
    },
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def lcdpr_gerar_arquivo(request):
    """Gera o arquivo LCDPR via POST (formulário web)."""
    return responder_lcdpr(request, diagnostico=False)
