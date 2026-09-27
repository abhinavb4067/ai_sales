from rest_framework import status
from rest_framework.test import APITestCase

from apps.agents.models import Agent
from apps.core.testing import authenticated_client, create_business_with_owner
from apps.leads.models import Lead, LeadStage
from apps.leads.services import apply_lead_fields, compute_score, get_or_create_lead_for_conversation


class LeadStageSeedingTests(APITestCase):
    def test_default_stages_seeded_on_business_creation(self):
        _, business = create_business_with_owner()
        stage_names = list(LeadStage.objects.filter(business=business).order_by("order").values_list("name", flat=True))
        self.assertEqual(
            stage_names,
            ["New Lead", "Qualified", "Interested", "Demo Requested", "Proposal", "Negotiation", "Won", "Lost"],
        )


class LeadScoringTests(APITestCase):
    def test_score_increases_with_more_fields(self):
        _, business = create_business_with_owner()
        agent = Agent.objects.create(business=business, name="Agent")
        stage = LeadStage.objects.filter(business=business).first()
        lead = Lead.objects.create(business=business, agent=agent, stage=stage)
        self.assertEqual(compute_score(lead), 0)

        lead.email = "x@example.com"
        lead.budget = "$5000/mo"
        self.assertEqual(compute_score(lead), 40)


class LeadApiTests(APITestCase):
    def setUp(self):
        self.user, self.business = create_business_with_owner()
        self.client_auth = authenticated_client(self.user)
        self.agent = Agent.objects.create(business=self.business, name="Agent")
        self.stage = LeadStage.objects.filter(business=self.business).first()

    def test_list_leads_scoped_to_business(self):
        Lead.objects.create(business=self.business, agent=self.agent, stage=self.stage, name="A Lead")
        response = self.client_auth.get("/api/v1/leads/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)

    def test_change_stage_logs_activity(self):
        lead = Lead.objects.create(business=self.business, agent=self.agent, stage=self.stage)
        new_stage = LeadStage.objects.filter(business=self.business).order_by("order")[1]
        response = self.client_auth.post(f"/api/v1/leads/{lead.id}/change_stage/", {"stage": new_stage.id}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        lead.refresh_from_db()
        self.assertEqual(lead.stage_id, new_stage.id)
        self.assertTrue(lead.activities.filter(activity_type="stage_change").exists())


class LeadServiceTests(APITestCase):
    def setUp(self):
        self.user, self.business = create_business_with_owner()
        self.agent = Agent.objects.create(business=self.business, name="Agent")

    def test_get_or_create_lead_for_conversation_is_idempotent(self):
        from apps.conversations.models import Conversation

        conversation = Conversation.objects.create(business=self.business, agent=self.agent)
        lead1 = get_or_create_lead_for_conversation(business=self.business, agent=self.agent, conversation=conversation)
        lead2 = get_or_create_lead_for_conversation(business=self.business, agent=self.agent, conversation=conversation)
        self.assertEqual(lead1.id, lead2.id)

    def test_apply_lead_fields_stores_custom_fields(self):
        from apps.conversations.models import Conversation

        conversation = Conversation.objects.create(business=self.business, agent=self.agent)
        lead = get_or_create_lead_for_conversation(business=self.business, agent=self.agent, conversation=conversation)
        apply_lead_fields(lead, {"email": "a@b.com", "team_size": "50"})
        lead.refresh_from_db()
        self.assertEqual(lead.email, "a@b.com")
        self.assertEqual(lead.custom_fields.get("team_size"), "50")
