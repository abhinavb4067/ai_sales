from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class InboundMessage:
    """Normalized shape every provider's webhook payload gets parsed into
    — the rest of the system (conversation lookup, the chat pipeline)
    never sees a provider-specific structure, same rule as AIResponse in
    apps.ai.providers."""

    external_conversation_ref: str
    text: str
    external_message_id: str


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
        """Send the AI's reply back out over the channel."""
