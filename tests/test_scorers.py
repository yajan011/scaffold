"""Tests for the scorer layer.

Deterministic scorers (exact/regex/json_schema) use real logic; embedding and
llm_judge use injected fake providers/clients so no live API call is made.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from ankora.config import (
    Config,
    ConfigError,
    EmbeddingSimilarityScorerConfig,
    ExactScorerConfig,
    JSONSchemaScorerConfig,
    LLMJudgeScorerConfig,
    ModelRef,
    ProviderConfig,
    RegexScorerConfig,
    TargetConfig,
)
from ankora.models import Case, CaseReference
from ankora.providers.base import Completion
from ankora.scorers.embedding import EmbeddingSimilarityScorer
from ankora.scorers.exact import ExactScorer
from ankora.scorers.json_schema import JSONSchemaScorer
from ankora.scorers.llm_judge import LLMJudgeScorer, _parse_judgement
from ankora.scorers.regex import RegexScorer
from ankora.scorers.registry import build_scorer, build_scorers


def _case(reference: str) -> Case:
    return Case(id="c1", reference=CaseReference(output=reference))


# --------------------------------------------------------------------------- #
# Exact
# --------------------------------------------------------------------------- #
def test_exact_normalized_match_passes() -> None:
    result = ExactScorer().score(_case("Paris"), "  paris\n")
    assert result.score == 1.0
    assert result.passed is True
    assert result.scorer == "exact"


def test_exact_mismatch_fails() -> None:
    result = ExactScorer().score(_case("Paris"), "London")
    assert result.score == 0.0
    assert result.passed is False


def test_exact_without_normalization_is_case_sensitive() -> None:
    result = ExactScorer(normalize=False).score(_case("Paris"), "paris")
    assert result.passed is False


# --------------------------------------------------------------------------- #
# Regex
# --------------------------------------------------------------------------- #
def test_regex_match_passes_and_names_pattern() -> None:
    scorer = RegexScorer(pattern=r"\bParis\b")
    result = scorer.score(_case(""), "The capital is Paris.")
    assert result.score == 1.0
    assert result.passed is True
    assert "Paris" in result.detail


def test_regex_no_match_fails() -> None:
    result = RegexScorer(pattern=r"\bParis\b").score(_case(""), "The capital is London.")
    assert result.score == 0.0
    assert result.passed is False


# --------------------------------------------------------------------------- #
# JSON schema
# --------------------------------------------------------------------------- #
_SCHEMA = {
    "type": "object",
    "required": ["city", "temp"],
    "properties": {
        "city": {"type": "string"},
        "temp": {"type": "number", "minimum": -100, "maximum": 100},
    },
    "additionalProperties": False,
}


def test_json_schema_valid_passes() -> None:
    result = JSONSchemaScorer(schema=_SCHEMA).score(_case(""), '{"city": "Paris", "temp": 21}')
    assert result.score == 1.0
    assert result.passed is True


def test_json_schema_wrong_type_fails_with_detail() -> None:
    result = JSONSchemaScorer(schema=_SCHEMA).score(_case(""), '{"city": 5, "temp": 21}')
    assert result.score == 0.0
    assert "is not of type 'string'" in result.detail
    assert "city" in result.detail


def test_json_schema_spec_keywords_are_honored() -> None:
    # Keywords the old hand-rolled validator silently ignored must now reject.
    exclusive = JSONSchemaScorer(schema={"type": "number", "exclusiveMinimum": 5})
    assert exclusive.score(_case(""), "5").score == 0.0

    const = JSONSchemaScorer(schema={"const": "yes"})
    assert const.score(_case(""), '"no"').score == 0.0

    any_of = JSONSchemaScorer(schema={"anyOf": [{"type": "string"}, {"type": "number"}]})
    assert any_of.score(_case(""), "{}").score == 0.0
    assert any_of.score(_case(""), '"ok"').score == 1.0


def test_json_schema_integer_accepts_zero_fraction_float() -> None:
    # Per the JSON Schema spec, 2.0 is a valid "integer".
    assert JSONSchemaScorer(schema={"type": "integer"}).score(_case(""), "2.0").score == 1.0
    assert JSONSchemaScorer(schema={"type": "integer"}).score(_case(""), "2.5").score == 0.0


def test_json_schema_invalid_schema_raises_config_error() -> None:
    entry = JSONSchemaScorerConfig(type="json_schema", json_schema={"type": "not-a-type"})
    with pytest.raises(ConfigError, match="json_schema"):
        build_scorer(entry, _full_config())


def test_json_schema_missing_required_fails() -> None:
    result = JSONSchemaScorer(schema=_SCHEMA).score(_case(""), '{"city": "Paris"}')
    assert result.score == 0.0
    assert "required" in result.detail


def test_json_schema_unparseable_output_fails() -> None:
    result = JSONSchemaScorer(schema=_SCHEMA).score(_case(""), "not json at all")
    assert result.score == 0.0
    assert "not valid JSON" in result.detail


# --------------------------------------------------------------------------- #
# Embedding similarity (fake provider)
# --------------------------------------------------------------------------- #
class _FakeEmbeddingProvider:
    name = "openai"

    def __init__(self, vectors: dict[str, list[float]]) -> None:
        self._vectors = vectors

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._vectors[t] for t in texts]

    def complete(self, messages: Any, params: Any) -> Completion:  # pragma: no cover
        raise NotImplementedError


def test_embedding_similarity_math_and_threshold() -> None:
    # cosine([1,1], [1,0]) = 1 / sqrt(2) ~= 0.7071
    provider = _FakeEmbeddingProvider({"out": [1.0, 1.0], "ref": [1.0, 0.0]})
    case = _case("ref")

    high = EmbeddingSimilarityScorer(provider, threshold=0.85).score(case, "out")
    assert abs(high.score - 0.70710678) < 1e-6
    assert high.passed is False
    assert "cosine" in high.detail

    low = EmbeddingSimilarityScorer(provider, threshold=0.5).score(case, "out")
    assert low.passed is True


def test_embedding_identical_vectors_scores_one() -> None:
    provider = _FakeEmbeddingProvider({"out": [0.3, 0.4], "ref": [0.3, 0.4]})
    result = EmbeddingSimilarityScorer(provider, threshold=0.9).score(_case("ref"), "out")
    assert abs(result.score - 1.0) < 1e-9
    assert result.passed is True


# --------------------------------------------------------------------------- #
# LLM judge (fake provider) + parser robustness
# --------------------------------------------------------------------------- #
class _FakeJudgeProvider:
    name = "openai"

    def __init__(self, text: str) -> None:
        self.text = text
        self.calls: list[tuple[Any, Any]] = []

    def complete(self, messages: Any, params: Any) -> Completion:
        self.calls.append((messages, params))
        return Completion(text=self.text)

    def embed(self, texts: list[str]) -> list[list[float]]:  # pragma: no cover
        raise NotImplementedError


def test_llm_judge_clean_json_response() -> None:
    provider = _FakeJudgeProvider('{"score": 1, "justification": "fully consistent"}')
    scorer = LLMJudgeScorer(provider, rubric="Score 1 if consistent.", threshold=0.7)

    result = scorer.score(_case("Paris is the capital of France."), "Paris.")

    assert result.score == 1.0
    assert result.passed is True
    assert result.detail == "fully consistent"

    # The judge was called deterministically with the rubric in the prompt.
    messages, params = provider.calls[0]
    assert params["temperature"] == 0
    assert any("Score 1 if consistent." in m.content for m in messages)


def test_llm_judge_messy_prose_response() -> None:
    provider = _FakeJudgeProvider(
        "Hmm, I think the answer is largely correct. I'd give it a 0.8 out of 1. "
        "It matches the reference facts."
    )
    result = LLMJudgeScorer(provider, rubric="r", threshold=0.7).score(_case("ref"), "out")
    assert abs(result.score - 0.8) < 1e-9
    assert result.passed is True


def test_llm_judge_low_score_fails() -> None:
    provider = _FakeJudgeProvider("Score: 0 — the answer contradicts the reference.")
    result = LLMJudgeScorer(provider, rubric="r", threshold=0.7).score(_case("ref"), "out")
    assert result.score == 0.0
    assert result.passed is False


def test_parse_judgement_variants() -> None:
    assert _parse_judgement('{"score": 0.9, "justification": "x"}')[0] == 0.9
    assert _parse_judgement("The score = 0.42 here")[0] == 0.42
    assert _parse_judgement("rating 0.65 overall")[0] == 0.65
    assert _parse_judgement("no numbers here")[0] == 0.0


def test_parse_judgement_ratio_scales() -> None:
    # "N/M" and "N out of M" are explicit scales and become N/M.
    assert abs(_parse_judgement("I'd rate this 8/10, decent.")[0] - 0.8) < 1e-9
    assert abs(_parse_judgement("Score: 2 out of 10 — mostly wrong.")[0] - 0.2) < 1e-9
    assert abs(_parse_judgement("4 out of 5 stars")[0] - 0.8) < 1e-9
    # A labeled in-range score wins over a stray ratio elsewhere in the text.
    assert _parse_judgement("score: 0.9 — details: matched 3/5 criteria")[0] == 0.9


def test_parse_judgement_bare_integer_above_one_is_never_a_pass() -> None:
    # Regression guard: "score: 5" used to be clamped to a passing 1.0.
    for text in ("score: 5", "Score: 7", "I give it 10", '{"score": 5}'):
        value, detail = _parse_judgement(text)
        assert value == 0.0, text
        assert "could not parse" in detail, text


# --------------------------------------------------------------------------- #
# Registry wiring with injected fake client
# --------------------------------------------------------------------------- #
def _fake_openai_client() -> Any:
    def embeddings_create(**kwargs: Any) -> Any:
        count = len(kwargs["input"])
        return SimpleNamespace(data=[SimpleNamespace(embedding=[1.0, 0.0]) for _ in range(count)])

    def chat_create(**kwargs: Any) -> Any:
        message = SimpleNamespace(content='{"score": 1, "justification": "ok"}', tool_calls=None)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)], usage=None)

    return SimpleNamespace(
        embeddings=SimpleNamespace(create=embeddings_create),
        chat=SimpleNamespace(completions=SimpleNamespace(create=chat_create)),
    )


def _full_config() -> Config:
    return Config(
        target=TargetConfig(provider="openai", model="gpt-4o-mini"),
        providers={"openai": ProviderConfig(api_key_env="OPENAI_API_KEY")},
        scorers=[
            ExactScorerConfig(type="exact"),
            RegexScorerConfig(type="regex", pattern="Paris"),
            JSONSchemaScorerConfig(type="json_schema", json_schema={"type": "object"}),
            EmbeddingSimilarityScorerConfig(
                type="embedding_similarity",
                model=ModelRef(provider="openai", model="text-embedding-3-small"),
            ),
            LLMJudgeScorerConfig(
                type="llm_judge",
                judge=ModelRef(provider="openai", model="gpt-4o"),
                rubric="Score 1 if consistent.",
            ),
        ],
    )


def test_build_scorers_wires_all_types_with_injected_client() -> None:
    scorers = build_scorers(_full_config(), client=_fake_openai_client())

    assert [type(s) for s in scorers] == [
        ExactScorer,
        RegexScorer,
        JSONSchemaScorer,
        EmbeddingSimilarityScorer,
        LLMJudgeScorer,
    ]

    # The injected client flows through the wired providers (no network).
    case = _case("Paris")
    assert scorers[3].score(case, "Paris").score == 1.0  # embedding via fake client
    assert scorers[4].score(case, "Paris").score == 1.0  # judge via fake client
