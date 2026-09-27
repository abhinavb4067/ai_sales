from rest_framework.permissions import BasePermission


class HasApiKey(BasePermission):
    """Companion to ApiKeyAuthentication — confirms authentication actually
    resolved an api_key (rather than falling through to no credentials)."""

    message = "A valid API key is required."

    def has_permission(self, request, view):
        return getattr(request, "api_key", None) is not None
