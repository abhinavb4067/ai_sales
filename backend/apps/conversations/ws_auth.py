from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import AccessToken


@database_sync_to_async
def _user_from_access_token(raw_token: str):
    from apps.accounts.models import User

    try:
        validated = AccessToken(raw_token)
        return User.objects.get(id=validated["user_id"])
    except (TokenError, InvalidToken, User.DoesNotExist):
        return AnonymousUser()


class JWTAuthMiddleware(BaseMiddleware):
    """Channels has no concept of our JWT access tokens out of the box —
    the dashboard is JWT-authenticated, not session-authenticated, so the
    stock channels.auth.AuthMiddlewareStack (which reads Django sessions)
    doesn't apply. A WebSocket handshake can't carry a normal Authorization
    header from browser JS, so the token travels as a `?token=` query
    param instead — same access token already held in memory by the
    dashboard's apiClient, over wss:// in production.
    """

    async def __call__(self, scope, receive, send):
        query_string = scope.get("query_string", b"").decode()
        token = parse_qs(query_string).get("token", [None])[0]
        scope["user"] = await _user_from_access_token(token) if token else AnonymousUser()
        return await super().__call__(scope, receive, send)
