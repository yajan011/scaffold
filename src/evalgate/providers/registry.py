"""Resolve a provider name to a Provider instance.

Logic is stubbed for v1 scaffolding.
"""

from __future__ import annotations

from evalgate.providers.base import Provider


def get_provider(name: str, model: str, api_key_env: str | None = None) -> Provider:
    """Construct the Provider adapter registered under ``name``.

    Not yet implemented — placeholder for v1 scaffolding.
    """
    raise NotImplementedError("providers.registry.get_provider is not implemented yet")
