"""Business-defined escalation rules (Refinement 13 / §14).

Independent of whatever the AI decides to propose — a business owner can
configure trigger phrases (e.g. "cancel my subscription", "legal",
"complaint") on Agent.escalation_rules, and if the customer's message
matches one, the conversation is force-escalated to HUMAN_HANDOFF
regardless of what the model says. This runs BEFORE the AI call so a
matched conversation is flagged even if the provider call fails.
"""
from apps.agents.models import AgentTool
from apps.conversations.models import Conversation


def check_escalation_rules(*, agent, conversation, customer_message: str) -> bool:
    """Returns True if the conversation was escalated."""
    rules = agent.escalation_rules or []
    if not rules:
        return False

    message_lower = customer_message.lower()
    matched = any(str(rule).lower() in message_lower for rule in rules)
    if not matched:
        return False

    conversation.status = Conversation.Status.HUMAN_HANDOFF
    conversation.save(update_fields=["status", "updated_at"])
    return True
