"""Replay a Suite against a target provider and score the outputs into a RunResult."""

from __future__ import annotations

import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from typing import Any

from ankora.config import Config, ConfigError, TargetConfig
from ankora.models import Case, CaseResult, RunResult, RunSummary, RunTarget, Suite
from ankora.providers.registry import get_provider
from ankora.scorers.registry import build_scorers
from ankora.storage import save_run
from ankora.suites import load_suites


def replay(
    config: Config,
    suite: Suite | None = None,
    target: str | None = None,
    concurrency: int = 8,
    client: Any | None = None,
) -> RunResult:
    """Replay every Case against the target provider, score, persist, and return.

    ``suite`` defaults to loading ``config.suites``. ``target`` optionally
    overrides the config target as ``"provider:model"``. ``client`` is injected
    into both the target provider and the scorers' providers so tests never make
    a live call. Cases run concurrently (thread pool) but ``case_results`` keep
    suite order.
    """
    if target is not None:
        config = _apply_target_override(config, target)
    if suite is None:
        suite = load_suites(config)

    provider = get_provider(config.target.provider, config, client=client)
    scorers = build_scorers(config, client=client)
    if not scorers:
        raise ConfigError(
            "No scorers configured — every case would pass vacuously. "
            "Add at least one entry under `scorers:`."
        )

    def _score_case(case: Case) -> CaseResult:
        completion = provider.complete(case.input.messages, case.input.params)
        scorer_results = [scorer.score(case, completion.text) for scorer in scorers]
        return CaseResult(
            case_id=case.id,
            output=completion.text,
            scorer_results=scorer_results,
            passed=all(result.passed for result in scorer_results),
        )

    with ThreadPoolExecutor(max_workers=max(1, concurrency)) as executor:
        # executor.map preserves the input (suite) order in its results.
        case_results = list(executor.map(_score_case, suite.cases))

    created_at = datetime.now(UTC)
    run = RunResult(
        run_id=f"{created_at:%Y%m%dT%H%M%SZ}-{uuid.uuid4().hex[:8]}",
        target=RunTarget(provider=config.target.provider, model=config.target.model),
        created_at=created_at,
        case_results=case_results,
        summary=RunSummary(
            total=len(case_results),
            passed=sum(1 for r in case_results if r.passed),
            failed=sum(1 for r in case_results if not r.passed),
        ),
    )
    save_run(run)
    return run


def _apply_target_override(config: Config, target: str) -> Config:
    provider, separator, model = target.partition(":")
    if not separator or not provider or not model:
        raise ConfigError(f"--target must be 'provider:model', got {target!r}.")
    return config.model_copy(update={"target": TargetConfig(provider=provider, model=model)})
