"""Anthropic provider adapter.

Wraps the official ``anthropic`` SDK behind the Provider protocol. The SDK client
is injected (constructed by the registry from a resolved API key, or by a test),
so this class performs no key handling of its own.
"""

from __future__ import annotations

from typing import Any

from ankora.models import Message
from ankora.providers.base import Completion

# Determinism defaults (see CLAUDE.md "Determinism rules"). Anthropic requires
# max_tokens and does not accept a seed param.
DEFAULT_TEMPERATURE = 0
DEFAULT_MAX_TOKENS = 1024


class AnthropicProvider:
    """Provider backed by the Anthropic Messages API."""

    name = "anthropic"
    requires_key = True

    def __init__(self, model: str, client: Any) -> None:
        self.model = model
        self.client = client

    @staticmethod
    def default_client(api_key: str, base_url: str | None = None) -> Any:
        """Construct a real Anthropic SDK client. Imported lazily to keep import cheap.

        ``base_url`` optionally overrides the endpoint; ``None`` uses the default.
        """
        import anthropic

        kwargs: dict[str, Any] = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        return anthropic.Anthropic(**kwargs)

    def complete(self, messages: list[Message], params: dict[str, Any]) -> Completion:
        """Call Anthropic and return a normalized Completion."""
        request = self._build_request(messages, params)
        response = self.client.messages.create(**request)
        return self._map_response(response)

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Anthropic has no first-party embeddings endpoint."""
        raise NotImplementedError(
            "Anthropic has no first-party embeddings endpoint; "
            "configure a dedicated embedding provider (e.g. openai)."
        )

    def _build_request(self, messages: list[Message], params: dict[str, Any]) -> dict[str, Any]:
        # Anthropic takes system prompts out-of-band and only user/assistant turns
        # in `messages`.
        system_parts = [m.content for m in messages if m.role == "system"]
        conversation = [
            {"role": m.role, "content": m.content} for m in messages if m.role != "system"
        ]
        request: dict[str, Any] = {
            "model": params.get("model", self.model),
            "messages": conversation,
            "temperature": params.get("temperature", DEFAULT_TEMPERATURE),
            "max_tokens": params.get("max_tokens", DEFAULT_MAX_TOKENS),
        }
        if params.get("top_p") is not None:
            request["top_p"] = params["top_p"]
        if system_parts:
            request["system"] = "\n\n".join(system_parts)
        return request

    @staticmethod
    def _map_response(response: Any) -> Completion:
        text_parts: list[str] = []
        tool_calls: list[dict[str, Any]] = []
        for block in getattr(response, "content", None) or []:
            block_type = getattr(block, "type", None)
            if block_type == "text":
                text_parts.append(getattr(block, "text", "") or "")
            elif block_type == "tool_use":
                tool_calls.append(
                    {
                        "id": getattr(block, "id", None),
                        "name": getattr(block, "name", None),
                        "arguments": getattr(block, "input", None),
                    }
                )

        usage: dict[str, Any] = {}
        raw_usage = getattr(response, "usage", None)
        if raw_usage is not None:
            usage = {
                "input_tokens": getattr(raw_usage, "input_tokens", None),
                "output_tokens": getattr(raw_usage, "output_tokens", None),
            }

        return Completion(
            text="".join(text_parts),
            tool_calls=tool_calls,
            raw=response,
            usage=usage,
        )
