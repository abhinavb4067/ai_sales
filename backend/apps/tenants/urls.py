from django.urls import path

from apps.tenants.views import BusinessMembershipListView, CurrentBusinessView

urlpatterns = [
    path("business/me/", CurrentBusinessView.as_view(), name="business-me"),
    path("business/members/", BusinessMembershipListView.as_view(), name="business-members"),
]
