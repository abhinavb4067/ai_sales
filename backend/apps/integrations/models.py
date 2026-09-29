import uuid

from django.db import models

from apps.core.fields import EncryptedTextField
from apps.core.models import TenantOwnedModel


class Integration(TenantOwnedModel):
    """A business's connection to an external messaging channel, bound to
    the one Agent that handles conversations coming through it. `provider`
    is a TextChoices today (WhatsApp only) but nothing here or in
    apps.integrations.providers switches on it with hard-coded branching
    outside registry.py — adding Telegram/Slack/etc. later is a new
    IntegrationProvider implementation plus a registry entry, not a
    rewrite of this model or the webhook views.
    """

    class Provider(models.TextChoices):
        WHATSAPP = "whatsapp", "WhatsApp"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        DISABLED = "disabled", "Disabled"

    # Public, non-secret identifier used in the webhook URL — mirrors
    # Agent.public_widget_id. The real secrets (access token, app secret,
    # verify token) live only in `credentials`, encrypted at rest.
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_index=True)

    agent = models.ForeignKey("agents.Agent", on_delete=models.CASCADE, related_name="integrations")
    provider = models.CharField(max_length=32, choices=Provider.choices)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE)
    external_account_id = models.CharField(
        max_length=255, blank=True, help_text="e.g. the WhatsApp phone_number_id."
    )
    credentials = EncryptedTextField(
        blank=True, default="", help_text="JSON-encoded secret credentials — never returned to the client."
    )

    class Meta:
        db_table = "integrations_integration"
        constraints = [
            models.UniqueConstraint(
                fields=["business", "provider", "external_account_id"], name="unique_integration_account"
            )
        ]

    def __str__(self):
        return f"{self.get_provider_display()} — {self.agent_id}"


class WebhookDelivery(TenantOwnedModel):
    """Append-only log of every inbound webhook call — audit trail plus a
    place to see why a message silently failed to reach an agent, without
    ever storing anything sensitive from the raw request beyond what the
    provider itself already sent as the message payload."""

    integration = models.ForeignKey(Integration, on_delete=models.CASCADE, related_name="webhook_deliveries")
    signature_valid = models.BooleanField(default=False)
    payload = models.JSONField()
    processed = models.BooleanField(default=False)
    error = models.TextField(blank=True)

    class Meta:
        db_table = "integrations_webhook_delivery"
        indexes = [models.Index(fields=["integration", "created_at"])]
