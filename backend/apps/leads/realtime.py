from apps.core.realtime import broadcast_business_event


def broadcast_lead_created(lead) -> None:
    broadcast_business_event(
        lead.business_id,
        "lead.created",
        {
            "lead": {
                "id": lead.id,
                "agent_id": lead.agent_id,
                "stage_id": lead.stage_id,
                "name": lead.name,
                "score": lead.score,
            }
        },
    )


def broadcast_lead_stage_changed(lead) -> None:
    broadcast_business_event(
        lead.business_id,
        "lead.stage_changed",
        {
            "lead": {
                "id": lead.id,
                "agent_id": lead.agent_id,
                "stage_id": lead.stage_id,
                "name": lead.name,
                "score": lead.score,
            }
        },
    )
