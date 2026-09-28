from rest_framework import status
from rest_framework.test import APITestCase

from apps.agents.models import Agent
from apps.core.testing import authenticated_client, create_business_with_owner
from apps.knowledge.models import KnowledgeChunk, KnowledgeDocument
from apps.knowledge.retrieval import MySQLKeywordRetriever
from apps.knowledge.services import ingest_manual_text


class KnowledgeIngestionTests(APITestCase):
    def setUp(self):
        self.user, self.business = create_business_with_owner()
        self.client_auth = authenticated_client(self.user)

    def test_manual_entry_creates_chunks(self):
        response = self.client_auth.post(
            "/api/v1/knowledge/",
            {"title": "FAQ", "content": "Our support hours are 9am-5pm.", "source_type": "manual"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        document = KnowledgeDocument.objects.get(id=response.data["id"])
        self.assertEqual(document.status, KnowledgeDocument.Status.READY)
        self.assertTrue(KnowledgeChunk.objects.filter(document=document).exists())

    def test_blank_content_rejected(self):
        response = self.client_auth.post(
            "/api/v1/knowledge/", {"title": "Empty", "content": "  ", "source_type": "manual"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_document_creation_blocked_once_plan_limit_reached(self):
        # Starter plan (the default trial plan) allows max_knowledge_documents=10.
        for i in range(10):
            ingest_manual_text(business=self.business, agent=None, title=f"Doc {i}", content="Some content.")

        response = self.client_auth.post(
            "/api/v1/knowledge/",
            {"title": "One too many", "content": "Overflow content.", "source_type": "manual"},
            format="json",
        )
        self.assertEqual(response.status_code, 402)
        self.assertEqual(response.data["error"]["code"], "PLAN_LIMIT_REACHED")


class KnowledgeRetrievalScopeTests(APITestCase):
    """Refinement 5: agent-specific knowledge must not leak to other agents."""

    def setUp(self):
        self.user, self.business = create_business_with_owner()
        self.agent_sales = Agent.objects.create(business=self.business, name="Sales")
        self.agent_support = Agent.objects.create(business=self.business, name="Support")

        ingest_manual_text(
            business=self.business, agent=None, title="Company FAQ",
            content="We are open every weekday for general business questions.",
        )
        ingest_manual_text(
            business=self.business, agent=self.agent_sales, title="Sales Pricing",
            content="Our premium plan pricing is confidential sales pricing information.",
        )

    def test_shared_knowledge_visible_to_all_agents(self):
        retriever = MySQLKeywordRetriever()
        results = retriever.search(self.business.id, self.agent_support.id, "weekday business questions")
        self.assertTrue(any("Company FAQ" == r.document_title for r in results))

    def test_agent_specific_knowledge_not_visible_to_other_agent(self):
        retriever = MySQLKeywordRetriever()
        results = retriever.search(self.business.id, self.agent_support.id, "confidential sales pricing information")
        self.assertFalse(any(r.document_title == "Sales Pricing" for r in results))

    def test_agent_specific_knowledge_visible_to_owning_agent(self):
        retriever = MySQLKeywordRetriever()
        results = retriever.search(self.business.id, self.agent_sales.id, "confidential sales pricing information")
        self.assertTrue(any(r.document_title == "Sales Pricing" for r in results))
