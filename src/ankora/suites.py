"""Load Cases from the suite globs declared in a Config into a Suite."""

from __future__ import annotations

import glob as globlib
from pathlib import Path

import yaml
from pydantic import ValidationError

from ankora.config import Config
from ankora.models import Case, Suite


class SuiteError(Exception):
    """Raised when suites cannot be loaded (e.g. a glob matches no files, or a
    Case file is malformed)."""


def load_suites(config: Config) -> Suite:
    """Expand ``config.suites`` globs and load every Case into a Suite.

    Files are loaded in sorted order per pattern for a stable suite order, and a
    file matched by multiple patterns is loaded once. Raises :class:`SuiteError`
    if any pattern matches no files.
    """
    cases: list[Case] = []
    source_paths: list[Path] = []
    seen: set[Path] = set()

    for pattern in config.suites:
        matches = sorted(globlib.glob(pattern, recursive=True))
        files = [Path(m) for m in matches if Path(m).is_file()]
        if not files:
            raise SuiteError(f"Suite pattern matched no files: {pattern!r}")
        for path in files:
            resolved = path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            try:
                case = Case.from_yaml(path.read_text(encoding="utf-8"))
            except (yaml.YAMLError, ValidationError, ValueError, TypeError) as exc:
                raise SuiteError(f"invalid YAML in {path}: {_short_reason(exc)}") from exc
            cases.append(case)
            source_paths.append(path)

    if not cases:
        raise SuiteError("No cases were loaded from the configured suite patterns.")

    return Suite(cases=cases, source_paths=source_paths)


def _short_reason(exc: Exception) -> str:
    """One short line describing why a Case file failed to parse/validate."""
    text = str(exc).strip()
    first = text.splitlines()[0] if text else type(exc).__name__
    return first[:200]
