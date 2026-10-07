from rest_framework import generics, permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import HasRole, IsBusinessMember
from apps.tenants.models import BusinessMembership
from apps.tenants.serializers import (
    BusinessMembershipSerializer,
    BusinessSerializer,
    ChangeMemberRoleSerializer,
    InviteMemberSerializer,
)
from apps.tenants.services import accept_invite, change_member_role, invite_member, revoke_member


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
            .select_related("user", "business")
            .order_by("-created_at")
        )


class InviteMemberView(APIView):
    """Only works for an email that's already registered — there's no
    invite-by-email-for-a-not-yet-existing-account flow yet (that would
    need a nullable user FK + an invite-token email, deliberately out of
    scope for now; the error message tells the inviter to ask the person
    to register first)."""

    permission_classes = [permissions.IsAuthenticated, IsBusinessMember, HasRole.roles("owner", "admin")]

    def post(self, request):
        serializer = InviteMemberSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        membership = invite_member(
            business=request.business,
            email=serializer.validated_data["email"],
            role=serializer.validated_data["role"],
            invited_by=request.user,
        )
        return Response(BusinessMembershipSerializer(membership).data, status=201)


class MyInvitesView(generics.ListAPIView):
    """Pending invites for the authenticated user, across every business
    — deliberately NOT business-scoped (IsBusinessMember would reject the
    request, since the user has no ACTIVE membership on the inviting
    business yet; that's exactly the state this endpoint exists to let
    them discover and accept)."""

    serializer_class = BusinessMembershipSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return (
            BusinessMembership.objects.filter(user=self.request.user, status=BusinessMembership.Status.PENDING)
            .select_related("user", "business")
            .order_by("-created_at")
        )


class AcceptInviteView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        membership = accept_invite(user=request.user, membership_id=pk)
        return Response(BusinessMembershipSerializer(membership).data)


class RevokeMemberView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsBusinessMember, HasRole.roles("owner", "admin")]

    def post(self, request, pk):
        membership = revoke_member(business=request.business, membership_id=pk)
        return Response(BusinessMembershipSerializer(membership).data)


class ChangeMemberRoleView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsBusinessMember, HasRole.roles("owner", "admin")]

    def post(self, request, pk):
        serializer = ChangeMemberRoleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        membership = change_member_role(
            business=request.business, membership_id=pk, new_role=serializer.validated_data["role"]
        )
        return Response(BusinessMembershipSerializer(membership).data)
