import hashlib
import hmac
import json
from unittest.mock import MagicMock, patch

from django.test import override_settings
from rest_framework.test import APITestCase

from apps.billing.models import Plan, Subscription
from apps.billing.providers.base import WebhookVerificationError
from apps.billing.providers.razorpay_provider import RazorpayPaymentProvider
from apps.billing.services import handle_razorpay_webhook_event, initiate_plan_change
from apps.core.testing import authenticated_client, create_business_with_owner

RAZORPAY_SETTINGS = dict(
    PAYMENT_PROVIDER="razorpay",
    RAZORPAY_KEY_ID="rzp_test_key",
    RAZORPAY_KEY_SECRET="test_secret",
    RAZORPAY_WEBHOOK_SECRET="whsec_test",
)


def _sign(payload: bytes) -> str:
    return hmac.new(RAZORPAY_SETTINGS["RAZORPAY_WEBHOOK_SECRET"].encode(), payload, hashlib.sha256).hexdigest()


@override_settings(**RAZORPAY_SETTINGS)
class RazorpayCheckoutTests(APITestCase):
    def setUp(self):
        self.user, self.business = create_business_with_owner()

    @patch("razorpay.Client")
    def test_initiate_plan_change_starts_checkout_without_activating(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client.subscription.create.return_value = {"id": "sub_abc123"}
        mock_client_cls.return_value = mock_client

        growth = Plan.objects.get(code="growth")
        result = initiate_plan_change(self.business, growth)

        self.assertEqual(result["type"], "checkout")
        self.assertEqual(result["client_data"]["razorpay_subscription_id"], "sub_abc123")
        self.assertEqual(result["client_data"]["key_id"], "rzp_test_key")

        # Subscription must NOT be activated yet — only a webhook does that.
        self.business.subscription.refresh_from_db()
        self.assertEqual(self.business.subscription.plan.code, "starter")
        self.assertEqual(self.business.subscription.status, Subscription.Status.TRIAL)

    @patch("razorpay.Client")
    def test_change_plan_endpoint_returns_checkout_payload(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client.subscription.create.return_value = {"id": "sub_xyz"}
        mock_client_cls.return_value = mock_client

        client = authenticated_client(self.user)
        response = client.post("/api/v1/billing/subscription/change-plan/", {"plan_code": "growth"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["type"], "checkout")
        self.assertEqual(response.data["client_data"]["razorpay_subscription_id"], "sub_xyz")


@override_settings(**RAZORPAY_SETTINGS)
class RazorpayWebhookSignatureTests(APITestCase):
    def test_construct_webhook_event_rejects_missing_signature(self):
        provider = RazorpayPaymentProvider()
        with self.assertRaises(WebhookVerificationError):
            provider.construct_webhook_event(payload=b'{"event": "x"}', headers={})

    def test_construct_webhook_event_rejects_wrong_signature(self):
        provider = RazorpayPaymentProvider()
        with self.assertRaises(WebhookVerificationError):
            provider.construct_webhook_event(
                payload=b'{"event": "x"}', headers={"X-Razorpay-Signature": "bogus"}
            )

    def test_construct_webhook_event_accepts_valid_signature(self):
        provider = RazorpayPaymentProvider()
        payload = json.dumps({"event": "subscription.charged"}).encode()
        event = provider.construct_webhook_event(payload=payload, headers={"X-Razorpay-Signature": _sign(payload)})
        self.assertEqual(event["event"], "subscription.charged")


@override_settings(**RAZORPAY_SETTINGS)
class RazorpayWebhookViewTests(APITestCase):
    def setUp(self):
        self.user, self.business = create_business_with_owner()

    def _post_webhook(self, event_body: dict):
        payload = json.dumps(event_body).encode()
        return self.client.post(
            "/api/v1/billing/webhooks/razorpay/",
            data=payload,
            content_type="application/json",
            HTTP_X_RAZORPAY_SIGNATURE=_sign(payload),
        )

    def test_invalid_signature_rejected_with_400(self):
        response = self.client.post(
            "/api/v1/billing/webhooks/razorpay/",
            data=json.dumps({"event": "subscription.activated"}),
            content_type="application/json",
            HTTP_X_RAZORPAY_SIGNATURE="bogus",
        )
        self.assertEqual(response.status_code, 400)

    def test_subscription_activated_event_activates_business_subscription(self):
        growth = Plan.objects.get(code="growth")
        body = {
            "event": "subscription.activated",
            "payload": {
                "subscription": {
                    "entity": {
                        "id": "sub_123",
                        "customer_id": "cust_456",
                        "notes": {"business_id": str(self.business.id), "plan_code": growth.code},
                    }
                }
            },
        }
        response = self._post_webhook(body)
        self.assertEqual(response.status_code, 200)

        self.business.subscription.refresh_from_db()
        self.assertEqual(self.business.subscription.status, Subscription.Status.ACTIVE)
        self.assertEqual(self.business.subscription.plan_id, growth.id)
        self.assertEqual(self.business.subscription.provider, Subscription.Provider.RAZORPAY)
        self.assertEqual(self.business.subscription.external_subscription_id, "sub_123")

    def test_subscription_pending_event_marks_past_due(self):
        sub = self.business.subscription
        sub.external_subscription_id = "sub_789"
        sub.status = Subscription.Status.ACTIVE
        sub.save(update_fields=["external_subscription_id", "status"])

        body = {
            "event": "subscription.pending",
            "payload": {"subscription": {"entity": {"id": "sub_789"}}},
        }
        response = self._post_webhook(body)
        self.assertEqual(response.status_code, 200)

        sub.refresh_from_db()
        self.assertEqual(sub.status, Subscription.Status.PAST_DUE)

    def test_unknown_subscription_id_is_ignored_not_errored(self):
        body = {
            "event": "subscription.charged",
            "payload": {"subscription": {"entity": {"id": "sub_does_not_exist"}}},
        }
        response = self._post_webhook(body)
        self.assertEqual(response.status_code, 200)


@override_settings(**RAZORPAY_SETTINGS)
class RazorpayCancelTests(APITestCase):
    def setUp(self):
        self.user, self.business = create_business_with_owner()

    @patch("razorpay.Client")
    def test_cancel_subscription_calls_provider_and_sets_cancel_at_period_end(self, mock_client_cls):
        sub = self.business.subscription
        sub.provider = Subscription.Provider.RAZORPAY
        sub.external_subscription_id = "sub_cancel_me"
        sub.status = Subscription.Status.ACTIVE
        sub.save(update_fields=["provider", "external_subscription_id", "status"])

        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        client = authenticated_client(self.user)
        response = client.post("/api/v1/billing/subscription/cancel/")
        self.assertEqual(response.status_code, 200)
        mock_client.subscription.cancel.assert_called_once_with("sub_cancel_me")

        sub.refresh_from_db()
        self.assertTrue(sub.cancel_at_period_end)
        # Razorpay-provider subscriptions stay ACTIVE until the provider
        # confirms cancellation via webhook — not flipped synchronously.
        self.assertEqual(sub.status, Subscription.Status.ACTIVE)
