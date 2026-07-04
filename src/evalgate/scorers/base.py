"""The Scorer protocol shared by all scorers.

Logic is stubbed for v1 scaffolding.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from evalgate.models import Case, ScorerResult


@runtime_checkable
class Scorer(Protocol):
    """Minimal surface every scorer must implement."""

    name: str
    threshold: float

    def score(self, case: Case, output: str) -> ScorerResult:
        """Grade ``output`` for ``case`` and return a ScorerResult."""
        ...
