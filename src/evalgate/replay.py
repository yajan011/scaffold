"""Replay a Suite against a target provider/model and score the outputs.

Logic is stubbed for v1 scaffolding.
"""

from __future__ import annotations

from evalgate.config import Config
from evalgate.models import RunResult, Suite


def run_suite(suite: Suite, config: Config) -> RunResult:
    """Replay every Case in a Suite and score the outputs into a RunResult.

    Not yet implemented — placeholder for v1 scaffolding.
    """
    raise NotImplementedError("replay.run_suite is not implemented yet")
