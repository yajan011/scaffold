"""OpenAI provider adapter.

Wraps the official ``openai`` SDK behind the Provider protocol. The SDK client is
injected (constructed by the registry from a resolved API key, or by a test), so
this class performs no key handling of its own.
"""

from __future__ import annotations

from typing import Any

from ankora.models import Message
from ankora.providers.base import Completion

# Determinism defaults (see CLAUDE.md "Determinism rules").
DEFAULT_TEMPERATURE = 0
DEFAULT_SEED = 0

# gen_ai.request.* params we forward to the Chat Completions API as-is.
_PASSTHROUGH_PARAMS = (
    "top_p",
    "max_tokens",
    "frequency_penalty",
    "presence_penalty",
    "stop",
)


class OpenAIProvider:
    """Provider backed by the OpenAI Chat Completions API."""

    name = "openai"
    requires_key = True

    def __init__(self, model: str, client: Any, *, seed: int | None = DEFAULT_SEED) -> None:
        self.model = model
        self.client = client
        self.seed = seed

    @staticmethod
    def default_client(api_key: str) -> Any:
        """Construct a real OpenAI SDK client. Imported lazily to keep import cheap."""
        import openai

        return openai.OpenAI(api_key=api_key)

    def complete(self, messages: list[Message], params: dict[str, Any]) -> Completion:
        """Call OpenAI and return a normalized Completion."""
        request = self._build_request(messages, params)
        response = self.client.chat.completions.create(**request)
        return self._map_response(response)

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one embedding vector per text via the embeddings endpoint."""
        response = self.client.embeddings.create(model=self.model, input=texts)
        return [item.embedding for item in response.data]

    def _build_request(self, messages: list[Message], params: dict[str, Any]) -> dict[str, Any]:
        request: dict[str, Any] = {
            "model": params.get("model", self.model),
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": params.get("temperature", DEFAULT_TEMPERATURE),
        }
        for key in _PASSTHROUGH_PARAMS:
            if params.get(key) is not None:
                request[key] = params[key]
        seed = params.get("seed", self.seed)
        if seed is not None:
            request["seed"] = seed
        return request

    @staticmethod
    def _map_response(response: Any) -> Completion:
        message = response.choices[0].message
        text = getattr(message, "content", None) or ""

        tool_calls: list[dict[str, Any]] = []
        for call in getattr(message, "tool_calls", None) or []:
            function = getattr(call, "function", None)
            tool_calls.append(
                {
                    "id": getattr(call, "id", None),
                    "type": getattr(call, "type", "function"),
                    "name": getattr(function, "name", None),
                    "arguments": getattr(function, "arguments", None),
                }
            )

        usage: dict[str, Any] = {}
        raw_usage = getattr(response, "usage", None)
        if raw_usage is not None:
            usage = {
                "input_tokens": getattr(raw_usage, "prompt_tokens", None),
                "output_tokens": getattr(raw_usage, "completion_tokens", None),
                "total_tokens": getattr(raw_usage, "total_tokens", None),
            }

        return Completion(text=text, tool_calls=tool_calls, raw=response, usage=usage)
