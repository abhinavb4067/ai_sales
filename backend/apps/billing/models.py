from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel


class Plan(TimeStampedModel):
    """A subscription tier. Limits are configuration, never hard-coded —
    apps.billing.services reads these fields instead of any magic numbers
    scattered through the codebase, so adding/changing a tier is a data
    change, not a deploy."""

    code = models.SlugField(max_length=64, unique=True)
    name = models.CharField(max_length=128)
    description = models.TextField(blank=True)

    monthly_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    currency = models.CharField(max_length=8, default="USD")

    max_agents = models.PositiveIntegerField(null=True, blank=True, help_text="Null = unlimited.")
    max_messages_per_month = models.PositiveIntegerField(null=True, blank=True, help_text="Null = unlimited.")
    max_knowledge_documents = models.PositiveIntegerField(null=True, blank=True, help_text="Null = unlimited.")
    max_team_members = models.PositiveIntegerField(null=True, blank=True, help_text="Null = unlimited.")

    trial_days = models.PositiveIntegerField(default=14)
    is_default = models.BooleanField(
        default=False, help_text="The plan a new business's trial subscription starts on."
    )
    is_public = models.BooleanField(default=True, help_text="Shown to customers as purchasable.")
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "billing_plan"
        ordering = ["sort_order", "monthly_price"]

    def __str__(self):
        return self.name


class Subscription(TimeStampedModel):
    """One active subscription per business. Deliberately never deleted on
    expiry/cancellation — status changes, the row (and any API keys tied to
    the business) stay put, per the "don't delete access, gate it" rule
    from the architecture doc."""

    class Status(models.TextChoices):
        TRIAL = "trial", "Trial"
        ACTIVE = "active", "Active"
        PAST_DUE = "past_due", "Past Due"
        SUSPENDED = "suspended", "Suspended"
        CANCELLED = "cancelled", "Cancelled"
        EXPIRED = "expired", "Expired"

    class Provider(models.TextChoices):
        MANUAL = "manual", "Manual"
        STRIPE = "stripe", "Stripe"
        RAZORPAY = "razorpay", "Razorpay"

    business = models.OneToOneField(
        "tenants.Business", on_delete=models.CASCADE, related_name="subscription"
    )
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT, related_name="subscriptions")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.TRIAL)

    current_period_start = models.DateTimeField()
    current_period_end = models.DateTimeField()
    trial_ends_at = models.DateTimeField(null=True, blank=True)
    cancel_at_period_end = models.BooleanField(default=False)

    provider = models.CharField(max_length=16, choices=Provider.choices, default=Provider.MANUAL)
    external_customer_id = models.CharField(max_length=255, blank=True)
    external_subscription_id = models.CharField(max_length=255, blank=True)

    class Meta:
        db_table = "billing_subscription"
        indexes = [models.Index(fields=["status"])]

    def __str__(self):
        return f"{self.business_id} — {self.plan.code} ({self.status})"
