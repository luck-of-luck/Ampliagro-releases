"""
Listener MQTT para ingestão contínua.

O CAMINHO DE PRODUÇÃO NÃO É ESTE
=================================
A ingestão viva é o webhook HTTP do TTN/ChirpStack
(`app/iot/urls.py` -> `iot_views.ttn_webhook`). O ChirpStack já consome o MQTT
e entrega por HTTP; nenhum `docker-compose.yml` do projecto tem mosquitto, e
`paho-mqtt` não está em `requirements.txt` — por decisão, quando
`mqtt_listener.py` foi movido de `app/iot/management/commands/` para aqui
(ver `docs/sistema/9.md`). Este comando é portanto um caminho OPCIONAL, para
quem opera um broker próprio e quer a ingestão sem o round-trip HTTP.

Não é uma dependência: nada no projecto o chama. Precisa de DUAS coisas que o
ambiente não tem — o pacote `paho-mqtt` e um broker MQTT a sério. Sem elas o
comando não faz nada, e por isso diz isso em vez de fingir que funciona.

Autenticação: o tópico NÃO autentica (é uma string que o cliente escolhe). Cada
payload tem de trazer `api_key`, validada contra `Gateway.api_key_hash` — a
mesma regra do pathway HTTP.

Uso:
  python manage.py mqtt_listener --host localhost --port 1883 --topic "ampliagro/+/+/+/telemetry"

Requer: pip install paho-mqtt  E  um broker MQTT a correr.
Assina tópicos, normaliza payload e grava via mesmo pipeline do HTTP push
(sem precisar de HTTP round-trip).
"""

import json

from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = (
        "Caminho OPCIONAL: escuta um broker MQTT e ingere telemetria. "
        "Requer paho-mqtt E um broker próprio — não está em requirements.txt "
        "e não há mosquitto no compose. A ingestão de produção é o webhook "
        "TTN/ChirpStack (api/iot/ -> ttn_webhook)."
    )

    def add_arguments(self, parser):
        parser.add_argument("--host", default="localhost")
        parser.add_argument("--port", type=int, default=1883)
        parser.add_argument("--topic", default="ampliagro/+/+/+/telemetry")
        parser.add_argument("--username", default=None)
        parser.add_argument("--password", default=None)

    def handle(self, *args, **opts):
        try:
            import paho.mqtt.client as mqtt
        except ImportError:
            self.stderr.write(
                "mqtt_listener: falta o pacote 'paho-mqtt'.\n"
                "  Este comando e' OPCIONAL e nao esta em requirements.txt — o\n"
                "  caminho de producao e' o webhook TTN/ChirpStack\n"
                "  (api/iot/ -> ttn_webhook), que nao precisa de broker.\n"
                "  Para usar este: pip install paho-mqtt E um broker MQTT a correr."
            )
            return

        from app.iot.alert_engine import evaluate_batch
        from app.iot.parsers import normalize_payload
        from app.models import Device, TelemetryData

        host, port, topic = opts["host"], opts["port"], opts["topic"]

        def on_connect(client, userdata, flags, rc, props=None):
            self.stdout.write(
                f"Conectado MQTT {host}:{port} rc={rc} — assinando {topic}"
            )
            client.subscribe(topic, qos=1)
            client.subscribe("ampliagro/+/+/+/status", qos=0)
            # O `verificar` do ciclo de comandos. QoS 1 porque o broker pode
            # repetir: por isso o `confirmar()` trata ACK repetido como no-op,
            # e nao como erro.
            client.subscribe("ampliagro/+/+/+/ack", qos=1)

        def on_message(client, userdata, msg):
            payload_raw = msg.payload
            t = msg.topic
            # extrai device_eui do tópico: ampliagro/{prop}/{gw}/{dev}/telemetry
            parts = t.split("/")
            dev_eui = parts[3] if len(parts) >= 4 else None
            try:
                text = payload_raw.decode()
                try:
                    payload = json.loads(text)
                except Exception:
                    payload = text
            except Exception:
                payload = {}
            if not isinstance(payload, dict):
                payload = {"valor": payload}

            # ──────────────────────────────────────────────────────────────
            # ZERO-TRUST: o tópico NÃO é prova de nada.
            #
            # Um tópico MQTT é uma string que o cliente escolhe. O `dev_eui`
            # aparece nele, na URL do push e no payload do TTN — não é
            # segredo. Sem isto, qualquer um que conheça um `dev_eui` existente
            # escreve `TelemetryData` com os valores que quiser, e esses
            # valores alimentam `evaluate_batch` — o motor que decide se uma
            # aplicação de glifosato vai ser lavada.
            #
            # A regra é a MESMA do pathway HTTP (`iot/views.py::_resolve_auth`):
            # só `Gateway.api_key` (Fernet em repouso, índice cego em repouso)
            # autentica. Nada de fallback por `device_eui`.
            # ──────────────────────────────────────────────────────────────
            from app.seguranca import hash_cego

            api_key = payload.get("api_key") or payload.get("apiKey")
            if not api_key:
                self.stderr.write(
                    f"telemetry sem api_key recusada ({t}) — o tópico não autentica"
                )
                return

            from app.models import Gateway

            try:
                gateway = Gateway.objects.select_related("propriedade").get(
                    api_key_hash=hash_cego(api_key)
                )
            except Gateway.DoesNotExist:
                self.stderr.write(f"api_key inválida em {t}")
                return

            # resolve device
            device = None
            if dev_eui:
                try:
                    device = Device.objects.select_related(
                        "propriedade", "gateway", "talhao", "estacao"
                    ).get(device_eui=dev_eui)
                except Device.DoesNotExist:
                    self.stderr.write(f"Device {dev_eui} não encontrado (tópico {t})")
                    return
            else:
                self.stderr.write(f"Tópico sem devEUI: {t}")
                return

            # O device tem de pertencer à gateway que autenticou — ou à mesma
            # propriedade. Mesma regra de `views.py:69-72`.
            if (
                device.gateway_id != gateway.id
                and device.propriedade_id != gateway.propriedade_id
            ):
                self.stderr.write(
                    f"device {dev_eui} não pertence à gateway autenticada — recusado"
                )
                return

            # ──────────────────────────────────────────────────────────────
            # O MESMO NÚCLEO, OUTRO PORTÃO.
            #
            # Um ACK confirma que uma acção FÍSICA aconteceu. A regra vive em
            # `app/iot/ack.py` e é a mesma que o portão HTTP usa — porque duas
            # copias divergem, e a segunda nunca é actualizada quando a
            # primeira muda. Aqui só se liga o mensageiro.
            #
            # A autenticação acima (api_key + posse do device) NÃO é repetida
            # aqui: já foi feita. E o tópico não autentica nada, exactamente
            # como não autenticava a telemetria.
            if t.endswith("/ack"):
                from app.iot.ack import AckRecusado, confirmar

                ok = payload.get("ok")
                if not isinstance(ok, bool):
                    # Um ACK sem `ok` booleano é ambíguo, e adivinhar "deu
                    # certo" fecharia o ciclo sobre um valor que ninguém disse.
                    self.stderr.write(
                        f"ack sem 'ok' booleano em {t} — recusado (cmd "
                        f"{payload.get('cmd_id')})"
                    )
                    return
                try:
                    cmd, mudou = confirmar(
                        cmd_id=payload.get("cmd_id"),
                        device=device,
                        propriedade=gateway.propriedade,
                        ok=ok,
                        resposta=(
                            payload.get("resposta")
                            if isinstance(payload.get("resposta"), dict)
                            else {}
                        ),
                        motivo=str(payload.get("motivo") or ""),
                    )
                except AckRecusado as r:
                    self.stderr.write(f"ack recusado: {r.motivo}")
                    return
                self.stdout.write(f"ack: cmd {cmd.id} -> {cmd.status} (mudou={mudou})")
                return

            # A chave não viaja para o banco: é segredo, e TelemetryData
            # guarda `raw_payload` do cliente.
            payload.pop("api_key", None)
            payload.pop("apiKey", None)

            readings = normalize_payload(payload, default_ts=timezone.now())
            if not readings:
                self.stderr.write(
                    f"Payload não reconhecido de {dev_eui}: {str(payload)[:200]}"
                )
                return
            objs = [
                TelemetryData(
                    device=device,
                    estacao=device.estacao,
                    propriedade=device.propriedade,
                    talhao=device.talhao,
                    metric=r["metric"],
                    value=r["value"],
                    unit=r.get("unit", ""),
                    timestamp=r["timestamp"],
                    qualidade="good",
                    raw_payload=r.get("raw_payload", {}),
                )
                for r in readings
            ]
            TelemetryData.objects.bulk_create(objs, batch_size=500)
            device.ultimo_push = timezone.now()
            device.save(update_fields=["ultimo_push"])
            if device.gateway:
                device.gateway.ultimo_contato = timezone.now()
                device.gateway.status = "online"
                device.gateway.save(update_fields=["ultimo_contato", "status"])
            try:
                evaluate_batch(device.propriedade, device, readings, now=timezone.now())
            except Exception as e:
                self.stderr.write(f"alert_engine erro: {e}")
            self.stdout.write(
                f"[{timezone.now():%H:%M:%S}] {dev_eui[:8]} <- {len(objs)} leituras ({t})"
            )

        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        if opts["username"]:
            client.username_pw_set(opts["username"], opts["password"])
        client.on_connect = on_connect
        client.on_message = on_message
        client.connect(host, port, 60)
        self.stdout.write(f"Iniciando loop MQTT {host}:{port} (Ctrl+C para parar)")
        try:
            client.loop_forever()
        except KeyboardInterrupt:
            client.disconnect()
            self.stdout.write("Encerrado")
