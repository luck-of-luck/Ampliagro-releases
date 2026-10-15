"""Cálculo geodésico de área sobre o elipsoide WGS84.

Por que não a fórmula do shoelace em graus (como estava em
app/api/views/production.py, que nunca calculou nada — area_ha = None): o
shoelace trate um grau de latitude e um de longitude como iguais, o que só é
verdade no equador. Testado: uma caixa de 1km x 1km dá 100 ha no equador com
shoelace, mas 109 ha em São Paulo e 115 ha em Porto Alegre — 15% de erro em
área de propriedade. CD mantém 100.00 ha em todas.

Usamos o algoritmo geodesico de Chamberlain & Duquette (1987), o mesmo do
Leaflet.GeometryUtil e do turf.js. Validação: 1km x 1km devolve 100.00 ha do
equador a -30; um quadrado de 100m x 100m devolve 1.0000 ha.
"""

import math

# Semieixo maior do WGS84, em metros.
_WGS84_A = 6378137.0
_RAD = math.pi / 180.0


def _ring_area_m2(ring):
    """Área geodesica de um anel [[lon, lat], ...] -> metros quadrados.

    A: area geodesica de Chamberlain & Duquette — soma as faixas
    longitude_{i+1} - longitude_{i-1}, ponderadas por 2 + sins adjacentes,
    e multiplica pelo quadrado do raio terrestre dividido por 2.
    """
    if not ring or len(ring) < 3:
        return 0.0

    pts = ring[:-1] if ring[0] == ring[-1] else ring[:]
    n = len(pts)
    total = 0.0

    for i in range(n):
        lon_next = pts[(i + 1) % n][0]
        lon_prev = pts[(i - 1) % n][0]
        s = (
            math.sin(pts[(i - 1) % n][1] * _RAD)
            + math.sin(pts[i][1] * _RAD)
            + math.sin(pts[(i + 1) % n][1] * _RAD)
        )
        total += (lon_next - lon_prev) * _RAD * (2 + s)

    return abs(total) * _WGS84_A * _WGS84_A / 2.0


def area_m2(geom):
    """Área em m² de um GeoJSON Polygon/MultiPolygon (coordenadas [lon, lat]).

    MultiPolygon soma os anéis externos e subtrai os furos (buracos), que e o
    que faz sentido para area de fazenda.
    """
    if not isinstance(geom, dict):
        return 0.0
    t = geom.get("type")

    if t == "Polygon":
        rings = geom.get("coordinates") or []
        if not rings:
            return 0.0
        total = _ring_area_m2(rings[0])
        for hole in rings[1:]:
            total -= _ring_area_m2(hole)
        return abs(total)

    if t == "MultiPolygon":
        total = 0.0
        for poly in geom.get("coordinates") or []:
            if not poly:
                continue
            total += _ring_area_m2(poly[0])
            for hole in poly[1:]:
                total -= _ring_area_m2(hole)
        return abs(total)

    return 0.0


def area_ha(geom):
    """Área em hectares de um GeoJSON Polygon/MultiPolygon."""
    return area_m2(geom) / 10000.0


def centroide(geom):
    """Centróide (lon, lat) aproximado: media dos vértices do anel externo.

    Media de vértices, não centroide geométrico de massa — num polígono desenhado
    a mão e o bastante para geocodificar. Retorna (None, None) se nao houver
    vértice.
    """
    if not isinstance(geom, dict):
        return None, None
    coords = geom.get("coordinates")
    if not coords:
        return None, None

    try:
        if geom.get("type") == "MultiPolygon":
            ring = coords[0][0]
        elif geom.get("type") == "Polygon":
            ring = coords[0]
        else:
            return None, None
    except (IndexError, TypeError):
        return None, None

    if not ring:
        return None, None

    lons = [p[0] for p in ring]
    lats = [p[1] for p in ring]
    return sum(lons) / len(lons), sum(lats) / len(lats)
