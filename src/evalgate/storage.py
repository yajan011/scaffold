"""Filesystem side effects: read/write runs and baseline under .evalgate/.

All fs access for runs/baselines is funneled through here so the rest of the
package stays pure. Logic is stubbed for v1 scaffolding.
"""

from __future__ import annotations

from pathlib import Path

from evalgate.models import RunResult

EVALGATE_DIR = Path(".evalgate")
RUNS_DIR = EVALGATE_DIR / "runs"
BASELINE_PATH = EVALGATE_DIR / "baseline.json"


def save_run(run: RunResult, base_dir: str | Path = EVALGATE_DIR) -> Path:
    """Persist a RunResult to .evalgate/runs/<run_id>.json."""
    raise NotImplementedError("storage.save_run is not implemented yet")


def load_run(run_id: str, base_dir: str | Path = EVALGATE_DIR) -> RunResult:
    """Load a persisted RunResult by id."""
    raise NotImplementedError("storage.load_run is not implemented yet")


def load_baseline(path: str | Path = BASELINE_PATH) -> RunResult:
    """Load the baseline RunResult."""
    raise NotImplementedError("storage.load_baseline is not implemented yet")


def set_baseline(run_id: str, path: str | Path = BASELINE_PATH) -> Path:
    """Promote a stored run to the baseline."""
    raise NotImplementedError("storage.set_baseline is not implemented yet")
