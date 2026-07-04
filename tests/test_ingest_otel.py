"""Tests for the OTel GenAI trace ingester.

Exercises both the modern (input/output.messages) and older (indexed
prompt/completion) conventions, tool-call capture, skipping of non-gen_ai
spans, and id stability. No provider calls.
"""

from __future__ import annotations

import json
from pathlib import Path

from evalgate.ingest.otel import IngestResult, ingest_otel
from evalgate.models import Case

SAMPLE = Path(__file__).resolve().parents[1] / "examples" / "sample_otel.json"


def _ingest() -> IngestResult:
    return ingest_otel(SAMPLE)


def test_sample_ingests_two_cases_and_skips_non_gen_ai() -> None:
    result = _ingest()
    assert result.total_spans == 3
    assert result.skipped == 1  # the plain HTTP span
    assert len(result.cases) == 2


def test_modern_convention_field_mapping() -> None:
    modern = _ingest().cases[0]

    roles = [m.role for m in modern.input.messages]
    contents = [m.content for m in modern.input.messages]
    assert roles == ["system", "user"]
    assert contents == ["You are a helpful assistant.", "What is the capital of France?"]

    assert modern.input.params["temperature"] == 0.0
    assert modern.input.params["top_p"] == 1.0
    assert modern.input.params["max_tokens"] == 256

    assert modern.reference.output == "The capital of France is Paris."
    assert modern.reference.tool_calls == []

    assert modern.metadata.original_model == "gpt-4o-mini"
    assert modern.metadata.source_trace_id == "b7ad6b7169203331"
    assert modern.metadata.created_at is not None


def test_older_convention_with_tool_call() -> None:
    older = _ingest().cases[1]

    assert [m.role for m in older.input.messages] == ["user"]
    assert older.input.messages[0].content == "What's the weather in Paris today?"
    assert older.input.params["temperature"] == 0.2

    # Completion carried no text, only a tool call.
    assert older.reference.output == ""
    assert len(older.reference.tool_calls) == 1
    call = older.reference.tool_calls[0]
    assert call["name"] == "get_weather"
    assert call["id"] == "call_abc123"
    assert call["arguments"] == {"city": "Paris", "unit": "celsius"}

    assert older.metadata.original_model == "gpt-4o"
    assert older.metadata.source_trace_id == "00f067aa0ba902b7"


def test_case_ids_derived_from_source_and_stable() -> None:
    cases = _ingest().cases
    assert cases[0].id == Case.make_id("b7ad6b7169203331")
    assert cases[1].id == Case.make_id("00f067aa0ba902b7")
    assert cases[0].id != cases[1].id

    # Re-ingesting the same trace yields identical ids (deterministic).
    again = _ingest().cases
    assert [c.id for c in again] == [c.id for c in cases]


def test_flat_list_of_spans_is_accepted(tmp_path: Path) -> None:
    span = {
        "spanId": "deadbeefcafef00d",
        "attributes": [
            {"key": "gen_ai.system", "value": {"stringValue": "anthropic"}},
            {"key": "gen_ai.request.model", "value": {"stringValue": "claude-sonnet-5"}},
            {"key": "gen_ai.prompt", "value": {"stringValue": "Hello there"}},
            {"key": "gen_ai.completion", "value": {"stringValue": "Hi! How can I help?"}},
        ],
    }
    path = tmp_path / "flat.json"
    path.write_text(json.dumps([span]), encoding="utf-8")

    result = ingest_otel(path)
    assert len(result.cases) == 1
    case = result.cases[0]
    assert case.input.messages[0].content == "Hello there"
    assert case.reference.output == "Hi! How can I help?"
    assert case.metadata.original_model == "claude-sonnet-5"


def test_gen_ai_span_without_io_is_skipped(tmp_path: Path) -> None:
    # Has gen_ai.* attributes but no prompt/completion at all -> skipped.
    span = {
        "spanId": "aaaa1111bbbb2222",
        "attributes": [
            {"key": "gen_ai.system", "value": {"stringValue": "openai"}},
            {"key": "gen_ai.request.model", "value": {"stringValue": "gpt-4o"}},
        ],
    }
    path = tmp_path / "empty.json"
    path.write_text(json.dumps([span]), encoding="utf-8")

    result = ingest_otel(path)
    assert result.total_spans == 1
    assert result.skipped == 1
    assert result.cases == []


def test_plain_dict_attribute_form_is_supported(tmp_path: Path) -> None:
    # Some exporters emit attributes as a plain {key: value} mapping.
    span = {
        "span_id": "0011223344556677",
        "attributes": {
            "gen_ai.system": "openai",
            "gen_ai.request.model": "gpt-4o-mini",
            "gen_ai.request.temperature": 0.5,
            "gen_ai.prompt.0.role": "user",
            "gen_ai.prompt.0.content": "ping",
            "gen_ai.completion.0.content": "pong",
        },
    }
    path = tmp_path / "dictattrs.json"
    path.write_text(json.dumps({"spans": [span]}), encoding="utf-8")

    result = ingest_otel(path)
    assert len(result.cases) == 1
    case = result.cases[0]
    assert case.input.messages[0].content == "ping"
    assert case.input.params["temperature"] == 0.5
    assert case.reference.output == "pong"


def test_written_case_yaml_round_trips(tmp_path: Path) -> None:
    case = _ingest().cases[0]
    path = tmp_path / f"{case.id}.yaml"
    path.write_text(case.to_yaml(), encoding="utf-8")
    assert Case.from_yaml(path.read_text(encoding="utf-8")) == case
