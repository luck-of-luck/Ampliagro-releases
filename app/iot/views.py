"""
Endpoints de ingestão de telemetria — HTTP push + consulta.

Autenticação — e SO esta, sem excepções:
- Header X-API-Key: <Gateway.api_key>
- Ou query ?api_key=...
- Ou Authorization: Bearer <api_key>

`Device.device_eui` NÃO autentica. É um identificador de hardware que viaja
em claro pelo radio: qualquer um que o ouça num packet pode escribir
telemetria em nome da placa. O `device_eui` é usado para RESOLVER o device
depois de autenticado, sempre com o gateway ou o `propriedade__user` no
mesmo filtro — nunca no lugar da credencial. Este parágrafo substitui o que
aqui estava antes, que descrevia um fallback por EUI que já não existe: a
docstring affirmava uma porta que o código tinha fechado.

Ingestão aceita qualquer formato suportado por parsers.normalize_payload.

Rotas (ver urls.py):
  POST /api/iot/push/                 — push genérico (resolve device por EUI ou gateway)
  POST /api/iot/push/<device_eui>/    — push direto para device
  POST /api/iot/mqtt/webhook/         — webhook TTN/ChirpStack
  GET  /api/iot/telemetry/            — query series

Sobre o webhook TTN
===================
Este texto dizia antes "sem api_key, valida por config". **Estava errado, e
a frase e' perigosa** porque descreve um bypass que nao existe.

O que acontece hoje: `ttn_webhook` delega a `push_telemetry`, que exige
`api_key` como qualquer outro push. Um TTN/ChirpStack que chegue sem
`X-API-Key` leva **401**, em `_get_device_from_request:134`. E' fail-closed,
e e' o estado correcto enquanto o bypass nao for implementado.

Reconhecer a FORMA do payload (`uplink_message`, `end_device_ids`) nao
autentica nada — serve so para extrair o `dev_eui` e perguntar por ele. E o
`iot.write` que o §VI do manifesto Agro 5.0 promete para a telemetria e'
hoje `Gateway.api_key_hash` com hash cego (`app/seguranca.py:hash_cego`),
que e' mais do que o manifesto descreve — mas e' so isto. Nao ha
`AMPLIAGRO_DATA_KEY`, e nao ha allowlist de `FonteDadosExterna` neste
caminho.

O bypass sem `api_key` continua POR FAZER, e o trabalho esta escrito na
`push_telemetry` (linha ~152). O guarda que o mantem fechado e'
`tests/test_webhook_ttn_sem_auth.py` — que falha de proposito se o bypass
aparecer sem validacao.
"""

import json
import logging

from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count, Max, Min
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from app.iot.alert_engine import evaluate_batch
from app.iot.parsers import normalize_payload
from app.models import Device, Gateway, Propriedade, TelemetryData

# O logger existe por causa de um `except: pass` que engolia falha de escrita.
# Ver o comentario em `persistir_telemetria`.
logger = logging.getLogger(__name__)


def _resolve_auth(request):
    api_key = (
        request.headers.get("X-API-Key")
        or request.headers.get("X-Api-Key")
        or request.GET.get("api_key")
    )
    if not api_key:
        auth = request.headers.get("Authorization", "")
        if auth.lower().startswith("bearer "):
            api_key = auth[7:].strip()
    if not api_key:
        return None, None
    # tenta gateway (índice cego: api_key em repouso é Fernet randomizado)
    try:
        from app.seguranca import hash_cego

        gw = Gateway.objects.select_related("propriedade").get(
            api_key_hash=hash_cego(api_key)
        )
        return gw, None
    except Gateway.DoesNotExist:
        pass
    # Fallback por device_eui REMOVIDO: qualquer um que conheça o EUI
    # podia injetar telemetria. Agora só Gateway.api_key (Fernet) autentica.
    return None, None


def _get_device_from_request(request, device_eui_url=None):
    """Resolve device alvo do push.

    A AUTENTICACAO VEM ANTES DA RESOLUCAO. E esta a correcao de uma incoerencia
    que o auditor encontrou pelo caminho inverso.

    A ordem antiga era:

        dev = Device.objects.get(device_eui=...)   # L64
        if not gw and not dev_hint: return 401     # L76
        ...
        except Device.DoesNotExist: return 404     # L81

    Com essa ordem, um POST sem `X-API-Key` para um EUI que NAO existe
    respondia 404, e para um EUI que existe respondia 401. A diferenca entre
    os dois codigos diz a quem nao tem credencial se um dispositivo existe.

    E um oraculo de enumeracao: os EUI sao identificadores de hardware que
    viajam por radio. Um atacante que consiga ouvir um packet consegue
    confirmar que a placa existe no sistema e depois usar esse conhecimento a
    favor. Nao permite escrever — para um device existente cai no 401 — mas
    transforma "poder tentar" em "saber o que existe".

    Autenticar primeiro tambem e a ordem correcta em si: nao se diz a quem nao
    autenticou nada sobre o que existe. Um 401 e a mesma resposta para todo o
    mundo, exista ou nao o device.

    O `gw is None`Mantem-se como esta: um device SEM gateway e um device de
    outro tenant dao o mesmo 403, e nao um 404 que confirma a existencia.
    """
    gw, dev_hint = _resolve_auth(request)

    # 1. AUTENTICAR. Antes de tocar na base de dados, e antes de responder.
    #
    # `dev_hint` ja e' um device resolvido por `_resolve_auth`, ou seja, ja
    # autenticado. `gw` tambem. Se nao ha nenhum dos dois, nao ha credencial —
    # e nao ha nada a dizer sobre o device.
    if not gw and not dev_hint:
        return None, JsonResponse({"error": "api_key inválida"}, status=401)

    # 2. RESOLVER. Agora com credencial, a resposta pode ser especifica.
    if device_eui_url:
        try:
            dev = Device.objects.select_related("propriedade", "gateway", "talhao").get(
                device_eui=device_eui_url
            )
            if gw and (
                dev.gateway_id != gw.id and dev.propriedade_id != gw.propriedade_id
            ):
                return None, JsonResponse(
                    {"error": "device não pertence ao gateway"}, status=403
                )
            return dev, None
        except Device.DoesNotExist:
            return None, JsonResponse({"error": "device não encontrado"}, status=404)
    # push genérico: tenta extrair device_eui do body
    if dev_hint:
        return dev_hint, None
    if gw:
        # exige device_eui no payload/query quando autenticado por gateway
        eui = request.GET.get("device_eui") or request.GET.get("devEui")
        if eui:
            try:
                dev = Device.objects.get(device_eui=eui, gateway=gw)
                return dev, None
            except Device.DoesNotExist:
                # auto-provisiona se gateway permite?
                return None, JsonResponse(
                    {"error": f"device {eui} não vinculado ao gateway"}, status=404
                )
        return None, JsonResponse(
            {"error": "device_eui obrigatório quando autenticado por gateway"},
            status=400,
        )
    return None, JsonResponse(
        {"error": "autenticação necessária (X-API-Key)"}, status=401
    )


# ────────────────────────────────────────────────────────────────────────────
# A QUALIDADE DA LEITURA
# ────────────────────────────────────────────────────────────────────────────
#
# MEDIDO 2026-10-04. Este ficheiro gravava `qualidade="good"` como literal, em
# dois sítios, e comentava `# ignora métricas fora do range absurdo (ex:
# -9999)` — mas não ignorava nada: o `try/except` à volta só apanha
# excepções, e `-9999` é um `float` finito, portanto passava o `math.isfinite`
# de `parsers.py` e era gravado como `good`.
#
# O efeito é o que `validators.py:20` descreve e que ninguém via acontecer:
# um painel mostrava uma temperatura de -9999 °C como medida boa, e nada
# acima disso denunciava. `suspect` existe em `app/ia/proveniencia.py:82`
# desde o início e nunca era construído em lado nenhum do `app/` — um estado
# declarado, documentado, e inalcançável.
#
# O QUE ESTE NÃO FAZ, E PORQUÊ
# ============================
# Não há faixas por métrica declaradas em lado nenhum do repositório, e
# inventá-las seria exactamente o defeito que a doutrina do projecto proíbe
# (`proveniencia.py:36`: "`suspect` — o sensor disse, e a física não
# permite o que disse"). Uma tabela de faixas escrita por um programador sem
# fonte seria um `suspect` inventado com forma de `good`.
#
# Por isso a tabela existe, está VAZIA de propósito, e o que está lá dentro
# tem de vir da ficha do sensor. O que se rejeita agora é o que o próprio
# código já declarava: o sentinela `-9999`.
#
# E o sentinela NÃO é descartado — é gravado como `suspect`, com o motivo no
# `raw_payload`. Descartar seria apagar a evidência de que o sensor
# falhou, e o comentário original prometia descartar sem o fazer: mais um
# docstring que descrevia um código que não existia.
#
# Preencher `FAIXAS_POR_METRICA` é uma tarefa de quem tem as fichas
# técnicas. Está aqui para que essa pessoa tenha um sítio, e não um
# `if` espalhado por três views.
_SENTINELAS = {
    -9999: "sentinela de sensor sem leitura",
    -9999.0: "sentinela de sensor sem leitura",
    -999: "sentinela de sensor sem leitura",
    -99.99: "sentinela de sensor sem leitura",
}

#: `metrica -> (minimo, maximo)`. VAZIA de propósito — ver acima.
#: Exemplos do formato, commented para nao parecer que ha mais:
#:   "temperatura_c": (-40.0, 85.0),   # ficha do sensor, nao opiniao
FAIXAS_POR_METRICA: dict = {}


def classifica_qualidade(metric: str, value) -> tuple:
    """`(qualidade, motivo)` — a qualidade que a leitura MERECE.

    `suspect` quando o valor e' um sentinela conhecido, ou quando a metrica
    tem faixa declarada e o valor cai fora dela. `good` quando o valor e'
    finito e nada o contradiz.

    O `motivo` volta para o `raw_payload`: uma leitura `suspect` sem
    explicação é indistinguível de uma leitura má, e quem depura o painel
    precisa de saber QUAL das duas foi.
    """
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "suspect", "valor nao numerico"

    if v in _SENTINELAS:
        return "suspect", _SENTINELAS[v]

    faixa = FAIXAS_POR_METRICA.get(metric)
    if faixa is not None:
        minimo, maximo = faixa
        if not (minimo <= v <= maximo):
            return "suspect", f"fora da faixa declarada ({minimo}, {maximo})"

    return "good", ""


@csrf_exempt
@require_http_methods(["POST"])
def comando_ack(request):
    """Portão HTTP do ACK. É o caminho de produção: o gateway confirma por aqui.

    A AUTENTICACAO E' A MESMA DA TELEMETRIA, e pela mesma razao: uma
    credencial que empurra telemetria pode confirmar um comando. Menos credenciais
    para uma coisa mais perigosa do que a outra seria um caminho mais facil.

    Fail-closed: sem `X-API-Key` valida nao ha ACK. O `Gateway` traz a
    propriedade, e e' ela que ancora a autorizacao — um gateway so confirma
    comandos da fazenda dele. Um ACK de outra propriedade e' 403, e nao um 404,
    porque quem tem credencial ja sabe que o comando existe.
    """
    from app.iot.ack import AckRecusado, confirmar

    gw, _dev_hint = _resolve_auth(request)
    if gw is None:
        return JsonResponse(
            {
                "ok": False,
                "erro": "sem credencial de gateway (X-API-Key)",
                "fonte_dado": "sem_dado",
            },
            status=401,
        )

    try:
        payload = json.loads((request.body or b"{}").decode("utf-8") or "{}")
    except (ValueError, UnicodeDecodeError):
        payload = {}
    if not isinstance(payload, dict):
        payload = {}

    device_eui = payload.get("device_eui") or payload.get("dev_eui") or ""
    dev = Device.objects.filter(
        device_eui=device_eui, propriedade_id=gw.propriedade_id
    ).first()
    if dev is None:
        # Nao se diz "nao existe" a quem tem credencial: 403 tanto faz.
        return JsonResponse(
            {
                "ok": False,
                "erro": "device nao pertence a este gateway",
                "fonte_dado": "sem_dado",
            },
            status=403,
        )

    ok = payload.get("ok")
    if not isinstance(ok, bool):
        # Um ACK sem `ok` explicito e' um ACK ambiguo. Adivinhar "deu certo"
        # seria a pior leitura possivel: fecharia o ciclo sobre um valor que
        # ninguem disse.
        return JsonResponse(
            {
                "ok": False,
                "erro": "`ok` tem de ser booleano. Um ACK sem 'ok' explicito "
                "nao diz se a acao aconteceu.",
                "fonte_dado": "sem_dado",
            },
            status=400,
        )

    try:
        cmd, mudou = confirmar(
            cmd_id=payload.get("cmd_id"),
            device=dev,
            propriedade=gw.propriedade,
            ok=ok,
            resposta=payload.get("resposta")
            if isinstance(payload.get("resposta"), dict)
            else {},
            motivo=str(payload.get("motivo") or ""),
        )
    except AckRecusado as r:
        return JsonResponse(
            {"ok": False, "erro": r.motivo, "fonte_dado": "sem_dado"},
            status=r.http_status,
        )

    return JsonResponse(
        {"ok": True, "mudou": mudou, "cmd_id": cmd.id, "status": cmd.status}
    )


@csrf_exempt
@require_http_methods(["POST"])
def push_telemetry(request, device_eui=None):
    # SEM autenticacao, este endpoint NAO ACEITA nada.
    #
    # O comentario que estava aqui descrevia um bypass para webhooks TTN sem
    # autenticacao,conditionado a uma validacao por `FonteDadosExterna` que
    # nuca foi escrita. Nenhuma das duas metades existia: o bypass nao estava
    # implementado, e o `FonteDadosExterna` nunca foi chamado aqui.
    #
    # Um webhook TTN que chegue sem `X-API-Key` leva 401 em
    # `_get_device_from_request`. E o certo enquanto o bypass nao existir —
    # fail-closed.
    #
    # PARA HABILITAR O WEBHOOK TTN (trabalho em aberto, nao feito):
    #   1. validar a `FonteDadosExterna` allowlisted — `app/seguranca.py`
    #      tem oAllowlist; o endpoint tem de a consultar e recusar tudo o que
    #      nao esteja na lista
    #   2. verificar assinatura do payload, se o broker a emitir
    #   3. testar o caminho em `tests/test_webhook_ttn_sem_auth.py`, que hoje
    #      falha de proposito se o bypass aparecer sem validacao
    try:
        raw_body = request.body.decode() if request.body else "{}"
    except Exception:
        raw_body = "{}"
    # tenta JSON, senão trata como string
    try:
        payload = json.loads(raw_body) if raw_body.strip() else {}
        # se for array JSON, mantém
        if isinstance(payload, str):
            payload = json.loads(payload)
    except Exception:
        payload = raw_body  # hex / csv string

    # Payload com a forma de TTN: `uplink_message` ou `end_device_ids`.
    #
    # Reconhecer a FORMA nao autentica nada. O que se segue e' so para extrair
    # o `dev_eui` e pedir ao `_get_device_from_request`, que e' quem decide se
    # ha credencial. Sem `gw` e sem `dev_hint`, la responde 401 — tanto faz o
    # payload vir com o EUI preenchido.
    is_ttn_webhook = isinstance(payload, dict) and (
        "uplink_message" in payload or "end_device_ids" in payload
    )
    if is_ttn_webhook and not device_eui:
        # extrai o EUI do corpo para poder perguntar por ele
        dev_eui = None
        try:
            dev_eui = (
                payload.get("end_device_ids", {}).get("dev_eui")
                or payload.get("end_device_ids", {}).get("device_id")
                or payload.get("device_eui")
            )
            if dev_eui:
                device_eui = dev_eui
        except Exception:
            pass

    device, err = _get_device_from_request(request, device_eui)
    if err:
        return err

    # normaliza
    readings = normalize_payload(payload, default_ts=timezone.now())
    if not readings:
        return JsonResponse(
            {
                "error": "payload vazio ou não reconhecido",
                "hint": "envie JSON com métricas numéricas ou SenML/Cayenne hex",
            },
            status=400,
        )

    # persiste
    objs = []
    now = timezone.now()
    for rd in readings:
        # A qualidade e' DERIVADA, nao literal. Ver `classifica_qualidade`
        # acima: antes isto gravava "good" para tudo e comentava que
        # ignorava o range, o que nao acontecia.
        qualidade, motivo = classifica_qualidade(rd["metric"], rd["value"])
        try:
            bruto = dict(rd.get("raw_payload") or {})
            if motivo:
                bruto["_qualidade_motivo"] = motivo
            objs.append(
                TelemetryData(
                    device=device,
                    estacao=device.estacao,
                    propriedade=device.propriedade,
                    talhao=device.talhao,
                    metric=rd["metric"],
                    value=rd["value"],
                    unit=rd.get("unit", ""),
                    timestamp=rd["timestamp"],
                    qualidade=qualidade,
                    raw_payload=bruto,
                )
            )
        except Exception:
            continue
    if objs:
        TelemetryData.objects.bulk_create(objs, batch_size=500)
        # também espelha em LeituraSensor para compatibilidade quando metric é legado e device tem estacao
        if device.estacao:
            try:
                from app.models import LeituraSensor

                legacy_map = {
                    "temperatura": "temperatura",
                    "umidade_ar": "umidade",
                    "pressao": "pressao",
                    "chuva": "chuva",
                    "vento_vel": "vento_vel",
                    "vento_dir": "vento_dir",
                    "radiacao": "radiacao",
                    "umidade_solo": "umidade_solo",
                    "condutividade": "condutividade",
                    "ph_solo": "ph",
                }
                bulk_legacy = []
                for rd in readings:
                    tipo = legacy_map.get(rd["metric"])
                    if tipo:
                        # Mesma derivacao do caminho novo acima — a tabela
                        # `LeituraSensor` nao pode ser mais confianca do que
                        # a `TelemetryData` que a alimenta, ou o mesmo
                        # numero aparece com qualidades diferentes em dois
                        # sitios, conforme o endpoint por onde entrou.
                        q_legado, motivo_legado = classifica_qualidade(
                            rd["metric"], rd["value"]
                        )
                        bulk_legacy.append(
                            LeituraSensor(
                                estacao=device.estacao,
                                tipo=tipo,
                                valor=rd["value"],
                                unidade=rd.get("unit", ""),
                                timestamp=rd["timestamp"],
                                qualidade=q_legado,
                            )
                        )
                if bulk_legacy:
                    LeituraSensor.objects.bulk_create(bulk_legacy, batch_size=500)
            except Exception:
                # MEDIDO 2026-10-06. Este `except: pass` engolia uma falha de
                # ESCRITA. Nao e' um detalhe: se o `bulk_create` rebentasse,
                # a telemetria chegava, nao se via nada, e o produtor ficava
                # com um sensor que "funciona" e nunca regista. O sintoma e'
                # um dashboard vazio sem erro - a mesma classe do painel que
                # lia um cookie HTTP-only e mostrava "sem dado".
                #
                # Um alerta de telemetria que falha NAO pode calar o sistema:
                # e' exatamente quando o produtor precisa de saber.
                logger.exception(
                    "[iot] telemetria de %s nao gravada (%s leituras)",
                    getattr(device, "device_eui", "?"),
                    len(readings),
                )
                raise
        # atualiza device/gateway
        try:
            device.ultimo_push = now
            # atualiza bateria/rssi se vieram nas leituras
            for rd in readings:
                if rd["metric"] == "bateria":
                    device.bateria_pct = rd["value"]
                if rd["metric"] == "rssi":
                    device.rssi = int(rd["value"])
            device.save(update_fields=["ultimo_push", "bateria_pct", "rssi"])
            if device.gateway:
                device.gateway.ultimo_contato = now
                device.gateway.status = "online"
                device.gateway.save(update_fields=["ultimo_contato", "status"])
        except Exception:
            pass
        # avalia alertas (threshold + agronômico por cultura)
        try:
            alerts = evaluate_batch(device.propriedade, device, readings, now=now)
        except Exception:
            alerts = []
        try:
            from app.iot.alert_engine import evaluate_culture_alerts

            alerts = list(alerts) + list(
                evaluate_culture_alerts(device.propriedade, readings, now=now)
            )
        except Exception:
            pass
        return JsonResponse(
            {
                "ok": True,
                "ingested": len(objs),
                "alerts": len(alerts),
                "device": device.device_eui,
            }
        )

    return JsonResponse({"error": "nenhuma métrica válida"}, status=400)


@csrf_exempt
@require_http_methods(["POST"])
def ttn_webhook(request):
    """Alias para push sem device_eui na URL — usado como webhook TTN/ChirpStack."""
    return push_telemetry(request, device_eui=None)


@login_required
@require_http_methods(["GET"])
def query_telemetry(request):
    """
    GET /api/iot/telemetry/?propriedade=1&device=<eui>&metric=temperatura&from=2026-08-20&to=2026-08-27&agg=hour&limit=1000
    """
    propriedade_id = request.GET.get("propriedade")
    if not propriedade_id:
        # usa primeira propriedade do user
        prop = Propriedade.objects.filter(user=request.user).first()
        if not prop:
            return JsonResponse({"error": "propriedade obrigatória"}, status=400)
        propriedade_id = prop.id
    else:
        try:
            prop = Propriedade.objects.get(id=propriedade_id, user=request.user)
        except Propriedade.DoesNotExist:
            return JsonResponse(
                {"error": "propriedade não encontrada ou sem permissão"}, status=404
            )

    qs = TelemetryData.objects.filter(propriedade=prop)
    device_eui = request.GET.get("device")
    if device_eui:
        qs = qs.filter(device__device_eui=device_eui)
    metric = request.GET.get("metric")
    if metric:
        qs = qs.filter(metric=metric)
    talhao_id = request.GET.get("talhao")
    if talhao_id:
        qs = qs.filter(talhao_id=talhao_id)
    from_str = request.GET.get("from") or request.GET.get("start")
    to_str = request.GET.get("to") or request.GET.get("end")
    from django.utils.dateparse import parse_date, parse_datetime

    if from_str:
        dt = parse_datetime(from_str) or (
            parse_date(from_str)
            and timezone.make_aware(
                timezone.datetime.combine(
                    parse_date(from_str), timezone.datetime.min.time()
                )
            )
        )
        if dt:
            qs = qs.filter(timestamp__gte=dt)
    if to_str:
        dt = parse_datetime(to_str) or (
            parse_date(to_str)
            and timezone.make_aware(
                timezone.datetime.combine(
                    parse_date(to_str), timezone.datetime.max.time()
                )
            )
        )
        if dt:
            qs = qs.filter(timestamp__lte=dt)

    agg = request.GET.get("agg")  # hour, day
    limit = min(int(request.GET.get("limit", 500)), 5000)
    if agg in ("hour", "day"):
        # agregação: usa extra com date_trunc (Postgres) ou strftime (SQLite)
        from django.db import connection

        qs = qs.order_by()
        if connection.vendor == "postgresql":
            trunc = "hour" if agg == "hour" else "day"
            qs = (
                qs.extra(select={"bucket": f"date_trunc('{trunc}', timestamp)"})
                .values("bucket", "metric")
                .annotate(
                    avg=Avg("value"),
                    max=Max("value"),
                    min=Min("value"),
                    count=Count("id"),
                )
                .order_by("bucket")
            )
            data = list(qs[:limit])
            # serializa Decimal/datetime
            for row in data:
                row["bucket"] = row["bucket"].isoformat() if row["bucket"] else None
                row["avg"] = float(row["avg"]) if row["avg"] is not None else None
                row["max"] = float(row["max"]) if row["max"] is not None else None
                row["min"] = float(row["min"]) if row["min"] is not None else None
            return JsonResponse({"propriedade": prop.id, "agg": agg, "data": data})
        else:
            # SQLite fallback: agrupa em Python (menos eficiente mas funciona)
            pass

    qs = qs.select_related("device").order_by("-timestamp")[:limit]
    data = [
        {
            "id": r.id,
            "device": r.device.device_eui if r.device else None,
            "device_nome": r.device.nome if r.device else None,
            "metric": r.metric,
            "value": float(r.value),
            "unit": r.unit,
            "timestamp": r.timestamp.isoformat(),
            "qualidade": r.qualidade,
        }
        for r in qs
    ]
    return JsonResponse({"propriedade": prop.id, "count": len(data), "data": data})


@login_required
@require_http_methods(["GET"])
def sensor_lookup(request):
    """
    GET /api/iot/sensor-lookup/?device_eui=<EUI>&id=<pk>
    Resolve o ID que o usuário digitou no cadastro: mostra nome/tipo do
    sensor + último dado de cada métrica recebido pela API.
    """
    eui = (request.GET.get("device_eui") or request.GET.get("eui") or "").strip()
    pk = request.GET.get("id")
    try:
        if pk:
            dev = Device.objects.select_related("propriedade", "gateway").get(
                id=pk, propriedade__user=request.user
            )
        elif eui:
            dev = Device.objects.select_related("propriedade", "gateway").get(
                device_eui__iexact=eui, propriedade__user=request.user
            )
        else:
            return JsonResponse(
                {"found": False, "error": "informe device_eui ou id"}, status=400
            )
    except Device.DoesNotExist:
        return JsonResponse(
            {
                "found": False,
                "error": "sensor não encontrado — pode cadastrar como novo",
                "device_eui": eui or None,
            }
        )

    # último dado de cada métrica (para mostrar "o dado" que a API recebe)
    latest = {}
    for row in (
        TelemetryData.objects.filter(device=dev)
        .order_by("metric", "-timestamp")
        .values("metric", "value", "unit", "timestamp", "qualidade")
    ):
        if row["metric"] not in latest:
            latest[row["metric"]] = {
                "value": float(row["value"]),
                "unit": row["unit"],
                "timestamp": row["timestamp"].isoformat() if row["timestamp"] else None,
                "qualidade": row["qualidade"],
            }
    total = TelemetryData.objects.filter(device=dev).count()
    return JsonResponse(
        {
            "found": True,
            "device": {
                "id": dev.id,
                "nome": dev.nome,
                "tipo": dev.tipo,
                "tipo_display": dev.get_tipo_display(),
                "device_eui": dev.device_eui,
                "protocolo": dev.protocolo,
                "propriedade": dev.propriedade_id,
                "propriedade_nome": dev.propriedade.nome,
                "gateway": dev.gateway_id,
                "gateway_nome": dev.gateway.nome if dev.gateway else None,
                "bateria_pct": float(dev.bateria_pct)
                if dev.bateria_pct is not None
                else None,
                "ativo": dev.ativo,
                "ultimo_push": dev.ultimo_push.isoformat() if dev.ultimo_push else None,
                "topic": dev.topic,
            },
            "latest": latest,
            "total_leituras": total,
        }
    )


@login_required
@require_http_methods(["GET"])
def sensor_stats(request):
    """
    GET /api/iot/sensor-stats/?device_eui=<EUI>&metric=temperatura&days=7
    Histórico acumulado + média/máxima/mínima/total para o painel lateral.
    """
    eui = (request.GET.get("device_eui") or request.GET.get("device") or "").strip()
    if not eui:
        return JsonResponse({"error": "device_eui obrigatório"}, status=400)
    try:
        dev = Device.objects.get(device_eui__iexact=eui, propriedade__user=request.user)
    except Device.DoesNotExist:
        return JsonResponse({"error": "sensor não encontrado"}, status=404)

    try:
        days = min(max(int(request.GET.get("days", 7)), 1), 365)
    except ValueError:
        days = 7
    since = timezone.now() - timezone.timedelta(days=days)
    qs = TelemetryData.objects.filter(device=dev, timestamp__gte=since)
    metric = request.GET.get("metric")
    if metric:
        qs = qs.filter(metric=metric)

    agg = qs.aggregate(
        total=Count("id"), media=Avg("value"), maxima=Max("value"), minima=Min("value")
    )
    last = qs.order_by("-timestamp").first()
    first = qs.order_by("timestamp").first()
    hist = list(
        qs.order_by("-timestamp").values("metric", "value", "unit", "timestamp")[:200]
    )
    for h in hist:
        h["value"] = float(h["value"])
        h["timestamp"] = h["timestamp"].isoformat() if h["timestamp"] else None
    return JsonResponse(
        {
            "device_eui": dev.device_eui,
            "device_nome": dev.nome,
            "metric": metric,
            "days": days,
            "total": agg["total"] or 0,
            "media": float(agg["media"]) if agg["media"] is not None else None,
            "maxima": float(agg["maxima"]) if agg["maxima"] is not None else None,
            "minima": float(agg["minima"]) if agg["minima"] is not None else None,
            "primeira": first.timestamp.isoformat() if first else None,
            "ultima": {
                "metric": last.metric,
                "value": float(last.value),
                "unit": last.unit,
                "timestamp": last.timestamp.isoformat(),
            }
            if last
            else None,
            "historico": hist,
        }
    )
