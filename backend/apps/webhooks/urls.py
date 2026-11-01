from rest_framework.routers import DefaultRouter

from apps.webhooks.views import OutboundWebhookDeliveryListView, WebhookSubscriptionViewSet

router = DefaultRouter()
router.register("webhook-subscriptions", WebhookSubscriptionViewSet, basename="webhook-subscription")
router.register("webhook-deliveries", OutboundWebhookDeliveryListView, basename="webhook-delivery")

urlpatterns = router.urls
