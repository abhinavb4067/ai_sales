from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework import status
from rest_framework.test import APITestCase

from apps.core.testing import authenticated_client, create_business_with_owner
from apps.knowledge.models import KnowledgeChunk, KnowledgeDocument
from apps.knowledge.services import process_document


class DocumentProcessingTests(APITestCase):
    def setUp(self):
        self.user, self.business = create_business_with_owner()

    @patch("apps.knowledge.extractors.extract_text_for_document", return_value="Extracted text content for the doc.")
    def test_process_document_populates_chunks_and_marks_ready(self, mock_extract):
        document = KnowledgeDocument.objects.create(
            business=self.business, title="Doc", source_type=KnowledgeDocument.SourceType.TXT,
            status=KnowledgeDocument.Status.PENDING,
        )
        process_document(document.id)
        document.refresh_from_db()
        self.assertEqual(document.status, KnowledgeDocument.Status.READY)
        self.assertTrue(KnowledgeChunk.objects.filter(document=document).exists())

    @patch("apps.knowledge.extractors.extract_text_for_document", side_effect=ValueError("boom"))
    def test_process_document_marks_failed_on_error(self, mock_extract):
        document = KnowledgeDocument.objects.create(
            business=self.business, title="Doc", source_type=KnowledgeDocument.SourceType.PDF,
            status=KnowledgeDocument.Status.PENDING,
        )
        process_document(document.id)
        document.refresh_from_db()
        self.assertEqual(document.status, KnowledgeDocument.Status.FAILED)
        self.assertIn("boom", document.failure_reason)


class DocumentUploadApiTests(APITestCase):
    def setUp(self):
        self.user, self.business = create_business_with_owner()
        self.client_auth = authenticated_client(self.user)

    @patch("apps.knowledge.tasks.process_document_task.delay")
    def test_txt_upload_enqueues_processing_task(self, mock_delay):
        upload = SimpleUploadedFile("policy.txt", b"Our refund policy is 30 days.", content_type="text/plain")
        response = self.client_auth.post(
            "/api/v1/knowledge/",
            {"title": "Refund Policy", "source_type": "txt", "file": upload},
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        document = KnowledgeDocument.objects.get(id=response.data["id"])
        self.assertEqual(document.status, KnowledgeDocument.Status.PENDING)
        mock_delay.assert_called_once_with(document.id)

    def test_file_required_for_file_source_types(self):
        response = self.client_auth.post(
            "/api/v1/knowledge/", {"title": "Missing file", "source_type": "pdf"}, format="multipart"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_url_required_for_url_source_type(self):
        response = self.client_auth.post(
            "/api/v1/knowledge/", {"title": "Missing url", "source_type": "url"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_oversized_file_rejected(self):
        big_content = b"x" * (16 * 1024 * 1024)
        upload = SimpleUploadedFile("big.txt", big_content, content_type="text/plain")
        response = self.client_auth.post(
            "/api/v1/knowledge/", {"title": "Too big", "source_type": "txt", "file": upload}, format="multipart"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
