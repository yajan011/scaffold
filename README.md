# ankora

**Turn the traces you already capture into regression tests that fail your CI when quality silently drops.**

Teams have observability but no tests. ~89% of teams run some form of LLM
observability, but only ~52% run evals — and quality is the No. 1 blocker to
shipping LLM features to production. So prompt tweaks, model-version bumps, and
silent provider changes ship undetected until users complain.

`ankora` closes that gap from the supply side: it replays the traces you
already have as a deterministic regression suite, scores the outputs, and
**exits non-zero when quality regresses** — so a GitHub Action can block the
merge. Local-first, bring-your-own-keys, no account, no telemetry.

---

## 60-second quickstart (no API keys required)

Install from source with [uv](https://docs.astral.sh/uv/):

```bash
git clone https://github.com/ankora/ankora
cd ankora
uv sync
```

> Coming once published to PyPI: `uv tool install ankora` (or `pip install ankora`).

Now run the fully offline demo — it uses the built-in deterministic `echo`
provider and deterministic scorers, so **no network and no keys**:

```bash
bash examples/run_demo.sh
```

You'll watch the full loop **run → baseline set → gate** and see the CI contract
both ways: a **green gate (exit 0)** when the run matches the baseline, then a
**red gate (exit 1)** after a Case is deliberately broken:

```
==> 3. Gate against the baseline (clean — expect exit 0)
No regressions — gate passed.
    clean gate exit code: 0
...
==> 5. Gate again (regression — expect non-zero exit)
1 regression(s) detected — failing the gate.
    broken gate exit code: 1
```

That's the whole idea: **a regression makes the command exit non-zero.**

---

## The core loop

In your own repo, the loop is four commands. Point `target.provider` at
`openai`/`anthropic` in `ankora.yaml` for real replays (keys come from your
env, below), or keep the keyless `echo` provider to try it out.

```bash
# 0. Scaffold ankora.yaml + an evals/ directory
ankora init

# 1. Turn an OpenTelemetry GenAI or Langfuse trace export into regression Cases
#    (format is auto-detected; force it with --format otel|langfuse)
ankora ingest traces.json --out evals/

# 2. Replay + score the suite; saves a run under .ankora/runs/
ankora run

# 3. Promote a good run to the baseline
ankora baseline set <run_id>

# 4. The CI entrypoint: replay, diff vs baseline, exit non-zero on regression
ankora gate
```

Inspect any two runs read-only (never fails the build):

```bash
ankora diff <baseline_run_id> <current_run_id>
```

Every command has `--help`; `--config` points at a non-default `ankora.yaml`,
`--target provider:model` overrides the target, and `--concurrency` bounds
parallel replays.

### Configuration (`ankora.yaml`)

```yaml
version: 1
suites: ["evals/**/*.yaml"]
target:
  provider: openai          # openai | anthropic | echo (keyless, for demos/CI)
  model: gpt-4o-mini
providers:
  openai: {api_key_env: OPENAI_API_KEY}      # keys read from env, never inlined
scorers:
  - type: exact             # deterministic, no key needed
    threshold: 1.0
  - type: regex
    pattern: '"country"'
  - type: json_schema
    schema: {type: object, required: [city, country]}
  - type: llm_judge         # needs a provider key
    judge: {provider: openai, model: gpt-4o}
    rubric: "Score 1 if factually consistent with the reference, else 0."
    threshold: 0.7
  - type: embedding_similarity
    model: {provider: openai, model: text-embedding-3-small}
    threshold: 0.85
gate:
  fail_on: regression       # "regression" (vs baseline) or "absolute" (vs thresholds)
  baseline: .ankora/baseline.json
```

---

## OpenAI-compatible endpoints

The `openai` provider can talk to any OpenAI-compatible endpoint — Google Gemini's
OpenAI-compat API, OpenRouter, Groq, Together, or a local Ollama / LM Studio
server — by setting `base_url` on the provider. Leave it unset to hit
`api.openai.com` as usual. Keys are still read from the env var you name; ankora
never sees or stores them.

**Gemini (free tier)** — get a key from [Google AI Studio](https://aistudio.google.com/apikey):

```yaml
target:
  provider: openai
  model: gemini-2.0-flash
providers:
  openai:
    api_key_env: GEMINI_API_KEY
    base_url: https://generativelanguage.googleapis.com/v1beta/openai/
scorers:
  - type: llm_judge                       # judge over the same endpoint
    judge: {provider: openai, model: gemini-2.0-flash}
    rubric: "Score 1 if factually consistent with the reference, else 0."
    threshold: 0.7
  - type: exact                           # deterministic, no model needed
    threshold: 1.0
```

```bash
export GEMINI_API_KEY=...   # from Google AI Studio
ankora run
```

**OpenRouter** — one key, hundreds of models ([openrouter.ai](https://openrouter.ai/)):

```yaml
target:
  provider: openai
  model: openai/gpt-4o-mini                # any OpenRouter model slug
providers:
  openai:
    api_key_env: OPENROUTER_API_KEY
    base_url: https://openrouter.ai/api/v1
```

> **Embeddings caveat:** many OpenAI-compatible endpoints expose only chat
> completions, not the `/embeddings` route. On those, prefer the `llm_judge` and
> deterministic (`exact`, `regex`, `json_schema`) scorers; use
> `embedding_similarity` only against a provider whose endpoint actually serves
> embeddings.

---

## Wire it into CI

Add a workflow to your repo that runs `ankora gate` on pull requests. Provider
keys come from repo secrets — ankora reads them from the environment and
**never sees or stores your tokens**.

```yaml
# .github/workflows/ankora.yml
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

A composite action that wraps those steps ships at
[`.github/actions/ankora-gate`](.github/actions/ankora-gate/action.yml).
Commit `.ankora/baseline.json` (or promote a run with `ankora baseline set`)
so CI has something to compare against.

---

## Why it's different

- **Local-first & offline.** Runs on your laptop or a CI runner. No account, no
  login, no hosted service — and **no telemetry, ever.**
- **Bring-your-own-keys.** Replays use *your* provider keys from env vars. We
  never carry token cost and never see your tokens.
- **Neutral & framework-agnostic.** Reads open formats (OpenTelemetry GenAI
  semantic conventions first). Your suite is plain YAML checked into your repo —
  no lock-in to a framework, provider, or storage backend.
- **It fails your CI.** The whole point: `ankora gate` exits non-zero on
  regression, so a quality drop blocks the merge instead of reaching users.

---

## v1 scope — and what's next

**Shipped in v1:**

- `init` — scaffold `ankora.yaml` + `evals/`
- `ingest` — OpenTelemetry GenAI **and Langfuse** traces → regression Cases (format auto-detected; override with `--format {otel,langfuse,auto}`)
- `run` — deterministic replay + scoring, persisted runs
- `diff` — per-case comparison of two runs
- `gate` — replay + baseline diff + non-zero exit on regression (the CI entrypoint)
- `baseline set` — promote a run to the baseline
- Providers: `openai`, `anthropic`, and a keyless `echo` provider for demos/CI
- Scorers: `exact`, `regex`, `json_schema` (deterministic), `embedding_similarity`, `llm_judge`

**Coming next (not built yet — no false promises):**

- A scheduled drift watch (`run` on a cron against a live endpoint)
- Multi-step agent-trajectory record/replay with tool mocking

v1 targets single-turn LLM replay; recorded tool calls are kept as reference
data but not yet re-executed.

---

## Development

```bash
uv sync
uv run pytest          # all provider calls are mocked; no live API calls
uv run ruff check
uv run ruff format --check
```

## Releasing

Maintainers: see [RELEASING.md](RELEASING.md). Publishing to PyPI happens
automatically when you cut a GitHub Release, via
[Trusted Publishing](https://docs.pypi.org/trusted-publishers/) (OIDC — no API
tokens stored in the repo).

## License

Apache-2.0 — see [LICENSE](LICENSE) and [NOTICE](NOTICE).
