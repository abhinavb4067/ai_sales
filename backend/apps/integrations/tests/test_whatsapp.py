import hashlib
import hmac
import json
from unittest.mock import patch

from rest_framework import status
from rest_framework.test import APITestCase

from apps.agents.models import Agent
from apps.ai.providers.base import AIResponse, Usage
from apps.conversations.models import Conversation, Message
from apps.core.testing import authenticated_client, create_business_with_owner
from apps.integrations.models import Integration, WebhookDelivery

APP_SECRET = "test-app-secret"
VERIFY_TOKEN = "test-verify-token"
ACCESS_TOKEN = "test-access-token"


class FakeProvider:
    def generate(self, messages, tools=None, temperature=0.4, max_tokens=800):
        return AIResponse(
            content="Thanks for reaching out!", tool_calls=[], usage=Usage(input_tokens=10, output_tokens=5),
            finish_reason="stop",
        )

    def embed(self, texts):
        raise NotImplementedError

    def count_tokens(self, text):
        return len(text) // 4


def _sign(payload: bytes) -> str:
    return "sha256=" + hmac.new(APP_SECRET.encode(), payload, hashlib.sha256).hexdigest()


def _whatsapp_payload(from_number="15551234567", text="Hi, do you deliver?", message_id="wamid.abc123"):
    return {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {"from": from_number, "id": message_id, "type": "text", "text": {"body": text}}
                            ]
                        }
                    }
                ]
            }
        ]
    }


class IntegrationManagementTests(APITestCase):
    def setUp(self):
        self.user, self.business = create_business_with_owner()
        self.client_auth = authenticated_client(self.user)
        self.agent = Agent.objects.create(business=self.business, name="Support Agent", status=Agent.Status.ACTIVE)

    def test_create_integration_with_valid_credentials(self):
        response = self.client_auth.post(
            "/api/v1/integrations/",
            {
                "agent": self.agent.id,
                "provider": "whatsapp",
                "external_account_id": "1234567890",
                "credentials": {
                    "access_token": ACCESS_TOKEN,
                    "app_secret": APP_SECRET,
                    "verify_token": VERIFY_TOKEN,
                },
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertNotIn("credentials", response.data)

        stored = Integration.objects.get(id=response.data["id"])
        self.assertEqual(stored.business_id, self.business.id)
        creds = json.loads(stored.credentials)
        self.assertEqual(creds["access_token"], ACCESS_TOKEN)

    def test_create_integration_rejects_missing_credentials(self):
        response = self.client_auth.post(
            "/api/v1/integrations/",
            {
                "agent": self.agent.id,
                "provider": "whatsapp",
                "external_account_id": "1234567890",
                "credentials": {"access_token": ACCESS_TOKEN},
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_list_integrations_never_exposes_credentials(self):
        Integration.objects.create(
            business=self.business,
            agent=self.agent,
            provider="whatsapp",
            external_account_id="1234567890",
            credentials=json.dumps({"access_token": ACCESS_TOKEN, "app_secret": APP_SECRET, "verify_token": VERIFY_TOKEN}),
        )
        response = self.client_auth.get("/api/v1/integrations/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for item in response.data["results"]:
            self.assertNotIn("credentials", item)

    def test_other_business_cannot_see_integration(self):
        integration = Integration.objects.create(
            business=self.business,
            agent=self.agent,
            provider="whatsapp",
            external_account_id="1234567890",
            credentials=json.dumps({"access_token": ACCESS_TOKEN, "app_secret": APP_SECRET, "verify_token": VERIFY_TOKEN}),
        )
        other_user, _ = create_business_with_owner(business_name="Other Co", email="other@example.com")
        other_client = authenticated_client(other_user)
        response = other_client.get(f"/api/v1/integrations/{integration.id}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class WhatsAppWebhookTests(APITestCase):
    def setUp(self):
        self.user, self.business = create_business_with_owner()
        self.agent = Agent.objects.create(business=self.business, name="Support Agent", status=Agent.Status.ACTIVE)
        self.integration = Integration.objects.create(
            business=self.business,
            agent=self.agent,
            provider=Integration.Provider.WHATSAPP,
            external_account_id="1234567890",
            credentials=json.dumps(
                {"access_token": ACCESS_TOKEN, "app_secret": APP_SECRET, "verify_token": VERIFY_TOKEN}
            ),
        )

    def test_verification_handshake_returns_challenge(self):
        response = self.client.get(
            f"/api/v1/integrations/whatsapp/webhook/{self.integration.public_id}/",
            {"hub.mode": "subscribe", "hub.verify_token": VERIFY_TOKEN, "hub.challenge": "12345"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "12345")

    def test_verification_handshake_rejects_wrong_token(self):
        response = self.client.get(
            f"/api/v1/integrations/whatsapp/webhook/{self.integration.public_id}/",
            {"hub.mode": "subscribe", "hub.verify_token": "wrong", "hub.challenge": "12345"},
        )
        self.assertEqual(response.status_code, 403)

    @patch("apps.integrations.providers.whatsapp.requests.post")
    @patch("apps.ai.orchestrator.get_provider_for_agent", return_value=FakeProvider())
    def test_inbound_message_creates_conversation_and_replies(self, mock_ai_provider, mock_requests_post):
        body = json.dumps(_whatsapp_payload()).encode()
        response = self.client.post(
            f"/api/v1/integrations/whatsapp/webhook/{self.integration.public_id}/",
            data=body,
            content_type="application/json",
            HTTP_X_HUB_SIGNATURE_256=_sign(body),
        )
        self.assertEqual(response.status_code, 200)

        conversation = Conversation.objects.get(business=self.business, channel=Conversation.Channel.WHATSAPP)
        self.assertEqual(conversation.external_customer_ref, "15551234567")
        self.assertEqual(Message.objects.filter(conversation=conversation).count(), 2)

        delivery = WebhookDelivery.objects.get(integration=self.integration)
        self.assertTrue(delivery.signature_valid)
        self.assertTrue(delivery.processed)
        self.assertEqual(delivery.error, "")

        mock_requests_post.assert_called_once()
        sent_url = mock_requests_post.call_args[0][0]
        self.assertIn("1234567890/messages", sent_url)
        sent_body = mock_requests_post.call_args.kwargs["json"]
        self.assertEqual(sent_body["to"], "15551234567")
        self.assertEqual(sent_body["text"]["body"], "Thanks for reaching out!")

    def test_inbound_message_rejected_with_bad_signature(self):
        body = json.dumps(_whatsapp_payload()).encode()
        response = self.client.post(
            f"/api/v1/integrations/whatsapp/webhook/{self.integration.public_id}/",
            data=body,
            content_type="application/json",
            HTTP_X_HUB_SIGNATURE_256="sha256=not-the-real-signature",
        )
        self.assertEqual(response.status_code, 200)  # always ack

        self.assertFalse(Conversation.objects.filter(business=self.business).exists())
        delivery = WebhookDelivery.objects.get(integration=self.integration)
        self.assertFalse(delivery.signature_valid)
        self.assertEqual(delivery.error, "Invalid webhook signature.")

    @patch("apps.integrations.providers.whatsapp.requests.post")
    @patch("apps.ai.orchestrator.get_provider_for_agent", return_value=FakeProvider())
    def test_second_inbound_message_reuses_open_conversation(self, mock_ai_provider, mock_requests_post):
        body = json.dumps(_whatsapp_payload(message_id="wamid.first")).encode()
        self.client.post(
            f"/api/v1/integrations/whatsapp/webhook/{self.integration.public_id}/",
            data=body, content_type="application/json", HTTP_X_HUB_SIGNATURE_256=_sign(body),
        )
        body2 = json.dumps(_whatsapp_payload(text="Follow-up question", message_id="wamid.second")).encode()
        self.client.post(
            f"/api/v1/integrations/whatsapp/webhook/{self.integration.public_id}/",
            data=body2, content_type="application/json", HTTP_X_HUB_SIGNATURE_256=_sign(body2),
        )

        conversations = Conversation.objects.filter(business=self.business, channel=Conversation.Channel.WHATSAPP)
        self.assertEqual(conversations.count(), 1)
        self.assertEqual(Message.objects.filter(conversation=conversations.first()).count(), 4)

    @patch("apps.ai.orchestrator.get_provider_for_agent", return_value=FakeProvider())
    def test_disabled_integration_does_not_process_messages(self, mock_ai_provider):
        self.integration.status = Integration.Status.DISABLED
        self.integration.save(update_fields=["status"])

        body = json.dumps(_whatsapp_payload()).encode()
        response = self.client.post(
            f"/api/v1/integrations/whatsapp/webhook/{self.integration.public_id}/",
            data=body, content_type="application/json", HTTP_X_HUB_SIGNATURE_256=_sign(body),
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Conversation.objects.filter(business=self.business).exists())
