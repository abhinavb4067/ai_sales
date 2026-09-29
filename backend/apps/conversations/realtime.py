from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer


def _broadcast(business_id, event: str, data: dict) -> None:
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


def broadcast_message_created(message) -> None:
    _broadcast(
        message.business_id,
        "message.created",
        {
            "conversation_id": message.conversation_id,
            "message": {
                "id": message.id,
                "sender_type": message.sender_type,
                "content_type": message.content_type,
                "content": message.content,
                "created_at": message.created_at.isoformat(),
            },
        },
    )


def broadcast_conversation_updated(conversation) -> None:
    _broadcast(
        conversation.business_id,
        "conversation.updated",
        {
            "conversation": {
                "id": conversation.id,
                "agent_id": conversation.agent_id,
                "channel": conversation.channel,
                "status": conversation.status,
                "last_activity_at": conversation.last_activity_at.isoformat(),
            },
        },
    )
