"""OpenAI provider adapter.

Wraps the official ``openai`` SDK behind the Provider protocol. The SDK client is
injected (constructed by the registry from a resolved API key, or by a test), so
this class performs no key handling of its own.
"""

from __future__ import annotations

from typing import Any

from ankora.models import Message
from ankora.providers.base import Completion
from ankora.providers.errors import request_with_retry

# Determinism defaults (see CLAUDE.md "Determinism rules").
DEFAULT_TEMPERATURE = 0
# seed is opt-in: many OpenAI-compatible endpoints (e.g. Gemini) reject an
# unknown "seed" field with a 400, so it is only sent when explicitly configured.
DEFAULT_SEED = None

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
    def default_client(api_key: str, base_url: str | None = None) -> Any:
        """Construct a real OpenAI SDK client. Imported lazily to keep import cheap.

        When ``base_url`` is set, the client targets that OpenAI-compatible
        endpoint; when ``None`` it hits api.openai.com unchanged.
        """
        import openai

        kwargs: dict[str, Any] = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        return openai.OpenAI(**kwargs)

    def complete(self, messages: list[Message], params: dict[str, Any]) -> Completion:
        """Call OpenAI and return a normalized Completion."""
        request = self._build_request(messages, params)
        response = request_with_retry(
            lambda: self.client.chat.completions.create(**request), provider=self.name
        )
        return self._map_response(response)

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one embedding vector per text via the embeddings endpoint."""
        response = request_with_retry(
            lambda: self.client.embeddings.create(model=self.model, input=texts),
            provider=self.name,
        )
        return [item.embedding for item in response.data]

    def _build_request(self, messages: list[Message], params: dict[str, Any]) -> dict[str, Any]:
        request: dict[str, Any] = {
            "model": params.get("model", self.model),
            "messages": [{"role": m.role, "content": m.content} for m in messages],
        }
        # Optional params: send only those with a non-None value. A null is
        # omitted entirely rather than forwarded (which some endpoints reject).
        optional: dict[str, Any] = {
            "temperature": params.get("temperature", DEFAULT_TEMPERATURE),
            "seed": params.get("seed", self.seed),
        }
        for key in _PASSTHROUGH_PARAMS:
            optional[key] = params.get(key)
        for key, value in optional.items():
            if value is not None:
                request[key] = value
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
