from rest_framework import status
from rest_framework.test import APITestCase

from apps.apikeys.models import ApiKey
from apps.core.testing import authenticated_client, create_business_with_owner


class ApiKeyManagementTests(APITestCase):
    def setUp(self):
        self.user, self.business = create_business_with_owner()
        self.client_auth = authenticated_client(self.user)

    def test_create_api_key_returns_raw_key_once(self):
        response = self.client_auth.post("/api/v1/api-keys/", {"name": "Zapier integration"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertIn("key", response.data)
        self.assertTrue(response.data["key"].startswith("sk_live_"))

        stored = ApiKey.objects.get(id=response.data["id"])
        self.assertEqual(stored.business_id, self.business.id)
        self.assertEqual(stored.hashed_key, ApiKey.hash_key(response.data["key"]))

    def test_list_api_keys_never_exposes_raw_key(self):
        self.client_auth.post("/api/v1/api-keys/", {"name": "Key 1"}, format="json")
        response = self.client_auth.get("/api/v1/api-keys/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for item in response.data["results"]:
            self.assertNotIn("key", item)
            self.assertNotIn("hashed_key", item)

    def test_revoke_api_key(self):
        created = self.client_auth.post("/api/v1/api-keys/", {"name": "Key 1"}, format="json").data
        response = self.client_auth.post(f"/api/v1/api-keys/{created['id']}/revoke/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], ApiKey.Status.REVOKED)

    def test_other_business_cannot_see_or_revoke_key(self):
        other_user, _ = create_business_with_owner(business_name="Other Co", email="other@example.com")
        created = self.client_auth.post("/api/v1/api-keys/", {"name": "Key 1"}, format="json").data

        other_client = authenticated_client(other_user)
        response = other_client.post(f"/api/v1/api-keys/{created['id']}/revoke/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
