from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from apps.agents.models import Agent
from apps.appointments.models import FollowUp
from apps.appointments.tasks import flag_overdue_follow_ups
from apps.core.testing import create_business_with_owner
from apps.leads.models import Lead, LeadStage


class FlagOverdueFollowUpsTests(TestCase):
    def setUp(self):
        self.user, self.business = create_business_with_owner()
        self.agent = Agent.objects.create(business=self.business, name="Agent")
        self.stage = LeadStage.objects.filter(business=self.business).first()
        self.lead = Lead.objects.create(business=self.business, agent=self.agent, stage=self.stage, email="a@b.com")

    def test_flags_overdue_pending_follow_up_and_logs_activity(self):
        follow_up = FollowUp.objects.create(
            business=self.business, agent=self.agent, lead=self.lead,
            due_at=timezone.now() - timedelta(hours=1), reason="Check in about the quote",
        )

        count = flag_overdue_follow_ups()

        self.assertEqual(count, 1)
        follow_up.refresh_from_db()
        self.assertIsNotNone(follow_up.overdue_notified_at)
        self.assertTrue(self.lead.activities.filter(content__icontains="overdue").exists())

    def test_does_not_reflag_already_notified_follow_up(self):
        follow_up = FollowUp.objects.create(
            business=self.business, agent=self.agent, lead=self.lead,
            due_at=timezone.now() - timedelta(hours=1), overdue_notified_at=timezone.now(),
        )

        count = flag_overdue_follow_ups()

        self.assertEqual(count, 0)

    def test_ignores_future_follow_ups(self):
        FollowUp.objects.create(
            business=self.business, agent=self.agent, lead=self.lead,
            due_at=timezone.now() + timedelta(hours=1),
        )

        count = flag_overdue_follow_ups()

        self.assertEqual(count, 0)

    def test_ignores_completed_follow_ups(self):
        FollowUp.objects.create(
            business=self.business, agent=self.agent, lead=self.lead,
            due_at=timezone.now() - timedelta(hours=1), status=FollowUp.Status.COMPLETED,
        )

        count = flag_overdue_follow_ups()

        self.assertEqual(count, 0)
