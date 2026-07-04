"""The Provider protocol and shared completion types.

All network access to model providers happens behind this boundary so tests can
mock a single seam. Logic is stubbed for v1 scaffolding.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, Field

from evalgate.models import Message


class Completion(BaseModel):
    """A normalized completion returned by any provider."""

    text: str
    raw: dict[str, Any] = Field(default_factory=dict)


@runtime_checkable
class Provider(Protocol):
    """Minimal surface every provider adapter must implement."""

    name: str

    def complete(self, messages: list[Message], params: dict[str, Any]) -> Completion:
        """Return a completion for the given messages and params."""
        ...
