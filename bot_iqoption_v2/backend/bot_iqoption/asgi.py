"""
ASGI config for bot_iqoption project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/howto/deployment/asgi/
"""

import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bot_iqoption.settings')

from django.core.asgi import get_asgi_application

# Initialize Django first so apps are loaded before importing routing that touches models
django_asgi_app = get_asgi_application()

from channels.routing import ProtocolTypeRouter, URLRouter
from .jwt_auth import JWTAuthMiddlewareStack
from trading import routing as trading_routing

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    # First try JWT via query string token, then fall back to session auth
    "websocket": JWTAuthMiddlewareStack(
        URLRouter(trading_routing.websocket_urlpatterns)
    ),
})
