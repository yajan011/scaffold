"""The evalgate command-line interface.

Wires the typer app and its subcommands. Command bodies are placeholders for v1
scaffolding — each announces itself and raises until the underlying logic lands.
The ``gate`` command is the CI entrypoint and is the one that must eventually
exit non-zero on regression.
"""

from __future__ import annotations

import typer
from rich.console import Console

from evalgate import __version__

app = typer.Typer(
    name="evalgate",
    help="Local-first, CI-native regression testing for LLM applications.",
    no_args_is_help=True,
    add_completion=False,
)

console = Console()


def _todo(command: str) -> None:
    """Announce an unimplemented command and raise consistently."""
    console.print(f"[yellow]evalgate {command}[/] is not implemented yet.")
    raise NotImplementedError(f"cli.{command} is not implemented yet")


@app.callback()
def _main() -> None:
    """evalgate: turn traces into replayable LLM regression suites."""


@app.command()
def version() -> None:
    """Print the evalgate version."""
    console.print(__version__)


@app.command()
def init() -> None:
    """Scaffold evalgate.yaml and an evals/ directory in the current repo."""
    _todo("init")


@app.command()
def ingest(
    trace_file: str = typer.Argument(..., help="Path to an OTel or Langfuse trace export."),
    out: str = typer.Option("evals/", "--out", help="Directory to write Case files into."),
) -> None:
    """Build or update regression Cases from a trace file."""
    _todo("ingest")


@app.command()
def run(
    suite: list[str] = typer.Option(None, "--suite", help="Glob(s) of Case files to run."),
    target: str = typer.Option(None, "--target", help="Override target as provider:model."),
) -> None:
    """Replay and score the suite, persist a RunResult, print a summary."""
    _todo("run")


@app.command()
def diff(
    baseline: str = typer.Argument(..., help="Path to the baseline run JSON."),
    current: str = typer.Argument(..., help="Path to the current run JSON."),
) -> None:
    """Show per-case regressions between two runs."""
    _todo("diff")


@app.command()
def gate() -> None:
    """Run the suite, diff against baseline, and exit non-zero on regression.

    This is the CI entrypoint.
    """
    _todo("gate")


baseline_app = typer.Typer(
    name="baseline",
    help="Manage the regression baseline.",
    no_args_is_help=True,
)
app.add_typer(baseline_app)


@baseline_app.command("set")
def baseline_set(
    run_id: str = typer.Argument(..., help="The run id to promote to baseline."),
) -> None:
    """Promote a stored run to the baseline."""
    _todo("baseline set")


if __name__ == "__main__":
    app()
