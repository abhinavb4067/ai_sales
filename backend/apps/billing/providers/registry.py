from django.conf import settings

from apps.billing.providers.manual import ManualPaymentProvider
from apps.billing.providers.razorpay_provider import RazorpayPaymentProvider

_PROVIDERS = {
    "manual": ManualPaymentProvider,
    "razorpay": RazorpayPaymentProvider,
}


def get_payment_provider():
    """Single swap point — mirrors apps.ai.providers.registry. Adding
    another provider later is registering a new class here, nothing that
    calls this function needs to change."""
    provider_key = getattr(settings, "PAYMENT_PROVIDER", "manual")
    provider_cls = _PROVIDERS.get(provider_key, ManualPaymentProvider)
    return provider_cls()
