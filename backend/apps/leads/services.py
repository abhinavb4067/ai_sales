"""Lead service layer — used by both the dashboard API and (mainly) the
AI tool executors in apps.ai.tools.service. Scoring is computed here,
server-side, rather than trusted from whatever the LLM reports about
itself, per the "sales does not mean uncontrolled trust in the model"
principle.
"""
from apps.leads.models import Lead, LeadActivity, LeadStage

# Simple weighted heuristic — a starting point businesses can eventually
# override with their own configured rules (not built in Phase 2). Kept
# as a pure function so it's trivially replaceable later.
_FIELD_WEIGHTS = {
    "email": 15,
    "phone": 10,
    "company": 10,
    "requirement": 15,
    "budget": 25,
    "timeline": 15,
}


def compute_score(lead: Lead) -> int:
    score = 0
    for field, weight in _FIELD_WEIGHTS.items():
        if getattr(lead, field, ""):
            score += weight
    return min(score, 100)


def get_or_create_lead_for_conversation(*, business, agent, conversation) -> Lead:
    existing = Lead.objects.filter(conversation=conversation).first()
    if existing:
        return existing
    default_stage = LeadStage.objects.filter(business=business).order_by("order").first()
    return Lead.objects.create(business=business, agent=agent, conversation=conversation, stage=default_stage)


def apply_lead_fields(lead: Lead, fields: dict, *, actor_label: str = "ai") -> Lead:
    allowed_fields = {"name", "email", "phone", "company", "requirement", "budget", "timeline"}
    changed = []
    for key, value in fields.items():
        if key in allowed_fields and value:
            setattr(lead, key, value)
            changed.append(key)
        elif value:
            lead.custom_fields[key] = value
            changed.append(key)

    lead.score = compute_score(lead)
    lead.save()

    if changed:
        LeadActivity.objects.create(
            business=lead.business,
            lead=lead,
            activity_type=LeadActivity.ActivityType.AI_ACTION,
            content=f"Updated fields: {', '.join(changed)}",
            actor_label=actor_label,
        )
    return lead


def log_activity(lead: Lead, *, activity_type: str, content: str, actor_label: str = "ai") -> LeadActivity:
    return LeadActivity.objects.create(
        business=lead.business, lead=lead, activity_type=activity_type, content=content, actor_label=actor_label
    )


def change_stage(lead: Lead, stage: LeadStage, *, actor_label: str = "system") -> Lead:
    old_name = lead.stage.name if lead.stage_id else None
    lead.stage = stage
    lead.save(update_fields=["stage", "updated_at"])
    LeadActivity.objects.create(
        business=lead.business,
        lead=lead,
        activity_type=LeadActivity.ActivityType.STAGE_CHANGE,
        content=f"Stage changed from {old_name} to {stage.name}",
        actor_label=actor_label,
    )
    return lead
