from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class CheckoutSession:
    """Normalized result of starting a checkout — the dashboard only ever
    sees this shape, never a provider-specific response."""

    checkout_url: str
    external_customer_id: str
    external_subscription_id: str


class PaymentProvider(ABC):
    """Normalized interface every payment provider (manual admin
    assignment today; Stripe/Razorpay later) must implement. Nothing
    outside apps.billing may depend on a provider-specific SDK/response
    shape — mirrors the AIProvider abstraction in apps.ai.providers.
    """

    @abstractmethod
    def start_checkout(self, *, business, plan) -> CheckoutSession:
        """Begin a purchase of `plan` for `business`. For providers that
        can't redirect to a hosted checkout (e.g. manual), this may
        activate the subscription immediately and return a checkout_url
        that just points back at the dashboard."""

    @abstractmethod
    def cancel_subscription(self, subscription) -> None:
        """Cancel at the provider. Must not raise if already cancelled."""

    @abstractmethod
    def verify_webhook_signature(self, *, payload: bytes, headers: dict) -> bool:
        """Providers that use webhooks (Stripe/Razorpay) must verify the
        signature before any webhook payload is trusted. Manual has no
        webhooks, so this always returns False."""
