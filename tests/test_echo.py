"""Tests for the keyless echo provider and its end-to-end replay path."""

from __future__ import annotations

from pathlib import Path

import pytest

from ankora.config import Config, ExactScorerConfig, TargetConfig
from ankora.models import Case, CaseInput, CaseReference, Message, Suite
from ankora.providers.echo import EchoProvider
from ankora.providers.registry import get_provider
from ankora.replay import replay


def _config() -> Config:
    return Config(
        target=TargetConfig(provider="echo", model="echo"),
        providers={},  # no provider credentials at all
        scorers=[ExactScorerConfig(type="exact")],
    )


def test_echo_complete_returns_last_user_message() -> None:
    provider = EchoProvider()
    completion = provider.complete(
        [
            Message(role="system", content="ignore me"),
            Message(role="user", content="hello world"),
        ],
        {},
    )
    assert completion.text == "hello world"
    assert completion.tool_calls == []


def test_echo_embed_raises() -> None:
    with pytest.raises(NotImplementedError):
        EchoProvider().embed(["x"])


def test_registry_returns_echo_without_key_or_client() -> None:
    # No providers configured, no client injected, no env var — must still work.
    provider = get_provider("echo", _config())
    assert isinstance(provider, EchoProvider)
    assert provider.model == "echo"


def test_replay_with_echo_is_fully_offline(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    suite = Suite(
        cases=[
            Case(
                id="match",
                input=CaseInput(messages=[Message(role="user", content="Paris")]),
                reference=CaseReference(output="Paris"),
            ),
            Case(
                id="mismatch",
                input=CaseInput(messages=[Message(role="user", content="London")]),
                reference=CaseReference(output="Paris"),
            ),
        ]
    )

    # No client injected: replay drives the real echo provider (no network).
    run = replay(_config(), suite=suite)

    assert [cr.case_id for cr in run.case_results] == ["match", "mismatch"]
    assert run.case_results[0].output == "Paris"
    assert run.case_results[0].passed is True
    assert run.case_results[1].passed is False
    assert run.summary.passed == 1
    assert run.summary.failed == 1
