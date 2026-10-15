import json
import logging
import math
import random
import re
import traceback
import unicodedata
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
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from app.api.perms import LeituraGlobalEscritaStaff
from app.api.serializers import *
from app.hierarquia import *
from app.models import *

from .utils import *  # noqa: F403

# Fix: import * não traz nomes com _ — importar explicitamente
from .utils import (  # noqa: F401
    _CULTURES_CONFIG_CACHE,
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


def _sem_acento(s):
    """'Café Arábica' -> 'cafe arabica'."""
    return "".join(
        c
        for c in unicodedata.normalize("NFD", str(s or "").casefold())
        if unicodedata.category(c) != "Mn"
    )


class PaginaCultura(PageNumberPagination):
    """709 linhas PARTILHADAS e estaticas; `PAGE_SIZE` global e' 50.

    MEDIDO: o `wizList` do assistente levava so' as 50 primeiras — todas com
    nome a comecar por 'A' (Abacate, Abacate-manteiga, Abacaxi, Abaca, Abio,
    Abobrinha). Cafe, Arroz, Soja, Milho e Feijao NAO estavam la dentro. O
    fallback `wizAcharNome` pesquisava essa janela e nao via nenhuma delas.
    O envelope `{count, results}` fica igual: muda o tamanho, nao o contrato.
    """

    page_size = 1000
    page_size_query_param = "page_size"
    max_page_size = 1000


class CulturaViewSet(viewsets.ModelViewSet):
    """O catálogo de culturas é PARTILHADO — e é por isso que este queryset não
    filtra por utilizador, ao contrário de todos os outros viewssets.

    Essa ausência é o que torna a mutação perigosa: uma linha de `Cultura`
    alterada aqui é uma linha que muda para todos os produtores, e as janelas
    de plantio alimentam o calendário, o VRA e o ZARC de cada um.

    `LeituraGlobalEscritaStaff` fecha a alteração e o apagamento sem partir
    o `POST` da página de cadastro de cultura. Ver `app/api/perms.py` para o
    porquê e para o que fica por fazer (um `Cultura` com dono).

    O `PROTECT` nas FKs continua a ser a segunda rede: mesmo staff recebe um
    409 em vez de perder safras de gente.
    """

    filterset_fields = ["grupo", "ativo"]
    ordering_fields = ["nome", "grupo"]
    pagination_class = PaginaCultura
    queryset = Cultura.objects.all()
    serializer_class = CulturaSerializer
    permission_classes = [LeituraGlobalEscritaStaff]

    def get_queryset(self):
        """Busca que sobrevive ao acento e a mais de uma palavra.

        MEDIDO 2026-10-05 em 709 linhas, reproduzindo `wizBuscarCultura`
        (app/static/js/ia-local/ia-local.js:3572), que envia o texto CRU:

            search='cafe'         -> 1   ['Cafe']       (passa por sorte:
                                                a base tem 'Cafe' E 'Café')
            search='feijao'       -> 0                 (nao ha 'feijao' sem acento)
            search='cafe arabica' -> 0                 (multi-palavra)
            search='arroz agulha' -> 0                 (multi-palavra)

        Duas causas, e so' duas:

        1. `SearchFilter` com `search_fields=["nome"]` gera `nome__icontains`,
           que o SQLite traduz para `LIKE`. O `LIKE` do SQLite so' faz
           case-folding ASCII: `C` casa com `c`, mas `é` nunca casa com `e`.
           Por isso 'Feijão' LIKE '%feijao%' e' FALSO. 'Cafe' passou so'
           porque existe TAMEM a linha 'Cafe' —Luck de dados, nao o metodo.

        2. `icontains` e' substring LITERAL. `nome__icontains='cafe arabica'`
           procura a frase exacta, que nao existe em 'Café Arábica'.

        Aqui as duas fecham: normaliza os dois lados e exige que TODAS as
        palavras do pedido aparecam no nome. 'cafe arabica' passa a casar
        'Café Arábica'.

        O `pk__in` e' das 709 linhas do catalogo partilhado, com
        `only("id","nome")`. Fica `Q(...) | Q(...)` para a busca nativa
        continuar a funcionar — NINGUEM dos dois lados perde.

        Vai em `get_queryset` e nao num filtro novo para o `filter_queryset`
        do DRF continuar a poder aplicar `grupo`/`ativo` sobre o resultado.
        """
        qs = super().get_queryset()
        bruto = (self.request.query_params.get("search") or "").strip()
        if bruto:
            palavras = [p for p in re.split(r"[^a-z0-9]+", _sem_acento(bruto)) if p]
            if not palavras:
                bruto = ""
        if bruto:
            ids = [
                c.pk
                for c in qs.only("id", "nome")
                if all(p in _sem_acento(c.nome) for p in palavras)
            ]
            qs = qs.filter(Q(nome__icontains=bruto) | Q(pk__in=ids))
        if str(self.request.query_params.get("dedupe") or "").lower() in (
            "1",
            "true",
            "yes",
            "sim",
        ):
            qs = self._dedupe(qs)
        return qs

    def _dedupe(self, qs):
        """Uma linha por planta — a de MENOR id. Só com `?dedupe=1`.

        MEDIDO 2026-10-05: a base tem 25 grupos de nomes que normalizam igual,
        e a busca devolvia as DUAS linhas em todos os 25. Pior: em muitos a
        duplicata tem o nome LITERALMENTE igual e um `grupo` diferente —


            busca 'acai' -> ['Açaí', 'Açaí']  ids 28310 e 28476
            busca 'chuchu' -> ['Chuchu', 'Chuchu']  grupos hortalicas e trepadeiras

        `wizSafraStep` com `hits.length > 1` responde "Achei 2: Açaí, Açaí.
        Qual delas?" — duas opcoes com o mesmo nome, e a escolha do produtor
        manda a safra para uma cultura arbitraria, em silencio.

        A regra NAO e' minha: `app/views/guias.py::_indice_cultura_por_nome`
        ja resolve identico por menor id, e e' o que `_resolver_cultura_key`
        usa. Aqui a busca nao seguia essa regra — as duas portas davam ids
        diferentes para a mesma planta. Passa a seguir.

        E' OPCIONAL de proposito: quem lista o catalogo para VER a divida
        (duas linhas iguais) precisa de as ver. Quem escolhe para TRABALHAR
        precisa de uma so. Por isso e' `?dedupe=1` e nao sempre.
        """
        canonicos = {}
        for c in qs.order_by("id").only("id", "nome"):
            canonicos.setdefault(_sem_acento(c.nome), c.pk)
        return qs.filter(pk__in=set(canonicos.values()))


@extend_schema(responses=SPASimpleSerializer)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def ibge_proxy_data(request):
    cultura_id = request.GET.get("cultura", "").strip()
    uf = request.GET.get("uf", "").strip().upper()
    force_fallback = request.GET.get("fallback", "").lower() == "true"

    # Normaliza: cult-graos-café / cult-leguminosas-soja -> cultura-cafe / cultura-soja
    import unicodedata

    def _norm(s):
        return "".join(
            c
            for c in unicodedata.normalize("NFD", str(s or "").lower())
            if unicodedata.category(c) != "Mn"
        )

    norm_id = _norm(cultura_id)
    BREED_TO_SPECIES = {
        "nelore": "bovino",
        "angus": "bovino",
        "brahman": "bovino",
        "guzera": "bovino",
        "holandes": "bovino",
        "boi gordo": "bovino",
        "bezerro": "bovino",
        "landrace": "suino",
        "large-white": "suino",
        "duroc": "suino",
        "suino": "suino",
        "galinha": "aves",
        "frango": "aves",
        "peru": "aves",
        "codorna": "codorna",
        "ovelha": "ovino",
        "cabra": "caprino",
        "quarto-de-milha": "equino",
        "bufalo": "bubalino",
        "tilapia": "tilapia",
        "tambaqui": "tambaqui",
        "pacu": "pacu",
        "pintado": "pintado",
        "carpa": "carpa",
        "truta": "truta",
        "camarao": "camarao",
        "ostra": "ostra",
    }
    mapping = IBGE_TABELAS.get(cultura_id)
    if not mapping:
        short = norm_id.split("-")[-1]
        species = BREED_TO_SPECIES.get(short)
        candidates = []
        if species:
            candidates.append(f"cultura-{species}")
        candidates.extend([f"cultura-{short}", short, f"cult-{short}", norm_id])
        for k in candidates:
            if k in IBGE_TABELAS:
                mapping = IBGE_TABELAS[k]
                break
        if not mapping:
            for kk, vv in IBGE_TABELAS.items():
                if short and short in _norm(kk):
                    mapping = vv
                    break
            if not mapping and species:
                for kk, vv in IBGE_TABELAS.items():
                    if species in _norm(kk):
                        mapping = vv
                        break
    result = {
        "metrics": [],
        "history": [],
        "history_by_metric": {},
        "source": "no_data",
        "cultura": cultura_id,
        "uf": uf or "BR",
    }

    if not mapping:
        return Response(result)

    # Try real IBGE SIDRA if mapped and not forced fallback
    if not force_fallback:
        tabela, codigo, nome = mapping
        nivel = "n1/1"
        if uf and uf in UF_CODES:
            nivel = f"n3/{UF_CODES[uf]}"
        # Classification code & column layout varies by table
        # PAM (5457), PEVS (289,291): D3=ano, D4=variavel
        # PPM (3939,3940): D3=variavel, D4=ano (swapped)
        if tabela == 5457:
            classificacao = "c782"
            class_col = "D4"
            year_col = "D3"
            var_id = "allxp"
        elif tabela == 289:
            classificacao = "c193"
            class_col = "D4"
            year_col = "D3"
            var_id = "allxp"
        elif tabela == 291:
            classificacao = "c194"
            class_col = "D4"
            year_col = "D3"
            var_id = "allxp"
        elif tabela == 3939:
            classificacao = "c79"
            class_col = "D4"
            year_col = "D3"
            var_id = "105"
        elif tabela == 3940:
            classificacao = "c654"
            class_col = "D4"
            year_col = "D3"
            var_id = "4146,215"
        else:
            classificacao = "c194"
            class_col = "D4"
            year_col = "D3"
            var_id = "allxp"
        # Fetch up to 10 recent years so each metric has its own history
        from datetime import date

        cy = date.today().year
        url = f"https://apisidra.ibge.gov.br/values/t/{tabela}/{nivel}/{classificacao}/{codigo}/p/{cy - 9}-{cy}/v/{var_id}/f/n?formato=json"
        try:
            resp = _ibge_cached_get(url=url, timeout=3)
            if resp and getattr(resp, "ok", False):
                data = resp.json()
                if isinstance(data, list) and len(data) > 0:
                    # Build per-variable, per-year values (somente números válidos)
                    var_by_year = {}
                    rows = data[1:] if isinstance(data, list) and len(data) > 1 else []
                    for row in rows:
                        ano = (row.get(f"{year_col}N") or "").strip()
                        var_name = (row.get(f"{class_col}N") or "").strip()
                        unid = (row.get("MN") or "").strip()
                        valor = _to_float(row.get("V"))

                        if not ano or not var_name or var_name in ("Variável", "Ano"):
                            continue
                        if valor is None:
                            continue

                        if var_name not in var_by_year:
                            var_by_year[var_name] = {}
                        var_by_year[var_name][ano] = {"valor": valor, "unid": unid}

                    # Build history_by_metric for each metric key
                    hist_map = {}
                    prod_hist = []

                    # Map SIDRA variable names → metric keys
                    var_to_metric = {
                        "Quantidade produzida": "producao_total",
                        "Quantidade produzida na extração vegetal": "producao_total",
                        "Quantidade produzida na silvicultura": "producao_total",
                        "Área plantada": "area_plantada",
                        "Área plantada ou destinada à colheita": "area_plantada",
                        "Área destinada à colheita": "area_plantada",
                        "Área colhida": "area_plantada",
                        "Rendimento médio da produção": "produtividade",
                        "Valor da produção": "receita_estimada",
                        "Valor da produção na extração vegetal": "receita_estimada",
                        "Valor da produção na silvicultura": "receita_estimada",
                        # PPM Livestock (tabela 3939)
                        "Efetivo dos rebanhos": "cabecas_total",
                        # PPM Aquicultura (tabela 3940)
                        "Produção da aquicultura": "producao_total",
                    }
                    for var_name, years_dict in var_by_year.items():
                        mkey = var_to_metric.get(var_name)
                        if not mkey:
                            continue
                        sorted_years = sorted(years_dict.keys())
                        vals = []
                        for ano in sorted_years:
                            v = years_dict[ano]
                            vals.append({"ano": ano, "valor": v["valor"]})
                        if vals:
                            hist_map[mkey] = vals
                            if mkey == "producao_total":
                                prod_hist = vals

                    if hist_map:
                        result["history"] = (
                            prod_hist if prod_hist else next(iter(hist_map.values()))
                        )
                        result["history_by_metric"] = hist_map
                        result["source"] = "ibge"

                        # Get most recent year metrics
                        is_pevs = tabela in (289, 291)
                        is_ppm_livestock = tabela == 3939
                        is_ppm_aquaculture = tabela == 3940

                        if is_ppm_livestock:
                            qty_var = "Efetivo dos rebanhos"
                            val_var = "Efetivo dos rebanhos"
                        elif is_ppm_aquaculture:
                            qty_var = "Produção da aquicultura"
                            val_var = "Valor da produção"
                        elif is_pevs:
                            qty_var = (
                                "Quantidade produzida na extração vegetal"
                                if tabela == 289
                                else "Quantidade produzida na silvicultura"
                            )
                            val_var = (
                                "Valor da produção na extração vegetal"
                                if tabela == 289
                                else "Valor da produção na silvicultura"
                            )
                        else:
                            qty_var = "Quantidade produzida"
                            val_var = "Valor da produção"

                        if var_by_year.get(qty_var):
                            latest_year = sorted(var_by_year.get(qty_var, {}).keys())[
                                -1
                            ]
                        else:
                            all_years = sorted(
                                {ano for vdict in var_by_year.values() for ano in vdict}
                            )
                            latest_year = all_years[-1] if all_years else ""

                        qtd = var_by_year.get(qty_var, {}).get(latest_year, {})
                        valor_p = (
                            var_by_year.get(val_var, {}).get(latest_year, {}) or qtd
                        )

                        if is_ppm_livestock:
                            metrics_list = [
                                {
                                    "key": "cabecas_total",
                                    "label": "Efetivo do Rebanho",
                                    "value": fmt_num(qtd.get("valor")),
                                    "unit": qtd.get("unid", "cabeças"),
                                },
                            ]
                            if valor_p.get("valor"):
                                metrics_list.append(
                                    {
                                        "key": "receita_estimada",
                                        "label": "Valor da Produção",
                                        "value": fmt_num(valor_p.get("valor")),
                                        "unit": valor_p.get("unid", "R$"),
                                    }
                                )
                        else:
                            receita_val = (
                                fmt_num(valor_p.get("valor")) if valor_p else "—"
                            )
                            receita_unit = (
                                valor_p.get("unid", "R$") if valor_p else "R$"
                            )

                            metrics_list = [
                                {
                                    "key": "producao_total",
                                    "label": "Produção Total",
                                    "value": fmt_num(qtd.get("valor")),
                                    "unit": qtd.get("unid", "t"),
                                },
                                {
                                    "key": "receita_estimada",
                                    "label": "Valor da Produção",
                                    "value": receita_val,
                                    "unit": receita_unit,
                                },
                            ]
                            if not is_pevs and not is_ppm_aquaculture:
                                area_p = (
                                    var_by_year.get(
                                        "Área plantada ou destinada à colheita", {}
                                    ).get(latest_year, {})
                                    or var_by_year.get("Área plantada", {}).get(
                                        latest_year, {}
                                    )
                                    or var_by_year.get(
                                        "Área destinada à colheita", {}
                                    ).get(latest_year, {})
                                )
                                area_c = var_by_year.get("Área colhida", {}).get(
                                    latest_year, {}
                                )
                                rend = var_by_year.get(
                                    "Rendimento médio da produção", {}
                                ).get(latest_year, {})
                                metrics_list.insert(
                                    1,
                                    {
                                        "key": "area_plantada",
                                        "label": "Área (Plantada)",
                                        "value": fmt_num(
                                            area_p.get("valor", area_c.get("valor"))
                                        ),
                                        "unit": area_p.get("unid", "")
                                        or area_c.get("unid", ""),
                                    },
                                )
                                metrics_list.insert(
                                    2,
                                    {
                                        "key": "produtividade",
                                        "label": "Rendimento Médio",
                                        "value": fmt_num(rend.get("valor")),
                                        "unit": rend.get("unid", "kg/ha") or "kg/ha",
                                    },
                                )

                        result["metrics"] = metrics_list
                        return Response(result)
        except Exception as e:
            logger.warning(f"IBGE proxy error for {cultura_id}: {e}")

    # Sem dado do IBGE, NAO se fabrica uma lavoura.
    #
    # Este caminho servia `FALLBACK_METRICS` — 210 culturas com producao,
    # area, produtividade e receita inventadas, mais um `DEFAULT_METRICS`
    # que dava 1 200 t / 30 ha / R$ 900K a qualquer cultura nao mapeada — e
    # ainda por cima `_gen_fallback_history`, que sorteava cinco anos de
    # curva em cima desses numeros. A mesma classe do bug do arroz/milho no
    # dashboard, com o carimbo `source: "fallback"` a dizer que era
    # fallback, o que nao e' o mesmo que dizer que e' verdade: o produtor
    # via uma curva de cinco anos e uma receita de R$ 8,1 M sem forma de
    # saber que nada disso foi medido.
    #
    # Sem dado do IBGE, a resposta honesta e' a mesma que a do dashboard:
    # sem dado, com o motivo, e a dizer que o IBGE nao respondeu.
    if mapping:
        result["source"] = "indisponivel"
        result["fonte_dado"] = "indisponivel"
        result["metrics"] = []
        result["history_by_metric"] = {}
        result["history"] = []
        result["motivo"] = (
            f"O IBGE nao devolveu dados para '{cultura_id}' "
            f"(SIDRA tabela {mapping}). Nao ha valor de mercado para esta "
            "cultura sem a fonte — o sistema nao estima receita, "
            "produtividade nem preco."
        )
        return Response(result)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def ibge_ufs(request):
    """Return list of UFs with dados reais no IBGE para a cultura informada."""
    cultura_id = request.GET.get("cultura", "").strip()
    import unicodedata

    def _norm2(s):
        return "".join(
            c
            for c in unicodedata.normalize("NFD", str(s or "").lower())
            if unicodedata.category(c) != "Mn"
        )

    norm_id = _norm2(cultura_id)
    BREED_TO_SPECIES2 = {
        "nelore": "bovino",
        "angus": "bovino",
        "brahman": "bovino",
        "guzera": "bovino",
        "holandes": "bovino",
        "boi gordo": "bovino",
        "bezerro": "bovino",
        "landrace": "suino",
        "large-white": "suino",
        "duroc": "suino",
        "suino": "suino",
        "galinha": "aves",
        "frango": "aves",
        "peru": "aves",
        "codorna": "codorna",
        "ovelha": "ovino",
        "cabra": "caprino",
        "quarto-de-milha": "equino",
        "bufalo": "bubalino",
        "tilapia": "tilapia",
        "tambaqui": "tambaqui",
        "pacu": "pacu",
        "pintado": "pintado",
        "carpa": "carpa",
        "truta": "truta",
        "camarao": "camarao",
        "ostra": "ostra",
    }
    mapping = IBGE_TABELAS.get(cultura_id)
    if not mapping:
        short2 = norm_id.split("-")[-1]
        species2 = BREED_TO_SPECIES2.get(short2)
        cands = []
        if species2:
            cands.append(f"cultura-{species2}")
        cands.extend([f"cultura-{short2}", short2, norm_id])
        for k in cands:
            if k in IBGE_TABELAS:
                mapping = IBGE_TABELAS[k]
                break
        if not mapping:
            for kk, vv in IBGE_TABELAS.items():
                if short2 and short2 in _norm2(kk):
                    mapping = vv
                    break
            if not mapping and species2:
                for kk, vv in IBGE_TABELAS.items():
                    if species2 in _norm2(kk):
                        mapping = vv
                        break
    if not mapping:
        return Response(
            {"ufs": [], "uf_options": [], "cultura": cultura_id, "source": "no_data"}
        )

    tabela, codigo, nome = mapping
    if tabela == 5457:
        classificacao = "c782"
        var_id = "allxp"
    elif tabela == 289:
        classificacao = "c193"
        var_id = "allxp"
    elif tabela == 291:
        classificacao = "c194"
        var_id = "allxp"
    elif tabela == 3939:
        classificacao = "c79"
        var_id = "105"
    elif tabela == 3940:
        classificacao = "c654"
        var_id = "4146,215"
    else:
        classificacao = "c194"
        var_id = "allxp"

    from datetime import date

    cy = date.today().year
    years = f"{cy - 6}-{cy}"
    url = f"https://apisidra.ibge.gov.br/values/t/{tabela}/n3/all/{classificacao}/{codigo}/p/{years}/v/{var_id}/f/n?formato=json"

    available = {}
    try:
        resp = _ibge_cached_get(url=url, timeout=3)
        if resp and getattr(resp, "ok", False):
            data = resp.json()
            rows = data[1:] if isinstance(data, list) and len(data) > 1 else []
            for row in rows:
                uf_nome = (row.get("D1N") or "").strip()
                if not uf_nome or uf_nome == "Unidade da Federação":
                    continue
                valor = _to_float(row.get("V"))
                if valor is None:
                    continue
                sigla = UF_NAME_TO_SIGLA.get(uf_nome)
                if sigla:
                    available[sigla] = uf_nome
    except Exception as e:
        logger.warning(f"IBGE UFs error for {cultura_id}: {e}")

    ordered = sorted(available.keys(), key=lambda s: UF_CODES.get(s, 999))
    uf_options = [
        {"sigla": sigla, "nome": available.get(sigla, sigla)} for sigla in ordered
    ]
    return Response(
        {
            "ufs": ordered,
            "uf_options": uf_options,
            "cultura": cultura_id,
            "tabela": tabela,
            "nome": nome,
            "source": "ibge",
        }
    )


def _ibge_cached_get(url, timeout=3):
    """GET com cache Redis 10min + TTL memória (evita martelar a apisidra). Timeout curto 3s."""
    import requests as _req
    from django.core.cache import cache as dj_cache

    cache_key = f"ibge:{hash(url)}"
    cached = dj_cache.get(cache_key)
    if cached is not None:
        return cached
    now = time.monotonic()
    hit = _IBGE_CACHE.get(url)
    if hit and hit[0] > now:
        return hit[1]
    try:
        resp = _req.get(url, timeout=timeout)
    except Exception:
        return None
    # só cacheia se ok, evita cachear erro que causa timeout repetido
    if getattr(resp, "ok", False):
        dj_cache.set(cache_key, resp, 600)
        _IBGE_CACHE[url] = (now + _IBGE_CACHE_TTL.total_seconds(), resp)
        if len(_IBGE_CACHE) > 200:
            _IBGE_CACHE.clear()
    return resp


def _load_cultures_config():
    global _CULTURES_CONFIG_CACHE
    if _CULTURES_CONFIG_CACHE is not None:
        return _CULTURES_CONFIG_CACHE
    try:
        import os

        from django.conf import settings

        path = os.path.join(
            settings.BASE_DIR, "app", "static", "data", "cultures-config.json"
        )
        with open(path, encoding="utf-8") as f:
            cfg = json.load(f)
        _CULTURES_CONFIG_CACHE = cfg
        return cfg
    except Exception:
        _CULTURES_CONFIG_CACHE = {}
        return _CULTURES_CONFIG_CACHE


def _chave_mercado_for_cultura(cultura):
    """Mapeia Cultura do banco -> id do cultures-config.json (cultura-soja, ...)."""
    cfg = _load_cultures_config()
    target = _normalize_nome(cultura.nome)
    if not target:
        return ""
    best = ""
    best_score = 0
    for g in cfg.get("groups", []):
        for sg in g.get("subgroups", []):
            for c in sg.get("cultures", []):
                dn = _normalize_nome(c.get("django_nome", "") or c.get("title", ""))
                if dn == target:
                    return c.get("id", "")
                if dn and (dn in target or target in dn):
                    score = min(len(dn), len(target))
                    if score > best_score:
                        best_score = score
                        best = c.get("id", "")
    return best


def _normalize_nome(s):
    import unicodedata

    s = unicodedata.normalize("NFD", str(s or "").strip().lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")
