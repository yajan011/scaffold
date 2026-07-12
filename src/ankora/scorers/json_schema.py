"""JSON-schema scorer: output must parse as JSON and validate against a schema.

Validation is delegated to the ``jsonschema`` library so every spec keyword
(anyOf/oneOf/allOf, const, exclusiveMinimum/Maximum, multipleOf, pattern, ...)
is honored rather than silently ignored, and ``2.0`` validates as an
``integer`` per the JSON Schema spec.
"""

from __future__ import annotations

import json
from typing import Any

import jsonschema

from ankora.models import Case, ScorerResult


class JSONSchemaScorer:
    """Score 1.0 when ``output`` is JSON valid against ``schema``, else 0.0.

    Raises ``jsonschema.exceptions.SchemaError`` at construction time if the
    schema itself is invalid (the scorer registry maps that to a ConfigError).
    """

    name = "json_schema"

    def __init__(self, schema: dict[str, Any], threshold: float = 1.0) -> None:
        self.schema = schema
        self.threshold = threshold
        validator_cls = jsonschema.validators.validator_for(schema)
        validator_cls.check_schema(schema)
        self._validator = validator_cls(schema)

    def score(self, case: Case, output: str) -> ScorerResult:
        try:
            instance = json.loads(output)
        except (json.JSONDecodeError, ValueError) as exc:
            return self._result(0.0, f"output is not valid JSON: {exc}")

        error = jsonschema.exceptions.best_match(self._validator.iter_errors(instance))
        if error is None:
            return self._result(1.0, "valid against schema")
        return self._result(0.0, f"{error.json_path}: {error.message}")

    def _result(self, value: float, detail: str) -> ScorerResult:
        return ScorerResult(
            scorer=self.name,
            score=value,
            passed=value >= self.threshold,
            threshold=self.threshold,
            detail=detail,
        )
