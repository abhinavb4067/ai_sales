from django.urls import path

from apps.superadmin.views import (
    SuperAdminAgentListView,
    SuperAdminBusinessListView,
    SuperAdminBusinessReactivateView,
    SuperAdminBusinessSuspendView,
    SuperAdminPlatformHealthView,
)

urlpatterns = [
    path("admin/tenants/", SuperAdminBusinessListView.as_view(), name="superadmin-tenants"),
    path("admin/tenants/<int:pk>/suspend/", SuperAdminBusinessSuspendView.as_view(), name="superadmin-tenant-suspend"),
    path(
        "admin/tenants/<int:pk>/reactivate/",
        SuperAdminBusinessReactivateView.as_view(),
        name="superadmin-tenant-reactivate",
    ),
    path("admin/agents/", SuperAdminAgentListView.as_view(), name="superadmin-agents"),
    path("admin/platform-health/", SuperAdminPlatformHealthView.as_view(), name="superadmin-platform-health"),
]
