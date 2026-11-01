from rest_framework import status
from rest_framework.test import APITestCase

from apps.agents.models import Agent
from apps.billing.models import Subscription
from apps.core.testing import authenticated_client, create_business_with_owner


class SuperAdminAccessTests(APITestCase):
    def setUp(self):
        self.owner, self.business = create_business_with_owner()
        self.staff_user, _ = create_business_with_owner(email="staff@example.com")
        self.staff_user.is_staff = True
        self.staff_user.save(update_fields=["is_staff"])

    def test_regular_business_owner_cannot_access_superadmin(self):
        client = authenticated_client(self.owner)
        response = client.get("/api/v1/admin/tenants/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_staff_user_can_list_tenants(self):
        client = authenticated_client(self.staff_user)
        response = client.get("/api/v1/admin/tenants/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        business_ids = {b["id"] for b in response.data["results"]}
        self.assertIn(self.business.id, business_ids)

    def test_unauthenticated_request_rejected(self):
        response = self.client.get("/api/v1/admin/tenants/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class SuperAdminSuspendTests(APITestCase):
    def setUp(self):
        self.owner, self.business = create_business_with_owner()
        self.staff_user, _ = create_business_with_owner(email="staff@example.com")
        self.staff_user.is_staff = True
        self.staff_user.save(update_fields=["is_staff"])
        self.client_admin = authenticated_client(self.staff_user)

    def test_suspend_and_reactivate_business(self):
        response = self.client_admin.post(f"/api/v1/admin/tenants/{self.business.id}/suspend/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.business.subscription.refresh_from_db()
        self.assertEqual(self.business.subscription.status, Subscription.Status.SUSPENDED)

        response = self.client_admin.post(f"/api/v1/admin/tenants/{self.business.id}/reactivate/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.business.subscription.refresh_from_db()
        self.assertEqual(self.business.subscription.status, Subscription.Status.ACTIVE)

    def test_suspended_business_is_blocked_from_chat(self):
        from apps.billing.services import enforce_subscription_and_limits
        from apps.core.exceptions import APIError

        self.client_admin.post(f"/api/v1/admin/tenants/{self.business.id}/suspend/")
        self.business.refresh_from_db()
        with self.assertRaises(APIError):
            enforce_subscription_and_limits(self.business)


class SuperAdminPlatformHealthTests(APITestCase):
    def setUp(self):
        self.owner, self.business = create_business_with_owner()
        self.staff_user, _ = create_business_with_owner(email="staff@example.com")
        self.staff_user.is_staff = True
        self.staff_user.save(update_fields=["is_staff"])
        self.client_admin = authenticated_client(self.staff_user)
        Agent.objects.create(business=self.business, name="Agent")

    def test_platform_health_returns_aggregate_counts(self):
        response = self.client_admin.get("/api/v1/admin/platform-health/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(response.data["total_businesses"], 2)
        self.assertGreaterEqual(response.data["total_agents"], 1)
        self.assertIn("subscriptions_by_status", response.data)
