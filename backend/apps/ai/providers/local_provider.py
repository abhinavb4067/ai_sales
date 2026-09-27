from apps.ai.providers.base import AIProvider, AIResponse, EmbeddingResult, Usage


class LocalModelProvider(AIProvider):
    """Placeholder for a self-hosted/local model backend (e.g. an
    OpenAI-API-compatible local server). Not wired into Phase 1 — exists so
    AIProviderConfig/registry plumbing is proven against more than one
    implementation from day one, per the "don't tightly couple to one
    provider" requirement."""

    def generate(self, messages, tools=None, temperature=0.4, max_tokens=800) -> AIResponse:
        raise NotImplementedError("LocalModelProvider is not implemented yet.")

    def embed(self, texts: list[str]) -> EmbeddingResult:
        raise NotImplementedError("LocalModelProvider is not implemented yet.")

    def count_tokens(self, text: str) -> int:
        return max(1, len(text) // 4)
