import requests

from apps.ai.providers.base import AIProvider, AIResponse, EmbeddingResult, ToolCall, Usage

_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"


def _to_gemini_contents(messages: list[dict]) -> tuple[str | None, list[dict]]:
    """Gemini has no "system" role — a leading system message is pulled out
    as systemInstruction, and OpenAI's assistant/user roles map to
    model/user."""
    system_text = None
    contents = []
    for message in messages:
        role = message.get("role")
        text = message.get("content") or ""
        if role == "system":
            system_text = (system_text + "\n" + text) if system_text else text
            continue
        contents.append({
            "role": "model" if role == "assistant" else "user",
            "parts": [{"text": text}],
        })
    return system_text, contents


def _to_gemini_tools(tools: list[dict]) -> list[dict]:
    return [{
        "functionDeclarations": [
            {"name": t["name"], "description": t.get("description", ""), "parameters": t.get("parameters", {})}
            for t in tools
        ]
    }]


class GeminiProvider(AIProvider):
    def generate(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        temperature: float = 0.4,
        max_tokens: int = 800,
    ) -> AIResponse:
        system_text, contents = _to_gemini_contents(messages)
        payload = {
            "contents": contents,
            "generationConfig": {"temperature": temperature, "maxOutputTokens": max_tokens},
        }
        if system_text:
            payload["systemInstruction"] = {"parts": [{"text": system_text}]}
        if tools:
            payload["tools"] = _to_gemini_tools(tools)

        response = requests.post(
            f"{_BASE_URL}/models/{self.config.model}:generateContent",
            params={"key": self.config.api_key},
            json=payload,
            timeout=60,
        )
        response.raise_for_status()
        data = response.json()

        candidate = (data.get("candidates") or [{}])[0]
        parts = candidate.get("content", {}).get("parts", [])

        text_chunks = []
        tool_calls = []
        for part in parts:
            if "text" in part:
                text_chunks.append(part["text"])
            elif "functionCall" in part:
                call = part["functionCall"]
                tool_calls.append(ToolCall(
                    id=call.get("name", "call"),
                    name=call.get("name", ""),
                    arguments=call.get("args", {}) or {},
                ))

        usage_meta = data.get("usageMetadata", {})
        return AIResponse(
            content="".join(text_chunks),
            tool_calls=tool_calls,
            usage=Usage(
                input_tokens=usage_meta.get("promptTokenCount", 0) or 0,
                output_tokens=usage_meta.get("candidatesTokenCount", 0) or 0,
            ),
            finish_reason=(candidate.get("finishReason") or "STOP").lower(),
        )

    def embed(self, texts: list[str]) -> EmbeddingResult:
        model = self.config.extra.get("embedding_model", "text-embedding-004")
        vectors = []
        total_tokens = 0
        for text in texts:
            response = requests.post(
                f"{_BASE_URL}/models/{model}:embedContent",
                params={"key": self.config.api_key},
                json={"content": {"parts": [{"text": text}]}},
                timeout=60,
            )
            response.raise_for_status()
            data = response.json()
            vectors.append(data.get("embedding", {}).get("values", []))
            total_tokens += self.count_tokens(text)
        return EmbeddingResult(vectors=vectors, usage=Usage(input_tokens=total_tokens))

    def count_tokens(self, text: str) -> int:
        # Gemini's countTokens API requires a network call per text; a
        # heuristic avoids an extra round trip for every usage estimate
        # (same approach OpenAIProvider falls back to for unknown models).
        return max(1, len(text) // 4)
