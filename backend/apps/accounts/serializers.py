from django.contrib.auth import authenticate
from django.db import transaction
from rest_framework import serializers

from apps.accounts.models import User
from apps.tenants.models import Business, BusinessMembership


class RegisterSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=10)
    business_name = serializers.CharField(max_length=255)

    def validate_email(self, value):
        value = value.lower().strip()
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("An account with this email already exists.")
        return value

    def validate_password(self, value):
        from django.contrib.auth.password_validation import validate_password

        validate_password(value)
        return value

    @transaction.atomic
    def create(self, validated_data):
        user = User.objects.create_user(
            email=validated_data["email"],
            password=validated_data["password"],
            name=validated_data["name"],
        )
        business = Business.objects.create(
            name=validated_data["business_name"],
            owner=user,
            email=validated_data["email"],
        )
        BusinessMembership.objects.create(
            user=user,
            business=business,
            role=BusinessMembership.Role.OWNER,
            status=BusinessMembership.Status.ACTIVE,
        )
        return user


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "email", "name", "is_email_verified", "created_at"]
        read_only_fields = fields


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        user = authenticate(
            username=attrs["email"].lower().strip(),
            password=attrs["password"],
        )
        if user is None or not user.is_active:
            raise serializers.ValidationError("Invalid email or password.")
        attrs["user"] = user
        return attrs
