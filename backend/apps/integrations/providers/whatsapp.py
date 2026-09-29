import hashlib
import hmac
import json

import requests

from apps.integrations.providers.base import InboundMessage, IntegrationProvider

GRAPH_API_BASE = "https://graph.facebook.com/v19.0"
REQUIRED_CREDENTIAL_KEYS = {"access_token", "app_secret", "verify_token"}


class WhatsAppProvider(IntegrationProvider):
    """WhatsApp Cloud API (Meta). Only plain text messages are sent/received
    in this first cut — media messages are ignored, not crashed on."""

    def validate_credentials(self, credentials: dict) -> bool:
        return REQUIRED_CREDENTIAL_KEYS.issubset(credentials.keys()) and all(
            credentials[k] for k in REQUIRED_CREDENTIAL_KEYS
        )

    def verify_webhook_signature(self, *, payload: bytes, headers: dict, integration) -> bool:
        signature_header = headers.get("X-Hub-Signature-256", "")
        if not signature_header.startswith("sha256="):
            return False

        credentials = json.loads(integration.credentials or "{}")
        app_secret = credentials.get("app_secret", "")
        if not app_secret:
            return False

        expected = hmac.new(app_secret.encode(), payload, hashlib.sha256).hexdigest()
        provided = signature_header.removeprefix("sha256=")
        return hmac.compare_digest(expected, provided)

    def parse_webhook_payload(self, payload: dict) -> list[InboundMessage]:
        messages: list[InboundMessage] = []
        for entry in payload.get("entry", []):
            for change in entry.get("changes", []):
                for raw_message in change.get("value", {}).get("messages", []):
                    if raw_message.get("type") != "text":
                        continue
                    messages.append(
                        InboundMessage(
                            external_conversation_ref=raw_message.get("from", ""),
                            text=raw_message.get("text", {}).get("body", ""),
                            external_message_id=raw_message.get("id", ""),
                        )
                    )
        return messages

    def send_message(self, *, integration, to_ref: str, text: str) -> None:
        credentials = json.loads(integration.credentials or "{}")
        access_token = credentials.get("access_token", "")

        response = requests.post(
            f"{GRAPH_API_BASE}/{integration.external_account_id}/messages",
            headers={"Authorization": f"Bearer {access_token}"},
            json={
                "messaging_product": "whatsapp",
                "to": to_ref,
                "type": "text",
                "text": {"body": text},
            },
            timeout=10,
        )
        response.raise_for_status()
