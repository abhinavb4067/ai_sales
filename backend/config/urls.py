from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from apps.core.health import healthcheck

urlpatterns = [
    path("admin/", admin.site.urls),
    path("health/", healthcheck, name="healthcheck"),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/v1/auth/", include("apps.accounts.urls")),
    path("api/v1/", include("apps.tenants.urls")),
    path("api/v1/", include("apps.agents.urls")),
    path("api/v1/", include("apps.knowledge.urls")),
    path("api/v1/", include("apps.conversations.urls")),
    path("api/v1/", include("apps.leads.urls")),
    path("api/v1/", include("apps.appointments.urls")),
    path("api/v1/", include("apps.apikeys.urls")),
    path("api/v1/", include("apps.billing.urls")),
    path("api/v1/", include("apps.integrations.urls")),
    path("api/v1/", include("apps.superadmin.urls")),
    path("api/v1/", include("apps.analytics.urls")),
]
