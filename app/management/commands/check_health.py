from django.core.management.base import BaseCommand

from app.services.health_alerts import send_health_alert
from app.views.health_dashboard import (
    _check_cache,
    _check_db,
    _check_disk,
    _check_migrations,
)


class Command(BaseCommand):
    help = "Verifica healthz (db, cache, disk, migrations) e opcionalmente envia alerta Slack/Telegram"

    def add_arguments(self, parser):
        parser.add_argument(
            "--alert",
            action="store_true",
            help="Envia alerta se status != ok (requer webhook env)",
        )
        parser.add_argument("--json", action="store_true", help="Sai em JSON puro")

    def handle(self, *args, **options):
        checks = {
            "db": _check_db(),
            "cache": _check_cache(),
            "disk": _check_disk(),
            "migrations": _check_migrations(),
        }
        statuses = [v.get("status") for v in checks.values()]
        if "fail" in statuses:
            status = "fail"
        elif "warn" in statuses:
            status = "warn"
        else:
            status = "ok"

        if options["json"]:
            import json

            self.stdout.write(
                json.dumps(
                    {"status": status, "checks": checks}, indent=2, ensure_ascii=False
                )
            )
        else:
            for name, chk in checks.items():
                self.stdout.write(f"{name}: {chk}")
            self.stdout.write(
                self.style.SUCCESS(f"status: {status}")
                if status == "ok"
                else self.style.WARNING(f"status: {status}")
            )

        if options["alert"] and status != "ok":
            result = send_health_alert(checks, status)
            self.stdout.write(f"alert: {result}")

        # exit code 2 se fail (para cron/celery)
        if status == "fail":
            raise SystemExit(2)
