"""
Parsers / normalizadores de payloads IoT.

Suporta:
- json: {"temperatura": 23.5, "umidade_ar": 88, "timestamp": "2026-08-27T12:00:00Z"}
- json array / senml: [{"n":"temperatura","v":23.5,"t":1693...}]
- cayenne_lpp (hex string ou bytes) — decodifica se biblioteca disponível
- csv: "temperatura,umidade_ar\n23.5,88"
- ttn/chirpstack uplink wrapper: {"uplink_message":{"decoded_payload":{...}, "fPort":2}}

Retorna lista de dicts: [{"metric": "...", "value": float, "unit": str, "timestamp": datetime}, ...]
"""

import base64
import csv
import io
import json
import math
import re
from datetime import datetime, timezone

from django.utils import timezone as dj_tz

# mapa de aliases comuns -> metric canonico
ALIASES = {
    "temp": "temperatura",
    "temperature": "temperatura",
    "temp_ar": "temperatura",
    "hum": "umidade_ar",
    "humidity": "umidade_ar",
    "hum_ar": "umidade_ar",
    "press": "pressao",
    "pressure": "pressao",
    "rain": "chuva",
    "precipitation": "chuva",
    "wind_speed": "vento_vel",
    "wind_dir": "vento_dir",
    "wind_gust": "vento_rajada",
    "solar_radiation": "radiacao",
    "radiation": "radiacao",
    "soil_moisture": "umidade_solo",
    "soil_temp": "temp_solo",
    "soil_ec": "condutividade",
    "soil_ph": "ph_solo",
    "water_level": "nivel",
    "flow": "vazao",
    "lat": "gps_lat",
    "latitude": "gps_lat",
    "lon": "gps_lon",
    "lng": "gps_lon",
    "longitude": "gps_lon",
    "battery": "bateria",
    "batt": "bateria",
}

VALID_METRICS = {
    "temperatura",
    "umidade_ar",
    "pressao",
    "chuva",
    "chuva_acum",
    "vento_vel",
    "vento_dir",
    "vento_rajada",
    "radiacao",
    "uv",
    "ponto_orvalho",
    "umidade_solo",
    "temp_solo",
    "condutividade",
    "ph_solo",
    "npk_n",
    "npk_p",
    "npk_k",
    "nivel",
    "vazao",
    "ph_agua",
    "turbidez",
    "gps_lat",
    "gps_lon",
    "gps_alt",
    "velocidade",
    "rpm",
    "combustivel",
    "horimetro",
    "temp_motor",
    "peso",
    "temp_corporal",
    "passos",
    "ruminação",
    "potencia",
    "energia_dia",
    "tensao",
    "corrente",
    "bateria",
    "rssi",
    "outro",
}

UNITS = {
    "temperatura": "°C",
    "umidade_ar": "%",
    "pressao": "hPa",
    "chuva": "mm",
    "chuva_acum": "mm",
    "vento_vel": "m/s",
    "vento_dir": "°",
    "vento_rajada": "m/s",
    "radiacao": "W/m²",
    "uv": "",
    "ponto_orvalho": "°C",
    "umidade_solo": "%",
    "temp_solo": "°C",
    "condutividade": "dS/m",
    "ph_solo": "",
    "npk_n": "mg/kg",
    "npk_p": "mg/kg",
    "npk_k": "mg/kg",
    "nivel": "m",
    "vazao": "L/s",
    "ph_agua": "",
    "turbidez": "NTU",
    "gps_lat": "°",
    "gps_lon": "°",
    "gps_alt": "m",
    "velocidade": "km/h",
    "rpm": "rpm",
    "combustivel": "%",
    "horimetro": "h",
    "temp_motor": "°C",
    "peso": "kg",
    "temp_corporal": "°C",
    "passos": "",
    "ruminação": "min",
    "potencia": "W",
    "energia_dia": "kWh",
    "tensao": "V",
    "corrente": "A",
    "bateria": "%",
    "rssi": "dBm",
    "outro": "",
}


def _canon(metric: str) -> str:
    m = metric.strip().lower().replace("-", "_").replace(" ", "_")
    m = ALIASES.get(m, m)
    return m if m in VALID_METRICS else m  # deixa passar 'outro' se desconhecido


def _parse_ts(value, default=None):
    if value is None:
        return default or dj_tz.now()
    if isinstance(value, (int, float)):
        # epoch seconds ou ms
        if value > 1e12:
            value = value / 1000
        try:
            return datetime.fromtimestamp(float(value), tz=timezone.utc)
        except Exception:
            return default or dj_tz.now()
    if isinstance(value, str):
        s = value.strip()
        # tenta ISO
        try:
            if s.endswith("Z"):
                s = s[:-1] + "+00:00"
            dt = datetime.fromisoformat(s)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except Exception:
            pass
        # epoch como string
        try:
            return _parse_ts(float(s), default)
        except Exception:
            return default or dj_tz.now()
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value
    return default or dj_tz.now()


def _coerce_value(v):
    """Converte para float, e RECUSA o que não é um número de verdade.

    `float("nan")` e `float("inf")` NÃO levantam excepção — são floats válidas.
    Antes esta função devolvia-as, e elas passavam o `if val is None: continue`
    a jusante. O estrago:

      * `alert_engine` faz `Avg("value")` sobre a propriedade. UM unico `NaN`
        contamina a media inteira, e como `delta` e `anomalia` (z-score)
        comparam contra ela, ficam com `mean = nan`, `stdev = nan`, e TODAS as
        comparacoes `>= thr` ficam `False` — para sempre.
      * Uma unica leitura pode silenciar permanentemente as regras agronomicas
        de uma fazenda, incluindo a que abre a valvula.

    E nao exige nenhum conhecimento: basta `{"umidade_solo": NaN}` num payload
    JSON valido. E negacao de servico no motor de decisao.

    E' o `Suspect` que a Seccao IV do documento promete: "dado que viola os
    limites de plausibilidade fisica (ex: NaN, Inf)". Nao havia estado para o
    atravessar, portanto o valor chegava ao painel como `medido`.

    `None` e o sinal de "isto nao e um numero" e o chamador sabe o que fazer
    com a ausencia. Um `NaN` e' pior: parece um numero, e nao e'.
    """
    try:
        n = float(v)
    except (TypeError, ValueError):
        return None
    return n if math.isfinite(n) else None


# ---- Cayenne LPP (se disponível) ----
try:
    import cayenne_lpp

    HAS_CAYENNE = True
except ImportError:
    HAS_CAYENNE = False


def _decode_cayenne(hex_str: str):
    """Decodifica payload Cayenne LPP hex -> dict. Fallback simples se lib não instalada."""
    if HAS_CAYENNE:
        try:
            bytes.fromhex(hex_str)
            # cayenne_lpp lib API varia; tenta genérico
            # fallback para parser manual simples
        except Exception:
            pass
    # Parser manual minimalista para tipos comuns (temp=0x67, humidity=0x68, barometer=0x73, etc.)
    # Formato: [channel, type, ...data]
    try:
        b = bytes.fromhex(hex_str.strip())
    except Exception:
        return {}
    i = 0
    out = {}
    while i + 2 <= len(b):
        ch = b[i]
        typ = b[i + 1]
        i += 2
        if typ == 0x67 and i + 2 <= len(b):  # temperature 2 bytes /10
            val = int.from_bytes(b[i : i + 2], "big", signed=True) / 10
            out[f"temperatura_ch{ch}"] = val
            i += 2
        elif typ == 0x68 and i + 1 <= len(b):  # humidity 1 byte /2
            val = b[i] / 2
            out[f"umidade_ar_ch{ch}"] = val
            i += 1
        elif typ == 0x73 and i + 2 <= len(b):  # barometer 2 bytes /10
            val = int.from_bytes(b[i : i + 2], "big") / 10
            out[f"pressao_ch{ch}"] = val
            i += 2
        elif typ == 0x02 and i + 2 <= len(b):  # analog input 2 bytes /100
            val = int.from_bytes(b[i : i + 2], "big", signed=True) / 100
            out[f"analog_ch{ch}"] = val
            i += 2
        else:
            break
    return out


# ---- Entradas principais ----


def _extract_ttn_wrapper(payload: dict):
    """Se payload é wrapper TTN/ChirpStack, extrai decoded_payload e metadata."""
    if "uplink_message" in payload:
        um = payload["uplink_message"]
        decoded = um.get("decoded_payload") or um.get("frm_payload") or {}
        # frm_payload pode ser base64
        if isinstance(decoded, str):
            try:
                decoded = json.loads(base64.b64decode(decoded).decode())
            except Exception:
                decoded = {}
        meta = {
            "rssi": um.get("rx_metadata", [{}])[0].get("rssi")
            if um.get("rx_metadata")
            else None,
            "snr": um.get("rx_metadata", [{}])[0].get("snr")
            if um.get("rx_metadata")
            else None,
            "fPort": um.get("f_port"),
        }
        ts = um.get("received_at") or payload.get("received_at")
        return decoded if isinstance(decoded, dict) else {}, meta, ts
    if "object" in payload and isinstance(payload["object"], dict):  # ChirpStack
        return (
            payload["object"],
            {"rssi": payload.get("rssi"), "snr": payload.get("snr")},
            payload.get("time"),
        )
    return None, None, None


def normalize_payload(raw, default_ts=None):
    """
    Normaliza qualquer payload em lista de leituras canônicas.
    raw: dict | list | str (JSON string, hex, csv)
    """
    default_ts = default_ts or dj_tz.now()
    # Se string, tenta JSON
    if isinstance(raw, (bytes, bytearray)):
        try:
            raw = raw.decode()
        except Exception:
            raw = str(raw)
    if isinstance(raw, str):
        s = raw.strip()
        # hex puro (Cayenne)
        if re.fullmatch(r"[0-9a-fA-F]+", s) and len(s) % 2 == 0 and len(s) >= 4:
            decoded = _decode_cayenne(s)
            return _dict_to_readings(decoded, default_ts, raw_payload={"hex": s})
        # JSON string
        try:
            raw = json.loads(s)
        except Exception:
            # CSV?
            if "," in s and "\n" in s:
                return _csv_to_readings(s, default_ts)
            return []

    # Wrapper TTN/ChirpStack?
    if isinstance(raw, dict):
        unwrapped, meta, ts_raw = _extract_ttn_wrapper(raw)
        if unwrapped is not None:
            ts = _parse_ts(ts_raw, default_ts)
            readings = _dict_to_readings(unwrapped, ts, raw_payload=raw)
            # anexa rssi/snr como leituras se existirem
            if meta and meta.get("rssi") is not None:
                readings.append(
                    {
                        "metric": "rssi",
                        "value": float(meta["rssi"]),
                        "unit": "dBm",
                        "timestamp": ts,
                        "raw_payload": raw,
                    }
                )
            return readings

    if isinstance(raw, dict):
        ts = _parse_ts(
            raw.get("timestamp")
            or raw.get("ts")
            or raw.get("time")
            or raw.get("@timestamp"),
            default_ts,
        )
        # remove chaves de controle
        clean = {
            k: v
            for k, v in raw.items()
            if k
            not in (
                "timestamp",
                "ts",
                "time",
                "@timestamp",
                "device_eui",
                "deviceEui",
                "devEUI",
            )
        }
        return _dict_to_readings(clean, ts, raw_payload=raw)

    if isinstance(raw, list):
        # SenML ou lista de dicts
        out = []
        for item in raw:
            if isinstance(item, dict) and "n" in item and "v" in item:
                metric = _canon(str(item["n"]))
                val = _coerce_value(item["v"])
                if val is None:
                    continue
                ts = _parse_ts(item.get("t") or item.get("time"), default_ts)
                out.append(
                    {
                        "metric": metric if metric in VALID_METRICS else "outro",
                        "value": val,
                        "unit": UNITS.get(metric, ""),
                        "timestamp": ts,
                        "raw_payload": raw,
                    }
                )
            elif isinstance(item, dict):
                out.extend(_dict_to_readings(item, default_ts, raw_payload=raw))
        return out

    return []


def _dict_to_readings(d: dict, ts, raw_payload=None):
    out = []
    for k, v in d.items():
        # ignora objetos aninhados não numéricos
        if isinstance(v, dict):
            # tenta extrair valor interno
            if "value" in v and isinstance(v["value"], (int, float, str)):
                v = v["value"]
            else:
                continue
        if isinstance(v, list):
            continue
        metric = _canon(str(k))
        if metric not in VALID_METRICS:
            # se desconhecido mas numérico, guarda como 'outro' com nome original em raw
            if _coerce_value(v) is None:
                continue
            out.append(
                {
                    "metric": "outro",
                    "value": _coerce_value(v),
                    "unit": "",
                    "timestamp": ts,
                    "raw_payload": raw_payload or d,
                    "_original_key": k,
                }
            )
            continue
        val = _coerce_value(v)
        if val is None:
            continue
        out.append(
            {
                "metric": metric,
                "value": val,
                "unit": UNITS.get(metric, ""),
                "timestamp": ts,
                "raw_payload": raw_payload or d,
            }
        )
    return out


def _csv_to_readings(csv_str: str, default_ts):
    try:
        reader = csv.DictReader(io.StringIO(csv_str))
        out = []
        for row in reader:
            ts = _parse_ts(
                row.get("timestamp") or row.get("ts") or row.get("time"), default_ts
            )
            for k, v in row.items():
                if k in ("timestamp", "ts", "time"):
                    continue
                metric = _canon(k)
                val = _coerce_value(v)
                if val is None or metric not in VALID_METRICS:
                    continue
                out.append(
                    {
                        "metric": metric,
                        "value": val,
                        "unit": UNITS.get(metric, ""),
                        "timestamp": ts,
                        "raw_payload": {"csv_row": row},
                    }
                )
        return out
    except Exception:
        return []
