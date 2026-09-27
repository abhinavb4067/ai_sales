"""KnowledgeService — the only entry point the rest of the app (including
the AI orchestrator) should use to read/write knowledge. Keeps
KnowledgeRetriever/chunking/embedding implementation details out of views
and out of apps.ai.
"""
import logging

from django.db import transaction

from apps.knowledge.models import KnowledgeChunk, KnowledgeDocument
from apps.knowledge.retrieval import RetrievedChunk, get_retriever

logger = logging.getLogger(__name__)

_CHUNK_SIZE_CHARS = 1000
_CHUNK_OVERLAP_CHARS = 150


def _chunk_text(text: str) -> list[str]:
    text = text.strip()
    if not text:
        return []
    if len(text) <= _CHUNK_SIZE_CHARS:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = start + _CHUNK_SIZE_CHARS
        chunks.append(text[start:end])
        start = end - _CHUNK_OVERLAP_CHARS
    return chunks


def _store_chunks(document: KnowledgeDocument, content: str) -> list[KnowledgeChunk]:
    chunks = _chunk_text(content)
    KnowledgeChunk.objects.filter(document=document).delete()
    created = KnowledgeChunk.objects.bulk_create(
        [
            KnowledgeChunk(
                business=document.business,
                agent=document.agent,
                document=document,
                chunk_index=i,
                content=chunk,
                token_count=len(chunk) // 4,
            )
            for i, chunk in enumerate(chunks)
        ]
    )
    return created


@transaction.atomic
def ingest_manual_text(*, business, agent, title: str, content: str, source_type=KnowledgeDocument.SourceType.MANUAL) -> KnowledgeDocument:
    """Synchronous ingestion path for manual/FAQ entries — small enough not
    to need Celery. File/URL ingestion goes through process_document_task
    (apps.knowledge.tasks) which calls _finish_ingestion below after
    extracting text, so the chunk/embed contract is identical either way.
    """
    document = KnowledgeDocument.objects.create(
        business=business,
        agent=agent,
        source_type=source_type,
        title=title,
        content=content,
        status=KnowledgeDocument.Status.PROCESSING,
    )
    _finish_ingestion(document, content)
    return document


def create_pending_document(*, business, agent, title: str, source_type: str, file=None, source_url: str = "") -> KnowledgeDocument:
    """Creates the document row and returns immediately — the caller
    (view) enqueues the actual Celery processing task with the returned
    document's id. Keeps the HTTP request from blocking on
    extraction/chunking/embedding for file/URL uploads."""
    return KnowledgeDocument.objects.create(
        business=business,
        agent=agent,
        source_type=source_type,
        title=title,
        file=file,
        source_url=source_url,
        status=KnowledgeDocument.Status.PENDING,
    )


def process_document(document_id) -> None:
    """Runs the extract -> chunk -> embed pipeline for a single document.
    Called from apps.knowledge.tasks.process_document_task (Celery), kept
    as a plain function so it's directly unit-testable without Celery."""
    from apps.knowledge.extractors import extract_text_for_document

    document = KnowledgeDocument.objects.get(id=document_id)
    document.status = KnowledgeDocument.Status.PROCESSING
    document.save(update_fields=["status", "updated_at"])

    try:
        content = extract_text_for_document(document)
        if not content.strip():
            raise ValueError("No text could be extracted from this document.")
        document.content = content
        document.save(update_fields=["content", "updated_at"])
        _finish_ingestion(document, content)
    except Exception as exc:  # noqa: BLE001 — persist failure, don't hide it
        logger.exception("Document processing failed for document_id=%s", document_id)
        document.status = KnowledgeDocument.Status.FAILED
        document.failure_reason = str(exc)
        document.save(update_fields=["status", "failure_reason", "updated_at"])


def _finish_ingestion(document: KnowledgeDocument, content: str) -> None:
    try:
        chunks = _store_chunks(document, content)
        _generate_embeddings(chunks)
        document.status = KnowledgeDocument.Status.READY
        document.save(update_fields=["status", "updated_at"])
    except Exception as exc:  # noqa: BLE001
        document.status = KnowledgeDocument.Status.FAILED
        document.failure_reason = str(exc)
        document.save(update_fields=["status", "failure_reason", "updated_at"])
        raise


def _generate_embeddings(chunks: list[KnowledgeChunk]) -> None:
    """Best-effort: if no embedding provider is configured (no API key in
    dev), chunks are simply left without embeddings and
    MySQLKeywordRetriever still works — embeddings only unlock
    EmbeddingRetriever (see apps.knowledge.retrieval)."""
    from django.conf import settings

    if not settings.OPENAI_API_KEY or not chunks:
        return

    from apps.ai.providers.registry import get_embedding_provider

    provider = get_embedding_provider()
    try:
        result = provider.embed([c.content for c in chunks])
    except Exception:
        logger.exception("Embedding generation failed; falling back to keyword retrieval for these chunks.")
        return

    for chunk, vector in zip(chunks, result.vectors):
        chunk.embedding = vector
    KnowledgeChunk.objects.bulk_update(chunks, ["embedding"])


def retrieve_context(*, business_id, agent_id, query: str, top_k: int = 5) -> list[RetrievedChunk]:
    retriever = get_retriever()
    return retriever.search(business_id=business_id, agent_id=agent_id, query=query, top_k=top_k)
