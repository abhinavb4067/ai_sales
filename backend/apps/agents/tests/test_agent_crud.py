from rest_framework import status
from rest_framework.test import APITestCase

from apps.agents.models import Agent, AgentTool
from apps.core.testing import authenticated_client, create_business_with_owner


class AgentCrudTests(APITestCase):
    def setUp(self):
        self.user, self.business = create_business_with_owner()
        self.client_auth = authenticated_client(self.user)

    def test_create_agent_provisions_default_tools(self):
        payload = {
            "name": "Sales Bot",
            "agent_type": Agent.AgentType.SALES,
            "primary_goal": Agent.Goal.LEAD_GENERATION,
            "tone": Agent.Tone.FRIENDLY,
        }
        response = self.client_auth.post("/api/v1/agents/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        agent = Agent.objects.get(id=response.data["id"])
        self.assertEqual(agent.business_id, self.business.id)
        self.assertTrue(AgentTool.objects.filter(agent=agent, tool_name="create_lead").exists())

    def test_list_agents_scoped_to_business(self):
        Agent.objects.create(business=self.business, name="A1")
        response = self.client_auth.get("/api/v1/agents/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)

    def test_update_agent(self):
        agent = Agent.objects.create(business=self.business, name="Original")
        response = self.client_auth.patch(f"/api/v1/agents/{agent.id}/", {"name": "Updated"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        agent.refresh_from_db()
        self.assertEqual(agent.name, "Updated")

    def test_delete_agent(self):
        agent = Agent.objects.create(business=self.business, name="ToDelete")
        response = self.client_auth.delete(f"/api/v1/agents/{agent.id}/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Agent.objects.filter(id=agent.id).exists())

    def test_invalid_temperature_rejected(self):
        response = self.client_auth.post(
            "/api/v1/agents/", {"name": "Bad", "temperature": 5.0}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unauthenticated_cannot_access_agents(self):
        response = self.client.get("/api/v1/agents/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_agent_creation_blocked_once_plan_limit_reached(self):
        # Starter plan (the default trial plan) allows max_agents=1.
        Agent.objects.create(business=self.business, name="Existing")
        response = self.client_auth.post("/api/v1/agents/", {"name": "Second"}, format="json")
        self.assertEqual(response.status_code, 402)
        self.assertEqual(response.data["error"]["code"], "PLAN_LIMIT_REACHED")

    def test_agent_creation_allowed_after_upgrading_plan(self):
        from apps.billing.services import activate_subscription
        from apps.billing.models import Plan

        Agent.objects.create(business=self.business, name="Existing")
        activate_subscription(business=self.business, plan=Plan.objects.get(code="growth"))

        response = self.client_auth.post("/api/v1/agents/", {"name": "Second"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
