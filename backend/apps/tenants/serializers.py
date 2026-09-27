from rest_framework import serializers

from apps.tenants.models import Business, BusinessMembership


class BusinessSerializer(serializers.ModelSerializer):
    class Meta:
        model = Business
        fields = [
            "id", "name", "email", "website", "industry", "description",
            "logo", "timezone", "currency", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class BusinessMembershipSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source="user.email", read_only=True)
    user_name = serializers.CharField(source="user.name", read_only=True)

    class Meta:
        model = BusinessMembership
        fields = [
            "id", "user", "user_email", "user_name", "role", "status",
            "joined_at", "created_at",
        ]
        read_only_fields = ["id", "user_email", "user_name", "joined_at", "created_at"]
