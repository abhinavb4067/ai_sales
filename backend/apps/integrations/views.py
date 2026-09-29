import json

from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import permissions, viewsets
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import IsBusinessMember, TenantScopedQuerySetMixin
from apps.integrations.models import Integration
from apps.integrations.serializers import IntegrationSerializer
from apps.integrations.services import handle_inbound_webhook


class IntegrationViewSet(TenantScopedQuerySetMixin, viewsets.ModelViewSet):
    serializer_class = IntegrationSerializer
    permission_classes = [permissions.IsAuthenticated, IsBusinessMember]
    queryset = Integration.objects.all().order_by("-created_at")


class WhatsAppWebhookView(APIView):
    """Public — secured by Meta's verify-token handshake (GET) and a
    signature check on every message payload (POST), never by a JWT or
    API key. public_id is the only thing standing between "this is our
    endpoint" and an arbitrary integration; parse_webhook_payload/
    verify_webhook_signature enforce the rest."""

    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request, public_id):
        integration = get_object_or_404(Integration, public_id=public_id, provider=Integration.Provider.WHATSAPP)
        credentials = json.loads(integration.credentials or "{}")

        if (
            request.query_params.get("hub.mode") == "subscribe"
            and request.query_params.get("hub.verify_token") == credentials.get("verify_token")
        ):
            return HttpResponse(request.query_params.get("hub.challenge", ""), content_type="text/plain")
        return Response(status=403)

    def post(self, request, public_id):
        integration = get_object_or_404(Integration, public_id=public_id, provider=Integration.Provider.WHATSAPP)
        handle_inbound_webhook(integration=integration, raw_payload=request.body, headers=request.headers)
        # Always ack with 200 — Meta retries aggressively on non-2xx, and
        # processing failures are captured in WebhookDelivery instead.
        return Response(status=200)
