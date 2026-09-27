from unittest.mock import patch

from rest_framework import status
from rest_framework.test import APITestCase

from apps.agents.models import Agent, AgentTool
from apps.ai.providers.base import AIResponse, Usage
from apps.conversations.models import Conversation, Message
from apps.core.testing import authenticated_client, create_business_with_owner


class FakeProvider:
    """Stands in for OpenAIProvider in tests — no network calls, no API key
    required. Returns a fixed, deterministic response."""

    def __init__(self, content="Hello, how can I help you today?", tool_calls=None):
        self._content = content
        self._tool_calls = tool_calls or []

    def generate(self, messages, tools=None, temperature=0.4, max_tokens=800):
        return AIResponse(
            content=self._content,
            tool_calls=self._tool_calls,
            usage=Usage(input_tokens=42, output_tokens=8),
            finish_reason="stop",
        )

    def embed(self, texts):
        raise NotImplementedError

    def count_tokens(self, text):
        return len(text) // 4


class PlaygroundChatTests(APITestCase):
    def setUp(self):
        self.user, self.business = create_business_with_owner()
        self.client_auth = authenticated_client(self.user)
        self.agent = Agent.objects.create(business=self.business, name="Test Agent", status=Agent.Status.ACTIVE)

    @patch("apps.ai.orchestrator.get_provider_for_agent", return_value=FakeProvider())
    def test_playground_chat_creates_conversation_and_messages(self, mock_provider):
        response = self.client_auth.post(
            "/api/v1/playground/chat/",
            {"agent_id": self.agent.id, "message": "What are your business hours?"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["message"]["content"], "Hello, how can I help you today?")

        conversation = Conversation.objects.get(id=response.data["conversation_id"])
        self.assertEqual(conversation.business_id, self.business.id)
        self.assertEqual(conversation.channel, Conversation.Channel.PLAYGROUND)

        messages = list(Message.objects.filter(conversation=conversation).order_by("created_at"))
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0].sender_type, Message.SenderType.CUSTOMER)
        self.assertEqual(messages[1].sender_type, Message.SenderType.AI)

    @patch("apps.ai.orchestrator.get_provider_for_agent", return_value=FakeProvider())
    def test_playground_chat_continues_existing_conversation(self, mock_provider):
        first = self.client_auth.post(
            "/api/v1/playground/chat/", {"agent_id": self.agent.id, "message": "Hi"}, format="json"
        )
        conversation_id = first.data["conversation_id"]

        second = self.client_auth.post(
            "/api/v1/playground/chat/",
            {"agent_id": self.agent.id, "conversation_id": conversation_id, "message": "Follow up"},
            format="json",
        )
        self.assertEqual(second.status_code, status.HTTP_200_OK)
        self.assertEqual(second.data["conversation_id"], conversation_id)
        self.assertEqual(Message.objects.filter(conversation_id=conversation_id).count(), 4)

    def test_playground_chat_requires_agent_in_own_business(self):
        response = self.client_auth.post(
            "/api/v1/playground/chat/", {"agent_id": 999999, "message": "hi"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    @patch("apps.ai.orchestrator.get_provider_for_agent")
    def test_human_handoff_tool_updates_conversation_status(self, mock_get_provider):
        from apps.ai.providers.base import ToolCall

        AgentTool.objects.create(business=self.business, agent=self.agent, tool_name="human_handoff", enabled=True)
        mock_get_provider.return_value = FakeProvider(
            content="Let me get a human to help you.",
            tool_calls=[ToolCall(id="call_1", name="human_handoff", arguments={"reason": "complex request"})],
        )

        response = self.client_auth.post(
            "/api/v1/playground/chat/",
            {"agent_id": self.agent.id, "message": "I need to speak to a person"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        conversation = Conversation.objects.get(id=response.data["conversation_id"])
        self.assertEqual(conversation.status, Conversation.Status.HUMAN_HANDOFF)
