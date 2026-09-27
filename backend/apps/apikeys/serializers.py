from rest_framework import serializers

from apps.apikeys.models import ApiKey


class ApiKeyCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)


class ApiKeySerializer(serializers.ModelSerializer):
    class Meta:
        model = ApiKey
        fields = ["id", "name", "prefix", "status", "last_used_at", "created_at", "revoked_at"]
        read_only_fields = fields
