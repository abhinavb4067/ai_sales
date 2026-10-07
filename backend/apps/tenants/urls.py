from django.urls import path

from apps.tenants.views import (
    AcceptInviteView,
    BusinessMembershipListView,
    ChangeMemberRoleView,
    CurrentBusinessView,
    InviteMemberView,
    MyInvitesView,
    RevokeMemberView,
)

urlpatterns = [
    path("business/me/", CurrentBusinessView.as_view(), name="business-me"),
    path("business/members/", BusinessMembershipListView.as_view(), name="business-members"),
    path("business/members/invite/", InviteMemberView.as_view(), name="business-member-invite"),
    path("business/members/<int:pk>/revoke/", RevokeMemberView.as_view(), name="business-member-revoke"),
    path("business/members/<int:pk>/role/", ChangeMemberRoleView.as_view(), name="business-member-role"),
    path("team/my-invites/", MyInvitesView.as_view(), name="my-invites"),
    path("team/invites/<int:pk>/accept/", AcceptInviteView.as_view(), name="accept-invite"),
]
