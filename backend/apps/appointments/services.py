"""Appointment/FollowUp service layer — used by both the dashboard API
and the AI tool executor (apps.ai.tools.service._execute_book_appointment).
Conflict checking lives here, server-side, so neither the dashboard form
nor the LLM can double-book a slot by skipping validation.
"""
from django.core.exceptions import ValidationError
from django.db import transaction

from apps.appointments.models import Appointment, FollowUp
from apps.webhooks.services import dispatch_event


def has_conflict(*, business, assigned_to, start_time, end_time, exclude_id=None) -> bool:
    if assigned_to is None:
        return False
    qs = Appointment.objects.filter(
        business=business,
        assigned_to=assigned_to,
        start_time__lt=end_time,
        end_time__gt=start_time,
    ).exclude(status=Appointment.Status.CANCELLED)
    if exclude_id:
        qs = qs.exclude(id=exclude_id)
    return qs.exists()


@transaction.atomic
def book_appointment(
    *, business, agent, conversation=None, lead=None, start_time, end_time, assigned_to=None, **fields
) -> Appointment:
    if end_time <= start_time:
        raise ValidationError("end_time must be after start_time.")
    if has_conflict(business=business, assigned_to=assigned_to, start_time=start_time, end_time=end_time):
        raise ValidationError("The selected time conflicts with an existing appointment.")

    appointment = Appointment.objects.create(
        business=business,
        agent=agent,
        conversation=conversation,
        lead=lead,
        start_time=start_time,
        end_time=end_time,
        assigned_to=assigned_to,
        **fields,
    )
    dispatch_event(business, "appointment.booked", {
        "appointment_id": appointment.id, "agent_id": agent.id,
        "start_time": start_time.isoformat(), "end_time": end_time.isoformat(),
    })
    return appointment


def reschedule_appointment(appointment: Appointment, *, start_time, end_time) -> Appointment:
    if end_time <= start_time:
        raise ValidationError("end_time must be after start_time.")
    if has_conflict(
        business=appointment.business,
        assigned_to=appointment.assigned_to,
        start_time=start_time,
        end_time=end_time,
        exclude_id=appointment.id,
    ):
        raise ValidationError("The selected time conflicts with an existing appointment.")
    appointment.start_time = start_time
    appointment.end_time = end_time
    appointment.status = Appointment.Status.SCHEDULED
    appointment.save(update_fields=["start_time", "end_time", "status", "updated_at"])
    return appointment


def cancel_appointment(appointment: Appointment) -> Appointment:
    appointment.status = Appointment.Status.CANCELLED
    appointment.save(update_fields=["status", "updated_at"])
    dispatch_event(appointment.business, "appointment.cancelled", {"appointment_id": appointment.id})
    return appointment


def schedule_follow_up(*, business, agent, conversation=None, lead=None, due_at, reason="", assigned_to=None) -> FollowUp:
    return FollowUp.objects.create(
        business=business,
        agent=agent,
        conversation=conversation,
        lead=lead,
        due_at=due_at,
        reason=reason,
        assigned_to=assigned_to,
    )
