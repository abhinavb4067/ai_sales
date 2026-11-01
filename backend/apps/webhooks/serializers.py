from rest_framework import serializers

from apps.webhooks.models import OutboundWebhookDelivery, WebhookSubscription


class WebhookSubscriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = WebhookSubscription
        fields = ["id", "public_id", "url", "event_types", "is_active", "created_at", "updated_at"]
        read_only_fields = ["id", "public_id", "created_at", "updated_at"]

    def validate_event_types(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError("Must be a list of event type strings.")
        valid = {choice[0] for choice in WebhookSubscription.EventType.choices}
        invalid = set(value) - valid
        if invalid:
            raise serializers.ValidationError(f"Unknown event type(s): {invalid}. Valid: {sorted(valid)}.")
        return value


class OutboundWebhookDeliverySerializer(serializers.ModelSerializer):
    class Meta:
        model = OutboundWebhookDelivery
        fields = [
            "id", "subscription", "event_type", "payload", "status", "attempt_count",
            "response_status_code", "last_error", "delivered_at", "created_at",
        ]
        read_only_fields = fields
