"""Read OpenTelemetry GenAI-semantic-convention traces into Cases.

This is the canonical input format. It reads a JSON file of OTel spans and turns
each ``gen_ai.*`` span into a :class:`~evalgate.models.Case`.

Two container shapes are accepted:

* the standard OTLP export — ``resourceSpans`` / ``scopeSpans`` / ``spans``
  (both camelCase and snake_case field names), and
* a flat top-level list of span objects.

Two GenAI conventions are understood per span:

* the modern structured convention — ``gen_ai.input.messages`` /
  ``gen_ai.output.messages`` carrying JSON message arrays, and
* the older attribute convention — ``gen_ai.prompt`` / ``gen_ai.completion``,
  either as indexed attributes (``gen_ai.prompt.0.role`` …) or single strings.

Parsing is deliberately tolerant: non-``gen_ai`` spans are skipped, missing
optional attributes never raise, and a ``gen_ai`` span carrying neither input
nor output is skipped rather than emitted.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from evalgate.models import (
    Case,
    CaseInput,
    CaseMetadata,
    CaseReference,
    Message,
)

GEN_AI_PREFIX = "gen_ai."
_REQUEST_PREFIX = "gen_ai.request."


class IngestResult(BaseModel):
    """Summary of an ingest run: the Cases produced plus skip accounting."""

    cases: list[Case] = Field(default_factory=list)
    total_spans: int = 0
    skipped: int = 0


def ingest_otel(trace_file: str | Path) -> IngestResult:
    """Parse an OTel GenAI trace export into Cases.

    Returns an :class:`IngestResult` with the produced Cases, the number of
    spans seen, and how many were skipped (non-``gen_ai`` or lacking any usable
    input/output). Raises ``FileNotFoundError`` if the file is missing and
    ``json.JSONDecodeError`` if it is not valid JSON — callers (the CLI) render
    those into friendly messages.
    """
    data = json.loads(Path(trace_file).read_text(encoding="utf-8"))

    spans = list(_iter_spans(data))
    cases: list[Case] = []
    skipped = 0
    for span in spans:
        case = _span_to_case(span)
        if case is None:
            skipped += 1
        else:
            cases.append(case)

    return IngestResult(cases=cases, total_spans=len(spans), skipped=skipped)


# --------------------------------------------------------------------------- #
# Span iteration
# --------------------------------------------------------------------------- #
def _iter_spans(data: Any) -> list[dict[str, Any]]:
    """Yield span dicts from either the OTLP container shape or a flat list."""
    if isinstance(data, list):
        return [s for s in data if isinstance(s, dict)]
    if not isinstance(data, dict):
        return []

    resource_spans = data.get("resourceSpans") or data.get("resource_spans")
    if resource_spans is None:
        # Fall back to {"spans": [...]} or a single bare span object.
        if isinstance(data.get("spans"), list):
            return [s for s in data["spans"] if isinstance(s, dict)]
        if _looks_like_span(data):
            return [data]
        return []

    spans: list[dict[str, Any]] = []
    for rs in resource_spans:
        if not isinstance(rs, dict):
            continue
        scope_spans = rs.get("scopeSpans") or rs.get("scope_spans") or []
        for ss in scope_spans:
            if not isinstance(ss, dict):
                continue
            for span in ss.get("spans", []) or []:
                if isinstance(span, dict):
                    spans.append(span)
    return spans


def _looks_like_span(obj: dict[str, Any]) -> bool:
    return any(k in obj for k in ("attributes", "spanId", "span_id", "traceId", "trace_id"))


# --------------------------------------------------------------------------- #
# Attribute normalization (OTLP list form and plain-dict form)
# --------------------------------------------------------------------------- #
def _normalize_attributes(carrier: dict[str, Any]) -> dict[str, Any]:
    """Return a flat {key: python_value} dict for a span's/event's attributes."""
    attrs = carrier.get("attributes")
    result: dict[str, Any] = {}
    if isinstance(attrs, dict):
        result.update(attrs)
    elif isinstance(attrs, list):
        for item in attrs:
            if not isinstance(item, dict):
                continue
            key = item.get("key")
            if key is None:
                continue
            result[key] = _otlp_value(item.get("value"))
    return result


def _otlp_value(value: Any) -> Any:
    """Unwrap an OTLP AnyValue object into a plain Python value."""
    if not isinstance(value, dict):
        return value
    if "stringValue" in value or "string_value" in value:
        return value.get("stringValue", value.get("string_value"))
    if "boolValue" in value or "bool_value" in value:
        return value.get("boolValue", value.get("bool_value"))
    if "intValue" in value or "int_value" in value:
        raw = value.get("intValue", value.get("int_value"))
        try:
            return int(raw)
        except (TypeError, ValueError):
            return raw
    if "doubleValue" in value or "double_value" in value:
        return value.get("doubleValue", value.get("double_value"))
    if "arrayValue" in value or "array_value" in value:
        arr = value.get("arrayValue", value.get("array_value")) or {}
        values = arr.get("values", []) if isinstance(arr, dict) else []
        return [_otlp_value(v) for v in values]
    if "kvlistValue" in value or "kvlist_value" in value:
        kv = value.get("kvlistValue", value.get("kvlist_value")) or {}
        values = kv.get("values", []) if isinstance(kv, dict) else []
        return {
            item.get("key"): _otlp_value(item.get("value"))
            for item in values
            if isinstance(item, dict)
        }
    return value


# --------------------------------------------------------------------------- #
# Span -> Case
# --------------------------------------------------------------------------- #
def _span_to_case(span: dict[str, Any]) -> Case | None:
    attrs = _normalize_attributes(span)
    if not _is_gen_ai_span(attrs):
        return None

    messages = _extract_input_messages(attrs)
    output_text, tool_calls = _extract_output(attrs)

    # A gen_ai span with neither input nor output is not a usable Case.
    if not messages and not output_text and not tool_calls:
        return None

    source_id = _source_id(span, attrs)
    original_model = attrs.get(f"{_REQUEST_PREFIX}model") or attrs.get("gen_ai.response.model")

    return Case(
        id=Case.make_id(source_id),
        input=CaseInput(messages=messages, params=_extract_params(attrs)),
        reference=CaseReference(output=output_text, tool_calls=tool_calls),
        metadata=CaseMetadata(
            source_trace_id=source_id,
            original_model=original_model,
            created_at=_extract_created_at(span),
        ),
    )


def _is_gen_ai_span(attrs: dict[str, Any]) -> bool:
    return any(key.startswith(GEN_AI_PREFIX) for key in attrs)


def _source_id(span: dict[str, Any], attrs: dict[str, Any]) -> str:
    """Stable identity for a span: prefer span id, then trace id, then a hash."""
    span_id = span.get("spanId") or span.get("span_id")
    if span_id:
        return str(span_id)
    trace_id = span.get("traceId") or span.get("trace_id")
    if trace_id:
        return str(trace_id)
    digest = hashlib.sha256(json.dumps(attrs, sort_keys=True, default=str).encode()).hexdigest()
    return digest[:32]


def _extract_params(attrs: dict[str, Any]) -> dict[str, Any]:
    """Collect top-level gen_ai.request.* params (temperature, top_p, ...)."""
    params: dict[str, Any] = {}
    for key, value in attrs.items():
        if not key.startswith(_REQUEST_PREFIX):
            continue
        name = key[len(_REQUEST_PREFIX) :]
        if name == "model" or "." in name:  # model handled separately; skip nested keys
            continue
        params[name] = value
    return params


def _extract_created_at(span: dict[str, Any]) -> datetime | None:
    raw = span.get("startTimeUnixNano") or span.get("start_time_unix_nano")
    if raw is None:
        return None
    try:
        nanos = int(raw)
    except (TypeError, ValueError):
        return None
    return datetime.fromtimestamp(nanos / 1_000_000_000, tz=UTC)


# --------------------------------------------------------------------------- #
# Input messages
# --------------------------------------------------------------------------- #
def _extract_input_messages(attrs: dict[str, Any]) -> list[Message]:
    # Modern: gen_ai.input.messages as a JSON array.
    raw = attrs.get("gen_ai.input.messages")
    if raw is not None:
        parsed = _coerce_json(raw)
        if isinstance(parsed, list):
            messages = [
                Message(role=str(m.get("role", "user")), content=_message_text(m))
                for m in parsed
                if isinstance(m, dict)
            ]
            if messages:
                return messages

    # Older: indexed gen_ai.prompt.<i>.{role,content}.
    indexed = _indexed_messages(attrs, "gen_ai.prompt")
    if indexed:
        return indexed

    # Oldest: a single gen_ai.prompt string.
    single = attrs.get("gen_ai.prompt")
    if isinstance(single, str) and single:
        return [Message(role="user", content=single)]

    return []


def _indexed_messages(attrs: dict[str, Any], base: str) -> list[Message]:
    prefix = f"{base}."
    by_index: dict[int, dict[str, Any]] = {}
    for key, value in attrs.items():
        if not key.startswith(prefix):
            continue
        parts = key[len(prefix) :].split(".")
        if len(parts) < 2 or not parts[0].isdigit():
            continue
        idx, field = int(parts[0]), parts[1]
        if field in ("role", "content"):
            by_index.setdefault(idx, {})[field] = value
    return [
        Message(
            role=str(by_index[i].get("role", "user")),
            content=str(by_index[i].get("content", "")),
        )
        for i in sorted(by_index)
    ]


# --------------------------------------------------------------------------- #
# Output / completion
# --------------------------------------------------------------------------- #
def _extract_output(attrs: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
    # Modern: gen_ai.output.messages as a JSON array.
    raw = attrs.get("gen_ai.output.messages")
    if raw is not None:
        parsed = _coerce_json(raw)
        if isinstance(parsed, list):
            texts: list[str] = []
            tool_calls: list[dict[str, Any]] = []
            for message in parsed:
                if not isinstance(message, dict):
                    continue
                text = _message_text(message)
                if text:
                    texts.append(text)
                tool_calls.extend(_message_tool_calls(message))
            if texts or tool_calls:
                return "\n".join(texts), tool_calls

    # Older: indexed gen_ai.completion.<i>.{content,tool_calls...}.
    text, tool_calls = _indexed_completion(attrs, "gen_ai.completion")
    if text or tool_calls:
        return text, tool_calls

    # Oldest: a single gen_ai.completion string.
    single = attrs.get("gen_ai.completion")
    if isinstance(single, str) and single:
        return single, []

    return "", []


def _indexed_completion(attrs: dict[str, Any], base: str) -> tuple[str, list[dict[str, Any]]]:
    prefix = f"{base}."
    contents: dict[int, str] = {}
    tool_calls: dict[tuple[int, int], dict[str, Any]] = {}
    for key, value in attrs.items():
        if not key.startswith(prefix):
            continue
        parts = key[len(prefix) :].split(".")
        if not parts[0].isdigit():
            continue
        idx = int(parts[0])
        if len(parts) == 2 and parts[1] == "content":
            contents[idx] = str(value)
        elif len(parts) >= 4 and parts[1] == "tool_calls" and parts[2].isdigit():
            call = tool_calls.setdefault((idx, int(parts[2])), {})
            call[parts[3]] = value

    text = "\n".join(contents[i] for i in sorted(contents) if contents[i])
    calls = [_normalize_tool_call(tool_calls[k]) for k in sorted(tool_calls)]
    return text, calls


def _normalize_tool_call(raw: dict[str, Any]) -> dict[str, Any]:
    arguments = raw.get("arguments")
    return {
        "id": raw.get("id"),
        "name": raw.get("name"),
        "arguments": _coerce_json(arguments) if arguments is not None else {},
    }


# --------------------------------------------------------------------------- #
# Message helpers (shared by modern input/output parsing)
# --------------------------------------------------------------------------- #
def _message_text(message: dict[str, Any]) -> str:
    """Concatenate the textual content of a message across content/parts forms."""
    content = message.get("content")
    if isinstance(content, str):
        return content

    texts: list[str] = []
    for source in (content, message.get("parts")):
        if isinstance(source, list):
            texts.extend(t for t in (_part_text(p) for p in source) if t)
    return "".join(texts)


def _part_text(part: Any) -> str:
    if isinstance(part, str):
        return part
    if not isinstance(part, dict):
        return ""
    if part.get("type") in (None, "text", "input_text", "output_text"):
        value = part.get("content")
        if value is None:
            value = part.get("text")
        return value if isinstance(value, str) else ""
    return ""


def _message_tool_calls(message: dict[str, Any]) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []
    existing = message.get("tool_calls")
    if isinstance(existing, list):
        calls.extend(tc for tc in existing if isinstance(tc, dict))
    parts = message.get("parts")
    if isinstance(parts, list):
        for part in parts:
            if isinstance(part, dict) and part.get("type") == "tool_call":
                calls.append(_normalize_tool_call(part))
    return calls


def _coerce_json(value: Any) -> Any:
    """Parse a JSON string to Python; pass dicts/lists through; else return as-is."""
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (json.JSONDecodeError, ValueError):
            return value
    return value
