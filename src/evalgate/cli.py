"""The evalgate command-line interface.

Wires the typer app and its subcommands. Command bodies are placeholders for v1
scaffolding — each announces itself and raises until the underlying logic lands.
The ``gate`` command is the CI entrypoint and is the one that must eventually
exit non-zero on regression.
"""

from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console

from evalgate import __version__
from evalgate.config import DEFAULT_CONFIG_YAML
from evalgate.ingest.otel import ingest_otel

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
def init(
    force: bool = typer.Option(False, "--force", help="Overwrite an existing evalgate.yaml."),
) -> None:
    """Scaffold evalgate.yaml and an evals/ directory in the current repo."""
    config_path = Path("evalgate.yaml")
    if config_path.exists() and not force:
        console.print(f"[red]{config_path} already exists.[/] Pass [bold]--force[/] to overwrite.")
        raise typer.Exit(code=1)

    config_path.write_text(DEFAULT_CONFIG_YAML, encoding="utf-8")
    evals_dir = Path("evals")
    evals_dir.mkdir(exist_ok=True)

    console.print(f"[green]Wrote[/] {config_path}")
    console.print(f"[green]Created[/] {evals_dir}/ (add Case files here)")
    console.print("Next: [bold]evalgate ingest <trace-file>[/] to build your first cases.")


@app.command()
def ingest(
    trace_file: str = typer.Argument(..., help="Path to an OTel or Langfuse trace export."),
    out: str = typer.Option("evals/", "--out", help="Directory to write Case files into."),
) -> None:
    """Build or update regression Cases from a trace file."""
    trace_path = Path(trace_file)
    if not trace_path.exists():
        console.print(f"[red]Trace file not found:[/] {trace_path}")
        raise typer.Exit(code=1)

    try:
        result = ingest_otel(trace_path)
    except json.JSONDecodeError as exc:
        console.print(f"[red]{trace_path} is not valid JSON:[/] {exc}")
        raise typer.Exit(code=1) from exc

    out_dir = Path(out)
    out_dir.mkdir(parents=True, exist_ok=True)
    for case in result.cases:
        (out_dir / f"{case.id}.yaml").write_text(case.to_yaml(), encoding="utf-8")

    console.print(
        f"[green]Wrote {len(result.cases)} case(s)[/] to {out_dir}"
        + (f" ({result.skipped} span(s) skipped" if result.skipped else " (0 skipped")
        + f", {result.total_spans} span(s) seen)."
    )


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
