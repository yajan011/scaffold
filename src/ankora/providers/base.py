"""The Provider protocol and the normalized Completion type.

All network access to model providers happens behind this boundary so tests can
mock a single seam: every provider takes an *injected* SDK client, and API keys
are resolved (via :meth:`Config.resolve_api_key`) at construction time in the
registry — never stored on the provider or on this model.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from ankora.models import Message


class Completion(BaseModel):
    """A provider-neutral completion.

    ``raw`` holds the untouched SDK response object for callers that need
    provider-specific detail; it is not serialized as part of any persisted
    artifact.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    text: str = ""
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    raw: Any = None
    usage: dict[str, Any] = Field(default_factory=dict)


@runtime_checkable
class Provider(Protocol):
    """Minimal surface every provider adapter must implement."""

    name: str

    def complete(self, messages: list[Message], params: dict[str, Any]) -> Completion:
        """Return a completion for the given messages and params."""
        ...

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return an embedding vector per input text.

        Providers without a first-party embeddings endpoint may raise
        ``NotImplementedError``.
        """
        ...
