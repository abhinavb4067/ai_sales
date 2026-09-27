"""AIProvider abstraction.

Nothing outside apps/ai/providers/*.py should ever see a provider-specific
response object (OpenAI SDK types, etc). Every provider implementation
normalizes into AIResponse / EmbeddingResult so the orchestrator, tool
service, and every other caller are provider-agnostic.

BYOK readiness (Refinement 7): `AIProviderConfig.api_key` is passed in
per-call rather than read from Django settings inside the provider class.
Today it's always populated from settings.OPENAI_API_KEY (managed mode);
a future BYOK feature only needs to source that string from an encrypted
per-business credential instead — no provider or orchestrator code changes.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class AIProviderConfig:
    api_key: str
    model: str
    extra: dict = field(default_factory=dict)


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass
class AIResponse:
    content: str
    tool_calls: list[ToolCall]
    usage: Usage
    finish_reason: str


@dataclass
class EmbeddingResult:
    vectors: list[list[float]]
    usage: Usage


class AIProvider(ABC):
    def __init__(self, config: AIProviderConfig):
        self.config = config

    @abstractmethod
    def generate(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        temperature: float = 0.4,
        max_tokens: int = 800,
    ) -> AIResponse:
        """messages: normalized [{role, content}] list. tools: normalized
        JSON-schema tool definitions (OpenAI function-calling shape is used
        as the canonical intermediate format since it's the most widely
        supported; providers that speak a different tool format translate
        at the edge inside their own implementation)."""

    @abstractmethod
    def embed(self, texts: list[str]) -> EmbeddingResult:
        ...

    @abstractmethod
    def count_tokens(self, text: str) -> int:
        ...
