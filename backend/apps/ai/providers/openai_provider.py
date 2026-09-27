import json

from apps.ai.providers.base import AIProvider, AIResponse, EmbeddingResult, ToolCall, Usage


class OpenAIProvider(AIProvider):
    def _client(self):
        from openai import OpenAI

        return OpenAI(api_key=self.config.api_key)

    def generate(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        temperature: float = 0.4,
        max_tokens: int = 800,
    ) -> AIResponse:
        client = self._client()
        kwargs = {
            "model": self.config.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if tools:
            kwargs["tools"] = [{"type": "function", "function": t} for t in tools]
            kwargs["tool_choice"] = "auto"

        completion = client.chat.completions.create(**kwargs)
        choice = completion.choices[0]
        message = choice.message

        tool_calls = []
        for tc in (getattr(message, "tool_calls", None) or []):
            try:
                arguments = json.loads(tc.function.arguments or "{}")
            except (json.JSONDecodeError, TypeError):
                arguments = {}
            tool_calls.append(ToolCall(id=tc.id, name=tc.function.name, arguments=arguments))

        usage = completion.usage
        return AIResponse(
            content=message.content or "",
            tool_calls=tool_calls,
            usage=Usage(
                input_tokens=getattr(usage, "prompt_tokens", 0) or 0,
                output_tokens=getattr(usage, "completion_tokens", 0) or 0,
            ),
            finish_reason=choice.finish_reason or "stop",
        )

    def embed(self, texts: list[str]) -> EmbeddingResult:
        client = self._client()
        model = self.config.extra.get("embedding_model", "text-embedding-3-small")
        response = client.embeddings.create(model=model, input=texts)
        vectors = [item.embedding for item in response.data]
        usage = response.usage
        return EmbeddingResult(
            vectors=vectors,
            usage=Usage(input_tokens=getattr(usage, "prompt_tokens", 0) or 0),
        )

    def count_tokens(self, text: str) -> int:
        try:
            import tiktoken

            encoding = tiktoken.encoding_for_model(self.config.model)
            return len(encoding.encode(text))
        except Exception:
            # Fallback heuristic — good enough for usage estimates when the
            # exact tokenizer for a model isn't available (e.g. new models,
            # non-OpenAI models routed through this provider's API).
            return max(1, len(text) // 4)
