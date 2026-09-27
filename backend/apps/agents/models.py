import uuid

from django.db import models

from apps.core.models import TenantOwnedModel


class Agent(TenantOwnedModel):
    """A configured AI agent belonging to a Business.

    `agent_type` and `primary_goal`/`secondary_goals` are kept as
    TextChoices for now (clear validation, simple migrations) rather than
    a lookup table — but nothing in the orchestration layer switches on
    these values with hard-coded branching; they only steer prompt
    construction and tool availability (see apps.ai.prompt_builder), so
    adding a new goal/type later is a choices-list change, not a
    behavioral rewrite.
    """

    class AgentType(models.TextChoices):
        SALES = "sales", "Sales"
        SUPPORT = "support", "Support"
        COMBINED = "combined", "Combined"

    class Goal(models.TextChoices):
        SALES = "sales", "Sales"
        CUSTOMER_SUPPORT = "customer_support", "Customer Support"
        SALES_AND_SUPPORT = "sales_and_support", "Sales & Support"
        LEAD_GENERATION = "lead_generation", "Lead Generation"
        INFORMATION = "information", "Information"

    class Tone(models.TextChoices):
        PROFESSIONAL = "professional", "Professional"
        FRIENDLY = "friendly", "Friendly"
        CASUAL = "casual", "Casual"
        FORMAL = "formal", "Formal"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        ACTIVE = "active", "Active"
        DISABLED = "disabled", "Disabled"

    # Public, non-secret identifier — safe to embed in widget snippets later
    # (Phase 3). Generated now so no migration is needed to add it then.
    public_widget_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_index=True)

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    agent_type = models.CharField(max_length=16, choices=AgentType.choices, default=AgentType.COMBINED)

    primary_goal = models.CharField(max_length=32, choices=Goal.choices, default=Goal.SALES_AND_SUPPORT)
    secondary_goals = models.JSONField(default=list, blank=True)

    # Personality / behavior configuration
    system_prompt = models.TextField(
        blank=True,
        help_text="Business-authored instructions. Rendered as AGENT CONFIGURATION "
        "in the prompt hierarchy — cannot override SYSTEM instructions.",
    )
    greeting = models.TextField(blank=True)
    language = models.CharField(max_length=16, default="en")
    tone = models.CharField(max_length=16, choices=Tone.choices, default=Tone.PROFESSIONAL)
    must_always_mention = models.JSONField(default=list, blank=True)
    must_never_say = models.JSONField(default=list, blank=True)
    escalation_rules = models.JSONField(
        default=list,
        blank=True,
        help_text="List of trigger phrases/conditions that force human handoff.",
    )

    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT)

    # AI model configuration — provider-agnostic identifiers, resolved to a
    # concrete AIProvider + model by apps.ai.providers.registry.
    model = models.CharField(max_length=128, default="gpt-4o-mini")
    temperature = models.FloatField(default=0.4)
    max_tokens = models.PositiveIntegerField(default=800)

    class Meta:
        db_table = "agents_agent"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["business", "status"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.business_id})"


class AgentSetting(TenantOwnedModel):
    """Flexible key/value config bucket for agent behavior that doesn't
    warrant a first-class column (kept generic on purpose — this is where
    future per-agent knobs land without a migration)."""

    agent = models.ForeignKey(Agent, on_delete=models.CASCADE, related_name="settings")
    key = models.CharField(max_length=128)
    value = models.JSONField()

    class Meta:
        db_table = "agents_agent_setting"
        constraints = [
            models.UniqueConstraint(fields=["agent", "key"], name="unique_agent_setting_key")
        ]


class AgentTool(TenantOwnedModel):
    """Which tools an agent is allowed to propose/execute, and whether
    execution requires human approval (Refinement 3). The AI can only ever
    call a tool that exists here with enabled=True for this exact agent —
    this table is what apps.ai.tools.ToolService checks before executing
    anything the model proposes."""

    class ToolName(models.TextChoices):
        CREATE_LEAD = "create_lead", "Create Lead"
        UPDATE_LEAD = "update_lead", "Update Lead"
        REQUEST_DEMO = "request_demo", "Request Demo"
        REQUEST_CALLBACK = "request_callback", "Request Callback"
        CREATE_TICKET = "create_ticket", "Create Support Ticket"
        CREATE_PAYMENT_LINK = "create_payment_link", "Create Payment Link"
        CREATE_QUOTE = "create_quote", "Create Quote"
        BOOK_APPOINTMENT = "book_appointment", "Book Appointment"
        HUMAN_HANDOFF = "human_handoff", "Human Handoff"

    class PermissionLevel(models.TextChoices):
        AUTO = "auto", "Execute automatically"
        REQUIRES_APPROVAL = "requires_approval", "Requires human approval"

    agent = models.ForeignKey(Agent, on_delete=models.CASCADE, related_name="tools")
    tool_name = models.CharField(max_length=32, choices=ToolName.choices)
    enabled = models.BooleanField(default=True)
    permission_level = models.CharField(
        max_length=20, choices=PermissionLevel.choices, default=PermissionLevel.AUTO
    )

    class Meta:
        db_table = "agents_agent_tool"
        constraints = [
            models.UniqueConstraint(fields=["agent", "tool_name"], name="unique_agent_tool")
        ]
