from unittest.mock import patch

from django.test import TestCase, override_settings

from apps.agents.models import Agent
from apps.ai.providers.base import EmbeddingResult, Usage
from apps.core.testing import create_business_with_owner
from apps.knowledge.models import KnowledgeChunk, KnowledgeDocument
from apps.knowledge.retrieval import EmbeddingRetriever, HybridRetriever


class FakeEmbeddingProvider:
    def __init__(self, vector_map):
        self._vector_map = vector_map

    def embed(self, texts):
        return EmbeddingResult(vectors=[self._vector_map[t] for t in texts], usage=Usage())


class EmbeddingRetrieverTests(TestCase):
    def setUp(self):
        self.user, self.business = create_business_with_owner()
        self.agent = Agent.objects.create(business=self.business, name="Agent")
        self.document = KnowledgeDocument.objects.create(
            business=self.business, title="Doc", status=KnowledgeDocument.Status.READY
        )
        self.chunk_relevant = KnowledgeChunk.objects.create(
            business=self.business, document=self.document, chunk_index=0,
            content="Our premium plan costs $99/month.", embedding=[1.0, 0.0, 0.0],
        )
        self.chunk_irrelevant = KnowledgeChunk.objects.create(
            business=self.business, document=self.document, chunk_index=1,
            content="We are located in Berlin.", embedding=[0.0, 1.0, 0.0],
        )

    @patch("apps.ai.providers.registry.get_embedding_provider")
    def test_ranks_by_cosine_similarity(self, mock_get_provider):
        mock_get_provider.return_value = FakeEmbeddingProvider({"how much does premium cost?": [1.0, 0.0, 0.0]})
        retriever = EmbeddingRetriever()
        results = retriever.search(self.business.id, self.agent.id, "how much does premium cost?")
        self.assertGreater(len(results), 0)
        self.assertEqual(results[0].chunk_id, self.chunk_relevant.id)

    @patch("apps.ai.providers.registry.get_embedding_provider")
    def test_chunks_without_embedding_are_excluded(self, mock_get_provider):
        KnowledgeChunk.objects.create(
            business=self.business, document=self.document, chunk_index=2, content="No embedding here.", embedding=None
        )
        mock_get_provider.return_value = FakeEmbeddingProvider({"query": [1.0, 0.0, 0.0]})
        retriever = EmbeddingRetriever()
        results = retriever.search(self.business.id, self.agent.id, "query")
        self.assertTrue(all(r.content != "No embedding here." for r in results))


class HybridRetrieverFallbackTests(TestCase):
    def setUp(self):
        self.user, self.business = create_business_with_owner()
        self.agent = Agent.objects.create(business=self.business, name="Agent")
        document = KnowledgeDocument.objects.create(
            business=self.business, title="Doc", status=KnowledgeDocument.Status.READY
        )
        KnowledgeChunk.objects.create(
            business=self.business, document=document, chunk_index=0,
            content="Our support hours are 9am-5pm weekdays.", embedding=None,
        )

    @override_settings(OPENAI_API_KEY="")
    def test_falls_back_to_keyword_search_when_no_api_key(self):
        retriever = HybridRetriever()
        results = retriever.search(self.business.id, self.agent.id, "support hours weekdays")
        self.assertTrue(any("support hours" in r.content for r in results))
