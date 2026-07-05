"""Read a Langfuse trace/observation JSON export into Cases.

Supported shapes:

* a single **trace** object with an ``observations`` list,
* a bare **observation** object (``type: GENERATION`` etc.),
* a **list** of observations, and
* a ``{"data": [...]}`` list (Langfuse public-API list responses).

Each generation-like observation maps to a :class:`~ankora.models.Case`:
``input`` -> ``input.messages``, ``modelParameters`` -> ``input.params``,
``output`` -> ``reference.output`` (+ ``reference.tool_calls``), ``model`` ->
``metadata.original_model``, and the observation ``id`` (else ``traceId``) ->
``metadata.source_trace_id`` via :meth:`Case.make_id`. Observations with neither
input nor output (e.g. plain SPAN/EVENT rows) are skipped.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ankora.ingest import IngestResult
from ankora.models import Case, CaseInput, CaseMetadata, CaseReference, Message

__all__ = ["ingest_langfuse", "is_langfuse_shape"]

# Langfuse observation `type` values (a generous superset).
_LANGFUSE_TYPES = {
    "GENERATION",
    "SPAN",
    "EVENT",
    "TRACE",
    "AGENT",
    "TOOL",
    "CHAIN",
    "RETRIEVER",
    "EMBEDDING",
    "GUARDRAIL",
}


def is_langfuse_shape(data: Any) -> bool:
    """True if parsed JSON looks like a Langfuse export."""
    if isinstance(data, dict):
        if isinstance(data.get("observations"), list):
            return True
        if isinstance(data.get("data"), list) and any(_obs_like(x) for x in data["data"]):
            return True
        return _obs_like(data) or ("input" in data and "output" in data)
    if isinstance(data, list):
        return any(_obs_like(x) for x in data)
    return False


def _obs_like(obj: Any) -> bool:
    if not isinstance(obj, dict):
        return False
    if any(k in obj for k in ("attributes", "spanId", "span_id")):
        return False  # that's an OTel span
    if "modelParameters" in obj:
        return True
    if obj.get("type") in _LANGFUSE_TYPES:
        return True
    if isinstance(obj.get("observations"), list):
        return True
    return "model" in obj and ("input" in obj or "output" in obj)


def ingest_langfuse(export_file: str | Path) -> IngestResult:
    """Parse a Langfuse export into Cases (as an :class:`IngestResult`)."""
    data = json.loads(Path(export_file).read_text(encoding="utf-8"))

    records = _iter_records(data)
    cases: list[Case] = []
    skipped = 0
    for record in records:
        case = _observation_to_case(record)
        if case is None:
            skipped += 1
        else:
            cases.append(case)

    return IngestResult(cases=cases, total=len(records), skipped=skipped)


def _iter_records(data: Any) -> list[dict[str, Any]]:
    """Flatten the supported export shapes into a list of observation dicts."""
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    if not isinstance(data, dict):
        return []
    if isinstance(data.get("observations"), list):
        return [x for x in data["observations"] if isinstance(x, dict)]
    if isinstance(data.get("data"), list):
        return [x for x in data["data"] if isinstance(x, dict)]
    # A single observation, or a trace that itself carries input/output.
    return [data]


def _observation_to_case(record: dict[str, Any]) -> Case | None:
    messages = _messages_from_input(record.get("input"))
    output_text, tool_calls = _output_to_reference(record.get("output"))

    # Nothing to replay or score against -> not a usable Case.
    if not messages and not output_text and not tool_calls:
        return None

    source_id = _source_id(record)
    params = record.get("modelParameters")
    return Case(
        id=Case.make_id(source_id),
        input=CaseInput(
            messages=messages,
            params=dict(params) if isinstance(params, dict) else {},
        ),
        reference=CaseReference(output=output_text, tool_calls=tool_calls),
        metadata=CaseMetadata(
            source_trace_id=source_id,
            original_model=record.get("model"),
            created_at=_parse_time(record.get("startTime") or record.get("timestamp")),
        ),
    )


def _source_id(record: dict[str, Any]) -> str:
    for key in ("id", "traceId", "trace_id"):
        value = record.get(key)
        if value:
            return str(value)
    digest = hashlib.sha256(json.dumps(record, sort_keys=True, default=str).encode()).hexdigest()
    return digest[:32]


# --------------------------------------------------------------------------- #
# Input -> messages
# --------------------------------------------------------------------------- #
def _messages_from_input(value: Any) -> list[Message]:
    if value is None:
        return []
    if isinstance(value, str):
        return [Message(role="user", content=value)] if value else []
    if isinstance(value, dict):
        if isinstance(value.get("messages"), list):
            return _messages_from_list(value["messages"])
        if "role" in value or "content" in value:
            return _messages_from_list([value])
        return []
    if isinstance(value, list):
        return _messages_from_list(value)
    return []


def _messages_from_list(items: list[Any]) -> list[Message]:
    messages: list[Message] = []
    for item in items:
        if isinstance(item, dict):
            role = str(item.get("role", "user"))
            messages.append(Message(role=role, content=_content_text(item.get("content"))))
        elif isinstance(item, str):
            messages.append(Message(role="user", content=item))
    return messages


# --------------------------------------------------------------------------- #
# Output -> reference.output + tool_calls
# --------------------------------------------------------------------------- #
def _output_to_reference(value: Any) -> tuple[str, list[dict[str, Any]]]:
    if value is None:
        return "", []
    if isinstance(value, str):
        return value, []
    if isinstance(value, dict):
        text = _content_text(value.get("content"))
        if not text:
            for key in ("text", "completion", "response"):
                candidate = value.get(key)
                if isinstance(candidate, str) and candidate:
                    text = candidate
                    break
        return text, _tool_calls(value.get("tool_calls"))
    if isinstance(value, list):
        texts: list[str] = []
        tool_calls: list[dict[str, Any]] = []
        for item in value:
            if isinstance(item, dict):
                text = _content_text(item.get("content"))
                if text:
                    texts.append(text)
                tool_calls.extend(_tool_calls(item.get("tool_calls")))
            elif isinstance(item, str):
                texts.append(item)
        return "\n".join(texts), tool_calls
    return "", []


def _tool_calls(value: Any) -> list[dict[str, Any]]:
    """Normalize Langfuse/OpenAI tool calls to {id, name, arguments} (parsed)."""
    if not isinstance(value, list):
        return []
    calls: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        function = item.get("function")
        if isinstance(function, dict):
            name = function.get("name")
            arguments = function.get("arguments")
        else:
            name = item.get("name")
            arguments = item.get("arguments")
        calls.append(
            {
                "id": item.get("id"),
                "name": name,
                "arguments": _coerce_json(arguments) if arguments is not None else {},
            }
        )
    return calls


# --------------------------------------------------------------------------- #
# Shared helpers
# --------------------------------------------------------------------------- #
def _content_text(content: Any) -> str:
    """Extract text from a message content field (string, parts list, or dict)."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(_part_text(part) for part in content)
    if isinstance(content, dict):
        return _part_text(content)
    return ""


def _part_text(part: Any) -> str:
    if isinstance(part, str):
        return part
    if not isinstance(part, dict):
        return ""
    if part.get("type") in (None, "text", "input_text", "output_text"):
        value = part.get("text")
        if value is None:
            value = part.get("content")
        return value if isinstance(value, str) else ""
    return ""


def _parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    text = value.strip()
    for candidate in (text, text.replace("Z", "+00:00")):
        try:
            parsed = datetime.fromisoformat(candidate)
        except ValueError:
            continue
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    return None


def _coerce_json(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (json.JSONDecodeError, ValueError):
            return value
    return value
