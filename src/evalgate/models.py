"""Canonical pydantic data models for evalgate.

These mirror the "Core data model" section of CLAUDE.md. They intentionally
carry no behavior beyond validation; logic lives in the modules that consume
them (ingest, replay, scorers, diff).
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml
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

    @staticmethod
    def make_id(source_trace_id: str) -> str:
        """Derive a stable, deterministic Case id from a source trace id.

        The same ``source_trace_id`` always yields the same id, and distinct
        inputs yield distinct ids (collision probability is that of the
        truncated SHA-256 digest). This lets re-ingesting the same trace update
        an existing Case in place rather than creating a duplicate.
        """
        digest = hashlib.sha256(source_trace_id.encode("utf-8")).hexdigest()
        return f"case-{digest[:16]}"

    def to_yaml(self) -> str:
        """Serialize this Case to a YAML string that round-trips via :meth:`from_yaml`."""
        return yaml.safe_dump(
            self.model_dump(mode="json"),
            sort_keys=False,
            allow_unicode=True,
            default_flow_style=False,
        )

    @classmethod
    def from_yaml(cls, text: str) -> Case:
        """Parse a Case from a YAML string produced by :meth:`to_yaml`."""
        data = yaml.safe_load(text) or {}
        return cls.model_validate(data)


class Suite(BaseModel):
    """A collection of Cases loaded from files in the user's repo.

    ``source_paths`` records the files the Cases were loaded from (in load
    order), so tooling can report where a Case came from or rewrite it in place.
    """

    cases: list[Case] = Field(default_factory=list)
    source_paths: list[Path] = Field(default_factory=list)


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

    def to_json(self, *, indent: int | None = 2) -> str:
        """Serialize this RunResult to JSON that round-trips via :meth:`from_json`."""
        return self.model_dump_json(indent=indent)

    @classmethod
    def from_json(cls, text: str | bytes) -> RunResult:
        """Parse a RunResult from a JSON string produced by :meth:`to_json`."""
        return cls.model_validate_json(text)
