import hashlib
import secrets

from django.conf import settings
from django.db import models

from apps.core.models import TenantOwnedModel


class ApiKey(TenantOwnedModel):
    """Secret key for server-to-server access to the public Chat API.

    Only `hashed_key` (sha256) is ever stored — the raw key is returned once
    from `generate()` at creation time and cannot be recovered afterwards.
    A fast hash is fine here because the raw key itself is a
    high-entropy random secret (unlike a user password), the same pattern
    used by Stripe/GitHub-style API keys.
    """

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        REVOKED = "revoked", "Revoked"

    name = models.CharField(max_length=255)
    prefix = models.CharField(max_length=12, db_index=True)
    hashed_key = models.CharField(max_length=64, unique=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    last_used_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "apikeys_apikey"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["business", "status"])]

    def __str__(self):
        return f"{self.name} ({self.prefix}...)"

    @staticmethod
    def hash_key(raw_key: str) -> str:
        return hashlib.sha256(raw_key.encode()).hexdigest()

    @classmethod
    def generate(cls, *, business, name, created_by=None):
        prefix = secrets.token_hex(4)
        raw_key = f"sk_live_{prefix}_{secrets.token_urlsafe(32)}"
        instance = cls.objects.create(
            business=business,
            name=name,
            prefix=prefix,
            hashed_key=cls.hash_key(raw_key),
            created_by=created_by,
        )
        return instance, raw_key


class UsageEvent(TenantOwnedModel):
    """One record per AI response, across every channel (playground,
    website widget, public API). Deliberately minimal — this is the
    Phase 3 ledger everything else (dashboards, plan limits, billing)
    reads from later; keep write-side cheap, aggregate on read."""

    agent = models.ForeignKey("agents.Agent", on_delete=models.CASCADE, related_name="usage_events")
    api_key = models.ForeignKey(
        ApiKey, on_delete=models.SET_NULL, null=True, blank=True, related_name="usage_events"
    )
    channel = models.CharField(max_length=16)
    input_tokens = models.PositiveIntegerField(default=0)
    output_tokens = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "apikeys_usage_event"
        indexes = [models.Index(fields=["business", "created_at"])]
