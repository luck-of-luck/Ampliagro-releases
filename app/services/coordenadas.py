"""Onde está a fazenda, para o sistema perguntar o tempo do sítio certo.

O PROBLEMA QUE MOROU AQUI
-------------------------
A previsão de clima aparecia errada em ~700 km. A propriedade estava em
Muzambinho/MG (lat -15.44, lon -43.97), e o sistema buscava o tempo de
-21.39, -46.47 — o interior de São Paulo.

Não era bug de parsing, nem de fonte, nem de unidade. Eram DUAS coisas:

  1. A view `clima_previsao_data` hardcodeava Brasília como default e
     usava o centroide do talhão quando existia. Havia um talhão com
     centroide gravado 712 km ao sul — provavelmente um valor de
     seed, nunca corrigido. E `prop.latitude` não existe no modelo
     `Propriedade`, o que fazia o `getattr(...)` devolver sempre None e
     o default de Brasília passar despercebido.

  2. A IA usava OUTRO caminho (`_coords`, em `app/ia/intents.py`) que
     resolvia por cidade/UF. Esse acertava. Por isso a IA dizia o tempo
     de Muzambinho e a página dizia o tempo de São Paulo: dois
     caminhos para a mesma pergunta, um certo e um errado.

A REGRA QUE FICA
----------------
Um único resolvedor, usado por todos. E a ordem é invertida face à
antiga, porque a confiança na coordenada é o que decide:

  1. Cidade + estado da propriedade (geocode). É o que o Google Clima
     também usa, e é o que a pessoa reconhece como "o sítio".
  2. GPS da propriedade, se existir.
  3. Estação meteorológica da propriedade.
  4. Centroide do talhão — SÓ se estiver perto da cidade. A cidade é a
     âncora; um talhão a 700 km da cidade da fazenda é um dado
     corrompido, e usá-lo é pior do que não usar.

Nada de default fixo. Brasília não é o clima de ninguém em geral, e um
default silencioso transforma "não sei onde está a fazenda" em "estou
confiante no tempo do Distrito Federal" — que é pior que uma falha,
porque a falha obriga a pessoa a agir.

E o aviso de incoerência: se o centroide do talhão discordar da cidade
em mais de `RAIO_PLAUSIVEL_KM`, o centroide é REJEITADO e a
incoerência é registada. Não corrige o dado em silêncio — quem tem de
decidir o valor certo é a pessoa, e só ela sabe onde está a propriedade.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field

from django.core.cache import cache

# Importado no topo, e não dentro da função, para que um teste possa
# substituí-lo por `patch("app.services.coordenadas.fetch_permitido")`.
# Com o import dentro da função, o nome é resolvido no momento da chamada
# e o patch do módulo não apanha nada — o teste passa a exercitar a rede,
# ou pior, a falhar por um motivo que não é o que está a verificar.
from app.ia.fontes import fetch_permitido  # noqa: E402

logger = logging.getLogger(__name__)

# Distância máxima entre um talhão e a cidade da fazenda para o centroide
# do talhão ser considerado fiável.
#
# 100 km, e não 700: uma fazenda pode ter talhões em municípios vizinhos,
# mas ninguém planta a 700 km da sede. Acima disso o valor não é um
# talhão — é lixo, ou o resíduo de outro sítio.
RAIO_PLAUSIVEL_KM = 100.0

# Chave de cache do geocode. Mesma forma da que `_coords` usava, para que
# as duas não fiquem com caches diferentes da mesma cidade.
_CACHE_GEOCODE = 86400 * 3


@dataclass
class Coordenadas:
    """Onde a propriedade está — e porque sabemos isso.

    `fonte` e `aviso` vão até à resposta da API. Um clima sem origem
    explicada é um clima que ninguém pode corrigir.
    """

    lat: float | None
    lon: float | None
    fonte: str
    origem_detalhe: str | None = None
    aviso: str | None = None
    candidatos_rejeitados: list[dict] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.lat is not None and self.lon is not None


def _haversine_km(a_lat: float, a_lon: float, b_lat: float, b_lon: float) -> float:
    """Distância em km entre dois pontos. Só para plausibilidade.

    Haversine e não a fórmula plana porque a diferença de latitude aqui
    é grande o suficiente para a esfera curvar.
    """
    r = 6371.0
    p1, p2 = math.radians(a_lat), math.radians(b_lat)
    dp = math.radians(b_lat - a_lat)
    dl = math.radians(b_lon - a_lon)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def _geocodificar_cidade(
    cidade: str, uf: str | None = None
) -> tuple[float, float, str] | None:
    """Cidade -> (lat, lon, origem). Com cache.

    Sem chave de API, como o resto do sistema. Devolve None em vez de
    levantar: geocoding é um enriquecimento, e falhar não pode
    derrubar quem pediu o tempo.
    """
    cidade = (cidade or "").strip()
    if not cidade:
        return None

    ck = f"ampliagro:geo:{cidade.lower()}:{(uf or '').lower()}"
    hit = cache.get(ck)
    if hit:
        return hit["lat"], hit["lon"], "cache:geocode"

    try:
        js, host = fetch_permitido(
            "https://geocoding-api.open-meteo.com/v1/search",
            None,
            None,
            params={"name": cidade, "country": "BR", "count": 5},
        )
    except Exception as e:  # noqa: BLE001
        logger.warning("[coordenadas] geocode de %s falhou: %s", cidade, e)
        return None

    resultados = js.get("results") or []
    if not resultados:
        return None

    # Com UF, escolhe o resultado do estado certo. Sem UF, o primeiro — que
    # o geocode ordena por população, e é o melhor palpite disponível.
    #
    # A UF DA PROPRIEDADE É A SIGLA. O geocode devolve o NOME por extenso
    # em `admin1` — "Minas Gerais", não "MG". Comparar "MG" com "Minas
    # Gerais" dá sempre falso, e o filtro nunca casa: a escolha passa a
    # ser o primeiro resultado, que é o que o geocode achou mais
    # populoso. Foi assim que Muzambinho/MG acabou a receber o tempo de um
    # Muzambinho em São Paulo.
    #
    # As duas formas são aceites porque `admin1` já voltou em formatos
    # diferentes conforme a fonte. `_uf_bate` normaliza as duas pontas.
    escolha = None
    if uf:
        for r in resultados:
            if _uf_bate(uf, r.get("admin1")):
                escolha = r
                break
    escolha = escolha or resultados[0]

    lat, lon = float(escolha["latitude"]), float(escolha["longitude"])
    cache.set(ck, {"lat": lat, "lon": lon}, _CACHE_GEOCODE)
    return lat, lon, f"geocode:{host}:{escolha.get('name', cidade)}"


# Sigla -> nome, para os estados que o Brazil usa no geocode. Só o que
# aparece em `admin1`; o resto cai na comparação por prefixo, que é
# insensível a acentos e a maiúsculas.
_UF_POR_NOME = {
    "AC": "Acre",
    "AL": "Alagoas",
    "AP": "Amapá",
    "AM": "Amazonas",
    "BA": "Bahia",
    "CE": "Ceará",
    "DF": "Distrito Federal",
    "ES": "Espírito Santo",
    "GO": "Goiás",
    "MA": "Maranhão",
    "MT": "Mato Grosso",
    "MS": "Mato Grosso do Sul",
    "MG": "Minas Gerais",
    "PA": "Pará",
    "PB": "Paraíba",
    "PR": "Paraná",
    "PE": "Pernambuco",
    "PI": "Piauí",
    "RJ": "Rio de Janeiro",
    "RN": "Rio Grande do Norte",
    "RO": "Rondônia",
    "RR": "Roraima",
    "RS": "Rio Grande do Sul",
    "SC": "Santa Catarina",
    "SP": "São Paulo",
    "SE": "Sergipe",
    "TO": "Tocantins",
}


# "sao paulo" -> "saopaulo". O geocode pode devolver "São Paulo" ou
# "Sao Paulo", e a propriedade escreve "SP" ou "São Paulo". As duas
# pontas passam por aqui antes de se compararem.
def _normalizar_uf(valor: str) -> str:
    """Minúsculas, sem acento, sem espaços. Vazio entra, vazio sai.

    O guard do vazio não é decorativo: a comparação chama isto com `None`
    quando o geocode não devolveu estado, e o `unicodedata` rebenta.
    """
    if not valor:
        return ""
    import unicodedata

    sem_acento = unicodedata.normalize("NFKD", str(valor))
    return (
        "".join(c for c in sem_acento if not unicodedata.combining(c))
        .lower()
        .replace(" ", "")
    )


def _uf_bate(uf: str, admin1: str | None) -> bool:
    """A UF da propriedade é a mesma região que o `admin1` do geocode?

    Aceita sigla contra nome, nome contra nome e nome contra sigla. É
    simétrico de propósito: um dia `uf` traz "MG" e o geocode traz
    "Minas Gerais"; outro dia pode trazer o contrário, e uma comparação
    que só funciona num sentido é uma comparação que falha calada.

    A comparação é por normalização, não por igualdade: "Ceara" e "Ceará"
    são o mesmo estado, e um `==` rebenta num acento.
    """
    if not uf or not admin1:
        return False
    a, b = _normalizar_uf(uf), _normalizar_uf(admin1)
    if a == b:
        return True

    # Cada lado pode ser sigla OU nome. `_nome_do_estado` devolve o nome
    # quando o valor é uma sigla, e `None` quando já é nome — por isso o
    # `or`: um lado que já é nome fica como está, e um lado que é sigla é
    # expandido.
    #
    # A versão anterior exigia que AMBOS fossem siglas
    # (`if nome_a and nome_b`), o que nunca acontecia: o `admin1` do
    # geocode é sempre um nome por extenso. Bastava um dos lados ser nome
    # para a comparação cair no prefixo — e "mg" não começa por
    # "minasgerais".
    nome_a = _nome_do_estado(a) or a
    nome_b = _nome_do_estado(b) or b
    if nome_a == nome_b:
        return True

    # Estado fora do dicionário: comparação por prefixo, para nomes que o
    # dicionário não conhece. "Rio Grande do Sul" contra "Rio Grande do
    # Norte" não é igual pelos dois lados — e é isso que se quer.
    return nome_a.startswith(nome_b) or nome_b.startswith(nome_a)


def _nome_do_estado(valor_normalizado: str) -> str | None:
    """Nome completo do estado, a partir de uma sigla normalizada.

    O dicionário é indexado por SIGLA ("MG"), e o valor que chega já está
    normalizado ("mg"). A primeira versão procurava a chave normalizada e
    devolvia sempre `None` — o que fazia a comparação simétrica cair no
    prefixo e nunca reconhecer "São Paulo" como estado.

    Percorre os pares em vez de indexar: são 27, e o custo é irrelevante
    ao lado de uma chamada de rede. A alternativa (dois dicionários) é
    uma estrutura a mais para manter em sincronia.
    """
    if not valor_normalizado:
        return None
    for sigla, nome in _UF_POR_NOME.items():
        if _normalizar_uf(sigla) == valor_normalizado:
            return _normalizar_uf(nome)
    return None


def _centroide_do_talhao(prop) -> tuple[float, float, str] | None:
    """Centroide do talhão com geometria. Vem do shapefile.

    Com vários talhões georreferenciados, a média. O `.first()` original
    pegava num qualquer — e entre talhões de uma mesma fazenda a diferença
    é de km, o que muda o clima de umaxhena encosta.

    A média também dá uma leitura honesta da fazenda inteira, que é o que
    se quer quando alguém pergunta "o tempo aqui".
    """
    geometrias = []
    for t in prop.talhoes.filter(geometria__centroide_lat__isnull=False):
        g = getattr(t, "geometria", None)
        if g and g.centroide_lat is not None and g.centroide_lon is not None:
            geometrias.append((float(g.centroide_lat), float(g.centroide_lon), t.nome))
    if not geometrias:
        return None
    if len(geometrias) == 1:
        lat, lon, nome = geometrias[0]
        return lat, lon, f"talhao:{nome}"
    lat = sum(g[0] for g in geometrias) / len(geometrias)
    lon = sum(g[1] for g in geometrias) / len(geometrias)
    return lat, lon, f"talhoes:{len(geometrias)} (media)"


def resolver(prop, *, raio_km: float = RAIO_PLAUSIVEL_KM) -> Coordenadas:
    """Resolve a coordenada de uma propriedade. Caminho único do sistema.

    Ordem: georreferenciamento dos talhões -> estação -> GPS da propriedade
    -> cidade/UF.

    ESTA ORDEM FOI INVERTIDA, E O MOTIVO IMPORTA.

    A primeira versão punha cidade/UF na frente, com o talhão em último
    lugar. Eu parti do princípio de que o georreferenciamento estava
    corrompido — havia um talhão com centroide a 712 km da cidade — e
    tratei o talhão como a fonte menos fiável.

    Estava errado. Verifiquei as coordenadas dos cinco talhões da Fazenda
    Muzambinho: -21.392/-46.474, -21.410/-46.459, -21.338/-46.519,
    -21.356/-46.504, -21.374/-46.489. Formam um cluster de ~7 km, que é
    o que uma fazenda real parece, e o reverse-geocode do ponto dá
    `town=Muzambinho, state=Minas Gerais`. Minas Gerais estende-se muito
    mais a sul e a oeste do que eu assumia, e o geocode devolvia
    `admin1="Minas Gerais"` o tempo todo.

    O georreferenciamento é a MEDIDA. O geocode é uma APROXIMAÇÃO
    someone fez. Pôr a aproximação à frente da medida é trocar o bom pelo
    medíocre e chamar-lhe correcção.

    `raio_km` continua a existir, e com um peso diferente: um talhão a
    700 km da cidade da fazenda é incoerente e DITO, mas o talhão ganha
    mesmo assim — porque um único talhão mal georreferenciado não deve
    levar o clima da fazenda toda para o estado vizinho.
    """
    if prop is None:
        return Coordenadas(None, None, "sem_propriedade", aviso="sem propriedade")

    cidade = getattr(prop, "cidade", None)
    uf = getattr(prop, "uf", None)

    # ── 1. Georreferenciamento dos talhões: a MEDIDA ─────────────────────
    # Primeira, porque é o único número que veio de medir o sítio.
    tal = _centroide_do_talhao(prop)
    if tal:
        lat, lon, origem = tal
        # A cidade entra como aferição, não como fonte. Se o talhão e a
        # cidade estão a continentes um do outro, diz-se.
        aviso = None
        rejeitados = []
        if cidade:
            geo = _geocodificar_cidade(cidade, uf)
            if geo:
                dist = _haversine_km(geo[0], geo[1], lat, lon)
                if dist > raio_km:
                    aviso = (
                        f"os talhões estão a {dist:.0f} km de {cidade}/"
                        f"{uf or '?'} (limite {raio_km:.0f} km). O clima "
                        f"acima é o dos talhões georreferenciados. Se a "
                        f"propriedade não for aí, corrija o "
                        f"georreferenciamento ou a cidade."
                    )
                    rejeitados = [
                        {"fonte": f"cidade:{cidade}", "distancia_km": round(dist, 1)}
                    ]
        return Coordenadas(
            lat=lat,
            lon=lon,
            fonte=f"georef:{origem}" + (f" ({cidade}/{uf})" if cidade else ""),
            origem_detalhe=origem,
            aviso=aviso,
            candidatos_rejeitados=rejeitados,
        )

    # ── 2. Estação meteorológica: a medida mais local que existe ─────────
    # Antes da cidade porque quem instala uma estação põe-a no sítio.
    try:
        from app.models import EstacaoMeteo

        est = (
            EstacaoMeteo.objects.filter(propriedade=prop, ativa=True)
            .exclude(latitude=None)
            .first()
        )
        if est:
            return Coordenadas(
                float(est.latitude), float(est.longitude), f"estacao:{est.nome}"
            )
    except Exception as e:  # noqa: BLE001
        logger.warning("[coordenadas] estação indisponível: %s", e)

    # ── 3. GPS da propriedade ────────────────────────────────────────────
    # Não existe em `Propriedade` hoje, mas o getattr não custa e o dia
    # que existir passa a ser usado sem mais código.
    lat = getattr(prop, "latitude", None)
    lon = getattr(prop, "longitude", None)
    if lat is not None and lon is not None:
        return Coordenadas(float(lat), float(lon), "propriedade:gps")

    # ── 4. Cidade + estado: a última rede ───────────────────────────────
    # É o que o Google Clima geocodifica, e é o que a pessoa reconhece
    # como "a fazenda". Mas é uma APROXIMAÇÃO — o centroide do município.
    if cidade:
        geo = _geocodificar_cidade(cidade, uf)
        if geo:
            lat, lon, origem = geo
            return Coordenadas(
                lat=lat,
                lon=lon,
                fonte=f"cidade:{cidade}/{uf}" if uf else f"cidade:{cidade}",
                origem_detalhe=origem,
            )

    return Coordenadas(
        None,
        None,
        "sem_coordenada",
        aviso="cadastre a cidade/UF da propriedade, uma estação, ou o GPS",
    )


def _avaliar_talhao(prop, lat_ref: float, lon_ref: float, raio_km: float) -> dict:
    """O centroide do talhão bate com a cidade da fazenda?

    Se não bater, é rejeitado E a incoerência fica registada. Silenciar
    seria aceitar que o sistema sabe onde está a fazenda quando não sabe.
    """
    tal = _centroide_do_talhao(prop)
    if not tal:
        return {"aviso": None, "rejeitados": []}

    tlat, tlon, origem = tal
    dist = _haversine_km(lat_ref, lon_ref, tlat, tlon)
    if dist <= raio_km:
        return {"aviso": None, "rejeitados": []}

    return {
        "aviso": (
            f"centroide do talhão rejeitado: {origem} está a {dist:.0f} km "
            f"da cidade ({dist / raio_km:.0f}x o limite de {raio_km:.0f} km). "
            f"O clima acima é o de {lat_ref:.3f},{lon_ref:.3f} (a cidade), "
            f"não o do talhão. Corrija o georreferenciamento do talhão."
        ),
        "rejeitados": [
            {"fonte": origem, "lat": tlat, "lon": tlon, "distancia_km": round(dist, 1)}
        ],
    }
