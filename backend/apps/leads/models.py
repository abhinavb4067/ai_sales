from django.conf import settings
from django.db import models

from apps.core.models import TenantOwnedModel


class LeadStage(TenantOwnedModel):
    """Per-business configurable pipeline stage. Seeded with a sensible
    default set when a Business is created (apps.leads.signals), but the
    business can rename/reorder/add/remove stages afterwards — nothing in
    the platform hard-codes stage names."""

    name = models.CharField(max_length=100)
    order = models.PositiveIntegerField(default=0)
    is_won = models.BooleanField(default=False)
    is_lost = models.BooleanField(default=False)

    class Meta:
        db_table = "leads_stage"
        ordering = ["order"]
        constraints = [
            models.UniqueConstraint(fields=["business", "name"], name="unique_business_stage_name")
        ]

    def __str__(self):
        return self.name


class Lead(TenantOwnedModel):
    agent = models.ForeignKey("agents.Agent", on_delete=models.CASCADE, related_name="leads")
    conversation = models.ForeignKey(
        "conversations.Conversation", on_delete=models.SET_NULL, null=True, blank=True, related_name="leads"
    )
    stage = models.ForeignKey(LeadStage, on_delete=models.PROTECT, related_name="leads")

    name = models.CharField(max_length=255, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=32, blank=True)
    company = models.CharField(max_length=255, blank=True)
    requirement = models.TextField(blank=True)
    budget = models.CharField(max_length=100, blank=True)
    timeline = models.CharField(max_length=100, blank=True)
    custom_fields = models.JSONField(default=dict, blank=True)

    score = models.IntegerField(default=0)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )

    class Meta:
        db_table = "leads_lead"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["business", "stage"]), models.Index(fields=["business", "agent"])]

    def __str__(self):
        return self.name or self.email or f"Lead {self.id}"


class LeadActivity(TenantOwnedModel):
    class ActivityType(models.TextChoices):
        NOTE = "note", "Note"
        STAGE_CHANGE = "stage_change", "Stage Change"
        ASSIGNMENT = "assignment", "Assignment"
        AI_ACTION = "ai_action", "AI Action"

    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name="activities")
    activity_type = models.CharField(max_length=20, choices=ActivityType.choices)
    content = models.TextField(blank=True)
    actor_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+",
        help_text="Null when the actor is 'ai' or 'system' — see actor_label.",
    )
    actor_label = models.CharField(max_length=32, default="system", help_text="'ai', 'system', or a display label.")

    class Meta:
        db_table = "leads_lead_activity"
        ordering = ["-created_at"]
