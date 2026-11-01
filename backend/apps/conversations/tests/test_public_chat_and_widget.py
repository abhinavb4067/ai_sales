from unittest.mock import patch

from rest_framework import status
from rest_framework.test import APITestCase

from apps.agents.models import Agent
from apps.apikeys.models import ApiKey, UsageEvent
from apps.conversations.models import Conversation, Message
from apps.conversations.tests.test_playground import FakeProvider
from apps.core.testing import create_business_with_owner


class PublicChatApiTests(APITestCase):
    def setUp(self):
        self.user, self.business = create_business_with_owner()
        self.agent = Agent.objects.create(business=self.business, name="Test Agent", status=Agent.Status.ACTIVE)
        self.api_key, self.raw_key = ApiKey.generate(business=self.business, name="Integration", created_by=self.user)

    def _auth(self, raw_key):
        return {"HTTP_AUTHORIZATION": f"Bearer {raw_key}"}

    @patch("apps.ai.orchestrator.get_provider_for_agent", return_value=FakeProvider())
    def test_public_chat_with_valid_key_creates_conversation_and_usage_event(self, mock_provider):
        response = self.client.post(
            "/api/v1/public/chat/",
            {"agent_id": self.agent.id, "message": "Hi there"},
            format="json",
            **self._auth(self.raw_key),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)

        conversation = Conversation.objects.get(id=response.data["conversation_id"])
        self.assertEqual(conversation.channel, Conversation.Channel.API)
        self.assertEqual(conversation.business_id, self.business.id)

        event = UsageEvent.objects.get(business=self.business)
        self.assertEqual(event.api_key_id, self.api_key.id)
        self.assertEqual(event.channel, Conversation.Channel.API)

    def test_public_chat_rejects_missing_key(self):
        response = self.client.post("/api/v1/public/chat/", {"agent_id": self.agent.id, "message": "Hi"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_public_chat_rejects_invalid_key(self):
        response = self.client.post(
            "/api/v1/public/chat/",
            {"agent_id": self.agent.id, "message": "Hi"},
            format="json",
            **self._auth("sk_live_not_a_real_key"),
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_public_chat_rejects_revoked_key(self):
        self.api_key.status = ApiKey.Status.REVOKED
        self.api_key.save(update_fields=["status"])
        response = self.client.post(
            "/api/v1/public/chat/",
            {"agent_id": self.agent.id, "message": "Hi"},
            format="json",
            **self._auth(self.raw_key),
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @patch("apps.ai.orchestrator.get_provider_for_agent", return_value=FakeProvider())
    def test_public_chat_cannot_reach_other_business_agent(self, mock_provider):
        other_user, other_business = create_business_with_owner(business_name="Other Co", email="other@example.com")
        other_agent = Agent.objects.create(business=other_business, name="Other Agent", status=Agent.Status.ACTIVE)

        response = self.client.post(
            "/api/v1/public/chat/",
            {"agent_id": other_agent.id, "message": "Hi"},
            format="json",
            **self._auth(self.raw_key),
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class WidgetChatTests(APITestCase):
    def setUp(self):
        self.user, self.business = create_business_with_owner()
        self.agent = Agent.objects.create(
            business=self.business, name="Widget Agent", status=Agent.Status.ACTIVE, greeting="Welcome!"
        )

    def test_widget_config_is_public_and_unauthenticated(self):
        response = self.client.get(f"/api/v1/widget/{self.agent.public_widget_id}/config/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["agent_name"], "Widget Agent")
        self.assertEqual(response.data["greeting"], "Welcome!")

    def test_widget_config_404_for_unknown_widget_id(self):
        import uuid

        response = self.client.get(f"/api/v1/widget/{uuid.uuid4()}/config/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    @patch("apps.ai.orchestrator.get_provider_for_agent", return_value=FakeProvider())
    def test_widget_chat_creates_website_conversation(self, mock_provider):
        response = self.client.post(
            f"/api/v1/widget/{self.agent.public_widget_id}/chat/",
            {"message": "Hello", "session_id": "anon-session-1"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)

        conversation = Conversation.objects.get(id=response.data["conversation_id"])
        self.assertEqual(conversation.channel, Conversation.Channel.WEBSITE)
        self.assertEqual(conversation.external_customer_ref, "anon-session-1")

        event = UsageEvent.objects.get(business=self.business)
        self.assertIsNone(event.api_key_id)

    def test_widget_config_allows_cross_origin_requests(self):
        response = self.client.get(
            f"/api/v1/widget/{self.agent.public_widget_id}/config/", HTTP_ORIGIN="https://customer-site.example"
        )
        self.assertEqual(response["Access-Control-Allow-Origin"], "*")

    def test_widget_chat_preflight_is_answered_without_reaching_the_view(self):
        response = self.client.options(
            f"/api/v1/widget/{self.agent.public_widget_id}/chat/",
            HTTP_ORIGIN="https://customer-site.example",
            HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST",
        )
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response["Access-Control-Allow-Origin"], "*")

    def test_dashboard_endpoints_do_not_get_wildcard_cors(self):
        response = self.client.get("/api/v1/agents/", HTTP_ORIGIN="https://customer-site.example")
        self.assertNotIn("Access-Control-Allow-Origin", response)

    def test_widget_config_rejects_unregistered_origin_once_restricted(self):
        self.agent.allowed_origins = ["https://allowed.example"]
        self.agent.save(update_fields=["allowed_origins"])

        response = self.client.get(
            f"/api/v1/widget/{self.agent.public_widget_id}/config/", HTTP_ORIGIN="https://not-allowed.example"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_widget_config_allows_registered_origin(self):
        self.agent.allowed_origins = ["https://allowed.example"]
        self.agent.save(update_fields=["allowed_origins"])

        response = self.client.get(
            f"/api/v1/widget/{self.agent.public_widget_id}/config/", HTTP_ORIGIN="https://allowed.example"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    @patch("apps.ai.orchestrator.get_provider_for_agent", return_value=FakeProvider())
    def test_widget_chat_stream_returns_sse_delta_and_done_events(self, mock_provider):
        response = self.client.post(
            f"/api/v1/widget/{self.agent.public_widget_id}/chat/",
            {"message": "Hello", "stream": True},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["Content-Type"], "text/event-stream")
        body = b"".join(response.streaming_content).decode()
        self.assertIn("event: delta", body)
        self.assertIn("event: done", body)

    @patch("apps.ai.orchestrator.get_provider_for_agent", return_value=FakeProvider())
    def test_widget_chat_rejects_unregistered_origin_once_restricted(self, mock_provider):
        self.agent.allowed_origins = ["https://allowed.example"]
        self.agent.save(update_fields=["allowed_origins"])

        response = self.client.post(
            f"/api/v1/widget/{self.agent.public_widget_id}/chat/",
            {"message": "Hello"},
            format="json",
            HTTP_ORIGIN="https://not-allowed.example",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

class WidgetMessageRatingTests(APITestCase):
    def setUp(self):
        self.user, self.business = create_business_with_owner()
        self.agent = Agent.objects.create(business=self.business, name="Widget Agent", status=Agent.Status.ACTIVE)

    @patch("apps.ai.orchestrator.get_provider_for_agent", return_value=FakeProvider())
    def test_customer_can_rate_an_ai_reply(self, mock_provider):
        chat_response = self.client.post(
            f"/api/v1/widget/{self.agent.public_widget_id}/chat/", {"message": "Hi"}, format="json"
        )
        message_id = chat_response.data["message"]["id"]

        response = self.client.post(
            f"/api/v1/widget/{self.agent.public_widget_id}/messages/{message_id}/rate/",
            {"rating": "up"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        message = Message.objects.get(id=message_id)
        self.assertEqual(message.rating, "up")
        self.assertIsNotNone(message.rated_at)

    @patch("apps.ai.orchestrator.get_provider_for_agent", return_value=FakeProvider())
    def test_rejects_invalid_rating_value(self, mock_provider):
        chat_response = self.client.post(
            f"/api/v1/widget/{self.agent.public_widget_id}/chat/", {"message": "Hi"}, format="json"
        )
        message_id = chat_response.data["message"]["id"]

        response = self.client.post(
            f"/api/v1/widget/{self.agent.public_widget_id}/messages/{message_id}/rate/",
            {"rating": "sideways"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("apps.ai.orchestrator.get_provider_for_agent", return_value=FakeProvider())
    def test_cannot_rate_a_customer_message(self, mock_provider):
        chat_response = self.client.post(
            f"/api/v1/widget/{self.agent.public_widget_id}/chat/", {"message": "Hi"}, format="json"
        )
        conversation_id = chat_response.data["conversation_id"]
        customer_message = Message.objects.get(conversation_id=conversation_id, sender_type=Message.SenderType.CUSTOMER)

        response = self.client.post(
            f"/api/v1/widget/{self.agent.public_widget_id}/messages/{customer_message.id}/rate/",
            {"rating": "up"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    @patch("apps.ai.orchestrator.get_provider_for_agent", return_value=FakeProvider())
    def test_cannot_rate_another_agents_message(self, mock_provider):
        other_user, other_business = create_business_with_owner(email="other@example.com")
        other_agent = Agent.objects.create(business=other_business, name="Other Agent", status=Agent.Status.ACTIVE)

        chat_response = self.client.post(
            f"/api/v1/widget/{self.agent.public_widget_id}/chat/", {"message": "Hi"}, format="json"
        )
        message_id = chat_response.data["message"]["id"]

        response = self.client.post(
            f"/api/v1/widget/{other_agent.public_widget_id}/messages/{message_id}/rate/",
            {"rating": "up"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
