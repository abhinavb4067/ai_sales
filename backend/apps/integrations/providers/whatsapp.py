import hashlib
import hmac
import json
from datetime import timedelta

from django.utils import timezone

import requests

from apps.integrations.providers.base import InboundMessage, IntegrationProvider

GRAPH_API_BASE = "https://graph.facebook.com/v19.0"
REQUIRED_CREDENTIAL_KEYS = {"access_token", "app_secret", "verify_token"}

# Meta's customer service window: a business can only send freeform
# (non-template) replies within 24 hours of the customer's last message.
# Outside that window, only a pre-approved template message is allowed.
CUSTOMER_SERVICE_WINDOW = timedelta(hours=24)

# Media message types the AI can at least acknowledge (caption-only — see
# InboundMessage docstring for what's not implemented yet: downloading
# the actual media bytes).
_MEDIA_TYPES = {"image", "document", "audio", "video", "sticker"}


def exchange_embedded_signup_code(code: str) -> str:
    """Step 2 of Meta's Embedded Signup flow: the frontend JS SDK
    (FB.login with the platform's config_id) hands the business a
    short-lived authorization `code`; this exchanges it server-side for
    an access token using the PLATFORM's app id/secret (never a
    per-business secret — that's the whole point of Embedded Signup, the
    business never sees or handles a raw access token themselves).
    Requires WHATSAPP_META_APP_ID/WHATSAPP_META_APP_SECRET to be
    configured; raises if they aren't (fails loudly rather than silently
    no-op-ing, since a business clicking "Connect WhatsApp" with this
    unconfigured should see a clear platform-setup error, not a fake
    success).
    """
    from django.conf import settings

    if not settings.WHATSAPP_META_APP_ID or not settings.WHATSAPP_META_APP_SECRET:
        raise ValueError("WhatsApp Embedded Signup is not configured on this platform yet.")

    response = requests.get(
        f"{GRAPH_API_BASE}/oauth/access_token",
        params={
            "client_id": settings.WHATSAPP_META_APP_ID,
            "client_secret": settings.WHATSAPP_META_APP_SECRET,
            "code": code,
        },
        timeout=10,
    )
    response.raise_for_status()
    return response.json()["access_token"]


def subscribe_app_to_waba(*, access_token: str, waba_id: str) -> None:
    """Step 3: subscribes the platform's app to receive webhooks for this
    specific WhatsApp Business Account — without this call, Meta never
    sends inbound-message webhooks for it, no matter how the Integration
    row is configured locally."""
    response = requests.post(
        f"{GRAPH_API_BASE}/{waba_id}/subscribed_apps",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=10,
    )
    response.raise_for_status()


class WhatsAppProvider(IntegrationProvider):
    """WhatsApp Cloud API (Meta). Text messages are fully handled.
    Media messages (image/document/audio/video/sticker) are acknowledged
    via their caption (or a placeholder) rather than ignored, but the
    media bytes themselves aren't downloaded/stored yet."""

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
            # Embedded Signup-provisioned integrations don't carry their
            # own app_secret (see provision_whatsapp_via_embedded_signup)
            # — Meta signs the webhook with the platform app's secret in
            # that case, since it's the platform's app receiving it.
            from django.conf import settings

            app_secret = settings.WHATSAPP_META_APP_SECRET
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
                    msg_type = raw_message.get("type")
                    if msg_type == "text":
                        messages.append(
                            InboundMessage(
                                external_conversation_ref=raw_message.get("from", ""),
                                text=raw_message.get("text", {}).get("body", ""),
                                external_message_id=raw_message.get("id", ""),
                            )
                        )
                    elif msg_type in _MEDIA_TYPES:
                        media = raw_message.get(msg_type, {})
                        caption = media.get("caption", "")
                        messages.append(
                            InboundMessage(
                                external_conversation_ref=raw_message.get("from", ""),
                                text=caption or f"[Customer sent a {msg_type}]",
                                external_message_id=raw_message.get("id", ""),
                                media_type=msg_type,
                                media_id=media.get("id", ""),
                            )
                        )
                    # Other types (reactions, system, unsupported) are
                    # neither crashed on nor silently acknowledged as
                    # messages — just not appended.
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

    def send_template_message(
        self, *, integration, to_ref: str, template_name: str, language_code: str = "en_US", parameters: list[str] | None = None
    ) -> None:
        """Sends a pre-approved WhatsApp template — the only way to reach a
        customer outside the 24-hour session window (e.g. an appointment
        reminder). `template_name` must already be approved for this
        WhatsApp Business Account in Meta Business Manager; this method
        does not create or validate templates, it only sends one."""
        credentials = json.loads(integration.credentials or "{}")
        access_token = credentials.get("access_token", "")

        components = []
        if parameters:
            components.append({
                "type": "body",
                "parameters": [{"type": "text", "text": p} for p in parameters],
            })

        response = requests.post(
            f"{GRAPH_API_BASE}/{integration.external_account_id}/messages",
            headers={"Authorization": f"Bearer {access_token}"},
            json={
                "messaging_product": "whatsapp",
                "to": to_ref,
                "type": "template",
                "template": {
                    "name": template_name,
                    "language": {"code": language_code},
                    "components": components,
                },
            },
            timeout=10,
        )
        response.raise_for_status()

    def is_within_messaging_window(self, *, last_customer_message_at) -> bool:
        if last_customer_message_at is None:
            return False
        return timezone.now() - last_customer_message_at <= CUSTOMER_SERVICE_WINDOW
