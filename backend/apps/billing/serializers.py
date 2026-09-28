from rest_framework import serializers

from apps.billing.models import Plan, Subscription


class PlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plan
        fields = [
            "id",
            "code",
            "name",
            "description",
            "monthly_price",
            "currency",
            "max_agents",
            "max_messages_per_month",
            "max_knowledge_documents",
            "max_team_members",
            "trial_days",
        ]
        read_only_fields = fields


class SubscriptionSerializer(serializers.ModelSerializer):
    plan = PlanSerializer(read_only=True)

    class Meta:
        model = Subscription
        fields = [
            "id",
            "plan",
            "status",
            "current_period_start",
            "current_period_end",
            "trial_ends_at",
            "cancel_at_period_end",
            "provider",
        ]
        read_only_fields = fields


class ChangePlanSerializer(serializers.Serializer):
    plan_code = serializers.SlugField()
