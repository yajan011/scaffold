"""Tests for the Langfuse ingester and ingest format auto-detection.

No live provider calls — pure JSON parsing and mapping.
"""

from __future__ import annotations

import json
from pathlib import Path

from ankora.ingest import detect_format, ingest_traces
from ankora.ingest.langfuse import ingest_langfuse, is_langfuse_shape
from ankora.ingest.otel import ingest_otel, is_otel_shape
from ankora.models import Case

ROOT = Path(__file__).resolve().parents[1]
LANGFUSE_SAMPLE = ROOT / "examples" / "sample_langfuse.json"
OTEL_SAMPLE = ROOT / "examples" / "sample_otel.json"


def test_langfuse_sample_ingests_two_cases_and_skips_non_generation() -> None:
    result = ingest_langfuse(LANGFUSE_SAMPLE)
    assert result.total == 3
    assert result.skipped == 1  # the SPAN observation
    assert len(result.cases) == 2


def test_langfuse_field_mapping() -> None:
    first = ingest_langfuse(LANGFUSE_SAMPLE).cases[0]

    assert [m.role for m in first.input.messages] == ["system", "user"]
    assert first.input.messages[1].content == "What is the capital of France?"
    assert first.input.params == {"temperature": 0.0, "top_p": 1.0, "max_tokens": 256}
    assert first.reference.output == "The capital of France is Paris."
    assert first.reference.tool_calls == []
    assert first.metadata.original_model == "gpt-4o-mini"
    assert first.metadata.source_trace_id == "b7ad6b7169203331"
    assert first.id == Case.make_id("b7ad6b7169203331")
    assert first.metadata.created_at is not None


def test_langfuse_tool_call_case() -> None:
    second = ingest_langfuse(LANGFUSE_SAMPLE).cases[1]

    assert [m.role for m in second.input.messages] == ["user"]
    assert second.input.params == {"temperature": 0.2}
    assert second.reference.output == ""  # tool-call turn had no text
    assert len(second.reference.tool_calls) == 1
    call = second.reference.tool_calls[0]
    assert call["id"] == "call_abc123"
    assert call["name"] == "get_weather"
    assert call["arguments"] == {"city": "Paris", "unit": "celsius"}
    assert second.metadata.original_model == "gpt-4o"


def test_langfuse_cases_equivalent_to_otel_path() -> None:
    # The two sample files describe the same interactions; ingesting either
    # yields the same Cases (same ids, messages, params, output, tool calls).
    otel_cases = ingest_otel(OTEL_SAMPLE).cases
    langfuse_cases = ingest_langfuse(LANGFUSE_SAMPLE).cases
    assert langfuse_cases == otel_cases


def test_langfuse_accepts_flat_list_of_observations(tmp_path: Path) -> None:
    observations = [
        {
            "id": "obs-1",
            "type": "GENERATION",
            "model": "gpt-4o-mini",
            "modelParameters": {"temperature": 0},
            "input": [{"role": "user", "content": "Ping?"}],
            "output": "Pong.",
        }
    ]
    path = tmp_path / "obs.json"
    path.write_text(json.dumps(observations), encoding="utf-8")

    result = ingest_langfuse(path)
    assert len(result.cases) == 1
    case = result.cases[0]
    assert case.input.messages[0].content == "Ping?"
    assert case.reference.output == "Pong."
    assert case.metadata.source_trace_id == "obs-1"


def test_langfuse_string_output_and_input(tmp_path: Path) -> None:
    obs = {
        "id": "obs-2",
        "type": "GENERATION",
        "model": "gpt-4o-mini",
        "input": "just a string prompt",
        "output": "just a string answer",
    }
    path = tmp_path / "single.json"
    path.write_text(json.dumps(obs), encoding="utf-8")

    case = ingest_langfuse(path).cases[0]
    assert case.input.messages[0].content == "just a string prompt"
    assert case.reference.output == "just a string answer"


# --------------------------------------------------------------------------- #
# Auto-detection
# --------------------------------------------------------------------------- #
def test_shape_predicates_distinguish_formats() -> None:
    otel_data = json.loads(OTEL_SAMPLE.read_text())
    langfuse_data = json.loads(LANGFUSE_SAMPLE.read_text())

    assert is_otel_shape(otel_data) is True
    assert is_otel_shape(langfuse_data) is False
    assert is_langfuse_shape(langfuse_data) is True
    assert is_langfuse_shape(otel_data) is False


def test_detect_format_on_both_samples() -> None:
    assert detect_format(json.loads(OTEL_SAMPLE.read_text())) == "otel"
    assert detect_format(json.loads(LANGFUSE_SAMPLE.read_text())) == "langfuse"


def test_auto_routes_otel_file() -> None:
    result, fmt = ingest_traces(OTEL_SAMPLE, "auto")
    assert fmt == "otel"
    assert len(result.cases) == 2


def test_auto_routes_langfuse_file() -> None:
    result, fmt = ingest_traces(LANGFUSE_SAMPLE, "auto")
    assert fmt == "langfuse"
    assert len(result.cases) == 2


def test_explicit_format_override() -> None:
    _, fmt = ingest_traces(LANGFUSE_SAMPLE, "langfuse")
    assert fmt == "langfuse"
    _, fmt = ingest_traces(OTEL_SAMPLE, "otel")
    assert fmt == "otel"


def test_flat_langfuse_list_is_not_misdetected_as_otel(tmp_path: Path) -> None:
    # Langfuse observations carry traceId but never attributes/spanId.
    observations = [
        {
            "id": "obs-9",
            "traceId": "t-9",
            "type": "GENERATION",
            "model": "gpt-4o",
            "input": [{"role": "user", "content": "hi"}],
            "output": "hello",
        }
    ]
    path = tmp_path / "flat_lf.json"
    path.write_text(json.dumps(observations), encoding="utf-8")

    _, fmt = ingest_traces(path, "auto")
    assert fmt == "langfuse"
