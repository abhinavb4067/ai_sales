from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel


class Business(TimeStampedModel):
    """A tenant. Deliberately generic — no industry-specific fields.
    `industry` is optional free text, never a hard-coded choice list, so
    the platform never assumes what kind of business is using it."""

    name = models.CharField(max_length=255)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="owned_businesses"
    )
    email = models.EmailField()
    website = models.URLField(blank=True)
    industry = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    logo = models.ImageField(upload_to="business_logos/", null=True, blank=True)
    timezone = models.CharField(max_length=64, default="UTC")
    currency = models.CharField(max_length=8, default="USD")

    class Meta:
        db_table = "tenants_business"

    def __str__(self):
        return self.name


class BusinessMembership(TimeStampedModel):
    class Role(models.TextChoices):
        OWNER = "owner", "Owner"
        ADMIN = "admin", "Admin"
        SALES = "sales", "Sales"
        SUPPORT = "support", "Support"
        VIEWER = "viewer", "Viewer"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        ACTIVE = "active", "Active"
        REVOKED = "revoked", "Revoked"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="memberships")
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="memberships")
    role = models.CharField(max_length=16, choices=Role.choices, default=Role.VIEWER)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    joined_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "tenants_business_membership"
        constraints = [
            models.UniqueConstraint(fields=["user", "business"], name="unique_user_business_membership")
        ]
        indexes = [models.Index(fields=["business", "status"])]

    def __str__(self):
        return f"{self.user_id} @ {self.business_id} ({self.role})"
