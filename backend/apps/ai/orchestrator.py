"""AI orchestration pipeline — the single "brain" every channel talks to.

receive_message() is intentionally the only public entry point. The
playground (Phase 1) and, later, the website widget / public Chat API /
WhatsApp / Telegram all call this exact function — none of them get a
simplified or alternate implementation (per the "don't build a throwaway
architecture" instruction). What differs between channels is only how
`agent` and `conversation` get resolved before this is called, and how
the response is transported back (sync HTTP for playground/API,
WebSocket push for widget/dashboard).
"""
from dataclasses import dataclass

from apps.ai.escalation import check_escalation_rules
from apps.ai.prompt_builder import build_messages
from apps.ai.providers.registry import get_provider_for_agent
from apps.ai.tools.service import available_tool_schemas, execute_proposed_tool_calls
from apps.knowledge.services import retrieve_context


@dataclass
class OrchestrationResult:
    content: str
    tool_results: list
    input_tokens: int
    output_tokens: int
    knowledge_chunks_used: int
    escalated: bool = False


def receive_message(*, agent, conversation, history: list[dict], customer_message: str) -> OrchestrationResult:
    """
    Pipeline:
      load knowledge -> build prompt (instruction hierarchy) ->
      check available tools -> call AI provider -> execute approved
      tool calls -> return normalized result for the caller to persist.

    Persisting the resulting Message rows is left to the caller
    (apps.conversations) so this function has no side effects beyond tool
    execution, and stays trivially testable/reusable across channels.
    """
    escalated = check_escalation_rules(agent=agent, conversation=conversation, customer_message=customer_message)

    knowledge_chunks = retrieve_context(
        business_id=agent.business_id,
        agent_id=agent.id,
        query=customer_message,
        top_k=5,
    )

    messages = build_messages(
        agent=agent,
        history=history,
        knowledge_chunks=knowledge_chunks,
        customer_message=customer_message,
    )

    tools = available_tool_schemas(agent)
    provider = get_provider_for_agent(agent)

    response = provider.generate(
        messages=messages,
        tools=tools if tools else None,
        temperature=agent.temperature,
        max_tokens=agent.max_tokens,
    )

    tool_results = []
    if response.tool_calls:
        tool_results = execute_proposed_tool_calls(
            agent=agent, conversation=conversation, tool_calls=response.tool_calls
        )

    return OrchestrationResult(
        content=response.content,
        tool_results=tool_results,
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
        knowledge_chunks_used=len(knowledge_chunks),
        escalated=escalated,
    )
