from unittest.mock import patch

from rest_framework import status
from rest_framework.test import APITestCase

from apps.agents.models import Agent, AgentTool
from apps.ai.providers.base import AIResponse, ToolCall, Usage
from apps.conversations.models import Conversation
from apps.core.testing import authenticated_client, create_business_with_owner
from apps.leads.models import Lead


class FakeProvider:
    def __init__(self, content="OK", tool_calls=None):
        self._content = content
        self._tool_calls = tool_calls or []

    def generate(self, messages, tools=None, temperature=0.4, max_tokens=800):
        return AIResponse(content=self._content, tool_calls=self._tool_calls, usage=Usage(10, 5), finish_reason="stop")

    def embed(self, texts):
        raise NotImplementedError

    def count_tokens(self, text):
        return len(text) // 4


class CreateLeadToolTests(APITestCase):
    def setUp(self):
        self.user, self.business = create_business_with_owner()
        self.client_auth = authenticated_client(self.user)
        self.agent = Agent.objects.create(business=self.business, name="Sales", status=Agent.Status.ACTIVE)
        AgentTool.objects.create(business=self.business, agent=self.agent, tool_name="create_lead", enabled=True)

    @patch("apps.ai.orchestrator.get_provider_for_agent")
    def test_create_lead_tool_call_creates_lead(self, mock_get_provider):
        mock_get_provider.return_value = FakeProvider(
            content="Got it, I've noted your details.",
            tool_calls=[ToolCall(id="1", name="create_lead", arguments={"email": "buyer@example.com", "company": "Acme"})],
        )
        response = self.client_auth.post(
            "/api/v1/playground/chat/",
            {"agent_id": self.agent.id, "message": "My email is buyer@example.com, I work at Acme"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        lead = Lead.objects.get(business=self.business)
        self.assertEqual(lead.email, "buyer@example.com")
        self.assertEqual(lead.company, "Acme")
        self.assertGreater(lead.score, 0)

    @patch("apps.ai.orchestrator.get_provider_for_agent")
    def test_create_lead_tool_rejected_when_not_enabled(self, mock_get_provider):
        AgentTool.objects.filter(agent=self.agent, tool_name="create_lead").update(enabled=False)
        mock_get_provider.return_value = FakeProvider(
            tool_calls=[ToolCall(id="1", name="create_lead", arguments={"email": "x@example.com"})]
        )
        response = self.client_auth.post(
            "/api/v1/playground/chat/", {"agent_id": self.agent.id, "message": "hi"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(Lead.objects.filter(business=self.business).exists())
        self.assertEqual(response.data["message"]["tool_calls"][0]["status"], "rejected")

    @patch("apps.ai.orchestrator.get_provider_for_agent")
    def test_payment_link_always_requires_approval(self, mock_get_provider):
        AgentTool.objects.create(
            business=self.business, agent=self.agent, tool_name="create_payment_link",
            enabled=True, permission_level=AgentTool.PermissionLevel.AUTO,
        )
        mock_get_provider.return_value = FakeProvider(
            tool_calls=[ToolCall(id="1", name="create_payment_link", arguments={"amount": 100})]
        )
        response = self.client_auth.post(
            "/api/v1/playground/chat/", {"agent_id": self.agent.id, "message": "charge me"}, format="json"
        )
        self.assertEqual(response.data["message"]["tool_calls"][0]["status"], "pending_approval")


class EscalationRuleTests(APITestCase):
    def setUp(self):
        self.user, self.business = create_business_with_owner()
        self.client_auth = authenticated_client(self.user)
        self.agent = Agent.objects.create(
            business=self.business, name="Support", status=Agent.Status.ACTIVE,
            escalation_rules=["cancel my subscription", "legal action"],
        )

    @patch("apps.ai.orchestrator.get_provider_for_agent", return_value=FakeProvider())
    def test_matching_message_forces_human_handoff(self, mock_provider):
        response = self.client_auth.post(
            "/api/v1/playground/chat/",
            {"agent_id": self.agent.id, "message": "I want to cancel my subscription immediately"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["escalated"])
        conversation = Conversation.objects.get(id=response.data["conversation_id"])
        self.assertEqual(conversation.status, Conversation.Status.HUMAN_HANDOFF)

    @patch("apps.ai.orchestrator.get_provider_for_agent", return_value=FakeProvider())
    def test_non_matching_message_does_not_escalate(self, mock_provider):
        response = self.client_auth.post(
            "/api/v1/playground/chat/", {"agent_id": self.agent.id, "message": "what are your hours?"}, format="json"
        )
        self.assertFalse(response.data["escalated"])
        conversation = Conversation.objects.get(id=response.data["conversation_id"])
        self.assertEqual(conversation.status, Conversation.Status.ACTIVE)


class HumanHandoffEndpointTests(APITestCase):
    def setUp(self):
        self.user, self.business = create_business_with_owner()
        self.client_auth = authenticated_client(self.user)
        self.agent = Agent.objects.create(business=self.business, name="Support")
        self.conversation = Conversation.objects.create(
            business=self.business, agent=self.agent, status=Conversation.Status.HUMAN_HANDOFF
        )

    def test_takeover_assigns_conversation(self):
        response = self.client_auth.post(f"/api/v1/conversations/{self.conversation.id}/takeover/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.conversation.refresh_from_db()
        self.assertEqual(self.conversation.assigned_to_id, self.user.id)

    def test_resolve_marks_conversation_resolved(self):
        response = self.client_auth.post(f"/api/v1/conversations/{self.conversation.id}/resolve/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.conversation.refresh_from_db()
        self.assertEqual(self.conversation.status, Conversation.Status.RESOLVED)

    def test_list_filters_by_status(self):
        Conversation.objects.create(business=self.business, agent=self.agent, status=Conversation.Status.ACTIVE)
        response = self.client_auth.get("/api/v1/conversations/?status=human_handoff")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [c["id"] for c in response.data["results"]]
        self.assertEqual(ids, [self.conversation.id])
