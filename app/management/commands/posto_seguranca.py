"""`manage.py posto_seguranca` — o texto que o operador precisa de ler.

Porque um comando e nao so um modulo
===================================

`app/services/posto_seguranca.py` mede. Este comando imprime. A razao de os
separar e' a mesma de `check_health.py`: quem instala nao vai abrir um modulo
Python para descobrir em que estado esta o TLS da sua instalacao — vai correr
um comando e ler a saida.

Sai com codigo 1 quando ha alguma protecao desligada, para que um script de
instalacao possa travar ali. Com `--so-falhas`, o comando cala-se quando
esta tudo em ordem: um relatorio vazio e' mais facil de ler do que seis
linhas a dizer que tudo esta bem.
"""

from django.conf import settings
from django.core.management.base import BaseCommand

from app.services.posto_seguranca import REGRAS, lacunas, relatorio


class Command(BaseCommand):
    help = "Diz o que segura a HTTPS nesta instalacao, e o que observar."

    def add_arguments(self, parser):
        parser.add_argument(
            "--so-falhas",
            action="store_true",
            help="nao imprime nada se estiver tudo ligado",
        )
        parser.add_argument(
            "--json",
            action="store_true",
            help="saida legivel por maquina",
        )

    def handle(self, *args, **options):
        faltam = lacunas(settings)

        if options["json"]:
            import json

            self.stdout.write(
                json.dumps(
                    {
                        "total": len(REGRAS),
                        "desligadas": [
                            {
                                "chave": a.chave,
                                "valor": a.valor,
                                "significa": a.significa,
                                "observar": a.observar,
                                "definida_no_ambiente": a.definida_no_ambiente,
                            }
                            for a in faltam
                        ],
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return

        if not faltam and options["so_falhas"]:
            return

        self.stdout.write(relatorio(settings))

        if faltam:
            raise SystemExit(1)
