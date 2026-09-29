from dataclasses import dataclass

from apps.ai.orchestrator import receive_message
from apps.apikeys.models import UsageEvent
from apps.billing.services import enforce_subscription_and_limits
from apps.conversations.models import Message
from apps.conversations.realtime import broadcast_conversation_updated, broadcast_message_created


@dataclass
class ChatTurn:
    conversation: object
    ai_message: Message
    result: object


def conversation_history_for_prompt(conversation, exclude_message_id=None) -> list[dict]:
    role_map = {
        Message.SenderType.CUSTOMER: "user",
        Message.SenderType.AI: "assistant",
        Message.SenderType.AGENT_USER: "assistant",
    }
    history = []
    qs = conversation.messages.exclude(sender_type=Message.SenderType.SYSTEM).order_by("created_at")
    if exclude_message_id:
        qs = qs.exclude(id=exclude_message_id)
    for msg in qs:
        role = role_map.get(msg.sender_type)
        if role:
            history.append({"role": role, "content": msg.content})
    return history


def run_chat_turn(*, business, agent, conversation, message, api_key=None) -> ChatTurn:
    """The single AI Agent Core pipeline — every channel (playground,
    public API, website widget, WhatsApp/future integrations) calls this
    exact function. Auth, rate limiting, and how the Conversation is
    looked up/created differ per channel; the orchestration, message
    persistence, real-time broadcast, and usage logging never do.
    """
    enforce_subscription_and_limits(business)

    history = conversation_history_for_prompt(conversation)

    customer_message = Message.objects.create(
        business=business,
        conversation=conversation,
        sender_type=Message.SenderType.CUSTOMER,
        content=message,
    )
    broadcast_message_created(customer_message)

    result = receive_message(
        agent=agent,
        conversation=conversation,
        history=history,
        customer_message=message,
    )

    ai_message = Message.objects.create(
        business=business,
        conversation=conversation,
        sender_type=Message.SenderType.AI,
        content=result.content,
        metadata={
            "input_tokens": result.input_tokens,
            "output_tokens": result.output_tokens,
            "knowledge_chunks_used": result.knowledge_chunks_used,
        },
        tool_calls=[
            {"tool_name": r.tool_name, "status": r.status, "result": r.result}
            for r in result.tool_results
        ]
        or None,
    )

    conversation.last_activity_at = ai_message.created_at
    conversation.save(update_fields=["last_activity_at"])

    broadcast_message_created(ai_message)
    broadcast_conversation_updated(conversation)

    UsageEvent.objects.create(
        business=business,
        agent=agent,
        api_key=api_key,
        channel=conversation.channel,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
    )

    return ChatTurn(conversation=conversation, ai_message=ai_message, result=result)
