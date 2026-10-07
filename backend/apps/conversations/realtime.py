from apps.core.realtime import broadcast_business_event


def broadcast_message_created(message) -> None:
    broadcast_business_event(
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
    broadcast_business_event(
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
