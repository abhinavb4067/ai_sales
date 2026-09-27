from rest_framework import generics, permissions

from apps.core.permissions import IsBusinessMember
from apps.tenants.models import BusinessMembership
from apps.tenants.serializers import BusinessMembershipSerializer, BusinessSerializer


class CurrentBusinessView(generics.RetrieveUpdateAPIView):
    """The business resolved from the authenticated user's membership
    (see apps.core.permissions.resolve_business_for_request). There is no
    "get business by id" endpoint on this API surface — a business is only
    ever reachable as "my current business", which structurally prevents
    enumerating/accessing other tenants."""

    serializer_class = BusinessSerializer
    permission_classes = [permissions.IsAuthenticated, IsBusinessMember]

    def get_object(self):
        return self.request.business


class BusinessMembershipListView(generics.ListAPIView):
    serializer_class = BusinessMembershipSerializer
    permission_classes = [permissions.IsAuthenticated, IsBusinessMember]

    def get_queryset(self):
        return (
            BusinessMembership.objects.filter(business=self.request.business)
            .select_related("user")
            .order_by("-created_at")
        )
