from django.db import migrations

DEFAULT_PLANS = [
    dict(
        code="starter",
        name="Starter",
        description="For a single agent handling a low volume of conversations.",
        monthly_price="0.00",
        max_agents=1,
        max_messages_per_month=200,
        max_knowledge_documents=10,
        max_team_members=2,
        trial_days=14,
        is_default=True,
        sort_order=0,
    ),
    dict(
        code="growth",
        name="Growth",
        description="For growing businesses running multiple agents and channels.",
        monthly_price="49.00",
        max_agents=5,
        max_messages_per_month=5000,
        max_knowledge_documents=100,
        max_team_members=10,
        trial_days=14,
        is_default=False,
        sort_order=1,
    ),
    dict(
        code="scale",
        name="Scale",
        description="For high-volume businesses with no meaningful ceiling.",
        monthly_price="199.00",
        max_agents=None,
        max_messages_per_month=None,
        max_knowledge_documents=None,
        max_team_members=None,
        trial_days=14,
        is_default=False,
        sort_order=2,
    ),
]


def seed_plans(apps, schema_editor):
    Plan = apps.get_model("billing", "Plan")
    for plan in DEFAULT_PLANS:
        Plan.objects.update_or_create(code=plan["code"], defaults=plan)


def remove_plans(apps, schema_editor):
    Plan = apps.get_model("billing", "Plan")
    Plan.objects.filter(code__in=[p["code"] for p in DEFAULT_PLANS]).delete()


class Migration(migrations.Migration):
    dependencies = [("billing", "0001_initial")]
    operations = [migrations.RunPython(seed_plans, remove_plans)]
