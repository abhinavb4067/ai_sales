from apps.billing.providers.base import CheckoutSession, PaymentProvider, WebhookVerificationError


class ManualPaymentProvider(PaymentProvider):
    """No real payment gateway wired up yet — an owner/admin picks a plan
    and it activates immediately (apps.billing.services.activate_subscription
    does the actual work; this class exists so the calling code path is
    identical to what a real gateway provider looks like).
    """

    def start_checkout(self, *, business, plan) -> CheckoutSession:
        return CheckoutSession()

    def cancel_subscription(self, subscription) -> None:
        return None

    def construct_webhook_event(self, *, payload: bytes, headers: dict) -> dict:
        raise WebhookVerificationError("Manual provider has no webhooks.")
