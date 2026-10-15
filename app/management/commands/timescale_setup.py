from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Cria hypertable TimescaleDB se disponível (ignora em SQLite)"

    def handle(self, *args, **opts):
        from app.iot.timescale import ensure_hypertable, is_timescale

        if not is_timescale():
            self.stdout.write(
                self.style.WARNING(
                    "Timescale não detectado (SQLite ou PG sem extensão) — skip. Índices normais já garantem performance até ~10M linhas."
                )
            )
            self.stdout.write(
                "Para ativar Timescale: docker compose -f docker-compose.telemetry.yml up -d timescaledb e ajuste DATABASES para porta 5433"
            )
            return
        msg = ensure_hypertable()
        self.stdout.write(self.style.SUCCESS(msg))
