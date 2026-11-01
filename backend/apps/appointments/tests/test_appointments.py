from datetime import timedelta

from django.core.exceptions import ValidationError
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.agents.models import Agent
from apps.appointments.models import Appointment
from apps.appointments.services import book_appointment, cancel_appointment, has_conflict, reschedule_appointment
from apps.core.testing import authenticated_client, create_business_with_owner


class AppointmentServiceTests(APITestCase):
    def setUp(self):
        self.user, self.business = create_business_with_owner()
        self.agent = Agent.objects.create(business=self.business, name="Agent")
        self.start = timezone.now() + timedelta(days=1)
        self.end = self.start + timedelta(hours=1)

    def test_book_appointment_creates_record(self):
        appointment = book_appointment(
            business=self.business, agent=self.agent, start_time=self.start, end_time=self.end,
        )
        self.assertEqual(appointment.status, Appointment.Status.SCHEDULED)

    def test_conflicting_slot_for_same_assignee_is_rejected(self):
        book_appointment(
            business=self.business, agent=self.agent, start_time=self.start, end_time=self.end,
            assigned_to=self.user,
        )
        with self.assertRaises(ValidationError):
            book_appointment(
                business=self.business, agent=self.agent,
                start_time=self.start + timedelta(minutes=30), end_time=self.end + timedelta(minutes=30),
                assigned_to=self.user,
            )

    def test_invalid_time_range_rejected(self):
        with self.assertRaises(ValidationError):
            book_appointment(business=self.business, agent=self.agent, start_time=self.end, end_time=self.start)

    def test_reschedule_checks_conflicts(self):
        appointment = book_appointment(
            business=self.business, agent=self.agent, start_time=self.start, end_time=self.end, assigned_to=self.user,
        )
        other = book_appointment(
            business=self.business, agent=self.agent,
            start_time=self.start + timedelta(hours=2), end_time=self.end + timedelta(hours=2),
            assigned_to=self.user,
        )
        with self.assertRaises(ValidationError):
            reschedule_appointment(other, start_time=self.start, end_time=self.end)

    def test_cancel_frees_up_the_slot(self):
        appointment = book_appointment(
            business=self.business, agent=self.agent, start_time=self.start, end_time=self.end, assigned_to=self.user,
        )
        cancel_appointment(appointment)
        self.assertFalse(
            has_conflict(business=self.business, assigned_to=self.user, start_time=self.start, end_time=self.end)
        )


class AppointmentApiTests(APITestCase):
    def setUp(self):
        self.user, self.business = create_business_with_owner()
        self.client_auth = authenticated_client(self.user)
        self.agent = Agent.objects.create(business=self.business, name="Agent")
        self.start = timezone.now() + timedelta(days=1)
        self.end = self.start + timedelta(hours=1)

    def test_create_and_list_scoped_to_business(self):
        response = self.client_auth.post(
            "/api/v1/appointments/",
            {"agent": self.agent.id, "start_time": self.start.isoformat(), "end_time": self.end.isoformat()},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        response = self.client_auth.get("/api/v1/appointments/")
        self.assertEqual(len(response.data["results"]), 1)

    def test_cannot_use_another_businesss_agent(self):
        _, other_business = create_business_with_owner(email="other@example.com")
        other_agent = Agent.objects.create(business=other_business, name="Other Agent")
        response = self.client_auth.post(
            "/api/v1/appointments/",
            {"agent": other_agent.id, "start_time": self.start.isoformat(), "end_time": self.end.isoformat()},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cancel_action(self):
        response = self.client_auth.post(
            "/api/v1/appointments/",
            {"agent": self.agent.id, "start_time": self.start.isoformat(), "end_time": self.end.isoformat()},
            format="json",
        )
        appointment_id = response.data["id"]
        response = self.client_auth.post(f"/api/v1/appointments/{appointment_id}/cancel/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "cancelled")
