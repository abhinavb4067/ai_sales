from unittest.mock import MagicMock, patch

from rest_framework import status
from rest_framework.test import APITestCase

from apps.core.testing import authenticated_client, create_business_with_owner
from apps.webhooks.models import OutboundWebhookDelivery, WebhookSubscription
from apps.webhooks.services import dispatch_event
from apps.webhooks.tasks import deliver_webhook_task, sign_payload


class WebhookSubscriptionApiTests(APITestCase):
    def setUp(self):
        self.user, self.business = create_business_with_owner()
        self.client_auth = authenticated_client(self.user)

    def test_create_returns_secret_exactly_once(self):
        response = self.client_auth.post(
            "/api/v1/webhook-subscriptions/",
            {"url": "https://example.com/hooks/ectama", "event_types": ["lead.created"]},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertIn("secret", response.data)

        subscription_id = response.data["id"]
        list_response = self.client_auth.get("/api/v1/webhook-subscriptions/")
        self.assertNotIn("secret", list_response.data["results"][0])

    def test_rejects_unknown_event_type(self):
        response = self.client_auth.post(
            "/api/v1/webhook-subscriptions/",
            {"url": "https://example.com/hooks", "event_types": ["not.a.real.event"]},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cannot_see_another_businesss_subscriptions(self):
        other_user, other_business = create_business_with_owner(email="other@example.com")
        WebhookSubscription.objects.create(
            business=other_business, url="https://other.com/hook", secret="s3cr3t"
        )
        response = self.client_auth.get("/api/v1/webhook-subscriptions/")
        self.assertEqual(len(response.data["results"]), 0)


class DispatchEventTests(APITestCase):
    def setUp(self):
        self.user, self.business = create_business_with_owner()

    @patch("apps.webhooks.tasks.deliver_webhook_task.delay")
    def test_dispatch_creates_delivery_for_matching_subscription(self, mock_delay):
        subscription = WebhookSubscription.objects.create(
            business=self.business, url="https://example.com/hook", secret="s3cr3t",
            event_types=["lead.created"],
        )
        dispatch_event(self.business, "lead.created", {"lead_id": 1})

        delivery = OutboundWebhookDelivery.objects.get(subscription=subscription)
        self.assertEqual(delivery.event_type, "lead.created")
        mock_delay.assert_called_once_with(delivery.id)

    @patch("apps.webhooks.tasks.deliver_webhook_task.delay")
    def test_dispatch_skips_subscription_not_wanting_event(self, mock_delay):
        WebhookSubscription.objects.create(
            business=self.business, url="https://example.com/hook", secret="s3cr3t",
            event_types=["appointment.booked"],
        )
        dispatch_event(self.business, "lead.created", {"lead_id": 1})

        self.assertFalse(OutboundWebhookDelivery.objects.exists())
        mock_delay.assert_not_called()

    @patch("apps.webhooks.tasks.deliver_webhook_task.delay")
    def test_empty_event_types_means_subscribed_to_everything(self, mock_delay):
        WebhookSubscription.objects.create(
            business=self.business, url="https://example.com/hook", secret="s3cr3t", event_types=[],
        )
        dispatch_event(self.business, "appointment.cancelled", {"appointment_id": 5})

        self.assertTrue(OutboundWebhookDelivery.objects.exists())

    @patch("apps.webhooks.tasks.deliver_webhook_task.delay")
    def test_dispatch_skips_inactive_subscription(self, mock_delay):
        WebhookSubscription.objects.create(
            business=self.business, url="https://example.com/hook", secret="s3cr3t", is_active=False,
        )
        dispatch_event(self.business, "lead.created", {"lead_id": 1})

        self.assertFalse(OutboundWebhookDelivery.objects.exists())


class DeliverWebhookTaskTests(APITestCase):
    def setUp(self):
        self.user, self.business = create_business_with_owner()
        self.subscription = WebhookSubscription.objects.create(
            business=self.business, url="https://example.com/hook", secret="s3cr3t",
        )
        self.delivery = OutboundWebhookDelivery.objects.create(
            business=self.business, subscription=self.subscription, event_type="lead.created", payload={"lead_id": 1},
        )

    @patch("apps.knowledge.net_safety.validate_url_is_safe")
    @patch("apps.webhooks.tasks.requests.post")
    def test_successful_delivery_signs_payload_and_marks_succeeded(self, mock_post, mock_validate):
        mock_post.return_value = MagicMock(status_code=200)

        deliver_webhook_task(self.delivery.id)

        self.delivery.refresh_from_db()
        self.assertEqual(self.delivery.status, OutboundWebhookDelivery.Status.SUCCEEDED)
        self.assertEqual(self.delivery.response_status_code, 200)
        self.assertIsNotNone(self.delivery.delivered_at)

        sent_headers = mock_post.call_args.kwargs["headers"]
        sent_body = mock_post.call_args.kwargs["data"]
        expected_signature = sign_payload("s3cr3t", sent_body)
        self.assertEqual(sent_headers["X-Ectama-Signature"], f"sha256={expected_signature}")
        self.assertEqual(sent_headers["X-Ectama-Event"], "lead.created")

    @patch("apps.knowledge.net_safety.validate_url_is_safe")
    @patch("apps.webhooks.tasks.requests.post")
    def test_non_2xx_response_retries(self, mock_post, mock_validate):
        mock_post.return_value = MagicMock(status_code=500)

        with self.assertRaises(Exception):  # celery Retry
            deliver_webhook_task(self.delivery.id)

        self.delivery.refresh_from_db()
        self.assertEqual(self.delivery.attempt_count, 1)
        self.assertNotEqual(self.delivery.status, OutboundWebhookDelivery.Status.SUCCEEDED)

    def test_unsafe_url_fails_permanently_without_retry(self):
        self.subscription.url = "http://169.254.169.254/latest/meta-data/"
        self.subscription.save(update_fields=["url"])

        deliver_webhook_task(self.delivery.id)

        self.delivery.refresh_from_db()
        self.assertEqual(self.delivery.status, OutboundWebhookDelivery.Status.FAILED)
        self.assertIn("disallowed", self.delivery.last_error.lower())
