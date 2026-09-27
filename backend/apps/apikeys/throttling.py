from rest_framework.throttling import ScopedRateThrottle


class ApiKeyRateThrottle(ScopedRateThrottle):
    """Scopes the public Chat API rate limit per API key rather than per IP
    — the default ScopedRateThrottle would bucket every anonymous caller
    together since request.user is always AnonymousUser here."""

    scope = "public_api"

    def get_cache_key(self, request, view):
        api_key = getattr(request, "api_key", None)
        if api_key is None:
            return None
        return self.cache_format % {"scope": self.scope, "ident": api_key.id}


class WidgetRateThrottle(ScopedRateThrottle):
    """Website widget has no secret to key on, so falls back to IP — this
    is intentionally looser/noisier than the API-key throttle and exists
    mainly to blunt abuse, not to enforce per-tenant plan limits."""

    scope = "widget"
