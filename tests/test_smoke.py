"""Smoke tests for the scaffolding: imports and CLI wiring.

No provider logic is implemented yet, so these only assert the package imports
and the CLI exposes every planned subcommand. Provider calls will be mocked once
command logic lands (never live in the test suite).
"""

from __future__ import annotations

from typer.testing import CliRunner

from ankora.cli import app

runner = CliRunner()


def test_package_imports() -> None:
    import ankora

    assert ankora.__version__


def test_help_lists_all_subcommands() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for command in ("init", "ingest", "run", "diff", "gate", "baseline"):
        assert command in result.output


def test_version_command() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
