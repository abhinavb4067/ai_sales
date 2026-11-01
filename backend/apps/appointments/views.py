from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from apps.appointments.models import Appointment, FollowUp
from apps.appointments.serializers import AppointmentSerializer, FollowUpSerializer
from apps.appointments.services import cancel_appointment, reschedule_appointment
from apps.core.permissions import IsBusinessMember, TenantScopedQuerySetMixin


class AppointmentViewSet(TenantScopedQuerySetMixin, viewsets.ModelViewSet):
    serializer_class = AppointmentSerializer
    permission_classes = [permissions.IsAuthenticated, IsBusinessMember]
    queryset = Appointment.objects.all()
    filterset_fields = ["status", "agent", "assigned_to"]

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        appointment = self.get_object()
        cancel_appointment(appointment)
        return Response(AppointmentSerializer(appointment, context={"request": request}).data)

    @action(detail=True, methods=["post"])
    def reschedule(self, request, pk=None):
        appointment = self.get_object()
        try:
            appointment = reschedule_appointment(
                appointment, start_time=request.data.get("start_time"), end_time=request.data.get("end_time")
            )
        except DjangoValidationError as exc:
            raise ValidationError(exc.messages)
        return Response(AppointmentSerializer(appointment, context={"request": request}).data)


class FollowUpViewSet(TenantScopedQuerySetMixin, viewsets.ModelViewSet):
    serializer_class = FollowUpSerializer
    permission_classes = [permissions.IsAuthenticated, IsBusinessMember]
    queryset = FollowUp.objects.all()
    filterset_fields = ["status", "agent", "assigned_to"]
