from rest_framework import status
from rest_framework.test import APITestCase

from apps.agents.models import Agent
from apps.conversations.models import Conversation
from apps.core.testing import authenticated_client, create_business_with_owner
from apps.leads.models import Lead, LeadStage


class AnalyticsOverviewTests(APITestCase):
    def setUp(self):
        self.user, self.business = create_business_with_owner()
        self.client_auth = authenticated_client(self.user)
        self.agent = Agent.objects.create(business=self.business, name="Agent")

    def test_overview_returns_counts_scoped_to_business(self):
        Conversation.objects.create(business=self.business, agent=self.agent, channel=Conversation.Channel.WEBSITE)
        stage = LeadStage.objects.filter(business=self.business).first()
        Lead.objects.create(business=self.business, agent=self.agent, stage=stage, email="a@b.com", score=60)

        response = self.client_auth.get("/api/v1/analytics/overview/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total_conversations"], 1)
        self.assertEqual(response.data["leads_captured_last_window"], 1)
        self.assertEqual(response.data["qualified_leads_last_window"], 1)
        self.assertIn("website", response.data["channel_breakdown"])
        self.assertIsNotNone(response.data["usage_against_plan"])

    def test_cannot_see_another_businesss_data(self):
        other_user, other_business = create_business_with_owner(email="other@example.com")
        other_agent = Agent.objects.create(business=other_business, name="Other Agent")
        Conversation.objects.create(business=other_business, agent=other_agent, channel=Conversation.Channel.WEBSITE)

        response = self.client_auth.get("/api/v1/analytics/overview/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total_conversations"], 0)

    def test_requires_authentication(self):
        response = self.client.get("/api/v1/analytics/overview/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
