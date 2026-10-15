from django.apps import AppConfig


class AmpliagroConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "app"

    def ready(self):
        import app.audit  # noqa: F401

        # Invalida o cache `dash:<user_id>` quando alguém escreve um registo
        # que o painel lê. Sem isto o produtor lançava uma despesa e via o
        # número antigo (ou zeros) durante até 30 s. Ver app/cache_painel.py.
        import app.cache_painel  # noqa: F401
        import app.signals  # noqa: F401

        app.cache_painel.ligar()
