"""LLM-judge scorer: a model grades the output against a rubric.

Logic is stubbed for v1 scaffolding.
"""

from __future__ import annotations

from evalgate.models import Case, ScorerResult


class LLMJudgeScorer:
    """Score an output by asking a judge model to apply a rubric."""

    name = "llm_judge"

    def __init__(
        self,
        provider: str,
        model: str,
        rubric: str,
        threshold: float = 0.7,
        api_key_env: str | None = None,
    ) -> None:
        self.provider = provider
        self.model = model
        self.rubric = rubric
        self.threshold = threshold
        self.api_key_env = api_key_env

    def score(self, case: Case, output: str) -> ScorerResult:
        """Not yet implemented — placeholder for v1 scaffolding."""
        raise NotImplementedError("LLMJudgeScorer.score is not implemented yet")
