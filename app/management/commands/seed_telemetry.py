"""
Cria stack IoT de demonstração com dados reais + estrutura completa.

Uso:
  python manage.py seed_telemetry --propriedade 1 --with-data
  python manage.py seed_telemetry --all --with-data

Cria:
  - 1 Gateway por propriedade (WIFI + LORAWAN)
  - Devices: METEO, SOLO (2 talhões), NIVEL, MAQUINARIO, ANIMAL, ENERGIA (quando existirem talhões/maquinário/animais)
  - Regras de alerta padrão
  - FonteDadosExterna (Open-Meteo)
  - Ingere 24h de dados reais via Open-Meteo para cada propriedade

Estrutura pós-seed é imediatamente utilizável pelos pushes reais:
  POST /api/iot/push/<device_eui>/  com header X-API-Key: <gateway.api_key>
  Payload JSON livre (ver parsers.py) ou hex Cayenne LPP ou TTN webhook
"""

import json
import random
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from django.core.management.base import BaseCommand
from django.utils import timezone

PROFILES_PATH = (
    Path(__file__).resolve().parent.parent.parent / "iot" / "device_profiles.json"
)


class Command(BaseCommand):
    help = "Seed completo de telemetria (gateways, devices, regras, dados reais)"

    def add_arguments(self, parser):
        parser.add_argument("--propriedade", type=int, default=None)
        parser.add_argument("--all", action="store_true")
        parser.add_argument(
            "--with-data", action="store_true", help="Ingere 24h reais via Open-Meteo"
        )

    def handle(self, *args, **opts):
        from app.models import (
            Animal,
            Device,
            FonteDadosExterna,
            Gateway,
            Maquinario,
            Propriedade,
            RegraAlertaTelemetria,
            Talhao,
        )

        if opts["all"]:
            props = list(Propriedade.objects.all())
        elif opts["propriedade"]:
            props = list(Propriedade.objects.filter(id=opts["propriedade"]))
        else:
            props = list(Propriedade.objects.all()[:1])
            if not props:
                self.stderr.write("Nenhuma propriedade encontrada — crie uma primeiro")
                return

        profiles = json.loads(PROFILES_PATH.read_text(encoding="utf-8"))["profiles"]

        for prop in props:
            self.stdout.write(f"\n=== {prop.nome} ({prop.uf}) ===")

            # Gateways
            gw_wifi, _ = Gateway.objects.get_or_create(
                propriedade=prop,
                gateway_eui=f"WIFI-{prop.id:04d}-01",
                defaults={
                    "nome": f"Gateway Wi-Fi {prop.nome}",
                    "tipo": "WIFI",
                    "status": "online",
                },
            )
            gw_lora, _ = Gateway.objects.get_or_create(
                propriedade=prop,
                gateway_eui=f"LORA-{prop.id:04d}-01",
                defaults={
                    "nome": f"Gateway LoRaWAN {prop.nome}",
                    "tipo": "LORAWAN",
                    "status": "online",
                },
            )
            self.stdout.write(
                f"  Gateways: {gw_wifi.gateway_eui} (key {gw_wifi.api_key[:8]}...), {gw_lora.gateway_eui}"
            )

            # EstacaoMeteo legado -> garante 1
            from app.models import EstacaoMeteo

            est, _ = EstacaoMeteo.objects.get_or_create(
                propriedade=prop,
                nome=f"Estação {prop.nome}",
                defaults={"latitude": -15.79, "longitude": -47.88, "ativa": True},
            )

            # Devices por tipo
            talhoes = list(Talhao.objects.filter(propriedade=prop)[:2])
            maqs = list(Maquinario.objects.filter(propriedade=prop)[:1])
            animais = list(Animal.objects.filter(propriedade=prop)[:1])

            def ensure_device(eui, nome, tipo, gateway, **extra):
                prof = profiles.get(tipo, profiles["GENERIC"])
                defaults = {
                    "propriedade": prop,
                    "gateway": gateway,
                    "nome": nome,
                    "tipo": tipo,
                    "protocolo": prof["push"]["protocol"],
                    "intervalo_seg": prof["push"]["interval_s"],
                    "profile": prof,
                    "ativo": True,
                }
                defaults.update(extra)
                dev, created = Device.objects.get_or_create(
                    device_eui=eui, defaults=defaults
                )
                if created:
                    self.stdout.write(f"  Device criado: {nome} [{tipo}] {eui}")
                else:
                    self.stdout.write(f"  Device ok: {nome} [{tipo}]")
                return dev

            ensure_device(
                f"METEO-{prop.id:04d}-01",
                f"Meteo {prop.nome}",
                "METEO",
                gw_wifi,
                estacao=est,
            )
            for i, t in enumerate(talhoes):
                ensure_device(
                    f"SOLO-{prop.id:04d}-{i + 1:02d}",
                    f"Solo {t.nome}",
                    "SOLO",
                    gw_lora,
                    talhao=t,
                )
            if not talhoes:
                ensure_device(
                    f"SOLO-{prop.id:04d}-01", f"Solo Geral {prop.nome}", "SOLO", gw_lora
                )

            ensure_device(
                f"NIVEL-{prop.id:04d}-01", f"Nível {prop.nome}", "NIVEL", gw_lora
            )

            if maqs:
                for m in maqs:
                    ensure_device(
                        f"MAQ-{m.id:04d}-01",
                        f"Rastreador {m.nome}",
                        "MAQUINARIO",
                        gw_wifi,
                        maquinario=m,
                    )
            else:
                ensure_device(
                    f"MAQ-{prop.id:04d}-01",
                    f"Rastreador Demo {prop.nome}",
                    "MAQUINARIO",
                    gw_wifi,
                )

            if animais:
                for a in animais:
                    ensure_device(
                        f"ANIMAL-{a.id:04d}-01",
                        f"Colar {a.get_especie_display()}",
                        "ANIMAL",
                        gw_lora,
                        animal=a,
                    )

            ensure_device(
                f"ENERGIA-{prop.id:04d}-01", f"Energia {prop.nome}", "ENERGIA", gw_wifi
            )

            # Regras padrão (se ainda não houver)
            if not RegraAlertaTelemetria.objects.filter(propriedade=prop).exists():
                defaults_rules = [
                    ("Temperatura alta", "temperatura", "threshold_max", 38, "warning"),
                    (
                        "Chuva forte acumulada",
                        "chuva_acum",
                        "threshold_max",
                        60,
                        "critical",
                    ),
                    ("Solo seco", "umidade_solo", "threshold_min", 28, "warning"),
                    ("Vento forte", "vento_rajada", "threshold_max", 18, "warning"),
                    (
                        "Motor superaquecido",
                        "temp_motor",
                        "threshold_max",
                        105,
                        "critical",
                    ),
                    ("Bateria baixa", "bateria", "threshold_min", 20, "warning"),
                    (
                        "pH solo ácido",
                        "ph_solo",
                        "threshold_min",
                        Decimal("5.0"),
                        "info",
                    ),
                ]
                for nome, metric, tipo, ref, sev in defaults_rules:
                    RegraAlertaTelemetria.objects.create(
                        propriedade=prop,
                        nome=nome,
                        metric=metric,
                        tipo=tipo,
                        valor_ref=ref,
                        severidade=sev,
                        janela_min=15,
                    )
                self.stdout.write(f"  Regras padrão criadas ({len(defaults_rules)})")
            else:
                self.stdout.write("  Regras já existem — skip")

            # Fonte externa
            FonteDadosExterna.objects.get_or_create(
                propriedade=prop,
                tipo="OPEN_METEO",
                nome=f"Open-Meteo {prop.nome}",
                defaults={
                    "config": {
                        "lat": float(est.latitude) if est.latitude else -15.79,
                        "lon": float(est.longitude) if est.longitude else -47.88,
                    },
                    "ativo": True,
                },
            )

        self.stdout.write(
            self.style.SUCCESS(f"\nSeed concluído para {len(props)} propriedade(s)")
        )

        if opts["with_data"]:
            self.stdout.write("\nIngerindo 24h reais via Open-Meteo...")
            from django.core.management import call_command

            for prop in props:
                try:
                    call_command(
                        "sync_inmet", propriedade=prop.id, horas=24, source="open-meteo"
                    )
                except Exception as e:
                    self.stderr.write(f"  sync_inmet erro para {prop.nome}: {e}")
            # Também gera dados simulados para SOLO/NIVEL/MAQUINARIO para demo completa
            try:
                self._inject_simulated(props)
            except Exception as e:
                self.stderr.write(f"  inject_sim simulated erro: {e}")

        self.stdout.write(
            self.style.SUCCESS(
                "\nEstrutura de pushes pronta. Exemplos:\n"
                "  curl -X POST http://localhost:8000/api/iot/push/METEO-0001-01/ \\\n"
                "    -H 'X-API-Key: <gateway.api_key>' \\\n"
                "    -H 'Content-Type: application/json' \\\n"
                '    -d \'{"temperatura": 27.3, "umidade_ar": 82, "pressao": 1012, "chuva": 0.2}\'\n'
                "  # TTN webhook: POST /api/iot/mqtt/webhook/  (payload TTN uplink_message)\n"
                "  # Query: GET /api/iot/telemetry/?propriedade=1&metric=temperatura&agg=hour\n"
            )
        )

    def _inject_simulated(self, props):
        import math

        from app.models import Device, TelemetryData

        now = timezone.now()
        for prop in props:
            devs = Device.objects.filter(
                propriedade=prop,
                tipo__in=["SOLO", "NIVEL", "MAQUINARIO", "ENERGIA", "ANIMAL"],
            )
            objs = []
            for dev in devs:
                # gera 24 pontos horários retro
                for h in range(24):
                    ts = now - timedelta(hours=24 - h)
                    if dev.tipo == "SOLO":
                        base = (
                            45
                            + 10 * math.sin(h / 24 * 2 * math.pi)
                            + random.uniform(-5, 5)
                        )
                        objs.append(
                            TelemetryData(
                                device=dev,
                                propriedade=prop,
                                talhao=dev.talhao,
                                metric="umidade_solo",
                                value=round(base, 2),
                                unit="%",
                                timestamp=ts,
                                qualidade="good",
                                raw_payload={"simulated": True},
                            )
                        )
                        objs.append(
                            TelemetryData(
                                device=dev,
                                propriedade=prop,
                                talhao=dev.talhao,
                                metric="temp_solo",
                                value=round(
                                    22
                                    + 3 * math.sin(h / 12 * math.pi)
                                    + random.uniform(-1, 1),
                                    1,
                                ),
                                unit="°C",
                                timestamp=ts,
                                qualidade="good",
                                raw_payload={"simulated": True},
                            )
                        )
                    elif dev.tipo == "NIVEL":
                        objs.append(
                            TelemetryData(
                                device=dev,
                                propriedade=prop,
                                metric="nivel",
                                value=round(
                                    2.1
                                    + 0.3 * math.sin(h / 12 * math.pi)
                                    + random.uniform(-0.1, 0.1),
                                    2,
                                ),
                                unit="m",
                                timestamp=ts,
                                qualidade="good",
                                raw_payload={"simulated": True},
                            )
                        )
                    elif dev.tipo == "MAQUINARIO":
                        if 6 <= ts.hour <= 18:  # só durante dia
                            objs.append(
                                TelemetryData(
                                    device=dev,
                                    propriedade=prop,
                                    metric="horimetro",
                                    value=round(1240 + h * 0.4, 1),
                                    unit="h",
                                    timestamp=ts,
                                    qualidade="good",
                                    raw_payload={"simulated": True},
                                )
                            )
                            objs.append(
                                TelemetryData(
                                    device=dev,
                                    propriedade=prop,
                                    metric="combustivel",
                                    value=round(
                                        max(10, 80 - h * 1.2 + random.uniform(-5, 5)), 1
                                    ),
                                    unit="%",
                                    timestamp=ts,
                                    qualidade="good",
                                    raw_payload={"simulated": True},
                                )
                            )
                    elif dev.tipo == "ENERGIA":
                        rad = (
                            max(0, 900 * math.sin((h - 6) / 12 * math.pi))
                            if 6 <= h <= 18
                            else 0
                        )
                        objs.append(
                            TelemetryData(
                                device=dev,
                                propriedade=prop,
                                metric="potencia",
                                value=round(rad * 0.8, 0),
                                unit="W",
                                timestamp=ts,
                                qualidade="good",
                                raw_payload={"simulated": True},
                            )
                        )
                    elif dev.tipo == "ANIMAL":
                        objs.append(
                            TelemetryData(
                                device=dev,
                                propriedade=prop,
                                metric="passos",
                                value=random.randint(80, 400),
                                unit="",
                                timestamp=ts,
                                qualidade="good",
                                raw_payload={"simulated": True},
                            )
                        )
            if objs:
                TelemetryData.objects.bulk_create(
                    objs, batch_size=500, ignore_conflicts=True
                )
                self.stdout.write(
                    f"  Simulados: {len(objs)} leituras (SOLO/NIVEL/MAQ/ENERGIA/ANIMAL)"
                )
