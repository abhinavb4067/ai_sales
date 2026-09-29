import json

from apps.conversations.models import Conversation
from apps.conversations.services import run_chat_turn
from apps.integrations.models import Integration, WebhookDelivery
from apps.integrations.providers.registry import get_integration_provider


def get_or_create_conversation(*, business, agent, channel, external_customer_ref) -> Conversation:
    """No conversation_id exists on an inbound channel message the way it
    does on the widget/API (the customer never sends one) — so channel
    conversations are threaded by the most recent non-resolved
    conversation for that external ref, and a fresh one is started
    whenever the last one was resolved."""
    conversation = (
        Conversation.objects.filter(
            business=business,
            agent=agent,
            channel=channel,
            external_customer_ref=external_customer_ref,
        )
        .exclude(status=Conversation.Status.RESOLVED)
        .order_by("-last_activity_at")
        .first()
    )
    if conversation:
        return conversation

    return Conversation.objects.create(
        business=business,
        agent=agent,
        channel=channel,
        external_customer_ref=external_customer_ref,
    )


def handle_inbound_webhook(*, integration: Integration, raw_payload: bytes, headers: dict) -> WebhookDelivery:
    provider = get_integration_provider(integration.provider)
    signature_valid = provider.verify_webhook_signature(payload=raw_payload, headers=headers, integration=integration)

    payload = json.loads(raw_payload or b"{}")
    delivery = WebhookDelivery.objects.create(
        business=integration.business,
        integration=integration,
        signature_valid=signature_valid,
        payload=payload,
    )

    if not signature_valid:
        delivery.error = "Invalid webhook signature."
        delivery.save(update_fields=["error", "updated_at"])
        return delivery

    if integration.status != Integration.Status.ACTIVE:
        delivery.error = "Integration is disabled."
        delivery.save(update_fields=["error", "updated_at"])
        return delivery

    try:
        for inbound in provider.parse_webhook_payload(payload):
            if not inbound.text:
                continue

            conversation = get_or_create_conversation(
                business=integration.business,
                agent=integration.agent,
                channel=Conversation.Channel.WHATSAPP,
                external_customer_ref=inbound.external_conversation_ref,
            )
            turn = run_chat_turn(
                business=integration.business,
                agent=integration.agent,
                conversation=conversation,
                message=inbound.text,
            )
            provider.send_message(
                integration=integration,
                to_ref=inbound.external_conversation_ref,
                text=turn.result.content,
            )
    except Exception as exc:  # noqa: BLE001 — always ack the webhook; the
        # provider will retry-storm a non-2xx response, so failures are
        # logged for operator visibility instead of propagated.
        delivery.error = str(exc)

    delivery.processed = True
    delivery.save(update_fields=["processed", "error", "updated_at"])
    return delivery
