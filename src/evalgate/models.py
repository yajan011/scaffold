"""Canonical pydantic data models for evalgate.

These mirror the "Core data model" section of CLAUDE.md. They intentionally
carry no behavior beyond validation; logic lives in the modules that consume
them (ingest, replay, scorers, diff).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class Message(BaseModel):
    """An OpenAI-style chat message."""

    role: str
    content: str


class CaseInput(BaseModel):
    """The replayable input of a Case."""

    messages: list[Message] = Field(default_factory=list)
    params: dict[str, Any] = Field(default_factory=dict)


class CaseReference(BaseModel):
    """The golden output recorded from the original trace."""

    output: str = ""
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)


class CaseMetadata(BaseModel):
    """Provenance for a Case."""

    source_trace_id: str | None = None
    original_model: str | None = None
    created_at: datetime | None = None
    tags: list[str] = Field(default_factory=list)


class Case(BaseModel):
    """One recorded interaction turned into a regression test."""

    id: str
    input: CaseInput = Field(default_factory=CaseInput)
    tools: list[dict[str, Any]] = Field(default_factory=list)
    reference: CaseReference = Field(default_factory=CaseReference)
    metadata: CaseMetadata = Field(default_factory=CaseMetadata)


class Suite(BaseModel):
    """A collection of Cases loaded from files in the user's repo."""

    cases: list[Case] = Field(default_factory=list)


class ScorerResult(BaseModel):
    """The outcome of a single scorer against a single output."""

    scorer: str
    score: float = Field(ge=0.0, le=1.0)
    passed: bool
    threshold: float
    detail: str = ""


class CaseResult(BaseModel):
    """The aggregated result of replaying and scoring one Case."""

    case_id: str
    output: str
    scorer_results: list[ScorerResult] = Field(default_factory=list)
    passed: bool


class RunTarget(BaseModel):
    """The provider/model a run was executed against."""

    provider: str
    model: str


class RunSummary(BaseModel):
    """Roll-up counts for a run."""

    total: int = 0
    passed: int = 0
    failed: int = 0


class RunResult(BaseModel):
    """The full result of a run, persisted under .evalgate/runs/."""

    run_id: str
    target: RunTarget
    created_at: datetime
    case_results: list[CaseResult] = Field(default_factory=list)
    summary: RunSummary = Field(default_factory=RunSummary)
