import json
import logging
import math
import random
import time
import traceback
from collections import defaultdict
from datetime import date, datetime, timedelta

import requests
from django.conf import settings
from django.contrib.auth import authenticate, login
from django.contrib.auth.models import User
from django.core.cache import cache
from django.db import OperationalError, transaction
from django.db.models import Avg, Count, F, Q, Sum
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_date
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from app.api.fallback_data import DEFAULT_METRICS, FALLBACK_METRICS
from app.api.serializers import *
from app.hierarquia import *
from app.models import *


class IsOwner(IsAuthenticated):
    def has_object_permission(self, request, view, obj):
        if hasattr(obj, "user"):
            return obj.user == request.user
        if hasattr(obj, "propriedade") and hasattr(obj.propriedade, "user"):
            return obj.propriedade.user == request.user
        return True


class SPASimpleSerializer(serializers.Serializer):
    data = serializers.DictField(child=serializers.CharField(), required=False)  # type: ignore[assignment]


def _parse_value(v):
    """Parse a value (string or number) into a float. Handles R$, M, K, etc.

    MEDIDO, 2026-10-04: esta função devolvia **2000** em QUALQUER falha — duas
    vezes nesta função (`v` não-string, e `float(s)` que não levanta). 2000 é
    um preço de café, não um sinal de "não sei". E é exactamente o que
    `app/ia/proveniencia.py` existe para impedir: uma ausência transformada
    num número que parece medido.

    `_to_float`, logo abaixo, devolve `None` na mesma situação — e `None` é o
    correcto: "sem dado" é distinto de "vale 2000", e quem chama sabe tratar
    a ausência.

    ESTA FUNÇÃO NÃO É CHAMADA (verificado: importada em `api/views/iot.py` e
    sem qualquer call-site). Passou a devolver `None` para não ficar a mina
    armada para quem a usar; apagar é a correção definitiva (ver plano P3).
    """
    if isinstance(v, (int, float)):
        return float(v)
    if not isinstance(v, str):
        return None
    s = v.strip()
    multiplier = 1
    if "R$ " in s:
        s = s.replace("R$ ", "")
    if s.endswith("M"):
        multiplier = 1_000_000
        s = s[:-1]
    elif s.endswith("K"):
        multiplier = 1_000
        s = s[:-1]
    s = s.replace(".", "").replace(",", ".").strip()
    try:
        return float(s) * multiplier
    except ValueError:
        return None


def _to_float(value):
    """Parse SIDRA numeric values safely (handles '-', ',', currency symbols, etc.)."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        v = float(value)
        return v if math.isfinite(v) else None

    s = str(value).strip()
    if not s or s in ("-", "...", "…", "x", "X"):
        return None

    s = s.replace(" ", "").replace("R$", "").replace(" ", "")
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")

    try:
        v = float(s)
        return v if math.isfinite(v) else None
    except ValueError:
        return None


def _atomic_with_retry(fn, max_retries=5):
    """Executa fn dentro de uma transacao atomica, repetindo se o SQLite
    reportar 'database is locked' (concorrencia de escrita no dev server)."""
    for attempt in range(max_retries):
        try:
            with transaction.atomic():
                return fn()
        except OperationalError as exc:
            if "locked" not in str(exc).lower() or attempt == max_retries - 1:
                raise
            # Delay exponencial limitado com jitter: max 500ms
            delay = min(0.1 * (2**attempt), 0.5) + random.uniform(0, 0.05)
            time.sleep(delay)
    return None


def fmt_num(value, ndigits=1):
    """Format number in pt-BR style; returns em dash for invalid values."""
    num = _to_float(value)
    if num is None:
        return "—"

    txt = f"{int(num):,}" if abs(num - int(num)) < 1e-09 else f"{num:,.{ndigits}f}"

    return txt.replace(",", "X").replace(".", ",").replace("X", ".")


@extend_schema(responses=SPASimpleSerializer)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def funcionarios_data(request):
    props = get_propriedade_optimizada(request.user)
    if not props:
        return Response({"funcionarios": []})
    funcs = Funcionario.objects.filter(propriedade=props)
    return Response(
        {
            "funcionarios": FuncionarioSerializer(funcs, many=True).data,
            "total": funcs.count(),
            "ativos": funcs.filter(ativo=True).count(),
        }
    )


@extend_schema(responses=SPASimpleSerializer)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def leituras_sensor_data(request):
    """Real-time sensor readings for IoT widget"""
    props = get_propriedade_optimizada(request.user)
    if not props:
        return Response([])
    estacoes = EstacaoMeteo.objects.filter(propriedade=props)
    leituras = LeituraSensor.objects.filter(estacao__in=estacoes).order_by(
        "-timestamp"
    )[:50]
    return Response(LeituraSensorSerializer(leituras, many=True).data)


IBGE_TABELAS = {
    # ── Todas usam tabela 5457 (Produção Agrícola Municipal combinada) ──
    # Lavoura Temporária
    "cultura-abacaxi": (5457, 40092, "Abacaxi*"),
    "cultura-algodao": (5457, 40099, "Algodão herbáceo (em caroço)"),
    "cultura-alho": (5457, 40100, "Alho"),
    "cultura-amendoim": (5457, 40101, "Amendoim (em casca)"),
    "cultura-arroz": (5457, 40102, "Arroz (em casca)"),
    "cultura-aveia": (5457, 40103, "Aveia (em grão)"),
    "cultura-batata": (5457, 40105, "Batata-inglesa"),
    "cultura-batata-doce": (5457, 40104, "Batata-doce"),
    "cultura-cana": (5457, 40106, "Cana-de-açúcar"),
    "cultura-cana-de-acucar": (5457, 40106, "Cana-de-açúcar"),
    "cultura-cebola": (5457, 40107, "Cebola"),
    "cultura-centeio": (5457, 40108, "Centeio (em grão)"),
    "cultura-cevada": (5457, 40109, "Cevada (em grão)"),
    "cultura-ervilha-seca": (5457, 40110, "Ervilha (em grão)"),
    "cultura-feijao": (5457, 40112, "Feijão (em grão)"),
    "cultura-fumo": (5457, 40113, "Fumo (em folha)"),
    "cultura-girassol": (5457, 40114, "Girassol (em grão)"),
    "cultura-mamona": (5457, 40118, "Mamona (baga)"),
    "cultura-mandioca": (5457, 40119, "Mandioca"),
    "cultura-melancia": (5457, 40120, "Melancia"),
    "cultura-melao": (5457, 40121, "Melão"),
    "cultura-milho": (5457, 40122, "Milho (em grão)"),
    "cultura-soja": (5457, 40124, "Soja (em grão)"),
    "cultura-sorgo": (5457, 40125, "Sorgo (em grão)"),
    "cultura-tomate": (5457, 40126, "Tomate"),
    "cultura-trigo": (5457, 40127, "Trigo (em grão)"),
    "cultura-triticale": (5457, 40128, "Triticale (em grão)"),
    # Lavoura Permanente
    "cultura-banana": (5457, 40136, "Banana (cacho)"),
    "cultura-cacau": (5457, 40138, "Cacau (em amêndoa)"),
    "cultura-cafe": (5457, 40139, "Café (em grão) Total"),
    "cultura-coco": (5457, 40145, "Coco-da-baía*"),
    "cultura-erva-mate": (5457, 40147, "Erva-mate (folha verde)"),
    "cultura-juta": (
        5457,
        40115,
        "Juta (fibra)",
    ),  # CORRIGIDO: antes 40152 (que é Limão)
    "cultura-laranja": (5457, 40151, "Laranja"),
    "cultura-maca": (5457, 40260, "Maçã"),
    "cultura-mamao": (5457, 40261, "Mamão"),
    "cultura-manga": (5457, 40262, "Manga"),
    "cultura-maracuja": (5457, 40263, "Maracujá"),
    "cultura-pimenta-do-reino": (
        5457,
        40269,
        "Pimenta-do-reino",
    ),  # CORRIGIDO: antes 40268 (que é Pêssego)
    "cultura-rami": (
        5457,
        40123,
        "Rami (fibra)",
    ),  # CORRIGIDO: antes 40173 (inexistente em 5457)
    "cultura-sisal": (
        5457,
        40270,
        "Sisal ou agave (fibra)",
    ),  # CORRIGIDO: antes 40130 (que é Algodão arbóreo)
    "cultura-uva": (5457, 40274, "Uva"),
    # Novas adições verificadas na tabela 5457
    "cultura-abacate": (5457, 40129, "Abacate"),
    "cultura-acai": (5457, 45982, "Açaí"),
    "cultura-caqui": (5457, 40142, "Caqui"),
    "cultura-dende": (5457, 40146, "Dendê (cacho de coco)"),
    "cultura-figo": (5457, 40148, "Figo"),
    "cultura-goiaba": (5457, 40149, "Goiaba"),
    "cultura-limao": (5457, 40152, "Limão"),
    "cultura-pera": (5457, 40267, "Pera"),
    "cultura-pessego": (5457, 40268, "Pêssego"),
    "cultura-tangerina": (5457, 40271, "Tangerina"),
    "cultura-azeitona": (5457, 40131, "Azeitona"),
    "cultura-palmito": (5457, 40266, "Palmito"),
    "cultura-noz": (5457, 40265, "Noz (fruto seco)"),
    "cultura-marmelo": (5457, 40264, "Marmelo"),
    # Aliases/grupos
    "cultura-citricultura": (5457, 40151, "Laranja"),
    "cultura-cafeicultura": (5457, 40139, "Café (em grão) Total"),
    "cultura-rizicultura": (5457, 40102, "Arroz (em casca)"),
    "cultura-olericultura": (5457, 40126, "Tomate"),
    "cultura-fruticultura": (5457, 40136, "Banana (cacho)"),
    "cultura-cerealicultura": (5457, 40127, "Trigo (em grão)"),
    # Fibras adicionais
    "cultura-linho": (5457, 40116, "Linho (semente)"),
    # ── PPM 3939 - Efetivo dos rebanhos (Pecuária) ──
    # Classification c79 (Tipo de rebanho)
    "cultura-bovino": (3939, 2670, "Bovino"),
    "cultura-bubalino": (3939, 2675, "Bubalino"),
    "cultura-equino": (3939, 2672, "Equino"),
    "cultura-ovino": (3939, 2677, "Ovino"),
    "cultura-caprino": (3939, 2681, "Caprino"),
    "cultura-suino": (3939, 32794, "Suíno - total"),
    "cultura-aves": (3939, 32796, "Galináceos - total"),
    "cultura-codorna": (3939, 2680, "Codornas"),
    "cultura-bufalo": (3939, 2675, "Bubalino"),
    # ── PPM 3940 - Produção da aquicultura ──
    # Classification c654 (Tipo de produto da aquicultura)
    "cultura-tilapia": (3940, 32877, "Tilápia"),
    "cultura-tambaqui": (3940, 32876, "Tambaqui"),
    "cultura-tambatinga": (3940, 32875, "Tambacu, tambatinga"),
    "cultura-pacu": (3940, 32870, "Pacu e patinga"),
    "cultura-pirarucu": (3940, 32874, "Pirarucu"),
    "cultura-camarao-marinho": (3940, 32887, "Camarão"),
    "cultura-camarao": (3940, 32887, "Camarão"),
    "cultura-ostra": (3940, 32889, "Ostras, vieiras e mexilhões"),
    "cultura-carpa": (3940, 32861, "Carpa"),
    "cultura-lambari": (3940, 32868, "Lambari"),
    "cultura-dourado": (3940, 32866, "Dourado"),
    "cultura-tucunare": (3940, 32880, "Tucunaré"),
    "cultura-truta": (3940, 32879, "Truta"),
    "cultura-matrinxa": (3940, 32869, "Matrinxã"),
    # ── PEVS 289 - Extração Vegetal ──
    "cultura-buriti": (289, 3424, "Buriti (fibra)"),
    "cultura-pequi": (289, 3444, "Pequi (amêndoa)"),
    # ── PEVS 291 - Silvicultura ──
    "cultura-eucalipto": (291, 3457, "Madeira em tora (eucalipto)"),
    "cultura-pinus": (291, 33248, "Lenha de pinus"),
    "cultura-acacia": (291, 3461, "Acácia-negra (casca)"),
}

_WEATHER_CACHE_TTL = 30 * 60  # 30 minutos

UF_NAME_TO_SIGLA = {
    "Acre": "AC",
    "Alagoas": "AL",
    "Amapá": "AP",
    "Amazonas": "AM",
    "Bahia": "BA",
    "Ceará": "CE",
    "Distrito Federal": "DF",
    "Espírito Santo": "ES",
    "Goiás": "GO",
    "Maranhão": "MA",
    "Mato Grosso": "MT",
    "Mato Grosso do Sul": "MS",
    "Minas Gerais": "MG",
    "Pará": "PA",
    "Paraíba": "PB",
    "Paraná": "PR",
    "Pernambuco": "PE",
    "Piauí": "PI",
    "Rio de Janeiro": "RJ",
    "Rio Grande do Norte": "RN",
    "Rio Grande do Sul": "RS",
    "Rondônia": "RO",
    "Roraima": "RR",
    "Santa Catarina": "SC",
    "São Paulo": "SP",
    "Sergipe": "SE",
    "Tocantins": "TO",
}

_IBGE_CACHE_TTL = timedelta(hours=12)

UF_CODES = {
    "RO": 11,
    "AC": 12,
    "AM": 13,
    "RR": 14,
    "PA": 15,
    "AP": 16,
    "TO": 17,
    "MA": 21,
    "PI": 22,
    "CE": 23,
    "RN": 24,
    "PB": 25,
    "PE": 26,
    "AL": 27,
    "SE": 28,
    "BA": 29,
    "MG": 31,
    "ES": 32,
    "RJ": 33,
    "SP": 35,
    "PR": 41,
    "SC": 42,
    "RS": 43,
    "MS": 50,
    "MT": 51,
    "GO": 52,
    "DF": 53,
}

_IBGE_CACHE: dict[str, dict] = {}

_CULTURES_CONFIG_CACHE = None

_WEATHER_CACHE: dict[str, dict] = {}

logger = logging.getLogger(__name__)


# ── Helpers restaurados da primeira versão (perdidos no split views.py → views/*.py) ──


def _gen_fallback_metrics(cultura_id):
    """NÃO serve métricas inventadas.

    Antes devolvia `FALLBACK_METRICS` — 210 lavouras fictícias, com produção,
    área, produtividade e receita escritas à mão — e caía em
    `DEFAULT_METRICS` (1 200 t / 30 ha / R$ 900K) para qualquer cultura não
    mapeada. Isto é o mesmo defeito do arroz/milho no dashboard, noutro
    sítio, com a agravante de estar em `/api/ibge-proxy/`, que é o caminho
    que o frontend usa quando o IBGE não responde — ou seja, no
    pior momento possível: quando a fonte real está em baixo.

    A função fica, e fica vazia, porque outros módulos a importam. Devolver
    `[]` é a resposta honesta; devolver um número seria inventar a lavoura
    de quem está a ver.
    """
    return []


def _gen_fallback_history(cultura_id):
    """NÃO gera histórico sintético.

    Antes: cinco anos de curva por `random.Random(cultura_id + "_hist")`,
    com variação de ±15% sobre o valor inventado. Um produtor via cinco
    anos de produção e de receita e não tinha forma de saber que a curva
    tinha sido sorteada a partir de um número inventado.

    Sem dado, não há curva. O gráfico mostra "sem dado" e o motivo fica no
    payload.
    """
    return {}


def _gen_fallback_history_antigo(cultura_id):
    """REMOVIDO de proposito. Nao chamar.

    Servia cinco anos de curva por `random.Random(cultura_id + "_hist")`,
    com variacao de ±15% sobre o valor inventado de `FALLBACK_METRICS`. Um
    produtor via cinco anos de producao e receita sem forma de saber que a
    curva tinha sido sorteada a partir de um numero que nao veio de
    ninguem.

    Fica aqui, desligada, como aviso para quem a procurar de volta: e' a
    mesma razao pela qual `FALLBACK_METRICS` continua no ficheiro em vez de
    ter sido apagado.
    """
    raise RuntimeError(
        "Historico sintetico nao existe. Sem fonte do IBGE nao ha curva — "
        "ver _gen_fallback_history."
    )


def _owm_icon(main, desc):
    m = (main or "").lower()
    d = (desc or "").lower()
    if "clear" in m or "sol" in d:
        return "bi-sun"
    if "thunder" in m or "storm" in d:
        return "bi-cloud-lightning-rain"
    if "snow" in m:
        return "bi-snow"
    if "rain" in m or "drizzle" in m or "chuva" in d:
        return "bi-cloud-rain"
    if "cloud" in m:
        return "bi-cloud-sun"
    return "bi-cloud"


def _num_inmet(valor):
    """Número que o INMET devolveu, ou None.

    O INMET serializa tudo como string: a temperatura chega como "25" e a
    humidade como "60". O código fazia `or 25` e `or 60`, e o `or` estava a
    decidir o que era um dado ausente — decidindo mal: "0" é truthy, e 0 °C
    é uma temperatura válida de madrugada, mas um producer nunca sabe se
    aquele 0 veio do INMET ou de um default.

    Um `or` com um valor inventado não é um default, é um RNG com semente
    fixa: o número que sai depende de o campo vir vazio, não de haver
    medição.
    """
    if valor is None or valor == "":
        return None
    try:
        return float(str(valor).strip().replace(",", "."))
    except (TypeError, ValueError):
        return None


def _clima_open_meteo(propriedade):
    """Open-Meteo: a fonte que o resto do sistema já usa e que funciona.

    POR QUE ESTE PASSO VEIO PRIMEIRO
    ================================
    A ordem antiga era INMET -> OpenWeatherMap -> número inventado. Verificada
    no ambiente real, essa ordem não tinha NENHUM caminho que respondesse:

      * o INMET devolvia `404 E_ROUTE_NOT_FOUND` para
        `/previsao/MT/Primavera%20do%20Leste` — a rota não aceita cidade com
        espaço, e a propriedade tem `cidade` livre;
      * o OpenWeatherMap exige `OPENWEATHER_API_KEY`, que não existe no
        `.env`;
      * logo, TODA propriedade sem uma fonte real caía no bloco de 28/26/23 °C
        escrito à mão — com `fonte: "simulado"` e sem nenhum aviso.

    E a fonte real estava ligada: existe `FonteDadosExterno` tipo
    `OPEN_METEO` com `ativo=True`, e a IA (`app/ia/intents.py`) consultava
    o Open-Meteo pelo serviço canônico `app/services/coordenadas.py` e
    acertava. Dois caminhos para a mesma pergunta, um a dar 31.7 °C medidos
    e o outro a dar 28 °C inventados.

    Aqui usa-se o MESMO serviço de coordenadas que a IA usa, para que a
    página e a IA não voltem a divergir: o clima do sítio certo, com a
    origem escrita.
    """
    try:
        from app.services.coordenadas import resolver

        coord = resolver(propriedade)
    except Exception as e:  # noqa: BLE001
        logger.warning("[clima] resolver() falhou: %s", e)
        return None

    if not coord.ok:
        return None

    try:
        from app.ia.fontes import fetch_permitido

        js, _host = fetch_permitido(
            "https://api.open-meteo.com/v1/forecast",
            None,
            propriedade,
            params={
                "latitude": coord.lat,
                "longitude": coord.lon,
                "current": "temperature_2m,relative_humidity_2m,precipitation,weather_code",
                "daily": (
                    "weather_code,temperature_2m_max,temperature_2m_min,"
                    "precipitation_sum,precipitation_probability_max"
                ),
                "forecast_days": 3,
                "timezone": "auto",
            },
        )
    except Exception as e:  # noqa: BLE001
        logger.warning("[clima] Open-Meteo falhou: %s", e)
        return None

    if not js:
        return None

    cur = js.get("current") or {}
    temp = cur.get("temperature_2m")
    if temp is None:
        return None

    dias = js.get("daily") or {}
    codigos = dias.get("weather_code") or []
    chuva_prob = dias.get("precipitation_probability_max") or []

    previsao = []
    rotulos = ("Hoje", "Amanhã", "Depois")
    for i, rotulo in enumerate(rotulos):
        if i >= len(dias.get("time") or []):
            break
        previsao.append(
            {
                "dia": rotulo,
                "icone": _om_icon(codigos[i] if i < len(codigos) else None),
                "temp": (
                    dias["temperature_2m_max"][i]
                    if i < len(dias.get("temperature_2m_max") or [])
                    else None
                ),
                "temp_min": (
                    dias["temperature_2m_min"][i]
                    if i < len(dias.get("temperature_2m_min") or [])
                    else None
                ),
                "umidade": cur.get("relative_humidity_2m") if i == 0 else None,
                "chuva_prob": chuva_prob[i] if i < len(chuva_prob) else None,
                "descricao": _om_descricao(codigos[i] if i < len(codigos) else None),
            }
        )

    origem = (
        f"{propriedade.cidade}/{propriedade.uf}"
        if propriedade.uf
        else (propriedade.cidade or "")
    )
    return {
        "cidade": origem,
        "fonte": "open-meteo",
        "coordenadas": [coord.lat, coord.lon],
        "coordenadas_origem": coord.fonte,
        "aviso": coord.aviso,
        "atual": {
            "dia": "Hoje",
            "icone": _om_icon(cur.get("weather_code")),
            "temp": round(float(temp)),
            "umidade": cur.get("relative_humidity_2m"),
            "chuva_mm": cur.get("precipitation"),
            "descricao": _om_descricao(cur.get("weather_code")),
        },
        "previsao": previsao,
    }


#: Códigos WMO do Open-Meteo -> (bootstrap icon, descrição em pt-BR).
#: A fonte devolve um número, e o número não diz nada a quem lê. Um cartão
#: com "weather_code: 51" e um sem ícone são o mesmo cartão; o ícone é o que
#: o produtor olha antes de decidir pulverizar.
_OM_CODIGOS = {
    0: ("bi-sun", "Ensolarado"),
    1: ("bi-sun", "Predominantemente ensolarado"),
    2: ("bi-cloud-sun", "Parcialmente nublado"),
    3: ("bi-cloud", "Encoberto"),
    45: ("bi-cloud-fog2", "Nevoeiro"),
    48: ("bi-cloud-fog2", "Nevoeiro com geada"),
    51: ("bi-cloud-drizzle", "Garoa fraca"),
    53: ("bi-cloud-drizzle", "Garoa"),
    55: ("bi-cloud-drizzle", "Garoa intensa"),
    61: ("bi-cloud-rain", "Chuva fraca"),
    63: ("bi-cloud-rain", "Chuva"),
    65: ("bi-cloud-rain-heavy", "Chuva forte"),
    71: ("bi-snow", "Neve fraca"),
    73: ("bi-snow", "Neve"),
    75: ("bi-snow", "Neve forte"),
    77: ("bi-snow", "Grãos de neve"),
    80: ("bi-cloud-rain", "Pancadas de chuva"),
    81: ("bi-cloud-rain", "Pancadas de chuva"),
    82: ("bi-cloud-lightning-rain", "Pancadas fortes"),
    85: ("bi-snow", "Pancadas de neve"),
    86: ("bi-snow", "Pancadas de neve"),
    95: ("bi-cloud-lightning-rain", "Trovoada"),
    96: ("bi-cloud-lightning-rain", "Trovoada com granizo"),
    99: ("bi-cloud-lightning-rain", "Trovoada com granizo"),
}


def _om_icon(codigo):
    return (_OM_CODIGOS.get(codigo) or ("bi-cloud", None))[0]


def _om_descricao(codigo):
    return (_OM_CODIGOS.get(codigo) or (None, None))[1]


def _get_real_weather(propriedade):
    """Previsão real: Open-Meteo -> INMET -> OpenWeatherMap -> SIM/DADO.

    O que muda em relação à versão anterior não é a ordem das fontes — é que
    agora uma delas RESPONDE, e a última deixou de ser um número inventado.
    """
    if not propriedade or not propriedade.cidade:
        return None
    from django.core.cache import cache as dj_cache

    _raw_key = f"weather:{propriedade.uf}|{propriedade.cidade}"
    cache_key = _raw_key.replace(":", "_").replace("|", "_").replace(" ", "_")
    cached = dj_cache.get(cache_key)
    if cached is not None:
        return cached
    # fallback in-memory per-worker (cold start sem Redis)
    _local = _WEATHER_CACHE.get(cache_key)
    if _local and (time.time() - _local["ts"]) < _WEATHER_CACHE_TTL:
        return _local["data"]

    import requests as req

    result = None

    # 1. Open-Meteo — via o serviço canônico de coordenadas, o mesmo que a
    #    IA usa. Sem chave, e a fonte que o produtor tem ativa no sistema.
    result = _clima_open_meteo(propriedade)

    # 2. INMET (gratuito, sem chave) — timeout curto 3s para não estourar ERR_TIMED_OUT
    if result is None:
        try:
            url = f"https://apitempo.inmet.gov.br/previsao/{propriedade.uf}/{propriedade.cidade}"
            r = req.get(url, timeout=3)
            if r.ok:
                data = r.json()
                items = data.get(propriedade.cidade, [])[:4]
                if items:
                    previsao = []
                    for item in items:
                        resumo = str(item.get("resumo", "") or "")
                        # O INMET devolve temperatura e humidade como STRINGS
                        # ("25", "60") — e por vezes omite o campo. Este código
                        # fazia `or 25` e `or 60`, que é uma escolha ao acaso:
                        # se a string viesse vazia entrava o 25; se viesse
                        # "0" — que é uma temperatura válida — ficava o 0.
                        #
                        # O pior não era o número. Era o carimbo: o bloco saía
                        # com `"fonte": "inmet"`, e o INMET é uma autoridade
                        # real. Um produtor a decidir irrigar por 25 °C e 60 %
                        # de humidade que o INMET não disse estava a usar
                        # números inventados com o nome de uma instituição
                        # pública.
                        #
                        # Agora o que o INMET não der é None, e a fonte diz o
                        # que ela é. A descrição deixou de ter um texto
                        # padrão: "Parcialmente nublado" é uma previsão, e
                        # também não vinha de lado nenhum.
                        temp = _num_inmet(item.get("temp_max")) or _num_inmet(
                            item.get("temp_min")
                        )
                        umidade = _num_inmet(item.get("umidade_max"))
                        previsao.append(
                            {
                                "dia": item.get("dia", "Hoje"),
                                "icone": "bi-sun"
                                if "sol" in resumo.lower()
                                else "bi-cloud-rain",
                                "temp": temp,
                                "umidade": umidade,
                                "descricao": resumo or None,
                            }
                        )
                    result = {
                        "cidade": f"{propriedade.cidade}/{propriedade.uf}",
                        "fonte": "inmet",
                        "atual": previsao[0],
                        "previsao": previsao,
                    }
        except Exception:
            pass

    # 2. OpenWeatherMap (apenas se houver chave)
    if result is None:
        try:
            import os

            from django.conf import settings as _dj_settings

            api_key = getattr(
                _dj_settings,
                "OPENWEATHER_API_KEY",
                os.environ.get("OPENWEATHER_API_KEY", ""),
            )
            if api_key:
                url = f"https://api.openweathermap.org/data/2.5/forecast?q={propriedade.cidade},{propriedade.uf}&appid={api_key}&units=metric&lang=pt_br"
                r = req.get(url, timeout=3)
                if r.status_code == 200:
                    data = r.json()
                    dias = {}
                    for item in data.get("list", [])[:8]:
                        day = datetime.fromtimestamp(item["dt"]).strftime("%A")
                        if day not in dias:
                            main = item["weather"][0]["main"]
                            desc = item["weather"][0]["description"]
                            dias[day] = {
                                "dia": day.capitalize(),
                                "temp": round(item["main"]["temp"]),
                                "umidade": item["main"]["humidity"],
                                "descricao": desc,
                                "icone": _owm_icon(main, desc),
                            }
                    lista = list(dias.values())
                    if lista:
                        result = {
                            "cidade": data.get("city", {}).get("name")
                            or f"{propriedade.cidade}/{propriedade.uf}",
                            "fonte": "openweathermap",
                            "atual": lista[0],
                            "previsao": lista,
                        }
        except Exception:
            pass

    # 4. Sem fonte respondeu: a tela DIZ QUE NÃO SABE.
    #
    # A versão anterior escrevia aqui 28/26/23 °C, "Ensolarado", e chamava
    # -lhe `fonte: "simulado"` — o que é honesto no nome e mentiroso no
    # efeito. O cartão dizia a mesma coisa para uma fazenda no Cerrado e
    # para outra no litoral, com a confiança de quem mediu. Um produtor
    # decide irrigar, pulverizar e contratar semente com esse número.
    #
    # O contrato que fica: TEMPO É INCLINADO PELA MEDIÇÃO. Se nenhuma fonte
    # respondeu, não há temperatura — e a ausência é visível, o que é o
    # oposto de um cartão bonito e falso.
    if result is None:
        result = {
            "cidade": f"{propriedade.cidade}/{propriedade.uf}",
            "fonte": "sem_fonte",
            "fonte_dado": "sem_dado",
            "motivo": (
                "Nenhuma fonte de previsão respondeu para "
                f"{propriedade.cidade}/{propriedade.uf}. "
                "Verifique a ligação ou cadastre uma estação meteorológica."
            ),
            "atual": {
                "dia": "Hoje",
                "icone": "bi-dash-circle",
                "temp": None,
                "umidade": None,
                "descricao": "Sem previsão",
            },
            "previsao": [],
        }

    try:
        dj_cache.set(cache_key, result, 600)
    except Exception:
        pass
    _WEATHER_CACHE[cache_key] = {"ts": time.time(), "data": result}
    return result
