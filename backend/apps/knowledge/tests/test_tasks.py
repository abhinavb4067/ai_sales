from unittest.mock import patch

from django.test import TestCase

from apps.core.testing import create_business_with_owner
from apps.knowledge.models import KnowledgeDocument
from apps.knowledge.tasks import resync_external_sources


class ResyncExternalSourcesTests(TestCase):
    def setUp(self):
        self.user, self.business = create_business_with_owner()

    @patch("apps.knowledge.tasks.process_document_task.delay")
    def test_queues_only_ready_url_and_api_sources(self, mock_delay):
        ready_url = KnowledgeDocument.objects.create(
            business=self.business, title="URL doc", source_type=KnowledgeDocument.SourceType.URL,
            source_url="https://example.com", status=KnowledgeDocument.Status.READY,
        )
        ready_api = KnowledgeDocument.objects.create(
            business=self.business, title="API doc", source_type=KnowledgeDocument.SourceType.API,
            source_url="https://example.com/api", status=KnowledgeDocument.Status.READY,
        )
        KnowledgeDocument.objects.create(
            business=self.business, title="Manual doc", source_type=KnowledgeDocument.SourceType.MANUAL,
            content="x", status=KnowledgeDocument.Status.READY,
        )
        KnowledgeDocument.objects.create(
            business=self.business, title="Pending URL", source_type=KnowledgeDocument.SourceType.URL,
            source_url="https://example.com/pending", status=KnowledgeDocument.Status.PENDING,
        )

        count = resync_external_sources()

        self.assertEqual(count, 2)
        queued_ids = {call.args[0] for call in mock_delay.call_args_list}
        self.assertEqual(queued_ids, {ready_url.id, ready_api.id})
        for call in mock_delay.call_args_list:
            self.assertTrue(call.kwargs.get("is_resync"))
