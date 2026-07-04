# evalgate

Local-first, CI-native regression testing for LLM and agent applications.

Teams have observability (traces) but no tests, so prompt tweaks, model version
bumps, and silent provider changes ship undetected until users complain.
`evalgate` closes that gap: it turns the traces you already capture into
replayable regression suites, replays them deterministically across providers,
scores the outputs, and **fails the CI build when quality silently regresses**.

> Status: early scaffolding. The CLI surface is wired but command logic is not
> implemented yet. See `CLAUDE.md` for the full design and v1 scope.

## Principles

- **Local-first & offline** — runs on your laptop or CI runner, no account, no
  telemetry, no required hosted service.
- **Bring-your-own-keys** — replays use your provider keys from env vars.
- **Neutral & framework-agnostic** — reads open formats (OpenTelemetry GenAI
  semantic conventions first); suites are plain files in your repo.
- **Legible over clever** — deterministic behavior beats magic.
- **CI is the primary surface** — `evalgate gate` exits non-zero on regression.

## Install (dev)

```bash
uv sync
uv run evalgate --help
```

## CLI

- `evalgate init` — scaffold `evalgate.yaml` and an `evals/` dir
- `evalgate ingest <trace-file> [--out evals/]` — build Cases from traces
- `evalgate run [--suite ...] [--target ...]` — replay + score
- `evalgate diff <baseline> <current>` — show per-case regressions
- `evalgate gate` — the CI entrypoint; exits non-zero on regression
- `evalgate baseline set <run_id>` — promote a run to the baseline

## License

Apache-2.0
