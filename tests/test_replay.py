"""Tests for the replay engine and suite loading, using an injected fake client.

No live API calls: the target provider is driven by a fake OpenAI-shaped client
that echoes the last user message as the completion.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from typer.testing import CliRunner

from ankora import storage
from ankora.cli import app
from ankora.config import (
    Config,
    ConfigError,
    ExactScorerConfig,
    ProviderConfig,
    TargetConfig,
)
from ankora.models import Case, CaseInput, CaseReference, Message, RunResult, Suite
from ankora.providers.errors import ProviderRateLimitError
from ankora.replay import replay
from ankora.suites import SuiteError, load_suites

runner = CliRunner()


def _echo_client() -> Any:
    """A fake OpenAI client whose completion echoes the final user message."""

    def chat_create(**kwargs: Any) -> Any:
        last = kwargs["messages"][-1]["content"]
        message = SimpleNamespace(content=last, tool_calls=None)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)], usage=None)

    return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=chat_create)))


def _config() -> Config:
    return Config(
        target=TargetConfig(provider="openai", model="gpt-4o-mini"),
        providers={"openai": ProviderConfig(api_key_env="OPENAI_API_KEY")},
        scorers=[ExactScorerConfig(type="exact")],
    )


def _case(case_id: str, prompt: str, reference: str) -> Case:
    return Case(
        id=case_id,
        input=CaseInput(messages=[Message(role="user", content=prompt)]),
        reference=CaseReference(output=reference),
    )


# --------------------------------------------------------------------------- #
# replay
# --------------------------------------------------------------------------- #
def test_replay_rejects_config_without_scorers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    config = _config().model_copy(update={"scorers": []})
    suite = Suite(cases=[_case("a", "prompt", "ref")])

    with pytest.raises(ConfigError, match="[Nn]o scorers"):
        replay(config, suite=suite, client=_echo_client())


def test_replay_scores_orders_and_persists(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    suite = Suite(
        cases=[
            _case("a", "Paris", "Paris"),
            _case("b", "London", "Paris"),
            _case("c", "Berlin", "Berlin"),
        ]
    )

    run = replay(_config(), suite=suite, client=_echo_client(), concurrency=4)

    # Case order preserved despite concurrency.
    assert [cr.case_id for cr in run.case_results] == ["a", "b", "c"]
    assert [cr.output for cr in run.case_results] == ["Paris", "London", "Berlin"]
    assert [cr.passed for cr in run.case_results] == [True, False, True]

    assert run.summary.total == 3
    assert run.summary.passed == 2
    assert run.summary.failed == 1
    assert run.target.provider == "openai"
    assert run.target.model == "gpt-4o-mini"

    # Persisted and reloads equal.
    assert storage.run_path(run.run_id).exists()
    assert storage.load_run(run.run_id) == run


def test_replay_target_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    run = replay(
        _config(),
        suite=Suite(cases=[_case("a", "hi", "hi")]),
        target="openai:gpt-4o",
        client=_echo_client(),
    )
    assert run.target.provider == "openai"
    assert run.target.model == "gpt-4o"


def test_replay_loads_suite_when_not_passed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    evals = tmp_path / "evals"
    evals.mkdir()
    (evals / "x.yaml").write_text(_case("x", "hi", "hi").to_yaml(), encoding="utf-8")

    run = replay(_config(), client=_echo_client())

    assert run.summary.total == 1
    assert run.case_results[0].case_id == "x"
    assert run.case_results[0].passed is True


# --------------------------------------------------------------------------- #
# suite loading
# --------------------------------------------------------------------------- #
def test_load_suites_reads_cases_and_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    evals = tmp_path / "evals"
    evals.mkdir()
    (evals / "a.yaml").write_text(_case("a", "p", "p").to_yaml(), encoding="utf-8")
    (evals / "b.yaml").write_text(_case("b", "q", "q").to_yaml(), encoding="utf-8")

    suite = load_suites(_config())

    assert sorted(c.id for c in suite.cases) == ["a", "b"]
    assert len(suite.source_paths) == 2


def test_load_suites_no_match_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SuiteError, match="matched no files"):
        load_suites(_config())


# --------------------------------------------------------------------------- #
# CLI wiring (replay monkeypatched to avoid any provider call)
# --------------------------------------------------------------------------- #
def test_cli_run_prints_table_and_saved_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["init"])  # writes a valid ankora.yaml

    canned = replay(
        _config(),
        suite=Suite(cases=[_case("a", "Paris", "Paris")]),
        client=_echo_client(),
    )

    def fake_replay(config: Config, **kwargs: Any) -> RunResult:
        return canned

    monkeypatch.setattr("ankora.cli.replay", fake_replay)

    result = runner.invoke(app, ["run"])
    assert result.exit_code == 0
    assert "1/1 passed" in result.output
    assert canned.run_id in result.output


def test_load_suites_reports_malformed_yaml(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    evals = tmp_path / "evals"
    evals.mkdir()
    # Unbalanced brackets -> a YAML parse error, not a stack trace.
    (evals / "broken.yaml").write_text("id: x\ninput: {messages: [", encoding="utf-8")

    with pytest.raises(SuiteError, match="invalid YAML in"):
        load_suites(_config())


def test_cli_run_reports_provider_error_cleanly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["init"])  # valid ankora.yaml

    def boom(config: Config, **kwargs: Any) -> RunResult:
        raise ProviderRateLimitError("Rate limited by openai (429). Retry in 2s.")

    monkeypatch.setattr("ankora.cli.replay", boom)

    result = runner.invoke(app, ["run"])
    assert result.exit_code == 1
    assert "Rate limited by openai (429)" in result.output
    # Clean exit: only a typer Exit, no leaked provider traceback.
    assert not isinstance(result.exception, ProviderRateLimitError)
