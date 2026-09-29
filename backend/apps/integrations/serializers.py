import json

from rest_framework import serializers

from apps.integrations.models import Integration
from apps.integrations.providers.registry import get_integration_provider


class IntegrationSerializer(serializers.ModelSerializer):
    credentials = serializers.DictField(write_only=True, required=False)
    webhook_url_path = serializers.SerializerMethodField()

    class Meta:
        model = Integration
        fields = [
            "id",
            "public_id",
            "agent",
            "provider",
            "status",
            "external_account_id",
            "credentials",
            "webhook_url_path",
            "created_at",
        ]
        read_only_fields = ["id", "public_id", "webhook_url_path", "created_at"]

    def get_webhook_url_path(self, obj):
        return f"/api/v1/integrations/{obj.provider}/webhook/{obj.public_id}/"

    def validate(self, attrs):
        provider_key = attrs.get("provider", getattr(self.instance, "provider", None))
        credentials = attrs.get("credentials")
        if credentials is not None:
            provider = get_integration_provider(provider_key)
            if not provider.validate_credentials(credentials):
                raise serializers.ValidationError(
                    {"credentials": f"Missing required credentials for {provider_key}."}
                )
        return attrs

    def create(self, validated_data):
        credentials = validated_data.pop("credentials", {})
        validated_data["credentials"] = json.dumps(credentials)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        if "credentials" in validated_data:
            validated_data["credentials"] = json.dumps(validated_data["credentials"])
        return super().update(instance, validated_data)
