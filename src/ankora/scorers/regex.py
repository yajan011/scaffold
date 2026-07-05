"""Regex scorer: output must match a configured pattern."""

from __future__ import annotations

import re

from ankora.models import Case, ScorerResult


class RegexScorer:
    """Score 1.0 when ``output`` matches ``pattern`` (via ``re.search``), else 0.0."""

    name = "regex"

    def __init__(self, pattern: str, threshold: float = 1.0, flags: int = 0) -> None:
        self.pattern = pattern
        self.threshold = threshold
        self._regex = re.compile(pattern, flags)

    def score(self, case: Case, output: str) -> ScorerResult:
        matched = self._regex.search(output) is not None
        value = 1.0 if matched else 0.0
        detail = (
            f"matched pattern {self.pattern!r}"
            if matched
            else f"no match for pattern {self.pattern!r}"
        )
        return ScorerResult(
            scorer=self.name,
            score=value,
            passed=value >= self.threshold,
            threshold=self.threshold,
            detail=detail,
        )
