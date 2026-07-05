"""Filesystem side effects: read/write runs and the baseline under .ankora/.

All fs access for runs/baselines is funneled through here so the rest of the
package stays pure. Runs live at ``<base_dir>/runs/<run_id>.json``; the baseline
lives at the path configured in ``config.gate.baseline``.
"""

from __future__ import annotations

from pathlib import Path

from ankora.config import Config
from ankora.models import RunResult

ANKORA_DIR = Path(".ankora")
RUNS_DIRNAME = "runs"


class StorageError(Exception):
    """Raised when a requested run or baseline cannot be found or read."""


def _runs_dir(base_dir: str | Path) -> Path:
    return Path(base_dir) / RUNS_DIRNAME


def run_path(run_id: str, base_dir: str | Path = ANKORA_DIR) -> Path:
    """Return the on-disk path for a run id (whether or not it exists yet)."""
    return _runs_dir(base_dir) / f"{run_id}.json"


def save_run(run: RunResult, base_dir: str | Path = ANKORA_DIR) -> Path:
    """Persist a RunResult to ``<base_dir>/runs/<run_id>.json``; return its path."""
    path = run_path(run.run_id, base_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(run.to_json(), encoding="utf-8")
    return path


def load_run(run_id: str, base_dir: str | Path = ANKORA_DIR) -> RunResult:
    """Load a persisted RunResult by id."""
    path = run_path(run_id, base_dir)
    if not path.exists():
        raise StorageError(f"No run found with id {run_id!r} (looked at {path}).")
    return RunResult.from_json(path.read_text(encoding="utf-8"))


def list_runs(base_dir: str | Path = ANKORA_DIR) -> list[str]:
    """Return stored run ids, newest first (by mtime, then id, descending)."""
    directory = _runs_dir(base_dir)
    if not directory.exists():
        return []
    files = [p for p in directory.glob("*.json") if p.is_file()]
    files.sort(key=lambda p: (p.stat().st_mtime, p.stem), reverse=True)
    return [p.stem for p in files]


def get_baseline(config: Config) -> RunResult:
    """Load the baseline RunResult from ``config.gate.baseline``."""
    path = Path(config.gate.baseline)
    if not path.exists():
        raise StorageError(
            f"No baseline found at {path}. Promote a run with `ankora baseline set <run_id>`."
        )
    return RunResult.from_json(path.read_text(encoding="utf-8"))


def set_baseline(config: Config, run_id: str, base_dir: str | Path = ANKORA_DIR) -> Path:
    """Promote a stored run to the baseline path in ``config.gate.baseline``."""
    run = load_run(run_id, base_dir)
    path = Path(config.gate.baseline)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(run.to_json(), encoding="utf-8")
    return path
