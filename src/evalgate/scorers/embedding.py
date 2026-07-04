"""Embedding-similarity scorer: cosine similarity vs the reference output.

Logic is stubbed for v1 scaffolding.
"""

from __future__ import annotations

from evalgate.models import Case, ScorerResult


class EmbeddingSimilarityScorer:
    """Score the cosine similarity between output and reference embeddings."""

    name = "embedding_similarity"

    def __init__(
        self,
        provider: str,
        model: str,
        threshold: float = 0.85,
        api_key_env: str | None = None,
    ) -> None:
        self.provider = provider
        self.model = model
        self.threshold = threshold
        self.api_key_env = api_key_env

    def score(self, case: Case, output: str) -> ScorerResult:
        """Not yet implemented — placeholder for v1 scaffolding."""
        raise NotImplementedError("EmbeddingSimilarityScorer.score is not implemented yet")
