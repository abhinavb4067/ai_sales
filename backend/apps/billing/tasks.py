"""Celery Beat periodic billing reconciliation (master spec section 18:
"billing reconciliation", section 16: "renewal/cancellation").

apps.billing.services.enforce_subscription_and_limits already expires a
lapsed trial the next time that business makes a chat request — but a
business that goes quiet right as their trial/period ends would
otherwise show as "trial"/"active" indefinitely in Super Admin/analytics
even though access should have lapsed. These tasks sweep proactively so
subscription status stays accurate regardless of whether the business
is actively using the product.

Both only ever read/write Subscription.status from data already stored
locally (current_period_end) — no external provider API call is made
here (that would need live Razorpay credentials this environment
doesn't have); a webhook or a future task hitting the provider's API
is the next step for genuinely re-verifying a provider-side charge.
"""
import logging
from datetime import timedelta

from celery import shared_task

logger = logging.getLogger(__name__)

# How long an ACTIVE subscription is allowed to sit past its
# current_period_end before being flagged — covers ordinary
# webhook/network delay for a renewal that's actually going to land,
# without flagging on every miss of a few seconds.
PAST_DUE_GRACE_PERIOD = timedelta(days=3)


@shared_task
def expire_lapsed_trials():
    from django.utils import timezone

    from apps.billing.models import Subscription

    count = Subscription.objects.filter(
        status=Subscription.Status.TRIAL, current_period_end__lte=timezone.now()
    ).update(status=Subscription.Status.EXPIRED)
    logger.info("Expired %d lapsed trial subscription(s).", count)
    return count


@shared_task
def flag_past_due_subscriptions():
    from django.utils import timezone

    from apps.billing.models import Subscription

    cutoff = timezone.now() - PAST_DUE_GRACE_PERIOD
    count = Subscription.objects.filter(
        status=Subscription.Status.ACTIVE, current_period_end__lt=cutoff
    ).update(status=Subscription.Status.PAST_DUE)
    logger.info("Flagged %d subscription(s) as past due.", count)
    return count
