"""Exact-match scorer: output must equal the reference output."""

from __future__ import annotations

from ankora.models import Case, ScorerResult


class ExactScorer:
    """Score 1.0 when output equals ``reference.output``, else 0.0.

    When ``normalize`` is set, both sides are stripped and lowercased first.
    """

    name = "exact"

    def __init__(self, threshold: float = 1.0, normalize: bool = True) -> None:
        self.threshold = threshold
        self.normalize = normalize

    def _prepare(self, text: str) -> str:
        return text.strip().lower() if self.normalize else text

    def score(self, case: Case, output: str) -> ScorerResult:
        reference = case.reference.output
        matched = self._prepare(output) == self._prepare(reference)
        value = 1.0 if matched else 0.0
        detail = "exact match" if matched else "output does not match reference"
        return ScorerResult(
            scorer=self.name,
            score=value,
            passed=value >= self.threshold,
            threshold=self.threshold,
            detail=detail,
        )
