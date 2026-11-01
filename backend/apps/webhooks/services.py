"""Outbound webhook dispatch — the entry point every event source
(apps.leads.services, apps.ai.tools.service, apps.appointments.services)
calls. Deliberately only wired at coarse, meaningful business events
(lead created/stage changed, human handoff, appointment booked/
cancelled) — NOT at the high-frequency message.created/conversation.
updated real-time events (apps.conversations.realtime), which would
otherwise fire a webhook on every single AI reply.
"""
import logging

from apps.webhooks.models import OutboundWebhookDelivery, WebhookSubscription

logger = logging.getLogger(__name__)


def dispatch_event(business, event_type: str, data: dict) -> None:
    subscriptions = WebhookSubscription.objects.filter(business=business, is_active=True)
    for subscription in subscriptions:
        if not subscription.wants_event(event_type):
            continue
        delivery = OutboundWebhookDelivery.objects.create(
            business=business,
            subscription=subscription,
            event_type=event_type,
            payload=data,
        )
        from apps.webhooks.tasks import deliver_webhook_task

        deliver_webhook_task.delay(delivery.id)
