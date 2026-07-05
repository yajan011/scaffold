"""Compare a current RunResult against a baseline to classify per-case changes.

The gate uses this to decide whether quality regressed. Interpretation of what
counts as a *regression* depends on ``config.gate.fail_on``:

* ``"regression"`` — a case regresses only if it passed in the baseline and now
  fails (crossing pass -> fail, i.e. its aggregate score dropped past the pass
  threshold). Cases absent from the baseline are reported as new, never as
  regressions.
* ``"absolute"`` — any case failing its scorer thresholds in the current run is
  a regression, regardless of the baseline.
"""

from __future__ import annotations

from collections import Counter
from enum import StrEnum

from pydantic import BaseModel, Field

from ankora.config import Config
from ankora.models import CaseResult, RunResult


class CaseStatus(StrEnum):
    """How a single case changed between baseline and current."""

    NEW_FAILURE = "new_failure"  # only in current, failing
    NEW_PASS = "new_pass"  # only in current, passing
    FIXED = "fixed"  # failed baseline, passes now
    REGRESSED = "regressed"  # passed baseline, fails now
    UNCHANGED = "unchanged"  # same pass/fail state in both
    REMOVED = "removed"  # only in baseline, missing from current


class CaseDiff(BaseModel):
    """The per-case comparison result."""

    case_id: str
    status: CaseStatus
    baseline_passed: bool | None = None
    current_passed: bool | None = None
    baseline_score: float | None = None
    current_score: float | None = None
    delta: float | None = None
    is_regression: bool = False
    detail: str = ""


class DiffReport(BaseModel):
    """The full comparison plus roll-up counts and the gate signal."""

    fail_on: str
    cases: list[CaseDiff] = Field(default_factory=list)
    has_regressions: bool = False
    regressions: int = 0
    regressed: int = 0
    new_failures: int = 0
    new_passes: int = 0
    fixed: int = 0
    unchanged: int = 0
    removed: int = 0


def diff_runs(baseline: RunResult, current: RunResult, config: Config) -> DiffReport:
    """Compare ``current`` to ``baseline`` under ``config.gate.fail_on``."""
    mode = config.gate.fail_on
    baseline_by_id = {cr.case_id: cr for cr in baseline.case_results}
    current_by_id = {cr.case_id: cr for cr in current.case_results}

    cases: list[CaseDiff] = []
    # Current run order first, so the report reads in suite order.
    for current_case in current.case_results:
        cases.append(_diff_case(baseline_by_id.get(current_case.case_id), current_case, mode))
    # Then any baseline cases that vanished from the current run.
    for baseline_case in baseline.case_results:
        if baseline_case.case_id not in current_by_id:
            cases.append(_removed_case(baseline_case))

    counts = Counter(case.status for case in cases)
    return DiffReport(
        fail_on=mode,
        cases=cases,
        has_regressions=any(case.is_regression for case in cases),
        regressions=sum(1 for case in cases if case.is_regression),
        regressed=counts[CaseStatus.REGRESSED],
        new_failures=counts[CaseStatus.NEW_FAILURE],
        new_passes=counts[CaseStatus.NEW_PASS],
        fixed=counts[CaseStatus.FIXED],
        unchanged=counts[CaseStatus.UNCHANGED],
        removed=counts[CaseStatus.REMOVED],
    )


def _diff_case(baseline: CaseResult | None, current: CaseResult, mode: str) -> CaseDiff:
    current_passed = current.passed
    current_score = _aggregate_score(current)

    if baseline is None:
        status = CaseStatus.NEW_FAILURE if not current_passed else CaseStatus.NEW_PASS
        # A brand-new case is never a regression under "regression"; under
        # "absolute" it regresses if it fails.
        is_regression = mode == "absolute" and not current_passed
        detail = "new case, failing" if not current_passed else "new case, passing"
        return CaseDiff(
            case_id=current.case_id,
            status=status,
            current_passed=current_passed,
            current_score=current_score,
            is_regression=is_regression,
            detail=detail,
        )

    baseline_passed = baseline.passed
    baseline_score = _aggregate_score(baseline)
    delta = current_score - baseline_score

    if baseline_passed and not current_passed:
        status = CaseStatus.REGRESSED
    elif not baseline_passed and current_passed:
        status = CaseStatus.FIXED
    else:
        status = CaseStatus.UNCHANGED

    if mode == "absolute":
        is_regression = not current_passed
    else:  # "regression": only a genuine pass -> fail crossing counts
        is_regression = status == CaseStatus.REGRESSED

    return CaseDiff(
        case_id=current.case_id,
        status=status,
        baseline_passed=baseline_passed,
        current_passed=current_passed,
        baseline_score=baseline_score,
        current_score=current_score,
        delta=delta,
        is_regression=is_regression,
        detail=f"score {baseline_score:.3f} -> {current_score:.3f} (Δ{delta:+.3f})",
    )


def _removed_case(baseline: CaseResult) -> CaseDiff:
    return CaseDiff(
        case_id=baseline.case_id,
        status=CaseStatus.REMOVED,
        baseline_passed=baseline.passed,
        baseline_score=_aggregate_score(baseline),
        is_regression=False,
        detail="case missing from current run",
    )


def _aggregate_score(case: CaseResult) -> float:
    """Mean of the case's scorer scores; falls back to pass/fail as 1.0/0.0."""
    if not case.scorer_results:
        return 1.0 if case.passed else 0.0
    return sum(result.score for result in case.scorer_results) / len(case.scorer_results)
