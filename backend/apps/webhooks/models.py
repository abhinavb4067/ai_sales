import secrets
import uuid

from django.db import models

from apps.core.fields import EncryptedTextField
from apps.core.models import TenantOwnedModel


class WebhookSubscription(TenantOwnedModel):
    """A business-configured endpoint that gets notified of events
    happening on their own tenant (lead created, conversation handed off
    to a human, appointment booked/cancelled) — the outbound counterpart
    to apps.integrations' inbound provider webhooks. Lets a business
    wire Ectama events into their own CRM/Zapier/Slack without Ectama
    building a bespoke integration for each one.
    """

    class EventType(models.TextChoices):
        LEAD_CREATED = "lead.created", "Lead Created"
        LEAD_STAGE_CHANGED = "lead.stage_changed", "Lead Stage Changed"
        CONVERSATION_HUMAN_HANDOFF = "conversation.human_handoff", "Conversation Escalated to Human"
        APPOINTMENT_BOOKED = "appointment.booked", "Appointment Booked"
        APPOINTMENT_CANCELLED = "appointment.cancelled", "Appointment Cancelled"

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_index=True)
    url = models.URLField()
    # Shown once at creation (apps.webhooks.serializers), like
    # ApiKey.generate — needed in plaintext on every delivery to compute
    # the HMAC signature, so stored encrypted rather than hashed (unlike
    # ApiKey, which never needs the raw value again after issuance).
    secret = EncryptedTextField()
    # Empty list = subscribed to every event type above.
    event_types = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "webhooks_subscription"
        indexes = [models.Index(fields=["business", "is_active"])]

    def __str__(self):
        return f"{self.url} ({self.business_id})"

    @classmethod
    def generate_secret(cls) -> str:
        return secrets.token_urlsafe(32)

    def wants_event(self, event_type: str) -> bool:
        return not self.event_types or event_type in self.event_types


class OutboundWebhookDelivery(TenantOwnedModel):
    """Append-only log of every outbound delivery attempt — lets a
    business see why an event never reached their endpoint (non-2xx
    response, timeout, connection refused) without needing platform
    support to check server logs."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"

    subscription = models.ForeignKey(WebhookSubscription, on_delete=models.CASCADE, related_name="deliveries")
    event_type = models.CharField(max_length=64)
    payload = models.JSONField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    attempt_count = models.PositiveIntegerField(default=0)
    response_status_code = models.PositiveIntegerField(null=True, blank=True)
    last_error = models.TextField(blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "webhooks_delivery"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["business", "subscription", "created_at"])]
