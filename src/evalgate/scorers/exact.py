"""Exact-match scorer: output must equal the reference output.

Logic is stubbed for v1 scaffolding.
"""

from __future__ import annotations

from evalgate.models import Case, ScorerResult


class ExactScorer:
    """Score 1.0 when output equals the reference exactly, else 0.0."""

    name = "exact"

    def __init__(self, threshold: float = 1.0) -> None:
        self.threshold = threshold

    def score(self, case: Case, output: str) -> ScorerResult:
        """Not yet implemented — placeholder for v1 scaffolding."""
        raise NotImplementedError("ExactScorer.score is not implemented yet")
