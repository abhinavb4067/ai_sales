from rest_framework import permissions, viewsets
from rest_framework.response import Response

from apps.core.permissions import IsBusinessMember, TenantScopedQuerySetMixin
from apps.webhooks.models import OutboundWebhookDelivery, WebhookSubscription
from apps.webhooks.serializers import OutboundWebhookDeliverySerializer, WebhookSubscriptionSerializer


class WebhookSubscriptionViewSet(TenantScopedQuerySetMixin, viewsets.ModelViewSet):
    serializer_class = WebhookSubscriptionSerializer
    permission_classes = [permissions.IsAuthenticated, IsBusinessMember]
    queryset = WebhookSubscription.objects.all().order_by("-created_at")

    def create(self, request, *args, **kwargs):
        """The signing secret is generated server-side and returned
        exactly once, in this response — never retrievable again (same
        pattern as apps.apikeys.models.ApiKey.generate). The business
        must copy it now; losing it means deleting the subscription and
        creating a new one."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        secret = WebhookSubscription.generate_secret()
        instance = serializer.save(business=request.business, secret=secret)
        data = serializer.data
        data["secret"] = secret
        return Response(data, status=201)


class OutboundWebhookDeliveryListView(TenantScopedQuerySetMixin, viewsets.ReadOnlyModelViewSet):
    serializer_class = OutboundWebhookDeliverySerializer
    permission_classes = [permissions.IsAuthenticated, IsBusinessMember]
    queryset = OutboundWebhookDelivery.objects.all().select_related("subscription")
    filterset_fields = ["subscription", "status", "event_type"]
