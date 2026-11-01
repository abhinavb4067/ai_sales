from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class InboundMessage:
    """Normalized shape every provider's webhook payload gets parsed into
    — the rest of the system (conversation lookup, the chat pipeline)
    never sees a provider-specific structure, same rule as AIResponse in
    apps.ai.providers.

    media_type/media_id are set for non-text messages (image/document/
    audio/video/sticker) — `text` is still always populated (the
    caption, or a bracketed placeholder like "[Image]" when there's no
    caption) so the chat pipeline keeps working without special-casing
    media. Downloading/storing the actual media bytes is not implemented
    yet — media_id is recorded so that's a follow-up, not a redesign.
    """

    external_conversation_ref: str
    text: str
    external_message_id: str
    media_type: str = ""
    media_id: str = ""


class IntegrationProvider(ABC):
    """Normalized interface every messaging channel (WhatsApp today;
    Telegram/Slack/Discord/Messenger/Instagram later) must implement.
    """

    @abstractmethod
    def validate_credentials(self, credentials: dict) -> bool:
        """Cheap structural check (required keys present) — not a live
        API call. Used when an owner saves integration credentials."""

    @abstractmethod
    def verify_webhook_signature(self, *, payload: bytes, headers: dict, integration) -> bool:
        """Must be checked before any webhook payload is trusted."""

    @abstractmethod
    def parse_webhook_payload(self, payload: dict) -> list[InboundMessage]:
        """A single webhook call can carry zero or more messages (or none,
        e.g. a delivery-status callback) — always returns a list."""

    @abstractmethod
    def send_message(self, *, integration, to_ref: str, text: str) -> None:
        """Send a freeform text reply — only valid inside the provider's
        customer-service session window (see is_within_messaging_window)."""

    def send_template_message(self, *, integration, to_ref: str, template_name: str, language_code: str, parameters: list[str]) -> None:
        """Send a pre-approved template message — the only way to message
        a customer outside the freeform session window. Optional: not
        every provider distinguishes template vs freeform sends, so the
        default raises rather than every provider needing a no-op
        override."""
        raise NotImplementedError(f"{type(self).__name__} does not support template messages.")

    def is_within_messaging_window(self, *, last_customer_message_at) -> bool:
        """Default: no window restriction. Providers with a customer
        service window (WhatsApp's 24-hour rule) override this."""
        return True
