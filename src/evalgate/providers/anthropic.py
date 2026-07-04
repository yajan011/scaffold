"""Anthropic provider adapter.

Wraps the official ``anthropic`` SDK behind the Provider protocol. Logic is
stubbed for v1 scaffolding.
"""

from __future__ import annotations

from typing import Any

from evalgate.models import Message
from evalgate.providers.base import Completion


class AnthropicProvider:
    """Provider backed by the Anthropic Messages API."""

    name = "anthropic"

    def __init__(self, model: str, api_key_env: str = "ANTHROPIC_API_KEY") -> None:
        self.model = model
        self.api_key_env = api_key_env

    def complete(self, messages: list[Message], params: dict[str, Any]) -> Completion:
        """Call Anthropic and return a normalized Completion.

        Not yet implemented — placeholder for v1 scaffolding.
        """
        raise NotImplementedError("AnthropicProvider.complete is not implemented yet")
