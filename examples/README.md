# examples

## Keyless offline demo

`run_demo.sh` runs the full `ankora` loop — **run → baseline set → gate** —
with **no network and no API keys**. It uses the built-in deterministic `echo`
provider (returns the last user message verbatim) and only the deterministic
scorers (`exact`, `regex`, `json_schema`).

```bash
bash examples/run_demo.sh
```

It proves the CI contract both ways:

- gate exits **0** when the current run matches the baseline, and
- gate exits **1** after a Case is deliberately broken (a regression).

Files:

- `demo/ankora.yaml` — `target.provider: echo` + deterministic scorers only.
- `demo/evals/*.yaml` — three tiny Cases (each echoes a JSON payload).
- `sample_otel.json` — a small OpenTelemetry GenAI trace for trying `ankora ingest`.
- `sample_langfuse.json` — the same interactions as a Langfuse export; ingesting
  either file yields equivalent Cases (`ankora ingest` auto-detects the format).

## Using ankora in your own CI

For a **real** (non-deterministic) suite, point `target.provider` at
`openai`/`anthropic` and provide keys from repo secrets. Minimal PR workflow:

```yaml
# .github/workflows/ankora.yml in YOUR repo
name: ankora
on: pull_request
jobs:
  gate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
      - run: uv tool install ankora      # once published to PyPI
      - run: ankora gate
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
```

A composite action wrapping those steps lives at
`.github/actions/ankora-gate`:

```yaml
      - uses: actions/checkout@v4
      - uses: your-org/ankora/.github/actions/ankora-gate@v1
        with:
          config: ankora.yaml
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
```

`ankora gate` exits non-zero when quality regresses against
`.ankora/baseline.json`, which blocks the merge. Commit the baseline (or
promote a run with `ankora baseline set <run_id>`) so CI has something to
compare against.
