from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.leads.models import LeadStage
from apps.tenants.models import Business

DEFAULT_STAGES = [
    ("New Lead", False, False),
    ("Qualified", False, False),
    ("Interested", False, False),
    ("Demo Requested", False, False),
    ("Proposal", False, False),
    ("Negotiation", False, False),
    ("Won", True, False),
    ("Lost", False, True),
]


@receiver(post_save, sender=Business)
def seed_default_lead_stages(sender, instance, created, **kwargs):
    if not created:
        return
    LeadStage.objects.bulk_create(
        [
            LeadStage(business=instance, name=name, order=i, is_won=won, is_lost=lost)
            for i, (name, won, lost) in enumerate(DEFAULT_STAGES)
        ]
    )
