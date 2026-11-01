from rest_framework import serializers

from apps.agents.models import Agent
from apps.billing.models import Subscription
from apps.tenants.models import Business


class SuperAdminSubscriptionSerializer(serializers.ModelSerializer):
    plan_name = serializers.CharField(source="plan.name", read_only=True)

    class Meta:
        model = Subscription
        fields = ["status", "plan_name", "provider", "current_period_end", "trial_ends_at", "cancel_at_period_end"]


class SuperAdminBusinessSerializer(serializers.ModelSerializer):
    owner_email = serializers.CharField(source="owner.email", read_only=True)
    subscription = SuperAdminSubscriptionSerializer(read_only=True)
    agent_count = serializers.IntegerField(read_only=True)
    member_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Business
        fields = [
            "id", "name", "email", "website", "industry", "owner_email",
            "subscription", "agent_count", "member_count", "created_at",
        ]


class SuperAdminAgentSerializer(serializers.ModelSerializer):
    business_name = serializers.CharField(source="business.name", read_only=True)

    class Meta:
        model = Agent
        fields = ["id", "business", "business_name", "name", "status", "provider", "model", "created_at"]
