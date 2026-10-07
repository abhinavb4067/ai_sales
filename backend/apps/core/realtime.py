from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer


def broadcast_business_event(business_id, event: str, data: dict) -> None:
    """Shared low-level broadcast used by every app that pushes real-time
    updates to the dashboard (apps.conversations.realtime,
    apps.leads.realtime, ...) — one Channels group per business
    (apps.conversations.consumers.ConversationConsumer joins it), so
    every app just needs an event name + a JSON-able payload, never its
    own group-naming/channel-layer logic.
    """
    channel_layer = get_channel_layer()
    if channel_layer is None:
        # No channel layer configured (e.g. some test environments) —
        # real-time is a UI enhancement, never a requirement for the
        # request/response pipeline to function.
        return
    async_to_sync(channel_layer.group_send)(
        f"business_{business_id}",
        {"type": "conversation.event", "payload": {"event": event, **data}},
    )
