"""Mandatory tenant-isolation tests: Business A must never be able to
read, modify, or enumerate Business B's data, across every tenant-owned
resource introduced in Phase 1."""
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.agents.models import Agent
from apps.core.testing import authenticated_client, create_business_with_owner
from apps.knowledge.models import KnowledgeDocument


class TenantIsolationTests(APITestCase):
    def setUp(self):
        self.user_a, self.business_a = create_business_with_owner(
            business_name="Business A", email="a@example.com"
        )
        self.user_b, self.business_b = create_business_with_owner(
            business_name="Business B", email="b@example.com"
        )
        self.client_a = authenticated_client(self.user_a)
        self.client_b = authenticated_client(self.user_b)

        self.agent_b = Agent.objects.create(business=self.business_b, name="B's Agent")
        self.doc_b = KnowledgeDocument.objects.create(
            business=self.business_b, title="B secret doc", content="secret", status=KnowledgeDocument.Status.READY
        )

    def test_current_business_endpoint_returns_own_business_only(self):
        response = self.client_a.get(reverse("business-me"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "Business A")
        self.assertNotEqual(response.data["name"], "Business B")

    def test_business_a_cannot_list_business_b_agents(self):
        response = self.client_a.get("/api/v1/agents/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [a["id"] for a in response.data["results"]] if "results" in response.data else response.data
        self.assertNotIn(self.agent_b.id, [a.get("id") if isinstance(a, dict) else a for a in ids])

    def test_business_a_cannot_retrieve_business_b_agent_by_id(self):
        response = self.client_a.get(f"/api/v1/agents/{self.agent_b.id}/")
        self.assertIn(response.status_code, (status.HTTP_404_NOT_FOUND,))

    def test_business_a_cannot_update_business_b_agent(self):
        response = self.client_a.patch(f"/api/v1/agents/{self.agent_b.id}/", {"name": "Hacked"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.agent_b.refresh_from_db()
        self.assertEqual(self.agent_b.name, "B's Agent")

    def test_business_a_cannot_delete_business_b_agent(self):
        response = self.client_a.delete(f"/api/v1/agents/{self.agent_b.id}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(Agent.objects.filter(id=self.agent_b.id).exists())

    def test_business_a_cannot_list_business_b_knowledge(self):
        response = self.client_a.get("/api/v1/knowledge/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data.get("results", response.data)
        titles = [d["title"] for d in results]
        self.assertNotIn("B secret doc", titles)

    def test_business_a_cannot_retrieve_business_b_knowledge_by_id(self):
        response = self.client_a.get(f"/api/v1/knowledge/{self.doc_b.id}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_business_a_cannot_view_business_b_members(self):
        response = self.client_a.get(reverse("business-members"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        emails = [m["user_email"] for m in response.data.get("results", response.data)]
        self.assertNotIn(self.user_b.email, emails)

    def test_x_business_id_header_cannot_grant_access_to_foreign_business(self):
        """A malicious client cannot use X-Business-ID to impersonate
        access to a business it has no membership on."""
        response = self.client_a.get(
            "/api/v1/agents/", HTTP_X_BUSINESS_ID=str(self.business_b.id)
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_playground_chat_rejects_foreign_agent(self):
        response = self.client_a.post(
            "/api/v1/playground/chat/",
            {"agent_id": self.agent_b.id, "message": "hi"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
