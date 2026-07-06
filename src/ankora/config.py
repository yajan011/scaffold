"""Load and validate ankora.yaml into a pydantic Config.

See CLAUDE.md "Config file" section for the target schema. Provider API keys are
never stored on the model — they are read from the configured env var at call
time via :meth:`Config.resolve_api_key`.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Annotated, Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError


class ConfigError(Exception):
    """Raised for any human-facing problem loading or validating a config.

    Carries a message intended to be printed straight to a user, rather than a
    raw pydantic error dump.
    """


class ProviderConfig(BaseModel):
    """How to reach a provider (keys read from env, never inlined).

    ``base_url`` optionally points an OpenAI-compatible provider at a custom
    endpoint (Gemini's OpenAI-compat API, OpenRouter, Groq, Together, a local
    Ollama/LM Studio server, ...). When ``None`` the provider's default endpoint
    is used unchanged.
    """

    api_key_env: str
    base_url: str | None = None


class TargetConfig(BaseModel):
    """The provider/model replays run against by default."""

    provider: str
    model: str


class ModelRef(BaseModel):
    """A provider/model reference used by scorers (judge, embedding model)."""

    provider: str
    model: str


class LLMJudgeScorerConfig(BaseModel):
    """Rubric-based judge scorer (``type: llm_judge``)."""

    type: Literal["llm_judge"]
    judge: ModelRef
    rubric: str
    threshold: float = 0.7


class EmbeddingSimilarityScorerConfig(BaseModel):
    """Cosine-similarity scorer over an embedding model (``type: embedding_similarity``)."""

    type: Literal["embedding_similarity"]
    model: ModelRef
    threshold: float = 0.85


class ExactScorerConfig(BaseModel):
    """Exact-match scorer (``type: exact``).

    ``normalize`` strips surrounding whitespace and lowercases both sides before
    comparing.
    """

    type: Literal["exact"]
    threshold: float = 1.0
    normalize: bool = True


class RegexScorerConfig(BaseModel):
    """Regex-match scorer (``type: regex``)."""

    type: Literal["regex"]
    pattern: str
    threshold: float = 1.0


class JSONSchemaScorerConfig(BaseModel):
    """JSON-schema validation scorer (``type: json_schema``).

    The schema is provided under the ``schema`` key in YAML; it is exposed on
    the model as ``json_schema`` to avoid shadowing pydantic internals.
    """

    model_config = ConfigDict(populate_by_name=True)

    type: Literal["json_schema"]
    json_schema: dict[str, Any] = Field(alias="schema")
    threshold: float = 1.0


# Discriminated on ``type`` so an unknown scorer type yields a clear error that
# names the valid tags. Kept under the name ``ScorerConfig`` for callers that
# import it (e.g. scorers.registry.build_scorer).
ScorerConfig = Annotated[
    LLMJudgeScorerConfig
    | EmbeddingSimilarityScorerConfig
    | ExactScorerConfig
    | RegexScorerConfig
    | JSONSchemaScorerConfig,
    Field(discriminator="type"),
]


class GateConfig(BaseModel):
    """How the gate decides pass/fail."""

    fail_on: Literal["regression", "absolute"] = "regression"
    baseline: str = ".ankora/baseline.json"


class Config(BaseModel):
    """The fully-parsed ankora.yaml."""

    version: int = 1
    suites: list[str] = Field(default_factory=lambda: ["evals/**/*.yaml"])
    target: TargetConfig
    providers: dict[str, ProviderConfig] = Field(default_factory=dict)
    scorers: list[ScorerConfig] = Field(default_factory=list)
    gate: GateConfig = Field(default_factory=GateConfig)

    def resolve_api_key(self, provider: str) -> str:
        """Read the API key for ``provider`` from its configured env var.

        The key is read at call time and never stored on the model. Raises
        :class:`ConfigError` if the provider is not configured or its env var is
        unset/empty.
        """
        provider_config = self.providers.get(provider)
        if provider_config is None:
            configured = ", ".join(sorted(self.providers)) or "(none)"
            raise ConfigError(
                f"Provider {provider!r} is not configured under `providers`. "
                f"Configured providers: {configured}."
            )
        key = os.environ.get(provider_config.api_key_env)
        if not key:
            raise ConfigError(
                f"Environment variable {provider_config.api_key_env!r} "
                f"(for provider {provider!r}) is not set. "
                "Export it before running, e.g. "
                f"`export {provider_config.api_key_env}=...`."
            )
        return key


# The default config written by `ankora init`; mirrors the CLAUDE.md example.
DEFAULT_CONFIG_YAML = """\
version: 1
suites: ["evals/**/*.yaml"]
target:
  provider: openai
  model: gpt-4o-mini
providers:
  openai: {api_key_env: OPENAI_API_KEY}
  anthropic: {api_key_env: ANTHROPIC_API_KEY}
scorers:
  - type: llm_judge
    judge: {provider: openai, model: gpt-4o}
    rubric: "Score 1 if the answer is factually consistent with the reference, else 0."
    threshold: 0.7
  - type: embedding_similarity
    model: {provider: openai, model: text-embedding-3-small}
    threshold: 0.85
gate:
  fail_on: regression
  baseline: .ankora/baseline.json
"""


def _format_location(loc: tuple[Any, ...]) -> str:
    """Render a pydantic error location as a readable dotted/indexed path."""
    parts: list[str] = []
    for item in loc:
        if isinstance(item, int):
            parts.append(f"[{item}]")
        elif parts:
            parts.append(f".{item}")
        else:
            parts.append(str(item))
    return "".join(parts) or "(root)"


def _humanize_validation_error(error: ValidationError, source: str) -> ConfigError:
    """Turn a pydantic ValidationError into a clear, user-facing ConfigError."""
    lines = [f"Invalid ankora config ({source}):"]
    for err in error.errors():
        location = _format_location(err["loc"])
        lines.append(f"  - {location}: {err['msg']}")
    return ConfigError("\n".join(lines))


def load_config(path: str | Path = "ankora.yaml") -> Config:
    """Read an ankora.yaml file and validate it into a :class:`Config`.

    Raises :class:`ConfigError` with a human-readable message for a missing
    file, malformed YAML, or a schema violation (unknown scorer ``type``,
    missing ``api_key_env``, malformed ``gate.fail_on``, etc.).
    """
    config_path = Path(path)
    try:
        raw = config_path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise ConfigError(
            f"Config file not found: {config_path}. Run `ankora init` to create one."
        ) from exc

    try:
        data = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise ConfigError(f"Config file {config_path} is not valid YAML: {exc}") from exc

    if data is None:
        raise ConfigError(f"Config file {config_path} is empty.")
    if not isinstance(data, dict):
        raise ConfigError(
            f"Config file {config_path} must be a YAML mapping, got {type(data).__name__}."
        )

    try:
        return Config.model_validate(data)
    except ValidationError as exc:
        raise _humanize_validation_error(exc, str(config_path)) from exc
