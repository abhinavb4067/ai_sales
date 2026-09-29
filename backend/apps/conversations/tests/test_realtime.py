from unittest.mock import patch

from channels.testing import WebsocketCommunicator
from django.test import TestCase
from rest_framework_simplejwt.tokens import AccessToken

from apps.agents.models import Agent
from apps.ai.providers.base import AIResponse, Usage
from apps.conversations.consumers import ConversationConsumer
from apps.conversations.ws_auth import JWTAuthMiddleware
from apps.core.testing import create_business_with_owner


class FakeProvider:
    def generate(self, messages, tools=None, temperature=0.4, max_tokens=800):
        return AIResponse(content="Hi there", tool_calls=[], usage=Usage(input_tokens=10, output_tokens=5), finish_reason="stop")

    def embed(self, texts):
        raise NotImplementedError

    def count_tokens(self, text):
        return len(text) // 4


def _make_app():
    return JWTAuthMiddleware(ConversationConsumer.as_asgi())


class ConversationConsumerAuthTests(TestCase):
    async def test_connect_rejected_without_token(self):
        communicator = WebsocketCommunicator(_make_app(), "/ws/conversations/")
        connected, close_code = await communicator.connect()
        self.assertFalse(connected)
        self.assertEqual(close_code, 4401)

    async def test_connect_rejected_with_invalid_token(self):
        communicator = WebsocketCommunicator(_make_app(), "/ws/conversations/?token=not-a-real-token")
        connected, close_code = await communicator.connect()
        self.assertFalse(connected)
        self.assertEqual(close_code, 4401)

    async def test_connect_accepted_with_valid_token_and_membership(self):
        from asgiref.sync import sync_to_async

        user, business = await sync_to_async(create_business_with_owner)()
        token = str(AccessToken.for_user(user))

        communicator = WebsocketCommunicator(_make_app(), f"/ws/conversations/?token={token}")
        connected, _ = await communicator.connect()
        self.assertTrue(connected)
        await communicator.disconnect()


class ConversationConsumerBroadcastTests(TestCase):
    async def test_playground_chat_broadcasts_messages_to_connected_dashboard(self):
        from asgiref.sync import sync_to_async

        user, business = await sync_to_async(create_business_with_owner)()
        agent = await sync_to_async(Agent.objects.create)(
            business=business, name="Test Agent", status=Agent.Status.ACTIVE
        )
        token = str(AccessToken.for_user(user))

        communicator = WebsocketCommunicator(_make_app(), f"/ws/conversations/?token={token}")
        connected, _ = await communicator.connect()
        self.assertTrue(connected)

        with patch("apps.ai.orchestrator.get_provider_for_agent", return_value=FakeProvider()):
            from apps.core.testing import authenticated_client

            client = await sync_to_async(authenticated_client)(user)
            response = await sync_to_async(client.post)(
                "/api/v1/playground/chat/", {"agent_id": agent.id, "message": "Hello"}, format="json"
            )
            self.assertEqual(response.status_code, 200)

        first = await communicator.receive_json_from()
        self.assertEqual(first["event"], "message.created")
        self.assertEqual(first["message"]["sender_type"], "customer")

        second = await communicator.receive_json_from()
        self.assertEqual(second["event"], "message.created")
        self.assertEqual(second["message"]["sender_type"], "ai")

        third = await communicator.receive_json_from()
        self.assertEqual(third["event"], "conversation.updated")

        await communicator.disconnect()

    async def test_events_are_isolated_per_business(self):
        from asgiref.sync import sync_to_async

        user_a, business_a = await sync_to_async(create_business_with_owner)(
            business_name="A Co", email="a@example.com"
        )
        user_b, business_b = await sync_to_async(create_business_with_owner)(
            business_name="B Co", email="b@example.com"
        )
        agent_a = await sync_to_async(Agent.objects.create)(
            business=business_a, name="Agent A", status=Agent.Status.ACTIVE
        )

        token_b = str(AccessToken.for_user(user_b))
        communicator_b = WebsocketCommunicator(_make_app(), f"/ws/conversations/?token={token_b}")
        connected, _ = await communicator_b.connect()
        self.assertTrue(connected)

        with patch("apps.ai.orchestrator.get_provider_for_agent", return_value=FakeProvider()):
            from apps.core.testing import authenticated_client

            client_a = await sync_to_async(authenticated_client)(user_a)
            await sync_to_async(client_a.post)(
                "/api/v1/playground/chat/", {"agent_id": agent_a.id, "message": "Hello"}, format="json"
            )

        received_anything = await communicator_b.receive_nothing(timeout=0.5)
        self.assertTrue(received_anything)

        await communicator_b.disconnect()
