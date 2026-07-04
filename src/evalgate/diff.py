"""Compare a current RunResult against a baseline to detect regressions.

Logic is stubbed for v1 scaffolding.
"""

from __future__ import annotations

from pydantic import BaseModel

from evalgate.models import RunResult


class Regression(BaseModel):
    """A single case that got worse relative to the baseline."""

    case_id: str
    scorer: str
    baseline_score: float
    current_score: float
    detail: str = ""


def diff_runs(baseline: RunResult, current: RunResult) -> list[Regression]:
    """Return the per-case regressions of ``current`` vs ``baseline``.

    Not yet implemented — placeholder for v1 scaffolding.
    """
    raise NotImplementedError("diff.diff_runs is not implemented yet")
