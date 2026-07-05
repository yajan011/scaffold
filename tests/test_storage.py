"""Tests for run/baseline storage round-trips."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from ankora import storage
from ankora.config import Config, GateConfig, TargetConfig
from ankora.models import CaseResult, RunResult, RunSummary, RunTarget, ScorerResult


def _run(run_id: str, passed: int = 1) -> RunResult:
    return RunResult(
        run_id=run_id,
        target=RunTarget(provider="openai", model="gpt-4o-mini"),
        created_at=datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC),
        case_results=[
            CaseResult(
                case_id="c1",
                output="Paris",
                scorer_results=[
                    ScorerResult(
                        scorer="exact", score=1.0, passed=True, threshold=1.0, detail="match"
                    )
                ],
                passed=True,
            )
        ],
        summary=RunSummary(total=1, passed=passed, failed=1 - passed),
    )


def _config_with_baseline(path: Path) -> Config:
    return Config(
        target=TargetConfig(provider="openai", model="gpt-4o-mini"),
        gate=GateConfig(baseline=str(path)),
    )


def test_save_and_load_round_trip(tmp_path: Path) -> None:
    run = _run("run-1")
    path = storage.save_run(run, base_dir=tmp_path)
    assert path.exists()
    assert storage.load_run("run-1", base_dir=tmp_path) == run


def test_load_missing_run_raises(tmp_path: Path) -> None:
    with pytest.raises(storage.StorageError, match="No run found"):
        storage.load_run("nope", base_dir=tmp_path)


def test_list_runs_empty(tmp_path: Path) -> None:
    assert storage.list_runs(base_dir=tmp_path) == []


def test_list_runs_newest_first(tmp_path: Path) -> None:
    storage.save_run(_run("run-2024-01-01"), base_dir=tmp_path)
    storage.save_run(_run("run-2024-01-02"), base_dir=tmp_path)
    ids = storage.list_runs(base_dir=tmp_path)
    assert ids[0] == "run-2024-01-02"
    assert set(ids) == {"run-2024-01-01", "run-2024-01-02"}


def test_baseline_round_trip(tmp_path: Path) -> None:
    run = _run("run-baseline")
    storage.save_run(run, base_dir=tmp_path)
    config = _config_with_baseline(tmp_path / "baseline.json")

    path = storage.set_baseline(config, "run-baseline", base_dir=tmp_path)
    assert path.exists()
    assert storage.get_baseline(config) == run


def test_get_baseline_missing_raises(tmp_path: Path) -> None:
    config = _config_with_baseline(tmp_path / "none.json")
    with pytest.raises(storage.StorageError, match="No baseline"):
        storage.get_baseline(config)
