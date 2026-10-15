from datetime import datetime, timedelta

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from app.hierarquia import get_propriedade_optimizada
from app.models.core import Propriedade
from app.services.clima import ClimaService
from app.services.coordenadas import resolver as resolver_coordenadas


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
def clima_previsao_data(request):
    """Previsão do tempo para a propriedade, resolvida por cidade/estado.

    A coordenada vem de `services.coordenadas.resolver` — o caminho ÚNICO
    do sistema. Antes, esta view tinha o seu próprio, com um default de
    Brasília e o centroide do talhão. Isso punha o clima 712 km longe da
    fazenda: uma propriedade em Muzambinho/MG recebia o tempo do interior
    de São Paulo. A IA usava outro caminho (`_coords`) que acertava — daí
    as duas discordarem entre si.
    """
    prop_id = request.GET.get("propriedade_id")

    if prop_id:
        prop = get_object_or_404(Propriedade, id=prop_id, user=request.user)
    else:
        prop = get_propriedade_optimizada(request.user)
        if not prop:
            return Response(
                {"error": "Propriedade não encontrada"},
                status=status.HTTP_404_NOT_FOUND,
            )

    coord = resolver_coordenadas(prop)
    if not coord.ok:
        # Sem coordenada declarada. O default antigo era Brasília: dizer o
        # tempo do Distrito Federal a quem planta em Minas é pior que
        # falhar, porque a falha obriga a agir e o default parece
        # resposta.
        return Response(
            {
                "erro": coord.aviso or "sem coordenada para a propriedade",
                "fonte": coord.fonte,
            },
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    try:
        dados = ClimaService.get_previsao(coord.lat, coord.lon)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    dados = dict(dados or {})
    # A origem viaja na resposta: quem vê 22°C pode ler de onde veio, e
    # corrigir se estiver errado.
    dados["fonte_coordenadas"] = coord.fonte
    if coord.origem_detalhe:
        dados["fonte_coordenadas_detalhe"] = coord.origem_detalhe
    if coord.aviso:
        dados["aviso_coordenadas"] = coord.aviso
    if coord.candidatos_rejeitados:
        dados["coordenadas_rejeitadas"] = coord.candidatos_rejeitados
    return Response(dados)


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
def clima_historico_data(request):
    """Histórico de clima dos últimos 30 dias, no mesmo lugar da previsão.

    Se a previsão e o histórico usassem lugares diferentes, as duas
    séries desmentiam-se a si próprias — e era o que acontecia: esta view
    repetia o bloco do default de Brasília e do centroide.
    """
    prop_id = request.GET.get("propriedade_id")

    if prop_id:
        prop = get_object_or_404(Propriedade, id=prop_id, user=request.user)
    else:
        prop = get_propriedade_optimizada(request.user)
        if not prop:
            return Response(
                {"error": "Propriedade não encontrada"},
                status=status.HTTP_404_NOT_FOUND,
            )

    coord = resolver_coordenadas(prop)
    if not coord.ok:
        return Response(
            {
                "erro": coord.aviso or "sem coordenada para a propriedade",
                "fonte": coord.fonte,
            },
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    hoje = datetime.now()
    inicio = (hoje - timedelta(days=30)).strftime("%Y-%m-%d")
    fim = (hoje - timedelta(days=1)).strftime("%Y-%m-%d")

    try:
        dados = ClimaService.get_historico(coord.lat, coord.lon, inicio, fim)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    dados = dict(dados or {})
    dados["fonte_coordenadas"] = coord.fonte
    if coord.origem_detalhe:
        dados["fonte_coordenadas_detalhe"] = coord.origem_detalhe
    if coord.aviso:
        dados["aviso_coordenadas"] = coord.aviso
    return Response(dados)


@extend_schema(
    parameters=[
        OpenApiParameter(
            name="talhao_id",
            type=int,
            location=OpenApiParameter.QUERY,
            description="ID do talhão",
        ),
    ]
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def ndvi_talhao_data(request):
    """NDVI do talhao, de Sentinel-2, quando ha fonte.

    Sem fonte, devolve `ndvi_medio: None` com o motivo. Ver NDVIService para
    porque o valor antigo (um sha256 do id) nao podia ser chamado NDVI.
    """
    from app.models.core import Talhao
    from app.services.ndvi import NDVIService

    talhao_id = request.GET.get("talhao_id")
    if not talhao_id:
        return Response(
            {"error": "talhao_id é obrigatório"}, status=status.HTTP_400_BAD_REQUEST
        )

    talhao = get_object_or_404(Talhao, id=talhao_id, propriedade__user=request.user)

    try:
        dados = NDVIService.process_talhao_ndvi(talhao.id)
        return Response(dados)
    except Exception as e:
        # Sem valor de satelite, o certo e' "indisponivel" — o mesmo que o
        # servico ja devolve quando nao ha credencial. Um 500 aqui dizia "a
        # app esta partida" a um produtor cujo unico problema era nao ter
        # Copernicus configurado.
        return Response(
            {
                "talhao_id": talhao.id,
                "ndvi_medio": None,
                "cobertura_nuvens": None,
                "data_captura": None,
                "satelite": None,
                "sanidade": None,
                "heatmap_url": None,
                "fonte_dado": "indisponivel",
                "motivo": f"{type(e).__name__}: {e}",
            }
        )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def ndvi_heatmap(request, talhao_id):
    """Heatmap NDVI 10m.

    Desenha o valor quando existe uma medicao real. Sem medicao, diz que
    nao ha: um rectangulo colorido com "Sentinel-2 L2A" por baixo e um
    veredicto agronómico ao lado e' uma imagem de satelite falsificada --
    o produtor que decisse irrigar por aquela cor estaria a decidir sobre
    um hash.
    """
    from django.http import HttpResponse

    from app.models.core import Talhao
    from app.services.ndvi import NDVIService

    talhao = get_object_or_404(Talhao, id=talhao_id, propriedade__user=request.user)
    dados = NDVIService.process_talhao_ndvi(talhao.id)

    if dados.get("ndvi_medio") is None:
        motivo = (dados.get("motivo") or "NDVI indisponivel")[:70]
        svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="300" height="180" viewBox="0 0 300 180"><rect width="300" height="180" fill="#1f2937"/><text x="150" y="78" text-anchor="middle" fill="#9ca3af" font-family="Inter,sans-serif" font-size="15" font-weight="600">Sem NDVI</text><text x="150" y="102" text-anchor="middle" fill="#6b7280" font-family="Inter,sans-serif" font-size="9">Talhao {talhao.id} · nao ha medicao de satelite</text><text x="150" y="122" text-anchor="middle" fill="#4b5563" font-family="Inter,sans-serif" font-size="8">{motivo}</text></svg>"""
        return HttpResponse(svg, content_type="image/svg+xml")

    ndvi = dados["ndvi_medio"]
    # cor por NDVI
    if ndvi >= 0.65:
        color = "#0f9d6e"
    elif ndvi >= 0.5:
        color = "#84cc16"
    else:
        color = "#f59e0b"
    captura = (dados.get("data_captura") or "")[:10]
    satelite = dados.get("satelite") or "Sentinel-2 L2A"
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="300" height="180" viewBox="0 0 300 180"><rect width="300" height="180" fill="{color}" opacity="0.85"/><text x="150" y="80" text-anchor="middle" fill="white" font-family="Inter,sans-serif" font-size="28" font-weight="700">{ndvi}</text><text x="150" y="105" text-anchor="middle" fill="white" font-family="Inter,sans-serif" font-size="11" opacity="0.9">{dados["sanidade"]}</text><text x="150" y="125" text-anchor="middle" fill="white" font-size="9" opacity="0.7">Talhao {talhao.id} • {captura}</text><text x="150" y="145" text-anchor="middle" fill="white" font-size="8" opacity="0.6">{satelite} • nuvens {dados["cobertura_nuvens"]}%</text></svg>"""
    return HttpResponse(svg, content_type="image/svg+xml")


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def compliance_ambiental_data(request):
    """Retorna o relatório de compliance ambiental da propriedade do usuário"""
    import logging

    from app.services.compliance_ambiental import ComplianceAmbientalService

    logger = logging.getLogger(__name__)

    propriedade_id = request.GET.get("propriedade_id")
    if propriedade_id:
        # Sem este filtro, ?propriedade_id=N entregava o relatório
        # CAR e de APP do vizinho a qualquer autenticado.
        prop = get_object_or_404(Propriedade, id=propriedade_id, user=request.user)
    else:
        prop = get_propriedade_optimizada(request.user)
        if not prop:
            return Response(
                {"error": "Propriedade não encontrada"},
                status=status.HTTP_404_NOT_FOUND,
            )

    try:
        dados = ComplianceAmbientalService.relatorio_compliance(prop.id)
        return Response(dados)
    except Exception:
        logger.exception("compliance_ambiental_data: propriedade=%s", prop.id)
        return Response(
            {"error": "Erro ao gerar relatório de compliance"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
