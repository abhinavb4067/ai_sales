from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings

from apps.agents.models import Agent
from apps.core.testing import create_business_with_owner
from apps.knowledge.models import KnowledgeChunk, KnowledgeDocument
from apps.knowledge.retrieval import VectorStoreRetriever
from apps.knowledge import vector_store


@override_settings(QDRANT_URL="http://qdrant.local:6333", QDRANT_COLLECTION="test_chunks")
class VectorStoreClientTests(TestCase):
    def test_is_enabled_reflects_settings(self):
        self.assertTrue(vector_store.is_enabled())

    @patch("apps.knowledge.vector_store.requests.put")
    def test_upsert_chunks_posts_points_with_tenant_payload(self, mock_put):
        self.user, self.business = create_business_with_owner()
        self.agent = Agent.objects.create(business=self.business, name="Agent")
        document = KnowledgeDocument.objects.create(business=self.business, title="Doc", content="x")
        chunk = KnowledgeChunk.objects.create(
            business=self.business, agent=self.agent, document=document, chunk_index=0, content="hello"
        )

        vector_store.upsert_chunks([chunk], [[0.1, 0.2, 0.3]])

        self.assertEqual(mock_put.call_count, 2)  # ensure_collection + points upsert
        points_call = mock_put.call_args_list[-1]
        sent_json = points_call.kwargs["json"]
        point = sent_json["points"][0]
        self.assertEqual(point["id"], chunk.id)
        self.assertEqual(point["vector"], [0.1, 0.2, 0.3])
        self.assertEqual(point["payload"]["business_id"], self.business.id)

    @patch("apps.knowledge.vector_store.requests.post")
    def test_delete_points_for_document_filters_by_document_id(self, mock_post):
        vector_store.delete_points_for_document(42)
        sent_json = mock_post.call_args.kwargs["json"]
        self.assertEqual(sent_json["filter"]["must"][0]["match"]["value"], 42)

    @patch("apps.knowledge.vector_store.requests.post")
    def test_search_sends_tenant_scoped_filter(self, mock_post):
        mock_post.return_value.json.return_value = {"result": [{"id": 1, "score": 0.9}]}
        mock_post.return_value.raise_for_status = lambda: None

        results = vector_store.search([0.1, 0.2], business_id=7, agent_id=None, top_k=5)

        self.assertEqual(results, [{"id": 1, "score": 0.9}])
        sent_json = mock_post.call_args.kwargs["json"]
        self.assertEqual(sent_json["filter"]["must"][0]["match"]["value"], 7)


@override_settings(QDRANT_URL="http://qdrant.local:6333", QDRANT_COLLECTION="test_chunks", OPENAI_API_KEY="sk-test")
class VectorStoreRetrieverTests(TestCase):
    def setUp(self):
        self.user, self.business = create_business_with_owner()
        self.agent = Agent.objects.create(business=self.business, name="Agent")
        self.document = KnowledgeDocument.objects.create(
            business=self.business, title="Doc", content="x", status=KnowledgeDocument.Status.READY
        )
        self.chunk = KnowledgeChunk.objects.create(
            business=self.business, agent=self.agent, document=self.document, chunk_index=0, content="Our refund policy is 30 days."
        )

    @patch("apps.knowledge.vector_store.search")
    @patch("apps.ai.providers.registry.get_embedding_provider")
    def test_search_maps_qdrant_hits_back_to_chunks(self, mock_get_provider, mock_search):
        mock_provider = MagicMock()
        mock_provider.embed.return_value.vectors = [[0.1, 0.2]]
        mock_get_provider.return_value = mock_provider
        mock_search.return_value = [{"id": self.chunk.id, "score": 0.87}]

        retriever = VectorStoreRetriever()
        results = retriever.search(self.business.id, self.agent.id, "refund policy", top_k=5)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].chunk_id, self.chunk.id)
        self.assertEqual(results[0].score, 0.87)

    @patch("apps.knowledge.vector_store.search", return_value=[])
    @patch("apps.ai.providers.registry.get_embedding_provider")
    def test_empty_query_returns_no_results(self, mock_get_provider, mock_search):
        retriever = VectorStoreRetriever()
        self.assertEqual(retriever.search(self.business.id, self.agent.id, "   ", top_k=5), [])
        mock_search.assert_not_called()
