"""Thin Qdrant REST client for the OPTIONAL dedicated external vector
store retrieval path (apps.knowledge.retrieval.VectorStoreRetriever /
QdrantBackedHybridRetriever).

The platform runs on Postgres with the pgvector extension
(config.settings.base.DATABASES, apps.knowledge.models.KnowledgeChunk.
embedding_vector) — PgVectorRetriever is the default native vector
search path and needs no separate service. This Qdrant integration
exists for deployments that specifically want a standalone vector
database instead (e.g. to share one vector store across non-Postgres
systems); it is NOT required and is disabled unless QDRANT_URL is set.
Reached over its HTTP API with `requests` (the same approach every
other external integration in this codebase uses —
apps.integrations.providers.whatsapp, apps.billing.providers.
razorpay_provider) rather than its Python SDK, to avoid a new
dependency.

NOT validated against a live Qdrant instance in this environment; the
request/response shapes follow Qdrant's documented REST API but should
be smoke-tested against a real collection before relying on it in
production.
"""
import requests
from django.conf import settings


def is_enabled() -> bool:
    return bool(settings.QDRANT_URL)


def _base_url() -> str:
    return settings.QDRANT_URL.rstrip("/")


def _headers() -> dict:
    headers = {"Content-Type": "application/json"}
    if settings.QDRANT_API_KEY:
        headers["api-key"] = settings.QDRANT_API_KEY
    return headers


def ensure_collection(vector_size: int) -> None:
    """PUT /collections/{name} is idempotent in Qdrant — safe to call on
    every ingestion run rather than tracking "already created" state
    ourselves."""
    requests.put(
        f"{_base_url()}/collections/{settings.QDRANT_COLLECTION}",
        headers=_headers(),
        json={"vectors": {"size": vector_size, "distance": "Cosine"}},
        timeout=10,
    )


def upsert_chunks(chunks, vectors: list[list[float]]) -> None:
    if not chunks or not vectors:
        return
    ensure_collection(len(vectors[0]))
    points = [
        {
            "id": chunk.id,
            "vector": vector,
            "payload": {
                "business_id": chunk.business_id,
                "agent_id": chunk.agent_id,
                "document_id": chunk.document_id,
            },
        }
        for chunk, vector in zip(chunks, vectors)
    ]
    response = requests.put(
        f"{_base_url()}/collections/{settings.QDRANT_COLLECTION}/points",
        headers=_headers(),
        json={"points": points},
        timeout=15,
    )
    response.raise_for_status()


def delete_points_for_document(document_id) -> None:
    """Called before re-ingesting a document (apps.knowledge.services)
    so a reprocessed/edited document doesn't leave stale vectors behind
    for chunks that no longer exist."""
    requests.post(
        f"{_base_url()}/collections/{settings.QDRANT_COLLECTION}/points/delete",
        headers=_headers(),
        json={"filter": {"must": [{"key": "document_id", "match": {"value": document_id}}]}},
        timeout=10,
    )


def search(vector: list[float], *, business_id, agent_id, top_k: int) -> list[dict]:
    """Returns Qdrant's raw scored points (each a dict with at least `id`
    and `score`) — tenant-scoped via a payload filter enforced in the
    query itself (never filtered client-side after the fact), same rule
    as every other tenant-scoped query in this codebase."""
    response = requests.post(
        f"{_base_url()}/collections/{settings.QDRANT_COLLECTION}/points/search",
        headers=_headers(),
        json={
            "vector": vector,
            "limit": top_k,
            "with_payload": False,
            "filter": {
                "must": [{"key": "business_id", "match": {"value": business_id}}],
                "should": [
                    {"key": "agent_id", "match": {"value": agent_id}},
                    {"is_empty": {"key": "agent_id"}},
                ],
            },
        },
        timeout=10,
    )
    response.raise_for_status()
    return response.json().get("result", [])
