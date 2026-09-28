from apps.billing.providers.base import CheckoutSession, PaymentProvider


class ManualPaymentProvider(PaymentProvider):
    """No real payment gateway wired up yet — an owner/admin picks a plan
    and it activates immediately (apps.billing.services.activate_subscription
    does the actual work; this class exists so the calling code path is
    identical to what a real StripeProvider will look like later).
    """

    def start_checkout(self, *, business, plan) -> CheckoutSession:
        return CheckoutSession(checkout_url="", external_customer_id="", external_subscription_id="")

    def cancel_subscription(self, subscription) -> None:
        return None

    def verify_webhook_signature(self, *, payload: bytes, headers: dict) -> bool:
        return False
