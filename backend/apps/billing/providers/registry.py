from django.conf import settings

from apps.billing.providers.manual import ManualPaymentProvider

_PROVIDERS = {
    "manual": ManualPaymentProvider,
}


def get_payment_provider():
    """Single swap point — mirrors apps.ai.providers.registry. Adding
    Stripe/Razorpay later is registering a new class here, nothing that
    calls this function needs to change."""
    provider_key = getattr(settings, "PAYMENT_PROVIDER", "manual")
    provider_cls = _PROVIDERS.get(provider_key, ManualPaymentProvider)
    return provider_cls()
