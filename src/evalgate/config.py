"""Load and validate evalgate.yaml into a pydantic Config.

Logic is stubbed for v1 scaffolding; see CLAUDE.md "Config file" section for
the target schema.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class ProviderConfig(BaseModel):
    """How to reach a provider (keys read from env, never inlined)."""

    api_key_env: str


class TargetConfig(BaseModel):
    """The provider/model replays run against by default."""

    provider: str
    model: str


class ScorerConfig(BaseModel):
    """A single scorer entry; shape varies by ``type``."""

    type: str
    threshold: float = 0.5
    # Remaining keys (rubric, judge, model, ...) are scorer-specific.
    options: dict[str, Any] = Field(default_factory=dict)


class GateConfig(BaseModel):
    """How the gate decides pass/fail."""

    fail_on: str = "regression"  # "regression" | "absolute"
    baseline: str = ".evalgate/baseline.json"


class Config(BaseModel):
    """The fully-parsed evalgate.yaml."""

    version: int = 1
    suites: list[str] = Field(default_factory=lambda: ["evals/**/*.yaml"])
    target: TargetConfig
    providers: dict[str, ProviderConfig] = Field(default_factory=dict)
    scorers: list[ScorerConfig] = Field(default_factory=list)
    gate: GateConfig = Field(default_factory=GateConfig)


def load_config(path: str | Path = "evalgate.yaml") -> Config:
    """Read and validate an evalgate.yaml file into a Config.

    Not yet implemented — placeholder for v1 scaffolding.
    """
    raise NotImplementedError("config.load_config is not implemented yet")
