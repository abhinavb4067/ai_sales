import hashlib
import hmac
import json

from django.conf import settings

from apps.billing.providers.base import CheckoutSession, PaymentProvider, WebhookVerificationError


class RazorpayPaymentProvider(PaymentProvider):
    """Razorpay has no Stripe-style hosted checkout redirect — a
    Subscription is created server-side, then the frontend opens
    Razorpay's own client-side Checkout widget (checkout.js) with that
    subscription id to collect payment authorization. The subscription
    only moves to ACTIVE once a signed webhook confirms the charge
    (subscription.activated / subscription.charged) — start_checkout
    never activates anything itself, same contract as every other
    provider.
    """

    def _client(self):
        import razorpay

        return razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))

    def start_checkout(self, *, business, plan) -> CheckoutSession:
        subscription = self._client().subscription.create(
            {
                "plan_id": plan.razorpay_plan_id,
                "customer_notify": 1,
                "total_count": 120,  # 10 years of monthly cycles — Razorpay has no "until cancelled" option
                "notes": {"business_id": str(business.id), "plan_code": plan.code},
            }
        )
        return CheckoutSession(
            external_subscription_id=subscription["id"],
            client_data={
                "razorpay_subscription_id": subscription["id"],
                "key_id": settings.RAZORPAY_KEY_ID,
            },
        )

    def cancel_subscription(self, subscription) -> None:
        if not subscription.external_subscription_id:
            return
        try:
            self._client().subscription.cancel(subscription.external_subscription_id)
        except Exception:
            # Already cancelled/expired at the provider — not our problem
            # to surface, our own status field is the source of truth for
            # the rest of the app either way.
            pass

    def construct_webhook_event(self, *, payload: bytes, headers: dict) -> dict:
        signature = headers.get("X-Razorpay-Signature", "")
        expected = hmac.new(settings.RAZORPAY_WEBHOOK_SECRET.encode(), payload, hashlib.sha256).hexdigest()
        if not signature or not hmac.compare_digest(signature, expected):
            raise WebhookVerificationError("Invalid Razorpay webhook signature.")
        try:
            return json.loads(payload)
        except (ValueError, TypeError) as exc:
            raise WebhookVerificationError("Malformed Razorpay webhook payload.") from exc
