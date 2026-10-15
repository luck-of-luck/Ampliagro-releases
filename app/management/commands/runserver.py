"""
Override do runserver para dev: `python manage.py runserver` agora sobe em 0.0.0.0:8001
sem precisar digitar o endereço. Evita WinError 10048 na 8000 e ERR_CONNECTION_REFUSED
no 127.0.0.1 filtrado por firewall/proxy. Use `python manage.py runserver 8000` se quiser a porta antiga.
"""

import os

from django.contrib.staticfiles.management.commands.runserver import (
    Command as RunserverCommand,
)


class Command(RunserverCommand):
    # default_addr / default_port são lidos pelo BaseRunserverCommand.handle()
    default_addr = "0.0.0.0"
    default_port = "8001"
    # mantém o help original mas deixa claro
    help = "Starts Ampliagro dev server on 0.0.0.0:8001 (override). Pass [addr:port] to customize."

    def handle(self, *args, **options):
        # Windows + Daphne + reloader = hang (testado: curl 000 com reloader, 200 com --noreload)
        # Força --noreload por padrão no Windows para evitar ERR_TIMED_OUT fantasma
        if os.name == "nt" and options.get("use_reloader") is True:
            # usuário não passou --noreload explicitamente, mas reloader está ativo por padrão -> desativa
            # só mantém reloader se passou --reload ou se não for Windows
            # Detecta se usuário passou --noreload: então use_reloader será False, não entra aqui
            # Se use_reloader é True (default), força False no Windows
            options["use_reloader"] = False
        return super().handle(*args, **options)
