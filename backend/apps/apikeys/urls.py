from django.urls import path

from apps.apikeys import views

urlpatterns = [
    path("api-keys/", views.ApiKeyListCreateView.as_view(), name="apikey-list"),
    path("api-keys/<int:pk>/revoke/", views.ApiKeyRevokeView.as_view(), name="apikey-revoke"),
    path("usage/summary/", views.UsageSummaryView.as_view(), name="usage-summary"),
]
