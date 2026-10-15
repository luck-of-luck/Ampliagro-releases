"""
Management command: verificar_offline
Job periódico do motor de automação: marca devices/gateways offline e cria
alertas (regras tipo offline). Chamado pelo alertas_diario.bat.
Uso: python manage.py verificar_offline
"""

from django.core.management.base import BaseCommand

from app.iot.alert_engine import check_offline_devices


class Command(BaseCommand):
    help = "Verifica devices/gateways offline e gera alertas"

    def handle(self, *args, **options):
        check_offline_devices()
        self.stdout.write(self.style.SUCCESS("verificação offline concluída"))
