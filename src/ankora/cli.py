"""The ankora command-line interface.

Wires the typer app and its subcommands (``init``, ``ingest``, ``run``, ``diff``,
``gate``, ``baseline set``). ``gate`` is the CI entrypoint: it exits non-zero
when quality regresses against the baseline.
"""

from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from ankora import __version__
from ankora.config import (
    DEFAULT_CONFIG_YAML,
    Config,
    ConfigError,
    TargetConfig,
    load_config,
)
from ankora.diff import DiffReport, diff_runs
from ankora.ingest import ingest_traces
from ankora.models import RunResult
from ankora.replay import replay
from ankora.storage import StorageError, get_baseline, load_run, run_path, set_baseline
from ankora.suites import SuiteError

app = typer.Typer(
    name="ankora",
    help="Local-first, CI-native regression testing for LLM applications.",
    no_args_is_help=True,
    add_completion=False,
)

console = Console()


def _version_callback(value: bool) -> None:
    if value:
        console.print(__version__)
        raise typer.Exit()


@app.callback()
def _main(
    _version: bool = typer.Option(
        False,
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="Show the ankora version and exit.",
    ),
) -> None:
    """ankora: turn the traces you already capture into CI regression tests."""


@app.command()
def version() -> None:
    """Print the ankora version."""
    console.print(__version__)


@app.command()
def init(
    force: bool = typer.Option(False, "--force", help="Overwrite an existing ankora.yaml."),
) -> None:
    """Scaffold ankora.yaml and an evals/ directory in the current repo."""
    config_path = Path("ankora.yaml")
    if config_path.exists() and not force:
        console.print(f"[red]{config_path} already exists.[/] Pass [bold]--force[/] to overwrite.")
        raise typer.Exit(code=1)

    config_path.write_text(DEFAULT_CONFIG_YAML, encoding="utf-8")
    evals_dir = Path("evals")
    evals_dir.mkdir(exist_ok=True)

    console.print(f"[green]Wrote[/] {config_path}")
    console.print(f"[green]Created[/] {evals_dir}/ (add Case files here)")
    console.print("Next: [bold]ankora ingest <trace-file>[/] to build your first cases.")


@app.command()
def ingest(
    trace_file: str = typer.Argument(
        ..., help="Path to an OpenTelemetry GenAI or Langfuse trace export (JSON)."
    ),
    out: str = typer.Option("evals/", "--out", help="Directory to write Case files into."),
    fmt: str = typer.Option(
        "auto", "--format", help="Trace format: auto (default), otel, or langfuse."
    ),
) -> None:
    """Build or update regression Cases from an OTel GenAI or Langfuse trace file."""
    if fmt not in ("auto", "otel", "langfuse"):
        console.print(f"[red]--format must be one of: auto, otel, langfuse[/] (got {fmt!r})")
        raise typer.Exit(code=1)

    trace_path = Path(trace_file)
    if not trace_path.exists():
        console.print(f"[red]Trace file not found:[/] {trace_path}")
        raise typer.Exit(code=1)

    try:
        result, detected = ingest_traces(trace_path, fmt)
    except json.JSONDecodeError as exc:
        console.print(f"[red]{trace_path} is not valid JSON:[/] {exc}")
        raise typer.Exit(code=1) from exc

    out_dir = Path(out)
    out_dir.mkdir(parents=True, exist_ok=True)
    for case in result.cases:
        (out_dir / f"{case.id}.yaml").write_text(case.to_yaml(), encoding="utf-8")

    console.print(
        f"[green]Wrote {len(result.cases)} case(s)[/] to {out_dir} "
        f"({detected} format; {result.skipped} skipped, {result.total} record(s) seen)."
    )


@app.command()
def run(
    suite: list[str] = typer.Option(None, "--suite", help="Glob(s) of Case files to run."),
    target: str = typer.Option(None, "--target", help="Override target as provider:model."),
    concurrency: int = typer.Option(8, "--concurrency", help="Max cases to replay in parallel."),
    config_path: str = typer.Option("ankora.yaml", "--config", help="Path to ankora.yaml."),
) -> None:
    """Replay and score the suite, persist a RunResult, print a summary."""
    try:
        config = load_config(config_path)
        if suite:
            config = config.model_copy(update={"suites": list(suite)})
        result = replay(config, target=target, concurrency=concurrency)
    except (ConfigError, SuiteError) as exc:
        console.print(f"[red]{exc}[/]")
        raise typer.Exit(code=1) from exc

    _print_run_table(result)
    console.print(f"\nSaved run [bold]{result.run_id}[/] to {run_path(result.run_id)}")


def _print_run_table(result: RunResult) -> None:
    table = Table(title=f"ankora run · {result.target.provider}:{result.target.model}")
    table.add_column("Case", overflow="fold")
    table.add_column("Result")
    table.add_column("Scores", overflow="fold")
    for case_result in result.case_results:
        status = "[green]PASS[/]" if case_result.passed else "[red]FAIL[/]"
        scores = ", ".join(
            f"{s.scorer} {s.score:.2f}{'✓' if s.passed else '✗'}"
            for s in case_result.scorer_results
        )
        table.add_row(case_result.case_id, status, scores or "—")
    console.print(table)

    summary = result.summary
    color = "green" if summary.failed == 0 else "red"
    console.print(f"[{color}]{summary.passed}/{summary.total} passed, {summary.failed} failed[/]")


@app.command()
def diff(
    baseline: str = typer.Argument(..., help="Baseline run id or path to a run JSON."),
    current: str = typer.Argument(..., help="Current run id or path to a run JSON."),
    config_path: str = typer.Option("ankora.yaml", "--config", help="Path to ankora.yaml."),
    fail_on: str = typer.Option(None, "--fail-on", help="Override gate.fail_on for this diff."),
) -> None:
    """Show per-case changes between two runs. Read-only; always exits 0."""
    config = _load_config_or_default(config_path)
    if fail_on:
        gate_config = config.gate.model_copy(update={"fail_on": fail_on})
        config = config.model_copy(update={"gate": gate_config})

    try:
        baseline_run = _resolve_run(baseline)
        current_run = _resolve_run(current)
    except StorageError as exc:
        console.print(f"[red]{exc}[/]")
        raise typer.Exit(code=1) from exc

    _print_diff_report(diff_runs(baseline_run, current_run, config))


@app.command()
def gate(
    config_path: str = typer.Option("ankora.yaml", "--config", help="Path to ankora.yaml."),
    target: str = typer.Option(None, "--target", help="Override target as provider:model."),
    concurrency: int = typer.Option(8, "--concurrency", help="Max cases to replay in parallel."),
) -> None:
    """Replay the suite, diff against baseline, and exit non-zero on regression.

    This is the CI entrypoint.
    """
    try:
        config = load_config(config_path)
        current = replay(config, target=target, concurrency=concurrency)
    except (ConfigError, SuiteError) as exc:
        console.print(f"[red]{exc}[/]")
        raise typer.Exit(code=1) from exc

    _print_run_table(current)

    try:
        baseline = get_baseline(config)
    except StorageError:
        console.print(
            "\n[yellow]No baseline yet[/] — nothing to regress against. "
            f"Promote this run with [bold]ankora baseline set {current.run_id}[/]."
        )
        raise typer.Exit(code=0) from None

    report = diff_runs(baseline, current, config)
    _print_diff_report(report)
    if report.has_regressions:
        console.print(f"\n[red]{report.regressions} regression(s) detected — failing the gate.[/]")
        raise typer.Exit(code=1)
    console.print("\n[green]No regressions — gate passed.[/]")


baseline_app = typer.Typer(
    name="baseline",
    help="Manage the regression baseline.",
    no_args_is_help=True,
)
app.add_typer(baseline_app)


@baseline_app.command("set")
def baseline_set(
    run_id: str = typer.Argument(..., help="The run id to promote to baseline."),
    config_path: str = typer.Option("ankora.yaml", "--config", help="Path to ankora.yaml."),
) -> None:
    """Promote a stored run to the baseline."""
    try:
        config = load_config(config_path)
        path = set_baseline(config, run_id)
    except (ConfigError, StorageError) as exc:
        console.print(f"[red]{exc}[/]")
        raise typer.Exit(code=1) from exc
    console.print(f"[green]Baseline set[/] to run [bold]{run_id}[/] at {path}")


def _load_config_or_default(config_path: str) -> Config:
    """Load config, or fall back to a minimal default (used by read-only diff)."""
    try:
        return load_config(config_path)
    except ConfigError:
        return Config(target=TargetConfig(provider="unknown", model="unknown"))


def _resolve_run(reference: str) -> RunResult:
    """Resolve a run reference that is either a path to a run JSON or a run id."""
    path = Path(reference)
    if path.exists():
        return RunResult.from_json(path.read_text(encoding="utf-8"))
    return load_run(reference)


def _print_diff_report(report: DiffReport) -> None:
    table = Table(title=f"ankora diff · fail_on={report.fail_on}")
    table.add_column("Case", overflow="fold")
    table.add_column("Status")
    table.add_column("Baseline")
    table.add_column("Current")
    table.add_column("Δ")
    table.add_column("Regression")
    for case in report.cases:
        table.add_row(
            case.case_id,
            case.status.value,
            _fmt_score(case.baseline_score),
            _fmt_score(case.current_score),
            f"{case.delta:+.3f}" if case.delta is not None else "—",
            "[red]yes[/]" if case.is_regression else "no",
        )
    console.print(table)
    console.print(
        f"regressed={report.regressed} new_failures={report.new_failures} "
        f"fixed={report.fixed} unchanged={report.unchanged} "
        f"new_passes={report.new_passes} removed={report.removed}"
    )


def _fmt_score(score: float | None) -> str:
    return f"{score:.3f}" if score is not None else "—"


if __name__ == "__main__":
    app()
