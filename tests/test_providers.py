"""Tests for the provider layer, using injected fake SDK clients only.

No live API calls: every provider is constructed with a fake client that records
the request kwargs and returns a canned response object shaped like the real SDK.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from ankora.config import Config, ProviderConfig, TargetConfig
from ankora.models import Message
from ankora.providers.anthropic import AnthropicProvider
from ankora.providers.base import Completion
from ankora.providers.errors import (
    MAX_RETRY_DELAY,
    ProviderError,
    ProviderRateLimitError,
    ProviderServerError,
)
from ankora.providers.openai import OpenAIProvider
from ankora.providers.registry import get_provider


class _FakeAPIError(Exception):
    """Mimics an openai/anthropic APIStatusError (has status_code + response)."""

    def __init__(self, status_code: int, retry_after: float | None = None) -> None:
        super().__init__(f"HTTP {status_code}")
        self.status_code = status_code
        if retry_after is not None:
            self.response = SimpleNamespace(headers={"retry-after": str(retry_after)})


def _raising_openai_client(exc_factory: Any, *, succeed_after: int | None = None) -> Any:
    """OpenAI-shaped client whose chat.completions.create raises exc_factory().

    If ``succeed_after`` is set, the Nth call (1-indexed) returns a real response
    instead of raising, to exercise retry recovery.
    """
    state = {"calls": 0}

    def create(**kwargs: Any) -> Any:
        state["calls"] += 1
        if succeed_after is not None and state["calls"] >= succeed_after:
            message = SimpleNamespace(content="ok", tool_calls=None)
            return SimpleNamespace(choices=[SimpleNamespace(message=message)], usage=None)
        raise exc_factory()

    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    client._state = state  # type: ignore[attr-defined]
    return client


class _RecordingCreate:
    """Stands in for ``client.<...>.create``: records kwargs, returns a canned result."""

    def __init__(self, result: Any) -> None:
        self.result = result
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        return self.result


# --------------------------------------------------------------------------- #
# Fake response builders (shaped like the real SDK objects)
# --------------------------------------------------------------------------- #
def _openai_response(
    text: str,
    tool_calls: list[dict[str, Any]] | None = None,
    usage: tuple[int, int] = (10, 5),
) -> SimpleNamespace:
    calls = [
        SimpleNamespace(
            id=tc["id"],
            type="function",
            function=SimpleNamespace(name=tc["name"], arguments=tc["arguments"]),
        )
        for tc in (tool_calls or [])
    ]
    message = SimpleNamespace(content=text, tool_calls=calls or None)
    usage_ns = SimpleNamespace(
        prompt_tokens=usage[0], completion_tokens=usage[1], total_tokens=sum(usage)
    )
    return SimpleNamespace(choices=[SimpleNamespace(message=message)], usage=usage_ns)


def _openai_client(response: Any = None, vectors: list[list[float]] | None = None) -> Any:
    completions = _RecordingCreate(response)
    embeddings = _RecordingCreate(
        SimpleNamespace(data=[SimpleNamespace(embedding=v) for v in (vectors or [])])
    )
    client = SimpleNamespace(
        chat=SimpleNamespace(completions=completions),
        embeddings=embeddings,
    )
    return client


def _anthropic_response(
    text: str,
    tool_uses: list[dict[str, Any]] | None = None,
    usage: tuple[int, int] = (12, 7),
) -> SimpleNamespace:
    blocks: list[SimpleNamespace] = [SimpleNamespace(type="text", text=text)]
    for tu in tool_uses or []:
        blocks.append(
            SimpleNamespace(type="tool_use", id=tu["id"], name=tu["name"], input=tu["input"])
        )
    usage_ns = SimpleNamespace(input_tokens=usage[0], output_tokens=usage[1])
    return SimpleNamespace(content=blocks, usage=usage_ns)


def _anthropic_client(response: Any) -> Any:
    return SimpleNamespace(messages=_RecordingCreate(response))


# --------------------------------------------------------------------------- #
# OpenAI
# --------------------------------------------------------------------------- #
def test_openai_complete_defaults_and_mapping() -> None:
    response = _openai_response(
        "Paris.",
        tool_calls=[{"id": "call_1", "name": "get_weather", "arguments": '{"city":"Paris"}'}],
    )
    client = _openai_client(response)
    provider = OpenAIProvider(model="gpt-4o-mini", client=client)

    completion = provider.complete(
        [Message(role="system", content="Be terse."), Message(role="user", content="Capital?")],
        {"top_p": 0.9},
    )

    sent = client.chat.completions.calls[0]
    assert sent["model"] == "gpt-4o-mini"
    assert sent["messages"] == [
        {"role": "system", "content": "Be terse."},
        {"role": "user", "content": "Capital?"},
    ]
    # temperature defaults to 0 (widely supported); seed is NOT sent by default
    # (OpenAI-compatible endpoints like Gemini reject an unknown "seed" field).
    assert sent["temperature"] == 0
    assert "seed" not in sent
    assert sent["top_p"] == 0.9

    assert isinstance(completion, Completion)
    assert completion.text == "Paris."
    assert completion.tool_calls[0]["name"] == "get_weather"
    assert completion.tool_calls[0]["arguments"] == '{"city":"Paris"}'
    assert completion.usage == {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15}
    assert completion.raw is response


def test_openai_seed_sent_when_explicitly_set_in_params() -> None:
    client = _openai_client(_openai_response("ok"))
    provider = OpenAIProvider(model="gpt-4o-mini", client=client)

    provider.complete([Message(role="user", content="hi")], {"temperature": 0.7, "seed": 42})

    sent = client.chat.completions.calls[0]
    assert sent["temperature"] == 0.7
    assert sent["seed"] == 42


def test_openai_seed_sent_when_configured_on_provider() -> None:
    client = _openai_client(_openai_response("ok"))
    provider = OpenAIProvider(model="gpt-4o-mini", client=client, seed=7)

    provider.complete([Message(role="user", content="hi")], {})

    assert client.chat.completions.calls[0]["seed"] == 7


def test_openai_none_valued_params_are_omitted() -> None:
    client = _openai_client(_openai_response("ok"))
    provider = OpenAIProvider(model="gpt-4o-mini", client=client)

    # Explicit None values must be dropped, not forwarded as null.
    provider.complete(
        [Message(role="user", content="hi")],
        {"top_p": None, "max_tokens": None, "seed": None},
    )

    sent = client.chat.completions.calls[0]
    assert "seed" not in sent
    assert "top_p" not in sent
    assert "max_tokens" not in sent
    # temperature still defaults to 0.
    assert sent["temperature"] == 0


def test_openai_embed() -> None:
    client = _openai_client(vectors=[[0.1, 0.2], [0.3, 0.4]])
    provider = OpenAIProvider(model="text-embedding-3-small", client=client)

    vectors = provider.embed(["a", "b"])

    assert vectors == [[0.1, 0.2], [0.3, 0.4]]
    sent = client.embeddings.calls[0]
    assert sent["model"] == "text-embedding-3-small"
    assert sent["input"] == ["a", "b"]


# --------------------------------------------------------------------------- #
# Anthropic
# --------------------------------------------------------------------------- #
def test_anthropic_complete_defaults_and_mapping() -> None:
    response = _anthropic_response(
        "The weather is sunny.",
        tool_uses=[{"id": "tu_1", "name": "get_weather", "input": {"city": "Paris"}}],
    )
    client = _anthropic_client(response)
    provider = AnthropicProvider(model="claude-sonnet-5", client=client)

    completion = provider.complete(
        [
            Message(role="system", content="Be helpful."),
            Message(role="user", content="Weather in Paris?"),
        ],
        {"max_tokens": 512},
    )

    sent = client.messages.calls[0]
    assert sent["model"] == "claude-sonnet-5"
    # System prompt is lifted out; only the user turn remains in messages.
    assert sent["messages"] == [{"role": "user", "content": "Weather in Paris?"}]
    assert sent["system"] == "Be helpful."
    assert sent["temperature"] == 0
    assert sent["max_tokens"] == 512
    assert "seed" not in sent  # Anthropic has no seed param.

    assert completion.text == "The weather is sunny."
    assert completion.tool_calls[0]["name"] == "get_weather"
    assert completion.tool_calls[0]["arguments"] == {"city": "Paris"}
    assert completion.usage == {"input_tokens": 12, "output_tokens": 7}


def test_anthropic_complete_defaults_max_tokens() -> None:
    client = _anthropic_client(_anthropic_response("hi"))
    provider = AnthropicProvider(model="claude-sonnet-5", client=client)

    provider.complete([Message(role="user", content="hi")], {})

    assert client.messages.calls[0]["max_tokens"] == 1024


def test_anthropic_embed_raises() -> None:
    provider = AnthropicProvider(model="claude-sonnet-5", client=object())
    with pytest.raises(NotImplementedError, match="embeddings"):
        provider.embed(["x"])


# --------------------------------------------------------------------------- #
# Registry
# --------------------------------------------------------------------------- #
def _config() -> Config:
    return Config(
        target=TargetConfig(provider="openai", model="gpt-4o-mini"),
        providers={
            "openai": ProviderConfig(api_key_env="OPENAI_API_KEY"),
            "anthropic": ProviderConfig(api_key_env="ANTHROPIC_API_KEY"),
        },
    )


def test_registry_returns_correct_provider_with_injected_client() -> None:
    config = _config()

    openai_provider = get_provider("openai", config, client=_openai_client())
    assert isinstance(openai_provider, OpenAIProvider)
    assert openai_provider.model == "gpt-4o-mini"  # falls back to target model

    anthropic_provider = get_provider("anthropic", config, client=object(), model="claude-opus-4-8")
    assert isinstance(anthropic_provider, AnthropicProvider)
    assert anthropic_provider.model == "claude-opus-4-8"


def test_registry_unknown_provider_raises() -> None:
    from ankora.config import ConfigError

    with pytest.raises(ConfigError, match="Unknown provider"):
        get_provider("cohere", _config(), client=object())


def test_registry_resolves_key_and_builds_client_when_none_injected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _config()
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-xyz")

    built: dict[str, Any] = {}

    def fake_default_client(api_key: str, base_url: str | None = None) -> Any:
        built["api_key"] = api_key
        built["base_url"] = base_url
        return _openai_client()

    monkeypatch.setattr(OpenAIProvider, "default_client", staticmethod(fake_default_client))

    provider = get_provider("openai", config)  # no client injected

    assert isinstance(provider, OpenAIProvider)
    # Key was resolved from the env var and handed to the SDK client, not stored.
    assert built["api_key"] == "sk-test-xyz"
    assert built["base_url"] is None  # no base_url configured -> default endpoint
    assert not hasattr(provider, "api_key")


def _base_url_config(base_url: str | None) -> Config:
    return Config(
        target=TargetConfig(provider="openai", model="gpt-4o-mini"),
        providers={"openai": ProviderConfig(api_key_env="OPENAI_API_KEY", base_url=base_url)},
    )


def test_registry_threads_base_url_from_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-xyz")
    seen: dict[str, Any] = {}

    def fake_default_client(api_key: str, base_url: str | None = None) -> Any:
        seen["base_url"] = base_url
        return _openai_client()

    monkeypatch.setattr(OpenAIProvider, "default_client", staticmethod(fake_default_client))
    get_provider(
        "openai", _base_url_config("https://generativelanguage.googleapis.com/v1beta/openai/")
    )

    assert seen["base_url"] == "https://generativelanguage.googleapis.com/v1beta/openai/"


def test_registry_base_url_is_none_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-xyz")
    seen: dict[str, Any] = {}

    def fake_default_client(api_key: str, base_url: str | None = None) -> Any:
        seen["base_url"] = base_url
        return _openai_client()

    monkeypatch.setattr(OpenAIProvider, "default_client", staticmethod(fake_default_client))
    get_provider("openai", _base_url_config(None))

    assert seen["base_url"] is None


def test_openai_default_client_forwards_base_url_to_real_client() -> None:
    # Constructs a real openai.OpenAI (no network call) and checks the endpoint.
    client = OpenAIProvider.default_client("sk-x", base_url="https://openrouter.ai/api/v1")
    assert "openrouter.ai/api/v1" in str(client.base_url)


def test_openai_default_client_defaults_to_openai_when_base_url_none() -> None:
    client = OpenAIProvider.default_client("sk-x")
    assert "api.openai.com" in str(client.base_url)


def test_registry_threads_seed_from_config() -> None:
    config = Config(
        target=TargetConfig(provider="openai", model="gpt-4o-mini"),
        providers={"openai": ProviderConfig(api_key_env="OPENAI_API_KEY", seed=123)},
    )
    provider = get_provider("openai", config, client=_openai_client())
    assert isinstance(provider, OpenAIProvider)
    assert provider.seed == 123


def test_registry_seed_defaults_to_none() -> None:
    provider = get_provider("openai", _config(), client=_openai_client())
    assert isinstance(provider, OpenAIProvider)
    assert provider.seed is None


# --------------------------------------------------------------------------- #
# Error handling & retries (mocked; no live calls)
# --------------------------------------------------------------------------- #
def test_rate_limit_retries_then_raises_clean_error(monkeypatch: pytest.MonkeyPatch) -> None:
    slept: list[float] = []
    monkeypatch.setattr("time.sleep", lambda s: slept.append(s))
    client = _raising_openai_client(lambda: _FakeAPIError(429, retry_after=0.5))
    provider = OpenAIProvider(model="gpt-4o", client=client)

    with pytest.raises(ProviderRateLimitError) as excinfo:
        provider.complete([Message(role="user", content="hi")], {})

    assert isinstance(excinfo.value, ProviderError)  # clean type, not a raw SDK error
    assert "Rate limited" in str(excinfo.value)
    assert client._state["calls"] == 3  # bounded: max_attempts
    assert slept == [0.5, 0.5]  # Retry-After respected, 2 sleeps before giving up


def test_rate_limit_recovers_after_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("time.sleep", lambda s: None)
    client = _raising_openai_client(lambda: _FakeAPIError(429), succeed_after=2)
    provider = OpenAIProvider(model="gpt-4o", client=client)

    completion = provider.complete([Message(role="user", content="hi")], {})

    assert completion.text == "ok"
    assert client._state["calls"] == 2  # failed once, succeeded on retry


def test_auth_error_is_clean_and_not_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("time.sleep", lambda s: None)
    client = _raising_openai_client(lambda: _FakeAPIError(401))
    provider = OpenAIProvider(model="gpt-4o", client=client)

    with pytest.raises(ProviderError, match="auth failed"):
        provider.complete([Message(role="user", content="hi")], {})
    assert client._state["calls"] == 1  # no retry for auth failures


def test_bad_request_is_clean(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("time.sleep", lambda s: None)
    client = _raising_openai_client(lambda: _FakeAPIError(400))
    provider = OpenAIProvider(model="gemini-2.0-flash", client=client)

    with pytest.raises(ProviderError, match="bad request"):
        provider.complete([Message(role="user", content="hi")], {})


def test_anthropic_rate_limit_raises_clean_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("time.sleep", lambda s: None)

    def create(**kwargs: Any) -> Any:
        raise _FakeAPIError(429)

    client = SimpleNamespace(messages=SimpleNamespace(create=create))
    provider = AnthropicProvider(model="claude-sonnet-5", client=client)

    with pytest.raises(ProviderRateLimitError, match="Rate limited"):
        provider.complete([Message(role="user", content="hi")], {})


def test_unknown_exception_is_not_masked(monkeypatch: pytest.MonkeyPatch) -> None:
    # A non-API error (real bug) must propagate unchanged, not become ProviderError.
    monkeypatch.setattr("time.sleep", lambda s: None)
    client = _raising_openai_client(lambda: ValueError("boom"))
    provider = OpenAIProvider(model="gpt-4o", client=client)

    with pytest.raises(ValueError, match="boom"):
        provider.complete([Message(role="user", content="hi")], {})


def test_server_error_is_retried_then_raises_clean_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    slept: list[float] = []
    monkeypatch.setattr("time.sleep", lambda s: slept.append(s))
    client = _raising_openai_client(lambda: _FakeAPIError(503))
    provider = OpenAIProvider(model="gpt-4o", client=client)

    with pytest.raises(ProviderServerError, match="server error"):
        provider.complete([Message(role="user", content="hi")], {})

    assert client._state["calls"] == 3  # bounded retries, like 429
    assert slept == [1.0, 2.0]  # exponential backoff


def test_server_error_recovers_after_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("time.sleep", lambda s: None)
    client = _raising_openai_client(lambda: _FakeAPIError(500), succeed_after=2)
    provider = OpenAIProvider(model="gpt-4o", client=client)

    completion = provider.complete([Message(role="user", content="hi")], {})

    assert completion.text == "ok"
    assert client._state["calls"] == 2


def test_retry_after_sleep_is_capped(monkeypatch: pytest.MonkeyPatch) -> None:
    slept: list[float] = []
    monkeypatch.setattr("time.sleep", lambda s: slept.append(s))
    client = _raising_openai_client(lambda: _FakeAPIError(429, retry_after=9999.0))
    provider = OpenAIProvider(model="gpt-4o", client=client)

    with pytest.raises(ProviderRateLimitError):
        provider.complete([Message(role="user", content="hi")], {})

    # A hostile/buggy Retry-After must not hang a CI worker.
    assert slept == [MAX_RETRY_DELAY, MAX_RETRY_DELAY]
