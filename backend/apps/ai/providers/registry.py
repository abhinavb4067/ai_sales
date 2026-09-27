"""Resolves which AIProvider implementation + credentials to use for a
given Agent.

Today (managed mode) this always returns the platform's own OpenAI key
from settings. BYOK (Refinement 7) will add a per-Business encrypted
credential lookup here — the call signature (`get_provider_for_agent`)
does not need to change for that; only the inside of this function does.
Never pass provider credentials through to the frontend or log them.
"""
from django.conf import settings

from apps.ai.providers.base import AIProvider, AIProviderConfig
from apps.ai.providers.local_provider import LocalModelProvider
from apps.ai.providers.openai_provider import OpenAIProvider

_PROVIDERS: dict[str, type[AIProvider]] = {
    "openai": OpenAIProvider,
    "local": LocalModelProvider,
}


def get_provider_for_agent(agent) -> AIProvider:
    provider_key = settings.AI_PROVIDER
    provider_cls = _PROVIDERS.get(provider_key)
    if provider_cls is None:
        raise ValueError(f"Unknown AI provider configured: {provider_key}")

    # Managed mode: platform-owned key. BYOK would branch here on a future
    # agent.business.ai_credential (encrypted) instead of settings.
    config = AIProviderConfig(
        api_key=settings.OPENAI_API_KEY,
        model=agent.model,
        extra={"embedding_model": settings.OPENAI_EMBEDDING_MODEL},
    )
    return provider_cls(config)


def get_embedding_provider() -> AIProvider:
    """Embeddings are not per-agent (unlike chat model choice) — one
    platform-level embedding model per business today. Still routed
    through the same provider registry/config shape so BYOK can plug in
    here the same way it will for get_provider_for_agent."""
    provider_key = settings.AI_PROVIDER
    provider_cls = _PROVIDERS.get(provider_key)
    if provider_cls is None:
        raise ValueError(f"Unknown AI provider configured: {provider_key}")

    config = AIProviderConfig(
        api_key=settings.OPENAI_API_KEY,
        model=settings.OPENAI_EMBEDDING_MODEL,
        extra={"embedding_model": settings.OPENAI_EMBEDDING_MODEL},
    )
    return provider_cls(config)
