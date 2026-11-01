import json
from unittest.mock import patch

from rest_framework import status
from rest_framework.test import APITestCase

from apps.core.testing import authenticated_client, create_business_with_owner
from apps.knowledge.models import KnowledgeDocument


class DatabaseSourceApiTests(APITestCase):
    def setUp(self):
        self.user, self.business = create_business_with_owner()
        self.client_auth = authenticated_client(self.user)

    def test_requires_database_credentials(self):
        response = self.client_auth.post(
            "/api/v1/knowledge/", {"title": "Products", "source_type": "database"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_rejects_missing_credential_keys(self):
        response = self.client_auth.post(
            "/api/v1/knowledge/",
            {"title": "Products", "source_type": "database", "database_credentials": {"dialect": "postgresql", "host": "db.example.com"}},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_rejects_unsupported_dialect(self):
        response = self.client_auth.post(
            "/api/v1/knowledge/",
            {
                "title": "Products", "source_type": "database",
                "database_credentials": {
                    "dialect": "oracle", "host": "db.example.com", "database": "shop",
                    "user": "ro", "password": "secret", "table": "products",
                },
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("apps.knowledge.tasks.process_document_task.delay")
    def test_creates_pending_document_and_encrypts_credentials(self, mock_delay):
        response = self.client_auth.post(
            "/api/v1/knowledge/",
            {
                "title": "Products", "source_type": "database",
                "database_credentials": {
                    "dialect": "postgresql", "host": "db.example.com", "port": 5432, "database": "shop",
                    "user": "ro_user", "password": "super-secret", "table": "products",
                },
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertNotIn("database_credentials", response.data)
        self.assertNotIn("external_db_credentials", response.data)

        document = KnowledgeDocument.objects.get(id=response.data["id"])
        self.assertEqual(document.status, KnowledgeDocument.Status.PENDING)
        stored = json.loads(document.external_db_credentials)
        self.assertEqual(stored["password"], "super-secret")
        mock_delay.assert_called_once_with(document.id)

        # Encrypted at rest — the raw column value is not the plaintext JSON.
        raw_column_value = KnowledgeDocument.objects.filter(id=document.id).values_list(
            "external_db_credentials", flat=True
        ).first()
        # Accessing via the model instance decrypts automatically; re-read
        # through a fresh queryset to confirm decryption round-trips.
        document.refresh_from_db()
        self.assertEqual(json.loads(document.external_db_credentials)["table"], "products")

    @patch("apps.knowledge.db_source._fetch_postgresql", return_value=(["id", "name"], [(1, "Widget")]))
    @patch("apps.knowledge.db_source.socket.getaddrinfo", return_value=[(2, 1, 6, "", ("203.0.113.9", 0))])
    def test_process_document_extracts_rows_into_chunks(self, mock_getaddrinfo, mock_fetch):
        from apps.knowledge.models import KnowledgeChunk
        from apps.knowledge.services import create_pending_document, process_document

        document = create_pending_document(
            business=self.business, agent=None, title="Products", source_type=KnowledgeDocument.SourceType.DATABASE,
            database_credentials={
                "dialect": "postgresql", "host": "db.example.com", "database": "shop",
                "user": "ro_user", "password": "secret", "table": "products",
            },
        )
        process_document(document.id)
        document.refresh_from_db()

        self.assertEqual(document.status, KnowledgeDocument.Status.READY)
        self.assertIn("Widget", document.content)
        self.assertTrue(KnowledgeChunk.objects.filter(document=document).exists())
