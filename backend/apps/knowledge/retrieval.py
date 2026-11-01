"""KnowledgeRetriever abstraction.

The AI orchestrator (apps.ai.orchestrator) only ever talks to
KnowledgeService, which delegates to whichever KnowledgeRetriever
implementation get_retriever() returns. PgVectorRetriever (native
Postgres pgvector) is the default now that the project runs on
Postgres; EmbeddingRetriever (in-process cosine similarity) remains as
a DB-agnostic fallback, and an external store (Qdrant) is available as
an opt-in alternative — see get_retriever() for the selection order.
Nothing in the orchestrator, prompt builder, or views needs to change
when swapping between them.
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


class KeywordRetriever(KnowledgeRetriever):
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
    skipped here — KeywordRetriever is the fallback for those via
    get_retriever()'s hybrid behavior below, not duplicated in this class.

    Kept as the fallback for non-Postgres backends (e.g. the sqlite test
    database) — PgVectorRetriever below is the native equivalent used in
    production.
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
        self._keyword_retriever = KeywordRetriever()

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
    """Dedicated vector database backend (Qdrant today — see
    apps.knowledge.vector_store) instead of the in-process cosine
    similarity EmbeddingRetriever computes. Only active when QDRANT_URL
    is configured (see get_retriever()); ingestion
    (apps.knowledge.services._generate_embeddings) upserts into the same
    Qdrant collection this reads from, keyed by KnowledgeChunk.id."""

    def search(self, business_id, agent_id, query: str, top_k: int = 5) -> list[RetrievedChunk]:
        if not query or not query.strip():
            return []

        from apps.ai.providers.registry import get_embedding_provider
        from apps.knowledge.models import KnowledgeChunk
        from apps.knowledge.vector_store import search as qdrant_search

        provider = get_embedding_provider()
        query_vector = provider.embed([query]).vectors[0]

        hits = qdrant_search(query_vector, business_id=business_id, agent_id=agent_id, top_k=top_k)
        if not hits:
            return []

        scores_by_id = {hit["id"]: hit["score"] for hit in hits}
        chunks = KnowledgeChunk.objects.filter(id__in=scores_by_id.keys()).select_related("document")

        results = [
            RetrievedChunk(
                chunk_id=chunk.id,
                document_id=chunk.document_id,
                document_title=chunk.document.title,
                content=chunk.content,
                score=scores_by_id[chunk.id],
            )
            for chunk in chunks
        ]
        results.sort(key=lambda c: c.score, reverse=True)
        return results


class QdrantBackedHybridRetriever(KnowledgeRetriever):
    """Same fallback contract as HybridRetriever, but using the dedicated
    vector store for the embedding-search half instead of computing
    cosine similarity in Python — used automatically once QDRANT_URL is
    configured (see get_retriever())."""

    def __init__(self):
        self._vector_retriever = VectorStoreRetriever()
        self._keyword_retriever = KeywordRetriever()

    def search(self, business_id, agent_id, query: str, top_k: int = 5) -> list[RetrievedChunk]:
        try:
            results = self._vector_retriever.search(business_id, agent_id, query, top_k)
            if results:
                return results
        except Exception:
            pass  # fall through to keyword search below
        return self._keyword_retriever.search(business_id, agent_id, query, top_k)


class PgVectorRetriever(KnowledgeRetriever):
    """Native Postgres pgvector search — orders by cosine distance in the
    database itself (via KnowledgeChunk.embedding_vector) instead of
    pulling candidate rows into Python like EmbeddingRetriever does. The
    default vector-search path once the project runs on Postgres (see
    get_retriever()); EmbeddingRetriever remains as a DB-agnostic
    fallback for non-Postgres backends.
    """

    def search(self, business_id, agent_id, query: str, top_k: int = 5) -> list[RetrievedChunk]:
        if not query or not query.strip():
            return []

        from pgvector.django import CosineDistance

        from apps.ai.providers.registry import get_embedding_provider

        provider = get_embedding_provider()
        query_vector = provider.embed([query]).vectors[0]

        candidates = (
            _scoped_ready_chunks(business_id, agent_id)
            .exclude(embedding_vector__isnull=True)
            .annotate(distance=CosineDistance("embedding_vector", query_vector))
            .order_by("distance")[:top_k]
        )

        return [
            RetrievedChunk(
                chunk_id=chunk.id,
                document_id=chunk.document_id,
                document_title=chunk.document.title,
                content=chunk.content,
                # CosineDistance is 1 - cosine_similarity — converted back
                # to a similarity score so every retriever's `score` means
                # the same thing (higher = more relevant).
                score=1 - chunk.distance,
            )
            for chunk in candidates
        ]


class PgVectorHybridRetriever(KnowledgeRetriever):
    """Same fallback contract as HybridRetriever/QdrantBackedHybridRetriever,
    backed by native pgvector instead — used automatically once the
    active database is Postgres and no external QDRANT_URL is set (see
    get_retriever())."""

    def __init__(self):
        self._vector_retriever = PgVectorRetriever()
        self._keyword_retriever = KeywordRetriever()

    def search(self, business_id, agent_id, query: str, top_k: int = 5) -> list[RetrievedChunk]:
        try:
            results = self._vector_retriever.search(business_id, agent_id, query, top_k)
            if results:
                return results
        except Exception:
            pass  # fall through to keyword search below
        return self._keyword_retriever.search(business_id, agent_id, query, top_k)


def get_retriever() -> KnowledgeRetriever:
    # Single switch point for the whole application. Priority: an
    # explicitly configured external vector store (QDRANT_URL) wins if
    # set; otherwise native pgvector is used when running on Postgres;
    # otherwise the fully in-process, DB-agnostic hybrid retriever (the
    # only option on e.g. the sqlite test database).
    from django.db import connection

    from apps.knowledge.vector_store import is_enabled as qdrant_enabled

    if qdrant_enabled():
        return QdrantBackedHybridRetriever()
    if connection.vendor == "postgresql":
        return PgVectorHybridRetriever()
    return HybridRetriever()
