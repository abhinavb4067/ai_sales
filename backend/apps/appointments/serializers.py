from rest_framework import serializers

from apps.appointments.models import Appointment, FollowUp
from apps.appointments.services import has_conflict


class AppointmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Appointment
        fields = [
            "id", "agent", "conversation", "lead", "customer_name", "customer_email", "customer_phone",
            "start_time", "end_time", "timezone", "status", "notes", "assigned_to", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate(self, attrs):
        start_time = attrs.get("start_time", getattr(self.instance, "start_time", None))
        end_time = attrs.get("end_time", getattr(self.instance, "end_time", None))
        if start_time and end_time and end_time <= start_time:
            raise serializers.ValidationError("end_time must be after start_time.")

        assigned_to = attrs.get("assigned_to", getattr(self.instance, "assigned_to", None))
        business = self.context["request"].business
        exclude_id = self.instance.id if self.instance else None
        if start_time and end_time and has_conflict(
            business=business, assigned_to=assigned_to, start_time=start_time, end_time=end_time, exclude_id=exclude_id
        ):
            raise serializers.ValidationError("The selected time conflicts with an existing appointment.")
        return attrs

    def validate_agent(self, value):
        if value.business_id != self.context["request"].business.id:
            raise serializers.ValidationError("Invalid agent.")
        return value


class FollowUpSerializer(serializers.ModelSerializer):
    class Meta:
        model = FollowUp
        fields = [
            "id", "agent", "conversation", "lead", "due_at", "reason", "status", "assigned_to",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_agent(self, value):
        if value.business_id != self.context["request"].business.id:
            raise serializers.ValidationError("Invalid agent.")
        return value
