"""OpenAI provider adapter.

Wraps the official ``openai`` SDK behind the Provider protocol. Logic is stubbed
for v1 scaffolding.
"""

from __future__ import annotations

from typing import Any

from evalgate.models import Message
from evalgate.providers.base import Completion


class OpenAIProvider:
    """Provider backed by the OpenAI Chat Completions API."""

    name = "openai"

    def __init__(self, model: str, api_key_env: str = "OPENAI_API_KEY") -> None:
        self.model = model
        self.api_key_env = api_key_env

    def complete(self, messages: list[Message], params: dict[str, Any]) -> Completion:
        """Call OpenAI and return a normalized Completion.

        Not yet implemented — placeholder for v1 scaffolding.
        """
        raise NotImplementedError("OpenAIProvider.complete is not implemented yet")
