from urllib.parse import parse_qs
from typing import Callable, Awaitable

from channels.middleware import BaseMiddleware
from channels.auth import AuthMiddlewareStack
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.authentication import JWTAuthentication

User = get_user_model()


@database_sync_to_async
def _get_user_from_token(token: str):
    """
    Validate the JWT using DRF SimpleJWT and return the associated user.
    Raises if token is invalid.
    """
    auth = JWTAuthentication()
    validated = auth.get_validated_token(token)
    return auth.get_user(validated)


class JWTAuthMiddleware(BaseMiddleware):
    """
    Channels middleware that authenticates a user based on a JWT token provided
    as a query string parameter named `token` on the WebSocket URL.

    Example: ws://host/ws/trading/?token=<ACCESS_TOKEN>
    """

    async def __call__(self, scope, receive, send):
        query_string = scope.get('query_string', b'').decode()
        params = parse_qs(query_string)
        token = None
        if 'token' in params and params['token']:
            token = params['token'][0]

        if token:
            try:
                user = await _get_user_from_token(token)
                scope['user'] = user
            except Exception:
                # Invalid token -> anonymous user; fall back to session auth chain if present
                scope['user'] = AnonymousUser()
        # If no token, leave scope['user'] as provided by inner stack (session auth) or Anonymous
        return await super().__call__(scope, receive, send)


def JWTAuthMiddlewareStack(inner: Callable[..., Awaitable]):
    """
    Compose with default session-based AuthMiddlewareStack first, then apply JWT
    so JWT can override Anonymous/session user when a valid token is provided.
    Order matters: outermost runs last.
    """
    return AuthMiddlewareStack(JWTAuthMiddleware(inner))
