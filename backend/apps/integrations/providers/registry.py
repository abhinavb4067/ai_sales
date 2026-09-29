from apps.integrations.models import Integration
from apps.integrations.providers.whatsapp import WhatsAppProvider

_PROVIDERS = {
    Integration.Provider.WHATSAPP: WhatsAppProvider,
}


def get_integration_provider(provider_key: str):
    """Single swap point — mirrors apps.ai.providers.registry and
    apps.billing.providers.registry. Adding Telegram/Slack/etc. later is
    registering a new class here."""
    provider_cls = _PROVIDERS.get(provider_key)
    if provider_cls is None:
        raise ValueError(f"No IntegrationProvider registered for '{provider_key}'.")
    return provider_cls()
