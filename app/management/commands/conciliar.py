"""
Management command: conciliar
Casa extrato bancário com lançamentos (baixa automática).
Uso: python manage.py conciliar [--conta ID] [--dias 3] [--dry-run]
"""

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from app.models import ContaBancaria
from app.services.conciliacao import conciliar_conta


class Command(BaseCommand):
    help = "Concilia extrato x lançamentos (valor exato, janela de dias)"

    def add_arguments(self, parser):
        parser.add_argument("--conta", type=int, default=None)
        parser.add_argument("--dias", type=int, default=3)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        qs = ContaBancaria.objects.filter(ativa=True)
        if options["conta"]:
            qs = qs.filter(id=options["conta"])
        total = 0
        for conta in qs:
            pares = conciliar_conta(
                conta, dias=options["dias"], dry_run=options["dry_run"]
            )
            for mov, lanc in pares:
                self.stdout.write(
                    f"  {conta.banco} {mov.data}: R$ {mov.valor} -> lançamento #{lanc.id}"
                )
                total += 1
        acao = "simulados" if options["dry_run"] else "conciliados"
        self.stdout.write(self.style.SUCCESS(f"{total} movimentos {acao}"))
