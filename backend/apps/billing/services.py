from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from apps.apikeys.models import UsageEvent
from apps.billing.models import Plan, Subscription
from apps.core.exceptions import APIError

ACTIVE_STATUSES = {Subscription.Status.TRIAL, Subscription.Status.ACTIVE}


def start_trial_subscription(business) -> Subscription:
    plan = Plan.objects.filter(is_default=True, is_active=True).first()
    if plan is None:
        plan = Plan.objects.filter(is_active=True).order_by("sort_order", "monthly_price").first()
    if plan is None:
        raise APIError(code="NO_PLAN_CONFIGURED", message="No billing plan is configured.", status_code=500)

    now = timezone.now()
    trial_ends_at = now + timedelta(days=plan.trial_days)
    return Subscription.objects.create(
        business=business,
        plan=plan,
        status=Subscription.Status.TRIAL,
        current_period_start=now,
        current_period_end=trial_ends_at,
        trial_ends_at=trial_ends_at,
    )


@transaction.atomic
def activate_subscription(
    *, business, plan, provider=Subscription.Provider.MANUAL, external_customer_id="", external_subscription_id=""
) -> Subscription:
    """Used by both the manual "change plan" endpoint today and, later, a
    Stripe/Razorpay webhook handler after a successful payment — the
    activation logic must be identical regardless of who triggered it."""
    subscription, _ = Subscription.objects.select_for_update().get_or_create(
        business=business,
        defaults={
            "plan": plan,
            "current_period_start": timezone.now(),
            "current_period_end": timezone.now() + timedelta(days=30),
        },
    )
    now = timezone.now()
    subscription.plan = plan
    subscription.status = Subscription.Status.ACTIVE
    subscription.current_period_start = now
    subscription.current_period_end = now + timedelta(days=30)
    subscription.cancel_at_period_end = False
    subscription.provider = provider
    subscription.external_customer_id = external_customer_id
    subscription.external_subscription_id = external_subscription_id
    subscription.save()
    return subscription


def _expire_if_trial_lapsed(subscription: Subscription) -> Subscription:
    if subscription.status == Subscription.Status.TRIAL and timezone.now() >= subscription.current_period_end:
        subscription.status = Subscription.Status.EXPIRED
        subscription.save(update_fields=["status", "updated_at"])
    return subscription


def get_current_usage_count(business, subscription: Subscription) -> int:
    return UsageEvent.objects.filter(
        business=business,
        created_at__gte=subscription.current_period_start,
        created_at__lt=subscription.current_period_end,
    ).count()


def enforce_subscription_and_limits(business) -> Subscription:
    """Single chokepoint called from the chat pipeline (apps.conversations
    _run_chat) — every channel (playground, public API, widget) is gated
    identically, no channel can bypass billing by taking a different code
    path.
    """
    try:
        subscription = business.subscription
    except Subscription.DoesNotExist:
        raise APIError(code="NO_SUBSCRIPTION", message="This business has no active subscription.", status_code=402)

    subscription = _expire_if_trial_lapsed(subscription)

    if subscription.status not in ACTIVE_STATUSES:
        raise APIError(
            code="SUBSCRIPTION_INACTIVE",
            message=f"Subscription is {subscription.get_status_display().lower()}. Upgrade to continue.",
            status_code=402,
        )

    limit = subscription.plan.max_messages_per_month
    if limit is not None and get_current_usage_count(business, subscription) >= limit:
        raise APIError(
            code="USAGE_LIMIT_EXCEEDED",
            message=f"Monthly message limit ({limit}) reached for the {subscription.plan.name} plan.",
            status_code=429,
        )

    return subscription


def check_plan_limit(business, *, limit_field: str, current_count: int, resource_name: str) -> None:
    """Generic per-resource cap check (agents, knowledge documents, ...) —
    unlike enforce_subscription_and_limits (per-message, called on every
    chat turn), this is called once at creation time for resources that
    accumulate rather than repeat. Same "null = unlimited" convention as
    every other Plan limit field.
    """
    try:
        subscription = business.subscription
    except Subscription.DoesNotExist:
        raise APIError(code="NO_SUBSCRIPTION", message="This business has no active subscription.", status_code=402)

    limit = getattr(subscription.plan, limit_field)
    if limit is not None and current_count >= limit:
        raise APIError(
            code="PLAN_LIMIT_REACHED",
            message=f"Your {subscription.plan.name} plan allows up to {limit} {resource_name}. "
            "Upgrade your plan to add more.",
            status_code=402,
        )
