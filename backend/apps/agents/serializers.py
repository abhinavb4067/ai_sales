from rest_framework import serializers

from apps.agents.models import Agent, AgentSetting, AgentTool


class AgentToolSerializer(serializers.ModelSerializer):
    class Meta:
        model = AgentTool
        fields = ["id", "tool_name", "enabled", "permission_level"]
        read_only_fields = ["id"]


class AgentSettingSerializer(serializers.ModelSerializer):
    class Meta:
        model = AgentSetting
        fields = ["id", "key", "value"]
        read_only_fields = ["id"]


class AgentSerializer(serializers.ModelSerializer):
    tools = AgentToolSerializer(many=True, read_only=True)

    class Meta:
        model = Agent
        fields = [
            "id", "public_widget_id", "name", "description", "agent_type",
            "primary_goal", "secondary_goals", "system_prompt", "greeting",
            "language", "tone", "must_always_mention", "must_never_say",
            "escalation_rules", "status", "model", "temperature", "max_tokens",
            "tools", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "public_widget_id", "tools", "created_at", "updated_at"]

    def validate_temperature(self, value):
        if not 0 <= value <= 2:
            raise serializers.ValidationError("temperature must be between 0 and 2.")
        return value

    def validate_max_tokens(self, value):
        if not 1 <= value <= 4000:
            raise serializers.ValidationError("max_tokens must be between 1 and 4000.")
        return value
