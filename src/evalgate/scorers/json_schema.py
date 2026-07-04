"""JSON-schema scorer: output must parse and validate against a schema.

Logic is stubbed for v1 scaffolding.
"""

from __future__ import annotations

from typing import Any

from evalgate.models import Case, ScorerResult


class JSONSchemaScorer:
    """Score 1.0 when output is JSON valid against ``schema``, else 0.0."""

    name = "json_schema"

    def __init__(self, schema: dict[str, Any], threshold: float = 1.0) -> None:
        self.schema = schema
        self.threshold = threshold

    def score(self, case: Case, output: str) -> ScorerResult:
        """Not yet implemented — placeholder for v1 scaffolding."""
        raise NotImplementedError("JSONSchemaScorer.score is not implemented yet")
