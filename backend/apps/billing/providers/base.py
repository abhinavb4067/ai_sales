from abc import ABC, abstractmethod
from dataclasses import dataclass, field


class WebhookVerificationError(Exception):
    """Raised when a webhook payload's signature doesn't check out, or the
    provider doesn't support webhooks at all. The view layer always treats
    this the same way — reject with 400, never process the payload."""


@dataclass
class CheckoutSession:
    """Normalized result of starting a checkout — the dashboard only ever
    sees this shape, never a provider-specific response. Two provider
    styles exist in the wild: redirect-to-hosted-page (Stripe-style —
    checkout_url is enough) and client-side-modal (Razorpay-style — the
    frontend needs a key + an id to open the provider's own JS widget,
    carried in client_data). A provider only populates the fields its
    flow actually uses."""

    checkout_url: str = ""
    external_customer_id: str = ""
    external_subscription_id: str = ""
    client_data: dict = field(default_factory=dict)


class PaymentProvider(ABC):
    """Normalized interface every payment provider (manual admin
    assignment today; Razorpay also implemented; Stripe could slot in
    the same way later) must implement. Nothing outside apps.billing may
    depend on a provider-specific SDK/response shape — mirrors the
    AIProvider abstraction in apps.ai.providers.
    """

    @abstractmethod
    def start_checkout(self, *, business, plan) -> CheckoutSession:
        """Begin a purchase of `plan` for `business`. For providers that
        can't redirect to a hosted checkout (e.g. manual), this may
        activate the subscription immediately and return a checkout_url
        that just points back at the dashboard. For real gateways, the
        subscription is NOT activated here — only once a webhook confirms
        payment (see apps.billing.services.handle_*_webhook_event)."""

    @abstractmethod
    def cancel_subscription(self, subscription) -> None:
        """Cancel at the provider. Must not raise if already cancelled."""

    @abstractmethod
    def construct_webhook_event(self, *, payload: bytes, headers: dict) -> dict:
        """Verify the webhook signature and return the parsed event body.
        Must raise WebhookVerificationError (never return an unverified
        payload) if the signature is missing/invalid, or the provider
        doesn't support webhooks."""
