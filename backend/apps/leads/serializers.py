from rest_framework import serializers

from apps.leads.models import Lead, LeadActivity, LeadStage


class LeadStageSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeadStage
        fields = ["id", "name", "order", "is_won", "is_lost"]
        read_only_fields = ["id"]


class LeadActivitySerializer(serializers.ModelSerializer):
    class Meta:
        model = LeadActivity
        fields = ["id", "activity_type", "content", "actor_label", "created_at"]
        read_only_fields = fields


class LeadSerializer(serializers.ModelSerializer):
    stage_name = serializers.CharField(source="stage.name", read_only=True)
    activities = LeadActivitySerializer(many=True, read_only=True)

    class Meta:
        model = Lead
        fields = [
            "id", "agent", "conversation", "stage", "stage_name", "name", "email", "phone",
            "company", "requirement", "budget", "timeline", "custom_fields", "score",
            "assigned_to", "activities", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "score", "stage_name", "activities", "created_at", "updated_at"]

    def validate_stage(self, value):
        request = self.context["request"]
        if value.business_id != request.business.id:
            raise serializers.ValidationError("Invalid stage.")
        return value

    def validate_agent(self, value):
        request = self.context["request"]
        if value.business_id != request.business.id:
            raise serializers.ValidationError("Invalid agent.")
        return value
