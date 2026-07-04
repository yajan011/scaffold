"""Tests for the canonical data models: round-trips and id stability.

No provider calls — these exercise pure serialization and hashing only.
"""

from __future__ import annotations

from datetime import UTC, datetime

from evalgate.models import (
    Case,
    CaseInput,
    CaseMetadata,
    CaseReference,
    CaseResult,
    Message,
    RunResult,
    RunSummary,
    RunTarget,
    ScorerResult,
)


def _sample_case() -> Case:
    return Case(
        id="case-0123456789abcdef",
        input=CaseInput(
            messages=[
                Message(role="system", content="You are helpful."),
                Message(role="user", content="Say hi in français 🙂"),
            ],
            params={"temperature": 0, "max_tokens": 128},
        ),
        tools=[{"type": "function", "function": {"name": "get_weather"}}],
        reference=CaseReference(
            output="Bonjour !",
            tool_calls=[{"name": "get_weather", "arguments": {"city": "Paris"}}],
        ),
        metadata=CaseMetadata(
            source_trace_id="trace-abc-123",
            original_model="gpt-4o-mini",
            created_at=datetime(2026, 7, 4, 12, 30, 0, tzinfo=UTC),
            tags=["smoke", "fr"],
        ),
    )


def _sample_run() -> RunResult:
    return RunResult(
        run_id="run-2026-07-04",
        target=RunTarget(provider="openai", model="gpt-4o-mini"),
        created_at=datetime(2026, 7, 4, 12, 30, 0, tzinfo=UTC),
        case_results=[
            CaseResult(
                case_id="case-0123456789abcdef",
                output="Bonjour !",
                scorer_results=[
                    ScorerResult(
                        scorer="exact",
                        score=1.0,
                        passed=True,
                        threshold=1.0,
                        detail="exact match",
                    ),
                ],
                passed=True,
            ),
        ],
        summary=RunSummary(total=1, passed=1, failed=0),
    )


def test_case_yaml_round_trip() -> None:
    case = _sample_case()
    restored = Case.from_yaml(case.to_yaml())
    assert restored == case


def test_run_result_json_round_trip() -> None:
    run = _sample_run()
    restored = RunResult.from_json(run.to_json())
    assert restored == run


def test_case_id_is_stable_for_same_input() -> None:
    assert Case.make_id("trace-abc-123") == Case.make_id("trace-abc-123")


def test_case_id_differs_for_different_input() -> None:
    assert Case.make_id("trace-abc-123") != Case.make_id("trace-xyz-999")


def test_case_id_has_expected_shape() -> None:
    case_id = Case.make_id("trace-abc-123")
    assert case_id.startswith("case-")
    assert len(case_id) == len("case-") + 16
