"""Echo provider: a deterministic, offline, keyless provider.

It performs no network call and needs no API key — it simply returns the last
user message as the completion. This makes the full replay/gate loop runnable in
CI, demos, and tests with no provider credentials. Select it with
``target.provider: echo`` in ankora.yaml.
"""

from __future__ import annotations

from typing import Any

from ankora.models import Message
from ankora.providers.base import Completion


class EchoProvider:
    """A provider that echoes back the last user message. No key, no network."""

    name = "echo"
    requires_key = False

    def __init__(self, model: str = "echo", client: Any | None = None) -> None:
        self.model = model
        self.client = client

    @staticmethod
    def default_client(api_key: str) -> Any:
        """Echo needs no client; present for a uniform provider interface."""
        return None

    def complete(self, messages: list[Message], params: dict[str, Any]) -> Completion:
        text = ""
        for message in messages:
            if message.role == "user":
                text = message.content
        if not text and messages:
            text = messages[-1].content
        return Completion(text=text, tool_calls=[], raw=None, usage={})

    def embed(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError("EchoProvider does not support embeddings.")
