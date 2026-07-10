# ankora

<div align="center">
  <img src="logo.png" alt="ankora Logo" width="200" height="200">

  <p>
    <strong>Local-first, CI-native regression testing for LLM and agent applications.</strong>
  </p>

  <p>
    <a href="https://pypi.org/project/ankora/"><img src="https://img.shields.io/pypi/v/ankora" alt="PyPI Version"/></a>
    <a href="https://pypi.org/project/ankora/"><img src="https://img.shields.io/pypi/pyversions/ankora" alt="Python Versions"/></a>
    <a href="https://github.com/yajan011/ankora/stargazers"><img src="https://img.shields.io/github/stars/yajan011/ankora" alt="Stars Badge"/></a>
    <a href="https://github.com/yajan011/ankora/network/members"><img src="https://img.shields.io/github/forks/yajan011/ankora" alt="Forks Badge"/></a>
    <a href="https://github.com/yajan011/ankora/pulls"><img src="https://img.shields.io/github/issues-pr/yajan011/ankora" alt="Pull Requests Badge"/></a>
    <a href="https://github.com/yajan011/ankora/issues"><img src="https://img.shields.io/github/issues/yajan011/ankora" alt="Issues Badge"/></a>
    <a href="https://github.com/yajan011/ankora/graphs/contributors"><img alt="GitHub contributors" src="https://img.shields.io/github/contributors/yajan011/ankora?color=2b9348"></a>
    <a href="https://github.com/yajan011/ankora/blob/main/LICENSE"><img src="https://img.shields.io/github/license/yajan011/ankora?color=2b9348" alt="License Badge"/></a>
  </p>
</div>

## 🌟 Overview

ankora is a local-first, CI-native regression testing tool for LLM and agent applications. It aims to solve the problem that many teams have observability but no automated tests for output quality, by converting the traces you already capture into a deterministic regression suite that replays them, scores the outputs, and exits with a non-zero status when quality drops. That single property lets a continuous integration job block a merge before a regression reaches users.

ankora runs entirely on your own machine or CI runner, uses your own provider API keys, and sends no telemetry.

## ✨ Features

- 🔁 **Traces to tests** - Ingest OpenTelemetry GenAI and Langfuse trace exports into replayable regression cases, with automatic format detection.
- 🚦 **CI gate** - `ankora gate` compares a run against a baseline and exits non-zero on regression, so a quality drop blocks the merge.
- 🎯 **Multiple scorers** - Deterministic scorers (`exact`, `regex`, `json_schema`) plus `embedding_similarity` and `llm_judge`.
- 🔌 **OpenAI-compatible endpoints** - Point the OpenAI provider at Gemini, OpenRouter, Groq, Together, or a local Ollama or LM Studio server via `base_url`.
- 🔑 **Bring your own keys** - Provider keys are read from environment variables and are never stored or proxied.
- 🖥️ **Local-first and offline** - No account, no login, no hosted service, and no telemetry.
- 🧪 **Keyless demo** - A built-in `echo` provider runs the full loop with no API keys, for demos and CI.

## 🎯 Quick Start

### Prerequisites

- Python 3.11 or higher
- [uv](https://docs.astral.sh/uv/) (recommended) or pip
- Git (only needed to work from source)

### Installation

1. **Install ankora**
   ```bash
   uv tool install ankora
   # or
   pip install ankora
   ```

2. **Scaffold a project**
   ```bash
   ankora init
   ```
   This writes an `ankora.yaml` configuration file and an `evals/` directory.

3. **Configure a provider key**
   ```bash
   export OPENAI_API_KEY=...   # the env var named in ankora.yaml
   ```

4. **Build cases, replay, and gate**
   ```bash
   ankora ingest traces.json --out evals/   # convert a trace export into cases
   ankora run                               # replay and score the suite
   ankora baseline set <run_id>             # promote a known-good run
   ankora gate                              # exits non-zero on regression
   ```

### Try it without any API keys

If you clone the repository, you can run the fully offline demonstration. It uses the built-in `echo` provider and deterministic scorers, so it makes no network calls and needs no keys:

```bash
git clone https://github.com/yajan011/ankora.git
cd ankora
uv sync
bash examples/run_demo.sh
```

The demo runs the complete loop and shows the gate passing (exit code 0) on a clean run and failing (exit code 1) after a case is deliberately broken.

## ⚙️ Configuration

Configuration lives in `ankora.yaml`:

```yaml
version: 1
suites: ["evals/**/*.yaml"]
target:
  provider: openai          # openai, anthropic, or echo (keyless, for demos and CI)
  model: gpt-4o-mini
providers:
  openai: {api_key_env: OPENAI_API_KEY}   # keys are read from the environment
scorers:
  - type: exact
    threshold: 1.0
  - type: json_schema
    schema: {type: object, required: [city, country]}
  - type: llm_judge
    judge: {provider: openai, model: gpt-4o}
    rubric: "Score 1 if factually consistent with the reference, else 0."
    threshold: 0.7
gate:
  fail_on: regression       # "regression" (compared to baseline) or "absolute" (against thresholds)
  baseline: .ankora/baseline.json
```

To use an OpenAI-compatible endpoint, add a `base_url` to the provider (for example Google Gemini's OpenAI-compatible API):

```yaml
providers:
  openai:
    api_key_env: GEMINI_API_KEY
    base_url: https://generativelanguage.googleapis.com/v1beta/openai/
```

Note: many OpenAI-compatible endpoints serve only chat completions and not embeddings. On those, use the `llm_judge` and deterministic scorers rather than `embedding_similarity`.

## 📚 Documentation

- [Examples and offline demo](examples/README.md)
- [Releasing guide](RELEASING.md)
- [License](LICENSE)

## 🏗️ Project Structure

```
ankora/
├── src/ankora/
│   ├── cli.py            # Typer command-line interface
│   ├── config.py         # ankora.yaml parsing and validation
│   ├── models.py         # Case, Run, and result data models
│   ├── replay.py         # replay a suite against a target provider
│   ├── diff.py           # compare a run against a baseline
│   ├── storage.py        # read and write runs and baselines
│   ├── suites.py         # load cases from evals/
│   ├── ingest/           # OpenTelemetry and Langfuse trace readers
│   ├── providers/        # openai, anthropic, echo, registry, errors
│   └── scorers/          # exact, regex, json_schema, embedding, llm_judge
├── tests/
├── examples/             # offline demo, sample traces, demo config
├── .github/
│   ├── workflows/        # CI (ankora.yml) and PyPI publish (publish.yml)
│   └── actions/ankora-gate/
├── pyproject.toml
├── README.md
├── LICENSE
└── NOTICE
```

## 🤝 Contributing

Contributions are welcome. Please open an issue to report a bug or propose a feature, or submit a pull request.

For local development:

```bash
uv sync
uv run pytest          # all provider calls are mocked; no live API calls
uv run ruff check
uv run ruff format --check
```

### Ways to Contribute

- 🐛 Report bugs
- 💡 Suggest new features
- 📝 Improve documentation
- 🔧 Submit pull requests

## 📊 Roadmap

- [x] Ingest OpenTelemetry GenAI and Langfuse traces
- [x] Deterministic, embedding-similarity, and LLM-judge scorers
- [x] CI gate with baseline comparison
- [x] OpenAI-compatible endpoints via `base_url`
- [ ] Scheduled drift watch (run on a cron schedule against a live endpoint)
- [ ] Multi-step agent-trajectory record and replay with tool mocking

See the [open issues](https://github.com/yajan011/ankora/issues) for a full list of proposed features and known issues.

## 🏆 Contributors

Thanks goes to these wonderful people ([emoji key](https://allcontributors.org/docs/en/emoji-key)):

<!-- ALL-CONTRIBUTORS-LIST:START -->
<!-- ALL-CONTRIBUTORS-LIST:END -->

## 📄 License

This project is licensed under the Apache License 2.0. See the [LICENSE](LICENSE) and [NOTICE](NOTICE) files for details.

