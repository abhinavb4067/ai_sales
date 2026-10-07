from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.core.testing import authenticated_client, create_business_with_owner
from apps.tenants.models import BusinessMembership


class TeamInviteTests(APITestCase):
    def setUp(self):
        self.owner, self.business = create_business_with_owner()
        self.owner_client = authenticated_client(self.owner)
        self.invitee = User.objects.create_user(email="invitee@example.com", password="StrongPass123!", name="Invitee")

    def test_invite_creates_pending_membership(self):
        response = self.owner_client.post(
            "/api/v1/business/members/invite/",
            {"email": "invitee@example.com", "role": "sales"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data["status"], BusinessMembership.Status.PENDING)
        self.assertEqual(response.data["role"], "sales")

        membership = BusinessMembership.objects.get(user=self.invitee, business=self.business)
        self.assertEqual(membership.status, BusinessMembership.Status.PENDING)
        self.assertEqual(membership.invited_by_id, self.owner.id)

    def test_invite_unregistered_email_returns_404(self):
        response = self.owner_client.post(
            "/api/v1/business/members/invite/",
            {"email": "nobody@example.com", "role": "sales"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data["error"]["code"], "USER_NOT_REGISTERED")

    def test_invite_cannot_assign_owner_role(self):
        response = self.owner_client.post(
            "/api/v1/business/members/invite/",
            {"email": "invitee@example.com", "role": "owner"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_non_admin_cannot_invite(self):
        viewer = User.objects.create_user(email="viewer@example.com", password="StrongPass123!", name="Viewer")
        BusinessMembership.objects.create(
            user=viewer, business=self.business, role=BusinessMembership.Role.VIEWER,
            status=BusinessMembership.Status.ACTIVE,
        )
        viewer_client = authenticated_client(viewer)

        response = viewer_client.post(
            "/api/v1/business/members/invite/",
            {"email": "invitee@example.com", "role": "sales"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_invite_blocked_once_plan_limit_reached(self):
        # Starter plan allows max_team_members=2: the owner counts as seat 1.
        second = User.objects.create_user(email="second@example.com", password="StrongPass123!", name="Second")
        BusinessMembership.objects.create(
            user=second, business=self.business, role=BusinessMembership.Role.SALES,
            status=BusinessMembership.Status.ACTIVE,
        )

        response = self.owner_client.post(
            "/api/v1/business/members/invite/",
            {"email": "invitee@example.com", "role": "sales"},
            format="json",
        )
        self.assertEqual(response.status_code, 402)
        self.assertEqual(response.data["error"]["code"], "PLAN_LIMIT_REACHED")

    def test_inviting_same_user_twice_while_pending_is_rejected(self):
        self.owner_client.post(
            "/api/v1/business/members/invite/", {"email": "invitee@example.com", "role": "sales"}, format="json"
        )
        response = self.owner_client.post(
            "/api/v1/business/members/invite/", {"email": "invitee@example.com", "role": "support"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["error"]["code"], "ALREADY_A_MEMBER")

    def test_reinviting_a_revoked_member_reuses_the_row(self):
        invite = self.owner_client.post(
            "/api/v1/business/members/invite/", {"email": "invitee@example.com", "role": "sales"}, format="json"
        ).data
        self.owner_client.post(f"/api/v1/business/members/{invite['id']}/revoke/")

        response = self.owner_client.post(
            "/api/v1/business/members/invite/", {"email": "invitee@example.com", "role": "support"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["id"], invite["id"])
        self.assertEqual(response.data["role"], "support")
        self.assertEqual(response.data["status"], BusinessMembership.Status.PENDING)


class AcceptInviteTests(APITestCase):
    def setUp(self):
        self.owner, self.business = create_business_with_owner()
        self.owner_client = authenticated_client(self.owner)
        self.invitee = User.objects.create_user(email="invitee@example.com", password="StrongPass123!", name="Invitee")
        self.invite = self.owner_client.post(
            "/api/v1/business/members/invite/", {"email": "invitee@example.com", "role": "sales"}, format="json"
        ).data

    def test_invitee_sees_pending_invite_in_my_invites(self):
        client = authenticated_client(self.invitee)
        response = client.get("/api/v1/team/my-invites/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [m["id"] for m in response.data.get("results", response.data)]
        self.assertIn(self.invite["id"], ids)

    def test_invitee_can_accept_their_own_invite(self):
        client = authenticated_client(self.invitee)
        response = client.post(f"/api/v1/team/invites/{self.invite['id']}/accept/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], BusinessMembership.Status.ACTIVE)

    def test_accepted_invitee_can_now_access_the_business(self):
        client = authenticated_client(self.invitee)
        client.post(f"/api/v1/team/invites/{self.invite['id']}/accept/")

        response = client.get("/api/v1/business/me/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], self.business.id)

    def test_pending_invitee_cannot_access_business_before_accepting(self):
        client = authenticated_client(self.invitee)
        response = client.get("/api/v1/business/me/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_other_user_cannot_accept_someone_elses_invite(self):
        stranger = User.objects.create_user(email="stranger@example.com", password="StrongPass123!", name="Stranger")
        client = authenticated_client(stranger)
        response = client.post(f"/api/v1/team/invites/{self.invite['id']}/accept/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class RevokeAndRoleChangeTests(APITestCase):
    def setUp(self):
        self.owner, self.business = create_business_with_owner()
        self.owner_client = authenticated_client(self.owner)
        self.member_user = User.objects.create_user(email="member@example.com", password="StrongPass123!", name="Member")
        self.membership = BusinessMembership.objects.create(
            user=self.member_user, business=self.business, role=BusinessMembership.Role.SALES,
            status=BusinessMembership.Status.ACTIVE,
        )

    def test_revoke_member(self):
        response = self.owner_client.post(f"/api/v1/business/members/{self.membership.id}/revoke/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.membership.refresh_from_db()
        self.assertEqual(self.membership.status, BusinessMembership.Status.REVOKED)

    def test_cannot_revoke_the_owner(self):
        owner_membership = BusinessMembership.objects.get(user=self.owner, business=self.business)
        response = self.owner_client.post(f"/api/v1/business/members/{owner_membership.id}/revoke/")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["error"]["code"], "CANNOT_REVOKE_OWNER")

    def test_change_member_role(self):
        response = self.owner_client.post(
            f"/api/v1/business/members/{self.membership.id}/role/", {"role": "admin"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.membership.refresh_from_db()
        self.assertEqual(self.membership.role, BusinessMembership.Role.ADMIN)

    def test_cannot_change_owner_role(self):
        owner_membership = BusinessMembership.objects.get(user=self.owner, business=self.business)
        response = self.owner_client.post(
            f"/api/v1/business/members/{owner_membership.id}/role/", {"role": "viewer"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_revoke_scoped_to_own_business(self):
        _, other_business = create_business_with_owner(business_name="Other Co", email="other@example.com")
        other_member = User.objects.create_user(email="othermember@example.com", password="StrongPass123!", name="OM")
        other_membership = BusinessMembership.objects.create(
            user=other_member, business=other_business, role=BusinessMembership.Role.SALES,
            status=BusinessMembership.Status.ACTIVE,
        )

        response = self.owner_client.post(f"/api/v1/business/members/{other_membership.id}/revoke/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
