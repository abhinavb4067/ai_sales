"""Business-facing dashboard analytics (master spec section 17).

Every number here is a single indexed, business-scoped, time-bounded
query — no unbounded full-table scans. At current scale this computing
on read is cheap enough; if/when it isn't, this is the one function to
replace with reads against a precomputed aggregate table/Celery job
without touching the view or serializer.
"""
from datetime import timedelta

from django.db.models import Count, Sum
from django.utils import timezone

from apps.apikeys.models import UsageEvent
from apps.appointments.models import Appointment
from apps.conversations.models import Conversation
from apps.leads.models import Lead


def business_overview(business, *, days: int = 30) -> dict:
    since = timezone.now() - timedelta(days=days)

    conversations = Conversation.objects.filter(business=business)
    conversations_in_window = conversations.filter(created_at__gte=since)

    channel_breakdown = dict(
        conversations_in_window.values_list("channel").annotate(count=Count("id"))
    )

    leads = Lead.objects.filter(business=business)
    leads_in_window = leads.filter(created_at__gte=since)

    usage = UsageEvent.objects.filter(business=business, created_at__gte=since).aggregate(
        input_tokens=Sum("input_tokens"), output_tokens=Sum("output_tokens")
    )

    subscription = getattr(business, "subscription", None)
    usage_against_plan = None
    if subscription is not None:
        from apps.billing.services import get_current_usage_count

        limit = subscription.plan.max_messages_per_month
        used = get_current_usage_count(business, subscription)
        usage_against_plan = {
            "plan": subscription.plan.name,
            "messages_used": used,
            "messages_limit": limit,
        }

    return {
        "window_days": days,
        "total_conversations": conversations.count(),
        "conversations_last_window": conversations_in_window.count(),
        "active_conversations": conversations.exclude(status=Conversation.Status.RESOLVED).count(),
        "human_handoff_conversations": conversations.filter(status=Conversation.Status.HUMAN_HANDOFF).count(),
        "channel_breakdown": channel_breakdown,
        "leads_captured_last_window": leads_in_window.count(),
        "qualified_leads_last_window": leads_in_window.filter(score__gte=50).count(),
        "appointments_upcoming": Appointment.objects.filter(
            business=business, start_time__gte=timezone.now(), status=Appointment.Status.SCHEDULED
        ).count(),
        "ai_input_tokens_last_window": usage["input_tokens"] or 0,
        "ai_output_tokens_last_window": usage["output_tokens"] or 0,
        "usage_against_plan": usage_against_plan,
    }
