from unittest.mock import patch

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APITestCase

from apps.core.testing import authenticated_client, create_business_with_owner
from apps.knowledge.net_safety import UnsafeURLError, safe_get


class SafeGetTests(TestCase):
    def test_rejects_localhost(self):
        with self.assertRaises(UnsafeURLError):
            safe_get("http://localhost:80/")

    def test_rejects_loopback_ip(self):
        with self.assertRaises(UnsafeURLError):
            safe_get("http://127.0.0.1/")

    def test_rejects_cloud_metadata_ip(self):
        with self.assertRaises(UnsafeURLError):
            safe_get("http://169.254.169.254/latest/meta-data/")

    def test_rejects_private_ip(self):
        with self.assertRaises(UnsafeURLError):
            safe_get("http://10.0.0.5/")

    def test_rejects_disallowed_scheme(self):
        with self.assertRaises(UnsafeURLError):
            safe_get("file:///etc/passwd")

    def test_rejects_disallowed_port(self):
        with self.assertRaises(UnsafeURLError):
            safe_get("http://example.com:8080/")


class ApiKnowledgeSourceApiTests(APITestCase):
    def setUp(self):
        self.user, self.business = create_business_with_owner()
        self.client_auth = authenticated_client(self.user)

    def test_api_source_requires_source_url(self):
        response = self.client_auth.post(
            "/api/v1/knowledge/", {"title": "Missing url", "source_type": "api"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_api_source_rejects_non_string_header_values(self):
        response = self.client_auth.post(
            "/api/v1/knowledge/",
            {
                "title": "Bad headers",
                "source_type": "api",
                "source_url": "https://example.com/data",
                "source_config": {"headers": {"X-Test": 123}},
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("apps.knowledge.tasks.process_document_task.delay")
    def test_api_source_enqueues_processing_task(self, mock_delay):
        response = self.client_auth.post(
            "/api/v1/knowledge/",
            {
                "title": "Products API",
                "source_type": "api",
                "source_url": "https://example.com/products",
                "source_config": {"headers": {"Accept": "application/json"}},
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        mock_delay.assert_called_once()
