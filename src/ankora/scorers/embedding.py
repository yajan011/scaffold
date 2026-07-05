"""Embedding-similarity scorer: cosine similarity vs the reference output."""

from __future__ import annotations

import math

from ankora.models import Case, ScorerResult
from ankora.providers.base import Provider


class EmbeddingSimilarityScorer:
    """Cosine similarity between ``output`` and ``reference.output`` embeddings.

    The embedding provider is injected (built from the config's ModelRef via the
    provider registry), so tests can pass a fake and no network call is made.
    """

    name = "embedding_similarity"

    def __init__(self, provider: Provider, threshold: float = 0.85) -> None:
        self.provider = provider
        self.threshold = threshold

    def score(self, case: Case, output: str) -> ScorerResult:
        reference = case.reference.output
        output_vec, reference_vec = self.provider.embed([output, reference])
        similarity = _cosine(output_vec, reference_vec)
        # ScorerResult scores are constrained to [0, 1]; cosine can be negative.
        value = max(0.0, min(1.0, similarity))
        return ScorerResult(
            scorer=self.name,
            score=value,
            passed=value >= self.threshold,
            threshold=self.threshold,
            detail=f"cosine similarity {similarity:.4f}",
        )


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)
