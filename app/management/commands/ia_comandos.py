"""Expira comandos IoT travados: python manage.py ia_comandos [--timeout-min 30]."""

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Marca como erro os comandos pendente/enviado expirados (gateway offline)"

    def add_arguments(self, parser):
        parser.add_argument("--timeout-min", type=int, default=None)

    def handle(self, *args, **options):
        from app.ia.comandos import expirar_comandos

        n = expirar_comandos(timeout_min=options["timeout_min"])
        self.stdout.write(self.style.SUCCESS(f"{n} comando(s) expirado(s)"))
