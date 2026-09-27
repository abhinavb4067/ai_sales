from django.contrib.auth.models import AnonymousUser
from django.utils import timezone
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

from apps.apikeys.models import ApiKey


class ApiKeyAuthentication(BaseAuthentication):
    """Authenticates public Chat API requests via a business-issued secret
    key — `Authorization: Bearer sk_live_...` or `X-API-Key: sk_live_...`.
    Sets request.business (never trusted from client input) and
    request.api_key on success, mirroring how IsBusinessMember sets
    request.business for JWT-authenticated dashboard requests.
    """

    keyword = "Bearer"

    def authenticate(self, request):
        raw_key = self._extract_key(request)
        if not raw_key:
            return None

        try:
            api_key = ApiKey.objects.select_related("business").get(
                hashed_key=ApiKey.hash_key(raw_key), status=ApiKey.Status.ACTIVE
            )
        except ApiKey.DoesNotExist:
            raise AuthenticationFailed("Invalid or revoked API key.")

        api_key.last_used_at = timezone.now()
        api_key.save(update_fields=["last_used_at"])

        request.business = api_key.business
        request.api_key = api_key
        return (AnonymousUser(), api_key)

    def _extract_key(self, request):
        header = request.headers.get("Authorization", "")
        if header.startswith(f"{self.keyword} "):
            return header[len(self.keyword) + 1 :].strip()
        return request.headers.get("X-API-Key")
