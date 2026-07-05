"""Tests for diff_runs classification and the gate CLI exit codes.

No live API calls: RunResults are constructed in-memory, and the gate test
monkeypatches replay/get_baseline so nothing touches a provider or the network.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from ankora.cli import app
from ankora.config import Config, GateConfig, TargetConfig
from ankora.diff import CaseStatus, diff_runs
from ankora.models import CaseResult, RunResult, RunSummary, RunTarget, ScorerResult

runner = CliRunner()


def _case(case_id: str, passed: bool, score: float) -> CaseResult:
    return CaseResult(
        case_id=case_id,
        output="",
        scorer_results=[
            ScorerResult(scorer="s", score=score, passed=passed, threshold=0.7, detail="")
        ],
        passed=passed,
    )


def _run(run_id: str, cases: list[CaseResult]) -> RunResult:
    passed = sum(1 for c in cases if c.passed)
    return RunResult(
        run_id=run_id,
        target=RunTarget(provider="openai", model="m"),
        created_at=datetime(2024, 1, 1, tzinfo=UTC),
        case_results=cases,
        summary=RunSummary(total=len(cases), passed=passed, failed=len(cases) - passed),
    )


def _config(mode: str) -> Config:
    return Config(target=TargetConfig(provider="openai", model="m"), gate=GateConfig(fail_on=mode))


def _by_id(report: Any) -> dict[str, Any]:
    return {c.case_id: c for c in report.cases}


# --------------------------------------------------------------------------- #
# diff_runs classification
# --------------------------------------------------------------------------- #
def _baseline() -> RunResult:
    return _run("base", [_case("A", True, 0.9), _case("B", True, 0.8), _case("C", False, 0.2)])


def _current() -> RunResult:
    # A regressed, B unchanged (still passing), C fixed, D new failure.
    return _run(
        "curr",
        [
            _case("A", False, 0.3),
            _case("B", True, 0.85),
            _case("C", True, 0.9),
            _case("D", False, 0.1),
        ],
    )


def test_regression_mode_classification() -> None:
    report = diff_runs(_baseline(), _current(), _config("regression"))
    cases = _by_id(report)

    assert cases["A"].status == CaseStatus.REGRESSED
    assert cases["A"].is_regression is True
    assert cases["B"].status == CaseStatus.UNCHANGED
    assert cases["B"].is_regression is False
    assert cases["C"].status == CaseStatus.FIXED
    assert cases["C"].is_regression is False
    # New failing case is reported as new, not a regression, in regression mode.
    assert cases["D"].status == CaseStatus.NEW_FAILURE
    assert cases["D"].is_regression is False

    assert report.has_regressions is True
    assert report.regressions == 1
    assert cases["A"].delta == pytest.approx(0.3 - 0.9)


def test_absolute_mode_classification() -> None:
    report = diff_runs(_baseline(), _current(), _config("absolute"))
    cases = _by_id(report)

    # Status labels are baseline-relative and unchanged across modes...
    assert cases["A"].status == CaseStatus.REGRESSED
    assert cases["D"].status == CaseStatus.NEW_FAILURE
    # ...but any currently-failing case counts as a regression in absolute mode.
    assert cases["A"].is_regression is True
    assert cases["D"].is_regression is True
    assert cases["B"].is_regression is False
    assert cases["C"].is_regression is False

    assert report.has_regressions is True
    assert report.regressions == 2


def test_case_missing_from_current_is_removed_not_regression() -> None:
    baseline = _run("base", [_case("A", True, 0.9), _case("E", True, 0.95)])
    current = _run("curr", [_case("A", True, 0.9)])

    report = diff_runs(baseline, current, _config("regression"))
    cases = _by_id(report)

    assert cases["E"].status == CaseStatus.REMOVED
    assert cases["E"].is_regression is False
    assert cases["E"].current_score is None
    assert report.has_regressions is False


def test_new_passing_case_is_not_a_regression_in_either_mode() -> None:
    baseline = _run("base", [_case("A", True, 0.9)])
    current = _run("curr", [_case("A", True, 0.9), _case("N", True, 0.95)])

    for mode in ("regression", "absolute"):
        report = diff_runs(baseline, current, _config(mode))
        cases = _by_id(report)
        assert cases["N"].status == CaseStatus.NEW_PASS
        assert cases["N"].is_regression is False
        assert report.has_regressions is False


def test_stable_runs_have_no_regressions() -> None:
    baseline = _run("base", [_case("A", True, 0.9), _case("B", True, 0.8)])
    current = _run("curr", [_case("A", True, 0.91), _case("B", True, 0.82)])
    report = diff_runs(baseline, current, _config("regression"))
    assert report.has_regressions is False
    assert report.regressed == 0


# --------------------------------------------------------------------------- #
# gate CLI (replay + baseline monkeypatched — no network)
# --------------------------------------------------------------------------- #
def _init_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["init"])  # writes a valid ankora.yaml (fail_on: regression)


def test_gate_exits_nonzero_on_regression(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _init_config(tmp_path, monkeypatch)
    baseline = _run("base", [_case("A", True, 0.9)])
    current = _run("curr", [_case("A", False, 0.3)])  # A regressed

    monkeypatch.setattr("ankora.cli.replay", lambda config, **kw: current)
    monkeypatch.setattr("ankora.cli.get_baseline", lambda config: baseline)

    result = runner.invoke(app, ["gate"])
    assert result.exit_code == 1
    assert "regression" in result.output.lower()


def test_gate_exits_zero_when_clean(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _init_config(tmp_path, monkeypatch)
    baseline = _run("base", [_case("A", True, 0.9)])
    current = _run("curr", [_case("A", True, 0.92)])

    monkeypatch.setattr("ankora.cli.replay", lambda config, **kw: current)
    monkeypatch.setattr("ankora.cli.get_baseline", lambda config: baseline)

    result = runner.invoke(app, ["gate"])
    assert result.exit_code == 0
    assert "gate passed" in result.output.lower()


def test_gate_exits_zero_when_no_baseline(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _init_config(tmp_path, monkeypatch)
    current = _run("curr", [_case("A", True, 0.9)])

    def _no_baseline(config: Config) -> RunResult:
        from ankora.storage import StorageError

        raise StorageError("no baseline")

    monkeypatch.setattr("ankora.cli.replay", lambda config, **kw: current)
    monkeypatch.setattr("ankora.cli.get_baseline", _no_baseline)

    result = runner.invoke(app, ["gate"])
    assert result.exit_code == 0
    assert "no baseline" in result.output.lower()
