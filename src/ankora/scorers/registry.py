"""Build Scorer instances from a Config's scorer entries.

Embedding and llm_judge scorers need a provider; it is constructed via the
provider registry using the scorer's own ModelRef. An optional ``client`` is
threaded through to ``get_provider`` so tests can inject fakes and avoid any
network call.
"""

from __future__ import annotations

from typing import Any

import jsonschema

from ankora.config import (
    Config,
    ConfigError,
    EmbeddingSimilarityScorerConfig,
    ExactScorerConfig,
    JSONSchemaScorerConfig,
    LLMJudgeScorerConfig,
    RegexScorerConfig,
)
from ankora.providers.registry import get_provider
from ankora.scorers.base import Scorer
from ankora.scorers.embedding import EmbeddingSimilarityScorer
from ankora.scorers.exact import ExactScorer
from ankora.scorers.json_schema import JSONSchemaScorer
from ankora.scorers.llm_judge import LLMJudgeScorer
from ankora.scorers.regex import RegexScorer


def build_scorer(entry: Any, config: Config, client: Any | None = None) -> Scorer:
    """Construct the Scorer described by a single scorer config entry."""
    if isinstance(entry, ExactScorerConfig):
        return ExactScorer(threshold=entry.threshold, normalize=entry.normalize)
    if isinstance(entry, RegexScorerConfig):
        return RegexScorer(pattern=entry.pattern, threshold=entry.threshold)
    if isinstance(entry, JSONSchemaScorerConfig):
        try:
            return JSONSchemaScorer(schema=entry.json_schema, threshold=entry.threshold)
        except jsonschema.exceptions.SchemaError as exc:
            raise ConfigError(f"Invalid json_schema scorer schema: {exc.message}") from exc
    if isinstance(entry, EmbeddingSimilarityScorerConfig):
        provider = get_provider(
            entry.model.provider, config, client=client, model=entry.model.model
        )
        return EmbeddingSimilarityScorer(provider=provider, threshold=entry.threshold)
    if isinstance(entry, LLMJudgeScorerConfig):
        provider = get_provider(
            entry.judge.provider, config, client=client, model=entry.judge.model
        )
        return LLMJudgeScorer(provider=provider, rubric=entry.rubric, threshold=entry.threshold)
    raise ConfigError(f"Unknown scorer config type: {type(entry).__name__}")


def build_scorers(config: Config, client: Any | None = None) -> list[Scorer]:
    """Construct every Scorer declared in ``config.scorers``."""
    return [build_scorer(entry, config, client=client) for entry in config.scorers]
