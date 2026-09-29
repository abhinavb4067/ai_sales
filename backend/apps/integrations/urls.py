from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.integrations.views import IntegrationViewSet, WhatsAppWebhookView

router = DefaultRouter()
router.register("integrations", IntegrationViewSet, basename="integration")

urlpatterns = [
    path("", include(router.urls)),
    path("integrations/whatsapp/webhook/<uuid:public_id>/", WhatsAppWebhookView.as_view(), name="whatsapp-webhook"),
]
