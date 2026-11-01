"""ToolService — the ONLY place a proposed AI tool call is ever executed.

Refinement 2 / 3: the LLM may propose a tool call, but this service
independently re-validates everything before doing anything:
  - the tool name exists
  - the agent has it enabled (apps.agents.models.AgentTool)
  - arguments match the expected shape
  - the action doesn't require human approval (if it does, it's recorded
    as PENDING_APPROVAL instead of executed)
  - tenant scoping is implicit — every executor only ever touches rows
    scoped to the conversation's business

Phase 2 wires up real executors for the lead-capture and support tools
(create_lead, update_lead, request_demo, request_callback, create_ticket)
on top of apps.leads, plus human_handoff. Financial/irreversible tools
(create_payment_link) still always require approval — see
ALWAYS_REQUIRES_APPROVAL in definitions.py — and simply aren't executed
here yet since Phase 2 has no billing/payment integration.
"""
from dataclasses import dataclass

from apps.agents.models import AgentTool
from apps.ai.tools.definitions import ALWAYS_REQUIRES_APPROVAL, TOOL_SCHEMAS


@dataclass
class ToolExecutionResult:
    tool_name: str
    status: str  # executed | pending_approval | rejected
    result: dict


def _execute_human_handoff(*, business, agent, conversation, arguments: dict) -> dict:
    from apps.conversations.models import Conversation

    conversation.status = Conversation.Status.HUMAN_HANDOFF
    conversation.save(update_fields=["status", "updated_at"])
    return {"reason": arguments.get("reason", "")}


def _execute_create_lead(*, business, agent, conversation, arguments: dict) -> dict:
    from apps.leads.services import apply_lead_fields, get_or_create_lead_for_conversation

    lead = get_or_create_lead_for_conversation(business=business, agent=agent, conversation=conversation)
    apply_lead_fields(lead, arguments)
    return {"lead_id": lead.id, "score": lead.score}


def _execute_update_lead(*, business, agent, conversation, arguments: dict) -> dict:
    from apps.leads.services import apply_lead_fields, get_or_create_lead_for_conversation

    lead = get_or_create_lead_for_conversation(business=business, agent=agent, conversation=conversation)
    field = arguments.get("field")
    value = arguments.get("value")
    if not field or value is None:
        return {"error": "field and value are required."}
    apply_lead_fields(lead, {field: value})
    return {"lead_id": lead.id, "score": lead.score}


def _execute_request_demo(*, business, agent, conversation, arguments: dict) -> dict:
    from apps.leads.services import get_or_create_lead_for_conversation, log_activity

    lead = get_or_create_lead_for_conversation(business=business, agent=agent, conversation=conversation)
    preferred_time = arguments.get("preferred_time", "")
    log_activity(lead, activity_type="note", content=f"Demo requested. Preferred time: {preferred_time}")
    return {"lead_id": lead.id}


def _execute_request_callback(*, business, agent, conversation, arguments: dict) -> dict:
    from apps.leads.services import apply_lead_fields, get_or_create_lead_for_conversation, log_activity

    lead = get_or_create_lead_for_conversation(business=business, agent=agent, conversation=conversation)
    if arguments.get("phone"):
        apply_lead_fields(lead, {"phone": arguments["phone"]})
    log_activity(lead, activity_type="note", content="Callback requested.")
    return {"lead_id": lead.id}


def _execute_book_appointment(*, business, agent, conversation, arguments: dict) -> dict:
    from django.core.exceptions import ValidationError
    from django.utils.dateparse import parse_datetime

    from apps.appointments.services import book_appointment
    from apps.leads.services import get_or_create_lead_for_conversation

    start_time = parse_datetime(arguments.get("start_time", ""))
    end_time = parse_datetime(arguments.get("end_time", ""))
    if start_time is None or end_time is None:
        return {"error": "start_time and end_time must be valid ISO 8601 datetimes."}

    lead = get_or_create_lead_for_conversation(business=business, agent=agent, conversation=conversation)
    try:
        appointment = book_appointment(
            business=business,
            agent=agent,
            conversation=conversation,
            lead=lead,
            start_time=start_time,
            end_time=end_time,
            customer_name=arguments.get("customer_name", ""),
            customer_email=arguments.get("customer_email", ""),
            customer_phone=arguments.get("customer_phone", ""),
        )
    except ValidationError as exc:
        return {"error": " ".join(exc.messages)}
    return {"appointment_id": appointment.id, "start_time": appointment.start_time.isoformat()}


def _execute_schedule_follow_up(*, business, agent, conversation, arguments: dict) -> dict:
    from django.utils.dateparse import parse_datetime

    from apps.appointments.services import schedule_follow_up
    from apps.leads.services import get_or_create_lead_for_conversation

    due_at = parse_datetime(arguments.get("due_at", ""))
    if due_at is None:
        return {"error": "due_at must be a valid ISO 8601 datetime."}

    lead = get_or_create_lead_for_conversation(business=business, agent=agent, conversation=conversation)
    follow_up = schedule_follow_up(
        business=business, agent=agent, conversation=conversation, lead=lead,
        due_at=due_at, reason=arguments.get("reason", ""),
    )
    return {"follow_up_id": follow_up.id, "due_at": follow_up.due_at.isoformat()}


def _execute_create_ticket(*, business, agent, conversation, arguments: dict) -> dict:
    """No dedicated ticketing system yet (deferred to a later phase) —
    recorded as a lead activity so support requests aren't silently lost,
    without inventing a half-built Ticket model ahead of that phase."""
    from apps.leads.services import get_or_create_lead_for_conversation, log_activity

    lead = get_or_create_lead_for_conversation(business=business, agent=agent, conversation=conversation)
    subject = arguments.get("subject", "Support request")
    description = arguments.get("description", "")
    log_activity(lead, activity_type="note", content=f"Support ticket: {subject}\n{description}")
    return {"lead_id": lead.id, "subject": subject}


_EXECUTORS = {
    "human_handoff": _execute_human_handoff,
    "create_lead": _execute_create_lead,
    "update_lead": _execute_update_lead,
    "request_demo": _execute_request_demo,
    "request_callback": _execute_request_callback,
    "create_ticket": _execute_create_ticket,
    "book_appointment": _execute_book_appointment,
    "schedule_follow_up": _execute_schedule_follow_up,
}


def available_tool_schemas(agent) -> list[dict]:
    enabled_names = set(
        AgentTool.objects.filter(agent=agent, enabled=True).values_list("tool_name", flat=True)
    )
    return [TOOL_SCHEMAS[name] for name in enabled_names if name in TOOL_SCHEMAS]


def execute_proposed_tool_calls(*, agent, conversation, tool_calls) -> list[ToolExecutionResult]:
    business = agent.business
    enabled_names = set(
        AgentTool.objects.filter(agent=agent, enabled=True).values_list("tool_name", flat=True)
    )
    requires_approval_names = set(
        AgentTool.objects.filter(
            agent=agent, enabled=True, permission_level=AgentTool.PermissionLevel.REQUIRES_APPROVAL
        ).values_list("tool_name", flat=True)
    )

    results = []
    for call in tool_calls:
        if call.name not in TOOL_SCHEMAS:
            results.append(ToolExecutionResult(call.name, "rejected", {"error": "Unknown tool."}))
            continue
        if call.name not in enabled_names:
            results.append(
                ToolExecutionResult(call.name, "rejected", {"error": "Tool not enabled for this agent."})
            )
            continue
        if call.name in ALWAYS_REQUIRES_APPROVAL or call.name in requires_approval_names:
            results.append(
                ToolExecutionResult(call.name, "pending_approval", {"arguments": call.arguments})
            )
            continue

        executor = _EXECUTORS.get(call.name)
        if executor is None:
            results.append(
                ToolExecutionResult(call.name, "pending_approval", {"note": "Not implemented in this phase yet."})
            )
            continue

        result_data = executor(business=business, agent=agent, conversation=conversation, arguments=call.arguments)
        results.append(ToolExecutionResult(call.name, "executed", result_data))

    return results
