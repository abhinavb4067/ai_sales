"""JSON-schema tool definitions offered to the AI provider. This is the
full catalog of tools the platform knows about; which ones a given agent
may actually use is controlled by apps.agents.models.AgentTool
(enabled + permission_level), checked in apps.ai.tools.service before
anything here is ever executed.
"""

TOOL_SCHEMAS = {
    "create_lead": {
        "name": "create_lead",
        "description": "Record a new sales lead captured during this conversation.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "email": {"type": "string"},
                "phone": {"type": "string"},
                "company": {"type": "string"},
                "requirement": {"type": "string"},
            },
            "required": [],
        },
    },
    "update_lead": {
        "name": "update_lead",
        "description": "Update information on an existing lead for this conversation.",
        "parameters": {
            "type": "object",
            "properties": {
                "field": {"type": "string"},
                "value": {"type": "string"},
            },
            "required": ["field", "value"],
        },
    },
    "request_demo": {
        "name": "request_demo",
        "description": "Record that the customer requested a product demo.",
        "parameters": {"type": "object", "properties": {"preferred_time": {"type": "string"}}},
    },
    "request_callback": {
        "name": "request_callback",
        "description": "Record that the customer requested a callback.",
        "parameters": {"type": "object", "properties": {"phone": {"type": "string"}}},
    },
    "create_ticket": {
        "name": "create_ticket",
        "description": "Create a customer support ticket for an issue that needs follow-up.",
        "parameters": {
            "type": "object",
            "properties": {"subject": {"type": "string"}, "description": {"type": "string"}},
            "required": ["subject"],
        },
    },
    "create_payment_link": {
        "name": "create_payment_link",
        "description": "Generate a payment link for the customer. Financial action — always requires approval.",
        "parameters": {"type": "object", "properties": {"amount": {"type": "number"}, "currency": {"type": "string"}}},
    },
    "create_quote": {
        "name": "create_quote",
        "description": "Prepare a price quote for the customer.",
        "parameters": {"type": "object", "properties": {"details": {"type": "string"}}},
    },
    "book_appointment": {
        "name": "book_appointment",
        "description": "Book an appointment/meeting with the customer at a specific start/end time "
        "(ISO 8601, e.g. 2026-11-05T15:00:00+05:30). Rejected server-side if the slot conflicts "
        "with an existing appointment.",
        "parameters": {
            "type": "object",
            "properties": {
                "start_time": {"type": "string", "description": "ISO 8601 datetime."},
                "end_time": {"type": "string", "description": "ISO 8601 datetime."},
                "customer_name": {"type": "string"},
                "customer_email": {"type": "string"},
                "customer_phone": {"type": "string"},
            },
            "required": ["start_time", "end_time"],
        },
    },
    "schedule_follow_up": {
        "name": "schedule_follow_up",
        "description": "Schedule a future follow-up/check-in with the customer (not a calendared appointment).",
        "parameters": {
            "type": "object",
            "properties": {
                "due_at": {"type": "string", "description": "ISO 8601 datetime."},
                "reason": {"type": "string"},
            },
            "required": ["due_at"],
        },
    },
    "human_handoff": {
        "name": "human_handoff",
        "description": "Escalate this conversation to a human team member.",
        "parameters": {"type": "object", "properties": {"reason": {"type": "string"}}},
    },
}

# Tools that always require human approval regardless of the per-agent
# AgentTool.permission_level setting — irreversible/financial actions.
ALWAYS_REQUIRES_APPROVAL = {"create_payment_link"}
