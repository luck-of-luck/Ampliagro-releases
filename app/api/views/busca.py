"""Endpoints pró-IA: busca textual unificada + contexto da fazenda em 1 chamada.

A IA resolve nomes ("talhão Sul", "João") sem N fetches: um GET com ?q=
devolve os candidatos de todos os cadastros do usuário, já escopados.
"""

from collections import defaultdict

from django.db.models import Count, Q, Sum
from django.db.models.functions import Coalesce
from drf_spectacular.utils import extend_schema
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from app.models import (
    Animal,
    Cultura,
    Device,
    Funcionario,
    Insumo,
    LoteAquatico,
    Safra,
    Talhao,
)


def _top(qs, label, chave_nome="nome", limite=5):
    return [
        {"tipo": label, "id": o.id, "nome": getattr(o, chave_nome) or str(o)}
        for o in qs[:limite]
    ]


@extend_schema(responses={"type": "object"})
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def busca_geral_data(request):
    """GET /api/busca-geral/?q=sul — candidatos em todos os cadastros."""
    q = (request.GET.get("q") or "").strip()
    if len(q) < 2:
        return Response({"resultados": [], "dica": "use ?q= com 2+ letras"})
    u = request.user
    grupos = []
    grupos += _top(
        Talhao.objects.filter(propriedade__user=u, nome__icontains=q), "talhao"
    )
    grupos += _top(Cultura.objects.filter(nome__icontains=q), "cultura")
    grupos += _top(
        Safra.objects.filter(propriedade__user=u).filter(
            Q(safra_nome__icontains=q) | Q(cultura__nome__icontains=q)
        ),
        "safra",
        "safra_nome",
    )
    grupos += _top(
        Funcionario.objects.filter(propriedade__user=u, nome__icontains=q),
        "funcionario",
    )
    grupos += _top(
        Animal.objects.filter(propriedade__user=u).filter(
            Q(raca__icontains=q) | Q(especie__icontains=q)
        ),
        "animal",
        "raca",
    )
    grupos += _top(
        LoteAquatico.objects.filter(propriedade__user=u, ambiente__icontains=q),
        "lote_aquatico",
        "ambiente",
    )
    grupos += _top(
        Insumo.objects.filter(propriedade__user=u, nome__icontains=q), "insumo"
    )
    grupos += _top(
        Device.objects.filter(propriedade__user=u, nome__icontains=q), "device"
    )
    return Response({"resultados": grupos[:20]})


@extend_schema(responses={"type": "object"})
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def contexto_ia_data(request):
    """GET /api/contexto-ia/ — tudo que a IA precisa saber em 1 chamada."""
    from django.utils import timezone as _tz

    from app.models import Propriedade

    u = request.user
    props = list(Propriedade.objects.filter(user=u).order_by("nome"))
    if not props:
        return Response({"propriedades": [], "totais": {}})
    ano = _tz.now().year
    out_props = []
    totais = {
        "talhoes": 0,
        "safras_ano": 0,
        "animais": 0,
        "lotes_aquaticos": 0,
        "funcionarios": 0,
        "devices": 0,
    }

    # Otimizacao: as contagens saem de 6 `COUNT(*)/SUM()` agrupados, no total.
    #
    # MEDIDO antes: o corpo do `for p in props` fazia 8 queries POR PROPRIEDADE
    # (6 contagens + as 2 listas do payload, que repetem as contagens). Com N
    # propriedades: 8N + 1. Medido em teste: 9 queries com 1 propriedade, 57
    # com 7 — e' a razao, nao o numero, que mata.
    #
    # `p.animais.all()` era o pior: trazia TODAS as linhas de Animal para o
    # servidor somar uma coluna. Com 5.000 cabecas isso e' 5.000 objetos
    # construido e descartados para devolver um inteiro. `Sum` faz o mesmo
    # numero dentro do banco e devolve uma linha.
    #
    # Os `default=0` sao obrigatorios, nao cosmeticos: uma propriedade sem
    # animais nao aparece em nenhum grupo, e sem default o `.get(...)` devolveria
    # None — que a soma transformaria em TypeError. `Coalesce` resolve tambem o
    # `SUM` de NULL (a coluna `quantidade` aceita NULL).
    ids = [p.id for p in props]
    # {propriedade_id: {metrica: valor}}. A metrica e' a chave interna porque as
    # seis linhas de SQL devolvem todas a MESMA coluna de agrupamento
    # (`propriedade_id`): agrupar por ela sem um nome proprio faria a ultima
    # sobrescrever as cinco anteriores.
    _por_prop: dict = defaultdict(dict)

    def _agrupado(qs, metrica, expr):
        for linha in qs.values("propriedade_id").annotate(_v=expr):
            _por_prop[linha["propriedade_id"]][metrica] = linha["_v"]

    _agrupado(
        Talhao.objects.filter(propriedade_id__in=ids, ativo=True),
        "talhoes",
        Count("id"),
    )
    _agrupado(
        Safra.objects.filter(propriedade_id__in=ids, ano=ano),
        "safras_ano",
        Count("id"),
    )
    _agrupado(
        Animal.objects.filter(propriedade_id__in=ids),
        "animais",
        Coalesce(Sum("quantidade"), 0),
    )
    _agrupado(
        LoteAquatico.objects.filter(propriedade_id__in=ids),
        "lotes_aquaticos",
        Count("id"),
    )
    _agrupado(
        Funcionario.objects.filter(propriedade_id__in=ids, ativo=True),
        "funcionarios",
        Count("id"),
    )
    _agrupado(
        Device.objects.filter(propriedade_id__in=ids),
        "devices",
        Count("id"),
    )

    # As DUAS listas do payload (`talhoes[:20]`, `safras[:10]`) sao 2 queries
    # para TODAS as propriedades, em vez de 2 por propriedade — `p.talhoes.all()`
    # dentro do loop voltaria a ser uma query por propriedade, que e' exactamente
    # o que esta mudanca remove.
    #
    # O `[:20]` e o `[:10]` sao aplicados em Python, e nao no queryset, porque o
    # limite e' POR PROPRIEDADE: um `.filter(...)[:20]` traria os 20 primeiros de
    # todas as fazendas juntas, e o produtor com 7 fazendas veria uma Property
    # com 20 talhoes e outra vazia. `values_list` em vez de modelos nao construi
    # objetos que so' servem para extrair dois campos.
    _talhoes_por_prop = defaultdict(list)
    for _pid, _nome in Talhao.objects.filter(
        propriedade_id__in=ids, ativo=True
    ).values_list("propriedade_id", "nome"):
        _talhoes_por_prop[_pid].append(_nome)

    _safras_por_prop = defaultdict(list)
    for _pid, _cult, _area in Safra.objects.filter(
        propriedade_id__in=ids, ano=ano
    ).values_list("propriedade_id", "cultura__nome", "area_plantada"):
        _safras_por_prop[_pid].append(f"{_cult} ({_area} ha)")

    for p in props:
        c = _por_prop[p.id]
        n_tal = c.get("talhoes", 0)
        n_saf = c.get("safras_ano", 0)
        n_ani = c.get("animais", 0)
        n_aq = c.get("lotes_aquaticos", 0)
        n_fun = c.get("funcionarios", 0)
        n_dev = c.get("devices", 0)
        totais["talhoes"] += n_tal
        totais["safras_ano"] += n_saf
        totais["animais"] += n_ani
        totais["lotes_aquaticos"] += n_aq
        totais["funcionarios"] += n_fun
        totais["devices"] += n_dev
        out_props.append(
            {
                "id": p.id,
                "nome": p.nome,
                "cidade": p.cidade,
                "uf": p.uf,
                "area_total": float(p.area_total or 0),
                "talhoes": _talhoes_por_prop[p.id][:20],
                "safras_ano": _safras_por_prop[p.id][:10],
                "contagens": {
                    "talhoes": n_tal,
                    "safras_ano": n_saf,
                    "animais": n_ani,
                    "lotes_aquaticos": n_aq,
                    "funcionarios": n_fun,
                    "devices": n_dev,
                },
            }
        )
    return Response({"ano": ano, "propriedades": out_props, "totais": totais})
