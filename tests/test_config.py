"""Tests for config loading, validation errors, and `ankora init`.

No provider calls — API-key resolution is exercised via monkeypatched env only.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from ankora.cli import app
from ankora.config import (
    Config,
    ConfigError,
    EmbeddingSimilarityScorerConfig,
    LLMJudgeScorerConfig,
    load_config,
)

runner = CliRunner()

VALID_CONFIG = """\
version: 1
suites: ["evals/**/*.yaml"]
target:
  provider: openai
  model: gpt-4o-mini
providers:
  openai: {api_key_env: OPENAI_API_KEY}
  anthropic: {api_key_env: ANTHROPIC_API_KEY}
scorers:
  - type: llm_judge
    judge: {provider: openai, model: gpt-4o}
    rubric: "Score 1 if consistent with the reference, else 0."
    threshold: 0.7
  - type: embedding_similarity
    model: {provider: openai, model: text-embedding-3-small}
    threshold: 0.85
gate:
  fail_on: regression
  baseline: .ankora/baseline.json
"""


def _write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "ankora.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def test_valid_config_parses(tmp_path: Path) -> None:
    config = load_config(_write(tmp_path, VALID_CONFIG))
    assert isinstance(config, Config)
    assert config.target.provider == "openai"
    assert config.target.model == "gpt-4o-mini"
    assert config.gate.fail_on == "regression"
    assert config.providers["openai"].api_key_env == "OPENAI_API_KEY"

    judge, embedding = config.scorers
    assert isinstance(judge, LLMJudgeScorerConfig)
    assert judge.judge.model == "gpt-4o"
    assert judge.threshold == 0.7
    assert isinstance(embedding, EmbeddingSimilarityScorerConfig)
    assert embedding.model.model == "text-embedding-3-small"


def test_missing_file_raises_config_error(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="not found"):
        load_config(tmp_path / "nope.yaml")


def test_unknown_scorer_type_raises_clear_error(tmp_path: Path) -> None:
    bad = VALID_CONFIG.replace("type: llm_judge", "type: bogus_scorer")
    with pytest.raises(ConfigError) as excinfo:
        load_config(_write(tmp_path, bad))
    message = str(excinfo.value)
    assert "scorers[0]" in message
    # The error should name the offending value, not dump raw pydantic internals.
    assert "bogus_scorer" in message


def test_missing_api_key_env_raises_clear_error(tmp_path: Path) -> None:
    bad = VALID_CONFIG.replace("openai: {api_key_env: OPENAI_API_KEY}", "openai: {}")
    with pytest.raises(ConfigError) as excinfo:
        load_config(_write(tmp_path, bad))
    message = str(excinfo.value)
    assert "providers.openai.api_key_env" in message


def test_malformed_gate_fail_on_raises_clear_error(tmp_path: Path) -> None:
    bad = VALID_CONFIG.replace("fail_on: regression", "fail_on: explode")
    with pytest.raises(ConfigError) as excinfo:
        load_config(_write(tmp_path, bad))
    message = str(excinfo.value)
    assert "gate.fail_on" in message


def test_resolve_api_key_reads_env_at_call_time(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = load_config(_write(tmp_path, VALID_CONFIG))
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-123")
    assert config.resolve_api_key("openai") == "sk-test-123"

    # Key is never stored on the model.
    assert "sk-test-123" not in config.model_dump_json()


def test_resolve_api_key_missing_env_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = load_config(_write(tmp_path, VALID_CONFIG))
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(ConfigError, match="OPENAI_API_KEY"):
        config.resolve_api_key("openai")


def test_resolve_api_key_unknown_provider_raises(tmp_path: Path) -> None:
    config = load_config(_write(tmp_path, VALID_CONFIG))
    with pytest.raises(ConfigError, match="not configured"):
        config.resolve_api_key("cohere")


def test_init_writes_parseable_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["init"])
    assert result.exit_code == 0

    config_path = tmp_path / "ankora.yaml"
    assert config_path.exists()
    assert (tmp_path / "evals").is_dir()

    # The generated file round-trips through the real loader.
    config = load_config(config_path)
    assert config.target.provider == "openai"
    assert len(config.scorers) == 2


def test_init_refuses_to_overwrite_without_force(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "ankora.yaml").write_text("version: 1\n", encoding="utf-8")

    result = runner.invoke(app, ["init"])
    assert result.exit_code == 1
    assert "already exists" in result.output
    # Original content preserved.
    assert (tmp_path / "ankora.yaml").read_text(encoding="utf-8") == "version: 1\n"


def test_init_force_overwrites(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "ankora.yaml").write_text("version: 1\n", encoding="utf-8")

    result = runner.invoke(app, ["init", "--force"])
    assert result.exit_code == 0
    config = load_config(tmp_path / "ankora.yaml")
    assert len(config.scorers) == 2
