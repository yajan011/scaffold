"""Build Scorer instances from ScorerConfig entries.

Logic is stubbed for v1 scaffolding.
"""

from __future__ import annotations

from evalgate.config import ScorerConfig
from evalgate.scorers.base import Scorer


def build_scorer(config: ScorerConfig) -> Scorer:
    """Construct the Scorer described by a ScorerConfig entry.

    Not yet implemented — placeholder for v1 scaffolding.
    """
    raise NotImplementedError("scorers.registry.build_scorer is not implemented yet")
