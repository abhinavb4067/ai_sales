import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task
def flag_overdue_follow_ups():
    """Celery Beat periodic task (see config.celery CELERY_BEAT_SCHEDULE)
    — surfaces FollowUps whose due_at has passed and are still PENDING,
    so staff see them without a human needing to notice. Deliberately
    does not auto-send anything (e.g. a WhatsApp template) on its own —
    that would need a business-approved template configured per
    business, which doesn't exist yet; this task's job is making the
    overdue follow-up visible, not acting on it unsupervised.
    """
    from django.utils import timezone

    from apps.appointments.models import FollowUp
    from apps.leads.services import log_activity

    overdue = FollowUp.objects.filter(
        status=FollowUp.Status.PENDING,
        due_at__lt=timezone.now(),
        overdue_notified_at__isnull=True,
    ).select_related("lead")

    count = 0
    for follow_up in overdue:
        if follow_up.lead_id:
            log_activity(
                follow_up.lead,
                activity_type="note",
                content=f"Follow-up overdue (was due {follow_up.due_at.isoformat()}): {follow_up.reason or 'no reason given'}",
                actor_label="system",
            )
        follow_up.overdue_notified_at = timezone.now()
        follow_up.save(update_fields=["overdue_notified_at", "updated_at"])
        count += 1

    logger.info("Flagged %d overdue follow-up(s).", count)
    return count
