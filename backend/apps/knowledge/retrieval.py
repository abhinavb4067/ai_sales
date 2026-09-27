"""KnowledgeRetriever abstraction.

The AI orchestrator (apps.ai.orchestrator) only ever talks to
KnowledgeService, which delegates to whichever KnowledgeRetriever
implementation is configured. Swapping this MySQL-computed cosine
similarity approach for a real vector store (Qdrant/pgvector/Pinecone)
later means writing one new class here and changing the factory at the
bottom of this file — nothing in the orchestrator, prompt builder, or
views needs to change.
"""
import math
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class RetrievedChunk:
    chunk_id: int
    document_id: int
    document_title: str
    content: str
    score: float


class KnowledgeRetriever(ABC):
    @abstractmethod
    def search(self, business_id, agent_id, query: str, top_k: int = 5) -> list[RetrievedChunk]:
        """Return the top_k most relevant chunks visible to `agent_id`
        within `business_id` (business-wide + agent-specific knowledge).
        Must never return chunks belonging to a different business.
        """


def _scoped_ready_chunks(business_id, agent_id):
    from django.db.models import Q

    from apps.knowledge.models import KnowledgeChunk, KnowledgeDocument

    scope = Q(business_id=business_id) & (Q(agent_id=agent_id) | Q(agent_id__isnull=True))
    return KnowledgeChunk.objects.filter(scope).filter(
        document__status=KnowledgeDocument.Status.READY
    ).select_related("document")


class MySQLKeywordRetriever(KnowledgeRetriever):
    """Keyword-overlap relevance heuristic over chunks scoped to the
    business+agent. Deliberately not using MySQL FULLTEXT to avoid a
    storage-engine/migration dependency — used whenever chunks don't have
    embeddings (no AI_PROVIDER API key configured, or embedding generation
    failed), so retrieval degrades gracefully instead of returning nothing.
    """

    def search(self, business_id, agent_id, query: str, top_k: int = 5) -> list[RetrievedChunk]:
        if not query or not query.strip():
            return []

        terms = [t.lower() for t in query.split() if len(t) > 2][:12]
        if not terms:
            return []

        candidates = _scoped_ready_chunks(business_id, agent_id)[:500]

        scored = []
        for chunk in candidates:
            content_lower = chunk.content.lower()
            score = sum(content_lower.count(term) for term in terms)
            if score > 0:
                scored.append(
                    RetrievedChunk(
                        chunk_id=chunk.id,
                        document_id=chunk.document_id,
                        document_title=chunk.document.title,
                        content=chunk.content,
                        score=float(score),
                    )
                )

        scored.sort(key=lambda c: c.score, reverse=True)
        return scored[:top_k]


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


class EmbeddingRetriever(KnowledgeRetriever):
    """Phase 2 RAG upgrade: embeds the query and ranks chunks by cosine
    similarity against their stored embeddings (apps.knowledge.services
    populates KnowledgeChunk.embedding at ingestion time). Chunks without
    an embedding (e.g. embedding generation failed/unconfigured) are
    skipped here — MySQLKeywordRetriever is the fallback for those via
    get_retriever()'s hybrid behavior below, not duplicated in this class.

    Computing similarity in Python rather than in MySQL is the documented
    Phase 2 tradeoff: no native vector type without pgvector/a dedicated
    vector DB. Fine at current per-tenant knowledge-base scale; the
    swap-in point for a real vector store is precisely this class.
    """

    def search(self, business_id, agent_id, query: str, top_k: int = 5) -> list[RetrievedChunk]:
        if not query or not query.strip():
            return []

        from apps.ai.providers.registry import get_embedding_provider

        provider = get_embedding_provider()
        query_vector = provider.embed([query]).vectors[0]

        candidates = _scoped_ready_chunks(business_id, agent_id).exclude(embedding__isnull=True)[:1000]

        scored = []
        for chunk in candidates:
            similarity = _cosine_similarity(query_vector, chunk.embedding)
            if similarity > 0:
                scored.append(
                    RetrievedChunk(
                        chunk_id=chunk.id,
                        document_id=chunk.document_id,
                        document_title=chunk.document.title,
                        content=chunk.content,
                        score=similarity,
                    )
                )

        scored.sort(key=lambda c: c.score, reverse=True)
        return scored[:top_k]


class HybridRetriever(KnowledgeRetriever):
    """Uses embedding similarity when possible, transparently falling back
    to keyword search for tenants/documents that have no embeddings yet
    (e.g. ingested before an OPENAI_API_KEY was configured). This is what
    get_retriever() returns by default — callers never need to know or
    care which strategy actually ran.
    """

    def __init__(self):
        self._embedding_retriever = EmbeddingRetriever()
        self._keyword_retriever = MySQLKeywordRetriever()

    def search(self, business_id, agent_id, query: str, top_k: int = 5) -> list[RetrievedChunk]:
        from django.conf import settings

        if settings.OPENAI_API_KEY:
            try:
                results = self._embedding_retriever.search(business_id, agent_id, query, top_k)
                if results:
                    return results
            except Exception:
                pass  # fall through to keyword search below
        return self._keyword_retriever.search(business_id, agent_id, query, top_k)


class VectorStoreRetriever(KnowledgeRetriever):
    """Placeholder for a future dedicated vector database backend
    (Qdrant/pgvector/Pinecone/etc). Not implemented yet — EmbeddingRetriever
    covers Phase 2's RAG needs at current scale."""

    def search(self, business_id, agent_id, query: str, top_k: int = 5) -> list[RetrievedChunk]:
        raise NotImplementedError("Vector store retrieval is not implemented yet.")


def get_retriever() -> KnowledgeRetriever:
    # Single switch point for the whole application.
    return HybridRetriever()
