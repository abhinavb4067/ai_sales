from celery import shared_task


@shared_task(bind=True, max_retries=2, default_retry_delay=30)
def process_document_task(self, document_id):
    from apps.knowledge.services import process_document

    process_document(document_id)
