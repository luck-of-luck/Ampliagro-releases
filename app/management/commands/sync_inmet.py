"""
Sincroniza dados reais do INMET / Open-Meteo / NASA POWER para uma propriedade.

Uso:
  python manage.py sync_inmet --propriedade 1 --horas 24
  python manage.py sync_inmet --all --horas 72 --source open-meteo

Fontes:
  - INMET: https://apitempo.inmet.gov.br/ (requer cadastro; fallback para Open-Meteo)
  - Open-Meteo: https://open-meteo.com (sem chave, usado como fallback e preferido)
  - NASA POWER: https://power.larc.nasa.gov/

Cria/faz upsert de FonteDadosExterna e ingere como TelemetryData em um Device virtual tipo METEO.
"""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = "Sincroniza dados climáticos reais (INMET/Open-Meteo) para telemetria"

    def add_arguments(self, parser):
        parser.add_argument("--propriedade", type=int, default=None)
        parser.add_argument("--all", action="store_true")
        parser.add_argument(
            "--horas", type=int, default=24, help="Horas para buscar (passado)"
        )
        parser.add_argument(
            "--source", choices=["open-meteo", "inmet", "nasa"], default="open-meteo"
        )

    def handle(self, *args, **opts):
        import requests

        from app.models import (
            Device,
            EstacaoMeteo,
            FonteDadosExterna,
            Gateway,
            Propriedade,
            TelemetryData,
        )

        horas = opts["horas"]
        source = opts["source"]

        if opts["all"]:
            props = Propriedade.objects.all()
        elif opts["propriedade"]:
            props = Propriedade.objects.filter(id=opts["propriedade"])
        else:
            self.stderr.write("Use --propriedade <id> ou --all")
            return

        for prop in props:
            # pega coordenadas: tenta gateway, senão propriedade cidade via geocoding fallback, senão centro BR
            lat, lon = None, None
            gw = Gateway.objects.filter(propriedade=prop).first()
            est = EstacaoMeteo.objects.filter(propriedade=prop).first()
            if est and est.latitude and est.longitude:
                lat, lon = float(est.latitude), float(est.longitude)
            elif gw and gw.latitude and gw.longitude:
                lat, lon = float(gw.latitude), float(gw.longitude)
            else:
                # fallback: tenta geocoding da cidade (requer httpx); senão usa Brasília
                lat, lon = -15.7939, -47.8828
                self.stdout.write(
                    f"Propriedade {prop.nome}: sem coords, usando fallback Brasília"
                )

            self.stdout.write(
                f"[{prop.nome}] sync {source} lat={lat} lon={lon} horas={horas}"
            )

            # garante Device virtual para dados externos
            gw_virt, _ = Gateway.objects.get_or_create(
                propriedade=prop,
                gateway_eui=f"VIRT-{prop.id:04d}",
                defaults={
                    "nome": "Virtual — Dados Externos",
                    "tipo": "WIFI",
                    "status": "online",
                },
            )
            dev_virt, _ = Device.objects.get_or_create(
                device_eui=f"VIRT-METEO-{prop.id:04d}",
                defaults={
                    "propriedade": prop,
                    "gateway": gw_virt,
                    "nome": "Meteo Virtual (INMET/Open-Meteo)",
                    "tipo": "METEO",
                    "protocolo": "HTTP",
                },
            )

            # Busca Open-Meteo (funciona sempre, sem chave)
            if source in ("open-meteo", "inmet"):
                try:
                    # Open-Meteo forecast + histórico horário
                    url = "https://api.open-meteo.com/v1/forecast"
                    params = {
                        "latitude": lat,
                        "longitude": lon,
                        "hourly": "temperature_2m,relative_humidity_2m,pressure_msl,precipitation,wind_speed_10m,wind_direction_10m,shortwave_radiation",
                        "past_hours": horas,
                        "forecast_hours": 0,
                        "timezone": "America/Sao_Paulo",
                    }
                    r = requests.get(url, params=params, timeout=30)
                    r.raise_for_status()
                    data = r.json()
                    hourly = data.get("hourly", {})
                    times = hourly.get("time", [])
                    # mapeia chaves Open-Meteo -> metrics internas
                    mapping = {
                        "temperature_2m": "temperatura",
                        "relative_humidity_2m": "umidade_ar",
                        "pressure_msl": "pressao",
                        "precipitation": "chuva",
                        "wind_speed_10m": "vento_vel",
                        "wind_direction_10m": "vento_dir",
                        "shortwave_radiation": "radiacao",
                    }
                    objs = []
                    for i, t in enumerate(times):
                        ts = timezone.datetime.fromisoformat(t)
                        if ts.tzinfo is None:
                            ts = timezone.make_aware(ts)
                        for om_key, metric in mapping.items():
                            vals = hourly.get(om_key, [])
                            if i < len(vals) and vals[i] is not None:
                                objs.append(
                                    TelemetryData(
                                        device=dev_virt,
                                        propriedade=prop,
                                        talhao=None,
                                        metric=metric,
                                        value=vals[i],
                                        unit="",
                                        timestamp=ts,
                                        qualidade="good",
                                        raw_payload={
                                            "source": "open-meteo",
                                            "open_meteo_key": om_key,
                                        },
                                    )
                                )
                    if objs:
                        TelemetryData.objects.bulk_create(
                            objs, batch_size=500, ignore_conflicts=True
                        )
                        self.stdout.write(
                            f"  -> {len(objs)} leituras ingeridas (Open-Meteo)"
                        )
                        # Atualiza FonteDadosExterna — SO aqui dentro.
                        #
                        # Este `update_or_create` estava FORA do `if objs`, e o
                        # resultado era uma Fonte marcada como sincronizada sem
                        # uma unica leitura: a resposta foi 200,
                        # `raise_for_status` nao disparou, e `hourly` veio sem
                        # `time` (ou so com `None`). A Fonte ficava com
                        # `ultimo_sync` fresco e `ativo=True` — e quem a
                        # consulta depois (a IA, pelo servico canonico de
                        # fontes) le "ja consultei, nao ha nada", que nao e' o
                        # mesmo que "nunca perguntei".
                        #
                        # Trava: tests/test_sync_inmet_ingestao.py::
                        #       test_resposta_vazia_nao_marca_a_fonte_como_sincronizada
                        FonteDadosExterna.objects.update_or_create(
                            propriedade=prop,
                            tipo="OPEN_METEO",
                            nome=f"Open-Meteo {prop.nome}",
                            defaults={
                                "config": {"lat": lat, "lon": lon, "horas": horas},
                                "ultimo_sync": timezone.now(),
                                "ativo": True,
                            },
                        )
                    else:
                        self.stderr.write(
                            f"  {prop.nome}: Open-Meteo respondeu sem leituras — "
                            "fonte NAO marcada como sincronizada"
                        )
                except Exception as e:
                    self.stderr.write(f"  Open-Meteo erro: {e}")

            if source == "nasa":
                try:
                    # NASA POWER daily
                    from datetime import date

                    end = date.today()
                    start = end - timedelta(days=7)
                    url = "https://power.larc.nasa.gov/api/temporal/daily/point"
                    params = {
                        "parameters": "T2M,RH2M,PRECTOTCORR,WS2M,ALLSKY_SFC_SW_DWN",
                        "community": "AG",
                        "longitude": lon,
                        "latitude": lat,
                        "start": start.strftime("%Y%m%d"),
                        "end": end.strftime("%Y%m%d"),
                        "format": "JSON",
                    }
                    r = requests.get(url, params=params, timeout=30)
                    r.raise_for_status()
                    j = r.json()
                    props_nasa = j.get("properties", {}).get("parameter", {})
                    # converte para TelemetryData diário
                    self.stdout.write(f"  NASA POWER: {list(props_nasa.keys())}")
                except Exception as e:
                    self.stderr.write(f"  NASA POWER erro: {e}")

        self.stdout.write("sync_inmet concluído")
