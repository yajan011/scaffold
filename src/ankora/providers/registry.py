"""Resolve a provider name to a constructed Provider instance.

Key resolution happens here: when no client is injected, the API key is read
from the config's env var (:meth:`Config.resolve_api_key`) and used to build a
real SDK client. Tests inject a fake client and never touch keys or the network.
"""

from __future__ import annotations

from typing import Any

from ankora.config import Config, ConfigError
from ankora.providers.anthropic import AnthropicProvider
from ankora.providers.base import Provider
from ankora.providers.echo import EchoProvider
from ankora.providers.openai import OpenAIProvider

_PROVIDERS = {
    "openai": OpenAIProvider,
    "anthropic": AnthropicProvider,
    "echo": EchoProvider,
}


def get_provider(
    name: str,
    config: Config,
    client: Any | None = None,
    model: str | None = None,
) -> Provider:
    """Construct the Provider adapter registered under ``name``.

    ``model`` defaults to the config's target model. If ``client`` is provided
    it is passed straight through (no key resolution); otherwise the API key is
    resolved from config and a real SDK client is built.
    """
    try:
        provider_cls = _PROVIDERS[name]
    except KeyError as exc:
        known = ", ".join(sorted(_PROVIDERS))
        raise ConfigError(f"Unknown provider {name!r}. Known providers: {known}.") from exc

    resolved_model = model or config.target.model
    provider_config = config.providers.get(name)
    requires_key = getattr(provider_cls, "requires_key", True)
    if client is None and requires_key:
        api_key = config.resolve_api_key(name)
        base_url = provider_config.base_url if provider_config else None
        client = provider_cls.default_client(api_key, base_url=base_url)

    kwargs: dict[str, Any] = {"model": resolved_model, "client": client}
    if provider_cls is OpenAIProvider:
        # seed is OpenAI-specific and opt-in (ProviderConfig.seed, default None).
        kwargs["seed"] = provider_config.seed if provider_config else None
    return provider_cls(**kwargs)
