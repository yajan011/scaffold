"""Regex scorer: output must match a configured pattern.

Logic is stubbed for v1 scaffolding.
"""

from __future__ import annotations

from evalgate.models import Case, ScorerResult


class RegexScorer:
    """Score 1.0 when output matches ``pattern``, else 0.0."""

    name = "regex"

    def __init__(self, pattern: str, threshold: float = 1.0) -> None:
        self.pattern = pattern
        self.threshold = threshold

    def score(self, case: Case, output: str) -> ScorerResult:
        """Not yet implemented — placeholder for v1 scaffolding."""
        raise NotImplementedError("RegexScorer.score is not implemented yet")
