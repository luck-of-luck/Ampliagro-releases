import os

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application
from django.urls import path

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.prod")

# Import the WebSocket consumer
from app.consumers import DashboardConsumer

application = ProtocolTypeRouter(
    {
        "http": get_asgi_application(),
        "websocket": AuthMiddlewareStack(
            URLRouter(
                [
                    path("ws/dashboard/", DashboardConsumer.as_asgi()),
                ]
            )
        ),
    }
)

from app.ia.agendador_local import iniciar

iniciar()
