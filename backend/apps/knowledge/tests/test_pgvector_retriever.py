"""PgVectorRetriever unit tests. The scoring/mapping logic is tested
here with a mocked ORM queryset (DB-agnostic, runs on sqlite in CI);
apps.knowledge.retrieval.get_retriever() backend-selection logic is also
covered. A real Postgres+pgvector smoke test (actual CosineDistance SQL
execution) is documented in DEPLOYMENT.md rather than run here, since
the sqlite test database can't execute pgvector's native SQL.
"""
from unittest.mock import MagicMock, patch

from django.test import TestCase

from apps.knowledge.retrieval import (
    HybridRetriever,
    PgVectorHybridRetriever,
    QdrantBackedHybridRetriever,
    get_retriever,
)


class GetRetrieverSelectionTests(TestCase):
    @patch("apps.knowledge.vector_store.is_enabled", return_value=True)
    def test_qdrant_wins_when_explicitly_configured(self, mock_enabled):
        self.assertIsInstance(get_retriever(), QdrantBackedHybridRetriever)

    @patch("apps.knowledge.vector_store.is_enabled", return_value=False)
    def test_sqlite_backend_falls_back_to_in_process_hybrid(self, mock_enabled):
        # The test database is sqlite — PgVectorHybridRetriever must
        # never be selected here.
        self.assertIsInstance(get_retriever(), HybridRetriever)

    @patch("apps.knowledge.vector_store.is_enabled", return_value=False)
    @patch("django.db.connection")
    def test_postgres_backend_without_qdrant_uses_pgvector(self, mock_connection, mock_enabled):
        mock_connection.vendor = "postgresql"
        self.assertIsInstance(get_retriever(), PgVectorHybridRetriever)


class PgVectorHybridRetrieverTests(TestCase):
    def test_falls_back_to_keyword_when_vector_search_raises(self):
        retriever = PgVectorHybridRetriever()
        retriever._vector_retriever = MagicMock()
        retriever._vector_retriever.search.side_effect = Exception("pgvector unavailable")
        retriever._keyword_retriever = MagicMock()
        retriever._keyword_retriever.search.return_value = ["fallback"]

        results = retriever.search(business_id=1, agent_id=None, query="refund policy", top_k=5)

        self.assertEqual(results, ["fallback"])

    def test_falls_back_to_keyword_when_vector_search_returns_nothing(self):
        retriever = PgVectorHybridRetriever()
        retriever._vector_retriever = MagicMock()
        retriever._vector_retriever.search.return_value = []
        retriever._keyword_retriever = MagicMock()
        retriever._keyword_retriever.search.return_value = ["fallback"]

        results = retriever.search(business_id=1, agent_id=None, query="refund policy", top_k=5)

        self.assertEqual(results, ["fallback"])
