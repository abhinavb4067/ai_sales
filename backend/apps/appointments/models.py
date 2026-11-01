from django.conf import settings
from django.db import models

from apps.core.models import TenantOwnedModel


class Appointment(TenantOwnedModel):
    """A scheduled meeting/call with a customer, created either manually
    by an employee or by the AI via the book_appointment tool
    (apps.ai.tools.service). Conflict checking and idempotent booking are
    enforced in apps.appointments.services, not here — the model only
    carries state.
    """

    class Status(models.TextChoices):
        SCHEDULED = "scheduled", "Scheduled"
        CONFIRMED = "confirmed", "Confirmed"
        CANCELLED = "cancelled", "Cancelled"
        COMPLETED = "completed", "Completed"
        NO_SHOW = "no_show", "No Show"

    agent = models.ForeignKey("agents.Agent", on_delete=models.CASCADE, related_name="appointments")
    conversation = models.ForeignKey(
        "conversations.Conversation", on_delete=models.SET_NULL, null=True, blank=True, related_name="appointments"
    )
    lead = models.ForeignKey(
        "leads.Lead", on_delete=models.SET_NULL, null=True, blank=True, related_name="appointments"
    )

    customer_name = models.CharField(max_length=255, blank=True)
    customer_email = models.EmailField(blank=True)
    customer_phone = models.CharField(max_length=32, blank=True)

    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    timezone = models.CharField(max_length=64, default="UTC")

    status = models.CharField(max_length=16, choices=Status.choices, default=Status.SCHEDULED)
    notes = models.TextField(blank=True)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )

    class Meta:
        db_table = "appointments_appointment"
        ordering = ["start_time"]
        indexes = [
            models.Index(fields=["business", "start_time"]),
            models.Index(fields=["business", "assigned_to", "start_time"]),
        ]

    def __str__(self):
        return f"Appointment {self.id} @ {self.start_time.isoformat()}"


class FollowUp(TenantOwnedModel):
    """A scheduled customer touchpoint (reminder/callback/check-in) that
    isn't a calendared appointment. Respecting consent/suppression status
    happens in apps.appointments.services at creation/execution time, not
    as a model constraint, since those rules can change independently of
    the schema.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    agent = models.ForeignKey("agents.Agent", on_delete=models.CASCADE, related_name="follow_ups")
    conversation = models.ForeignKey(
        "conversations.Conversation", on_delete=models.SET_NULL, null=True, blank=True, related_name="follow_ups"
    )
    lead = models.ForeignKey(
        "leads.Lead", on_delete=models.SET_NULL, null=True, blank=True, related_name="follow_ups"
    )

    due_at = models.DateTimeField()
    reason = models.TextField(blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    # Set the first time the overdue-detection task (see
    # apps.appointments.tasks.flag_overdue_follow_ups) surfaces this
    # follow-up as overdue — prevents it from re-notifying staff on every
    # scheduled run for the same still-pending follow-up.
    overdue_notified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "appointments_followup"
        ordering = ["due_at"]
        indexes = [models.Index(fields=["business", "status", "due_at"])]

    def __str__(self):
        return f"FollowUp {self.id} due {self.due_at.isoformat()}"
