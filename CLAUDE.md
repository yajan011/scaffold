# CLAUDE.md — context for building evalgate

This file is auto-loaded by Claude Code. It is the source of truth for what we are building and the rules for building it. `evalgate` is a placeholder name; if we rename, update this file first.

## What we are building

`evalgate` is an open-source, local-first, CI-native regression-testing tool for LLM and agent applications. It turns the traces a team already captures into replayable regression suites, replays them deterministically across model providers, scores the outputs, and fails the CI build when quality silently regresses.

The problem it solves, in one sentence: teams have observability (traces) but no tests, so prompt tweaks, model version bumps, and silent provider changes ship undetected until users complain. `evalgate` closes that gap from the supply side.

## Non-negotiable product principles

1. Local-first and offline. The core tool runs on a laptop or a CI runner with no account, no login, no network calls except to the model providers the user configures. Never add telemetry, phone-home, or a required hosted service to the OSS core.
2. Bring-your-own-keys. Replays run with the user's own provider API keys, read from env vars. We never carry token cost. Do not build anything that requires us to run inference on our infra.
3. Neutral and framework-agnostic. No lock-in to any one LLM framework, provider, or storage backend. Read open formats (OpenTelemetry GenAI semantic conventions first). Suites are plain files checked into the user's repo.
4. Legible over clever. Output, config, and (later) billing must be understandable at a glance. Deterministic behavior beats magic.
5. CI is the primary surface. The single most important command is the one that exits non-zero when quality regresses, so a GitHub Action can block a merge.

## Scope for v1 (what to build)

A Python CLI + library that does four things:

1. Ingest OTel / GenAI-semantic-convention traces (and Langfuse JSON export) into regression cases.
2. Author a regression suite from those traces, written as editable files in the repo.
3. Replay each case's input against a target provider/model deterministically, and score the output with pluggable scorers.
4. Gate: compare against a baseline, detect regressions, and exit non-zero for CI.

## Explicitly OUT of scope for v1 (do NOT build)

- Any hosted dashboard, web UI, user accounts, auth, or billing.
- Any telemetry or analytics on the user.
- A scheduled/live "drift monitor" (this is phase 2; it is just `run` on a cron against a live endpoint).
- Full multi-step agent trajectory record-replay with tool mocking (phase 2; v1 targets single-turn LLM replay and records tool calls as reference data only).
- Prompt management, a gateway/proxy, a vector DB, or an agent framework. We integrate with these, we do not replace them.

## Tech stack (decided — do not swap without updating this file)

- Language: Python 3.11+
- Packaging / env: `uv` (pyproject.toml, `uv run`, `uv sync`)
- CLI: `typer`
- Data models / validation: `pydantic` v2
- Provider SDKs: official `openai` and `anthropic` packages
- HTTP (if needed beyond SDKs): `httpx`
- Pretty terminal output: `rich`
- Config: YAML via `pyyaml`
- Local storage: JSON files under `.evalgate/`, SQLite only if a real need appears
- Tests: `pytest`, with all provider calls mocked (no live API calls in the test suite)
- Lint/format: `ruff`
- Trace format: OpenTelemetry GenAI semantic conventions (`gen_ai.*` attributes) as the canonical input; a Langfuse-export adapter as the second reader

## Directory structure (target)

```
evalgate/
  pyproject.toml
  README.md
  CLAUDE.md
  src/evalgate/
    __init__.py
    cli.py            # typer app, wires subcommands
    config.py         # load/validate evalgate.yaml -> pydantic Config
    models.py         # Case, Suite, RunResult, CaseResult, ScorerResult (pydantic)
    ingest/
      __init__.py
      otel.py         # OTel GenAI trace -> [Case]
      langfuse.py     # Langfuse export -> [Case]
    providers/
      __init__.py
      base.py         # Provider protocol: complete(messages, params) -> Completion
      openai.py
      anthropic.py
      registry.py
    scorers/
      __init__.py
      base.py         # Scorer protocol: score(case, output) -> ScorerResult
      exact.py
      regex.py
      json_schema.py
      embedding.py     # cosine similarity via embedding model
      llm_judge.py     # rubric-based judge
      registry.py
    replay.py         # run a Suite against a target -> RunResult
    diff.py           # compare RunResult vs baseline -> regressions
    storage.py        # read/write runs, baseline under .evalgate/
  tests/
  examples/           # a sample app + sample traces to demo on
  .github/workflows/  # the reusable action
```

## Core data model (canonical definitions)

A **Case** is one recorded interaction turned into a test:
```yaml
id: string                     # stable, derived from source trace id
input:
  messages: [{role, content}]  # OpenAI-style chat messages
  params: {temperature, top_p, max_tokens, ...}
tools: [...]                   # optional, tool schemas present at the time (recorded, not yet enforced in v1)
reference:
  output: string               # golden completion (the recorded output)
  tool_calls: [...]            # optional recorded tool calls (reference only in v1)
metadata:
  source_trace_id: string
  original_model: string
  created_at: iso8601
  tags: [string]
```

A **Suite** is a directory/glob of Case files checked into the user's repo (default `evals/**/*.yaml`).

A **ScorerResult**: `{scorer: str, score: float 0..1, passed: bool, threshold: float, detail: str}`.

A **CaseResult**: `{case_id, output, scorer_results: [ScorerResult], passed: bool}`.

A **RunResult**: `{run_id, target: {provider, model}, created_at, case_results: [CaseResult], summary: {total, passed, failed}}`, persisted to `.evalgate/runs/<run_id>.json`.

## Config file (evalgate.yaml, lives in user's repo)

```yaml
version: 1
suites: ["evals/**/*.yaml"]
target:
  provider: openai
  model: gpt-4o-mini
providers:
  openai: {api_key_env: OPENAI_API_KEY}
  anthropic: {api_key_env: ANTHROPIC_API_KEY}
scorers:
  - type: llm_judge
    judge: {provider: openai, model: gpt-4o}
    rubric: "Score 1 if the answer is factually consistent with the reference, else 0."
    threshold: 0.7
  - type: embedding_similarity
    model: {provider: openai, model: text-embedding-3-small}
    threshold: 0.85
gate:
  fail_on: regression        # "regression" (vs baseline) or "absolute" (vs thresholds)
  baseline: .evalgate/baseline.json
```

## CLI surface (target)

- `evalgate init` — scaffold `evalgate.yaml` and an `evals/` dir
- `evalgate ingest <trace-file> [--out evals/]` — build/update Cases from traces
- `evalgate run [--suite ...] [--target ...]` — replay + score, persist a RunResult, print a rich summary
- `evalgate diff <baseline> <current>` — show per-case regressions
- `evalgate gate` — run current suite, diff against baseline, print regressions, **exit non-zero** if any regression. This is the CI entrypoint.
- `evalgate baseline set <run_id>` — promote a run to the baseline

## Determinism rules (v1)

- Default `temperature: 0` for replays; pass provider seed params where supported.
- v1 determinism target is single-turn LLM replay. Record tool calls as reference data but do not yet re-execute or mock tools.
- Never call live provider APIs in the test suite; mock at the Provider boundary.

## Coding conventions

- Type-hint everything; pydantic models for all structured data.
- Small, pure functions where possible; side effects (fs, network) isolated in `storage.py`, `providers/`, and `ingest/`.
- Every module ships with pytest tests using mocked providers. No live API calls in tests.
- `ruff check` and `ruff format` must pass before a task is considered done.
- Keep the OSS core dependency-light. Do not add a dependency without noting why in the PR/commit message.

## Definition of done for any task

1. Code compiles and imports cleanly (`uv run python -c "import evalgate"`).
2. New behavior has pytest coverage with mocked providers; `uv run pytest` is green.
3. `ruff check` and `ruff format --check` pass.
4. The relevant CLI command runs end to end on the `examples/` sample data.
