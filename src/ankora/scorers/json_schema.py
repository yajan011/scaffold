"""JSON-schema scorer: output must parse as JSON and validate against a schema.

Uses a small self-contained validator covering the common JSON Schema keywords
(type, required, properties, items, enum, additionalProperties, numeric/string
bounds, pattern) rather than pulling in a validation dependency — the OSS core
is kept dependency-light per CLAUDE.md.
"""

from __future__ import annotations

import json
import re
from typing import Any

from ankora.models import Case, ScorerResult


class JSONSchemaScorer:
    """Score 1.0 when ``output`` is JSON valid against ``schema``, else 0.0."""

    name = "json_schema"

    def __init__(self, schema: dict[str, Any], threshold: float = 1.0) -> None:
        self.schema = schema
        self.threshold = threshold

    def score(self, case: Case, output: str) -> ScorerResult:
        try:
            instance = json.loads(output)
        except (json.JSONDecodeError, ValueError) as exc:
            return self._result(0.0, f"output is not valid JSON: {exc}")

        error = _validate(instance, self.schema, "$")
        if error is None:
            return self._result(1.0, "valid against schema")
        return self._result(0.0, error)

    def _result(self, value: float, detail: str) -> ScorerResult:
        return ScorerResult(
            scorer=self.name,
            score=value,
            passed=value >= self.threshold,
            threshold=self.threshold,
            detail=detail,
        )


def _validate(instance: Any, schema: Any, path: str) -> str | None:
    """Return the first validation error message, or None if valid."""
    if not isinstance(schema, dict):
        return None

    expected_type = schema.get("type")
    if expected_type is not None and not _check_type(instance, expected_type):
        return f"{path}: expected type {expected_type}, got {_json_type(instance)}"

    if "enum" in schema and instance not in schema["enum"]:
        return f"{path}: {instance!r} not in enum {schema['enum']}"

    if isinstance(instance, dict):
        error = _validate_object(instance, schema, path)
        if error:
            return error

    if isinstance(instance, list):
        error = _validate_array(instance, schema, path)
        if error:
            return error

    if isinstance(instance, str):
        error = _validate_string(instance, schema, path)
        if error:
            return error

    if isinstance(instance, (int, float)) and not isinstance(instance, bool):
        error = _validate_number(instance, schema, path)
        if error:
            return error

    return None


def _validate_object(instance: dict[str, Any], schema: dict[str, Any], path: str) -> str | None:
    for required in schema.get("required", []):
        if required not in instance:
            return f"{path}: missing required property '{required}'"

    properties = schema.get("properties", {})
    for key, subschema in properties.items():
        if key in instance:
            error = _validate(instance[key], subschema, f"{path}.{key}")
            if error:
                return error

    additional = schema.get("additionalProperties", True)
    extras = set(instance) - set(properties)
    if additional is False and extras:
        return f"{path}: additional properties not allowed: {sorted(extras)}"
    if isinstance(additional, dict):
        for key in sorted(extras):
            error = _validate(instance[key], additional, f"{path}.{key}")
            if error:
                return error
    return None


def _validate_array(instance: list[Any], schema: dict[str, Any], path: str) -> str | None:
    items = schema.get("items")
    if isinstance(items, dict):
        for index, item in enumerate(instance):
            error = _validate(item, items, f"{path}[{index}]")
            if error:
                return error
    minimum = schema.get("minItems")
    if minimum is not None and len(instance) < minimum:
        return f"{path}: expected at least {minimum} items, got {len(instance)}"
    maximum = schema.get("maxItems")
    if maximum is not None and len(instance) > maximum:
        return f"{path}: expected at most {maximum} items, got {len(instance)}"
    return None


def _validate_string(instance: str, schema: dict[str, Any], path: str) -> str | None:
    if "minLength" in schema and len(instance) < schema["minLength"]:
        return f"{path}: string shorter than minLength {schema['minLength']}"
    if "maxLength" in schema and len(instance) > schema["maxLength"]:
        return f"{path}: string longer than maxLength {schema['maxLength']}"
    pattern = schema.get("pattern")
    if pattern is not None and re.search(pattern, instance) is None:
        return f"{path}: string does not match pattern {pattern!r}"
    return None


def _validate_number(instance: float, schema: dict[str, Any], path: str) -> str | None:
    minimum = schema.get("minimum")
    if minimum is not None and instance < minimum:
        return f"{path}: {instance} < minimum {minimum}"
    maximum = schema.get("maximum")
    if maximum is not None and instance > maximum:
        return f"{path}: {instance} > maximum {maximum}"
    return None


def _check_type(instance: Any, expected: Any) -> bool:
    if isinstance(expected, list):
        return any(_check_type(instance, option) for option in expected)
    checks = {
        "object": lambda v: isinstance(v, dict),
        "array": lambda v: isinstance(v, list),
        "string": lambda v: isinstance(v, str),
        "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
        "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
        "boolean": lambda v: isinstance(v, bool),
        "null": lambda v: v is None,
    }
    check = checks.get(expected)
    return check(instance) if check else True


def _json_type(value: Any) -> str:
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, dict):
        return "object"
    if isinstance(value, list):
        return "array"
    if isinstance(value, str):
        return "string"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if value is None:
        return "null"
    return type(value).__name__
