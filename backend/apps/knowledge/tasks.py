import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=2, default_retry_delay=30)
def process_document_task(self, document_id, is_resync: bool = False):
    from apps.knowledge.services import process_document

    process_document(document_id, is_resync=is_resync)


@shared_task
def resync_external_sources():
    """Celery Beat periodic task (see config.celery CELERY_BEAT_SCHEDULE)
    — re-crawls/re-fetches every READY url/api KnowledgeDocument so
    content changes on the business's site/API eventually get picked up
    without a human re-uploading anything. Each one still goes through
    process_document_task's normal retry/failure handling; a single
    source failing here doesn't affect any other source's schedule."""
    from apps.knowledge.models import KnowledgeDocument

    document_ids = list(
        KnowledgeDocument.objects.filter(
            source_type__in=[KnowledgeDocument.SourceType.URL, KnowledgeDocument.SourceType.API],
            status=KnowledgeDocument.Status.READY,
        ).values_list("id", flat=True)
    )
    for document_id in document_ids:
        process_document_task.delay(document_id, is_resync=True)
    logger.info("Queued resync for %d knowledge source(s).", len(document_ids))
    return len(document_ids)
