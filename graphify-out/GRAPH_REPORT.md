# Graph Report - evalgate  (2026-07-06)

## Corpus Check
- 43 files · ~18,617 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 560 nodes · 1387 edges · 30 communities (23 shown, 7 thin omitted)
- Extraction: 76% EXTRACTED · 24% INFERRED · 0% AMBIGUOUS · INFERRED: 339 edges (avg confidence: 0.72)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `74e82762`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- [[_COMMUNITY_Case|Case]]
- [[_COMMUNITY_Config|Config]]
- [[_COMMUNITY_Message|Message]]
- [[_COMMUNITY_models.py|models.py]]
- [[_COMMUNITY_config.py|config.py]]
- [[_COMMUNITY_otel.py|otel.py]]
- [[_COMMUNITY_test_ingest_langfuse.py|test_ingest_langfuse.py]]
- [[_COMMUNITY_langfuse.py|langfuse.py]]
- [[_COMMUNITY_EchoProvider|EchoProvider]]
- [[_COMMUNITY_ingest_otel|ingest_otel]]
- [[_COMMUNITY_test_storage.py|test_storage.py]]
- [[_COMMUNITY_ankora|ankora]]
- [[_COMMUNITY_json_schema.py|json_schema.py]]
- [[_COMMUNITY_IngestResult|IngestResult]]
- [[_COMMUNITY_llm_judge.py|llm_judge.py]]
- [[_COMMUNITY_.make_id|.make_id]]
- [[_COMMUNITY_test_smoke.py|test_smoke.py]]
- [[_COMMUNITY_examples|examples]]
- [[_COMMUNITY_run_demo.sh|run_demo.sh]]
- [[_COMMUNITY___init__.py|__init__.py]]
- [[_COMMUNITY___init__.py|__init__.py]]
- [[_COMMUNITY___init__.py|__init__.py]]
- [[_COMMUNITY_ankora|ankora]]
- [[_COMMUNITY_test_scorers.py|test_scorers.py]]
- [[_COMMUNITY_ProviderError|ProviderError]]
- [[_COMMUNITY_Case|Case]]
- [[_COMMUNITY__FakeEmbeddingProvider|_FakeEmbeddingProvider]]
- [[_COMMUNITY_Provider|Provider]]
- [[_COMMUNITY__FakeJudgeProvider|_FakeJudgeProvider]]
- [[_COMMUNITY_ExactScorer|ExactScorer]]

## God Nodes (most connected - your core abstractions)
1. `Message` - 38 edges
2. `Config` - 33 edges
3. `Case` - 29 edges
4. `OpenAIProvider` - 28 edges
5. `_FakeJudgeProvider` - 24 edges
6. `_FakeEmbeddingProvider` - 23 edges
7. `ConfigError` - 21 edges
8. `RunResult` - 21 edges
9. `load_config()` - 20 edges
10. `Completion` - 20 edges

## Surprising Connections (you probably didn't know these)
- `_FakeAPIError` --uses--> `ConfigError`  [INFERRED]
  tests/test_providers.py → src/ankora/config.py
- `_RecordingCreate` --uses--> `ConfigError`  [INFERRED]
  tests/test_providers.py → src/ankora/config.py
- `test_registry_unknown_provider_raises()` --indirect_call--> `ConfigError`  [INFERRED]
  tests/test_providers.py → src/ankora/config.py
- `_config()` --calls--> `ProviderConfig`  [INFERRED]
  tests/test_replay.py → src/ankora/config.py
- `_FakeEmbeddingProvider` --uses--> `ProviderConfig`  [INFERRED]
  tests/test_scorers.py → src/ankora/config.py

## Import Cycles
- None detected.

## Communities (30 total, 7 thin omitted)

### Community 0 - "Case"
Cohesion: 0.12
Nodes (23): EmbeddingSimilarityScorerConfig, ExactScorerConfig, JSONSchemaScorerConfig, LLMJudgeScorerConfig, ModelRef, Load and validate ankora.yaml into a pydantic Config.  See CLAUDE.md "Config fil, A provider/model reference used by scorers (judge, embedding model)., Rubric-based judge scorer (``type: llm_judge``). (+15 more)

### Community 1 - "Config"
Cohesion: 0.06
Nodes (42): baseline_set(), diff(), _fmt_score(), gate(), init(), _load_config_or_default(), _main(), _print_diff_report() (+34 more)

### Community 2 - "Message"
Cohesion: 0.07
Nodes (63): SimpleNamespace, ProviderConfig, How to reach a provider (keys read from env, never inlined).      ``base_url`` o, The provider/model replays run against by default., TargetConfig, Message, An OpenAI-style chat message., AnthropicProvider (+55 more)

### Community 3 - "models.py"
Cohesion: 0.06
Nodes (58): BaseModel, _aggregate_score(), CaseDiff, CaseStatus, _diff_case(), diff_runs(), DiffReport, Compare a current RunResult against a baseline to classify per-case changes.  Th (+50 more)

### Community 4 - "config.py"
Cohesion: 0.16
Nodes (27): ConfigError, _format_location(), _humanize_validation_error(), load_config(), Any, Path, Read the API key for ``provider`` from its configured env var.          The key, Render a pydantic error location as a readable dotted/indexed path. (+19 more)

### Community 5 - "otel.py"
Cohesion: 0.14
Nodes (32): _coerce_json(), _extract_created_at(), _extract_input_messages(), _extract_output(), _extract_params(), _indexed_completion(), _indexed_messages(), _is_gen_ai_span() (+24 more)

### Community 6 - "test_ingest_langfuse.py"
Cohesion: 0.15
Nodes (19): ingest(), Build or update regression Cases from an OTel GenAI or Langfuse trace file., ingest_traces(), Path, Ingest a trace file, returning ``(result, detected_format)``.      ``fmt`` is on, ingest_langfuse(), Path, Parse a Langfuse export into Cases (as an :class:`IngestResult`). (+11 more)

### Community 7 - "langfuse.py"
Cohesion: 0.21
Nodes (20): _coerce_json(), _content_text(), is_langfuse_shape(), _iter_records(), _messages_from_input(), _messages_from_list(), _obs_like(), _observation_to_case() (+12 more)

### Community 8 - "EchoProvider"
Cohesion: 0.14
Nodes (13): EchoProvider, Any, Echo provider: a deterministic, offline, keyless provider.  It performs no netwo, A provider that echoes back the last user message. No key, no network., Echo needs no client; present for a uniform provider interface., _config(), MonkeyPatch, Path (+5 more)

### Community 9 - "ingest_otel"
Cohesion: 0.22
Nodes (15): ingest_otel(), Path, Parse an OTel GenAI trace export into Cases.      Returns an :class:`~ankora.ing, test_langfuse_cases_equivalent_to_otel_path(), _ingest(), Path, Tests for the OTel GenAI trace ingester.  Exercises both the modern (input/outpu, test_case_ids_derived_from_source_and_stable() (+7 more)

### Community 10 - "test_storage.py"
Cohesion: 0.29
Nodes (12): GateConfig, How the gate decides pass/fail., _config_with_baseline(), Path, Tests for run/baseline storage round-trips., _run(), test_baseline_round_trip(), test_get_baseline_missing_raises() (+4 more)

### Community 11 - "ankora"
Cohesion: 0.17
Nodes (11): 60-second quickstart (no API keys required), ankora, Configuration (`ankora.yaml`), Development, License, OpenAI-compatible endpoints, Releasing, The core loop (+3 more)

### Community 12 - "json_schema.py"
Cohesion: 0.35
Nodes (10): _check_type(), _json_type(), Any, JSON-schema scorer: output must parse as JSON and validate against a schema.  Us, Return the first validation error message, or None if valid., _validate(), _validate_array(), _validate_number() (+2 more)

### Community 13 - "IngestResult"
Cohesion: 0.25
Nodes (7): detect_format(), IngestResult, Any, Trace readers that turn recorded interactions into Cases.  Two readers are suppo, Summary of an ingest run: the Cases produced plus record accounting.      ``tota, Return ``"otel"``, ``"langfuse"``, or ``"unknown"`` for parsed JSON., test_detect_format_on_both_samples()

### Community 14 - "llm_judge.py"
Cohesion: 0.29
Nodes (10): _clamp(), _find_json_object(), _parse_judgement(), Any, LLM-judge scorer: a model grades the output against a rubric., Find and parse the first balanced ``{...}`` object in ``text``, if any., Extract a 0..1 score and a short justification from possibly-messy text., _summarize() (+2 more)

### Community 15 - ".make_id"
Cohesion: 0.24
Nodes (7): Derive a stable, deterministic Case id from a source trace id.          The same, Parse a Case from a YAML string produced by :meth:`to_yaml`., Tests for the canonical data models: round-trips and id stability.  No provider, test_case_id_differs_for_different_input(), test_case_id_has_expected_shape(), test_case_id_is_stable_for_same_input(), test_case_yaml_round_trip()

### Community 16 - "test_smoke.py"
Cohesion: 0.15
Nodes (32): Config, The fully-parsed ankora.yaml., A collection of Cases loaded from files in the user's repo.      ``source_paths`, Suite, _apply_target_override(), Any, Replay a Suite against a target provider and score the outputs into a RunResult., Replay every Case against the target provider, score, persist, and return. (+24 more)

### Community 17 - "examples"
Cohesion: 0.50
Nodes (3): examples, Keyless offline demo, Using ankora in your own CI

### Community 23 - "test_scorers.py"
Cohesion: 0.21
Nodes (18): JSONSchemaScorer, Score 1.0 when ``output`` is JSON valid against ``schema``, else 0.0., _case(), _fake_openai_client(), Tests for the scorer layer.  Deterministic scorers (exact/regex/json_schema) use, test_build_scorers_wires_all_types_with_injected_client(), test_exact_mismatch_fails(), test_exact_normalized_match_passes() (+10 more)

### Community 24 - "ProviderError"
Cohesion: 0.18
Nodes (15): Exception, _classify(), ProviderError, ProviderRateLimitError, Clean provider-error mapping and bounded retry for API calls.  Provider SDK exce, A provider API call failed. Carries a one-line, user-facing message., Raised when a provider keeps rate-limiting after the retry budget., Run ``call`` with a bounded retry on 429; map other API errors cleanly.      On (+7 more)

### Community 25 - "Case"
Cohesion: 0.18
Nodes (10): Case, One recorded interaction turned into a regression test., Serialize this Case to a YAML string that round-trips via :meth:`from_yaml`., The outcome of a single scorer against a single output., ScorerResult, Grade ``output`` for ``case`` and return a ScorerResult., LLMJudgeScorer, Grade an output by asking an injected judge provider to apply a rubric. (+2 more)

### Community 26 - "_FakeEmbeddingProvider"
Cohesion: 0.24
Nodes (7): _cosine(), EmbeddingSimilarityScorer, Embedding-similarity scorer: cosine similarity vs the reference output., Cosine similarity between ``output`` and ``reference.output`` embeddings.      T, _FakeEmbeddingProvider, test_embedding_identical_vectors_scores_one(), test_embedding_similarity_math_and_threshold()

### Community 27 - "Provider"
Cohesion: 0.29
Nodes (4): Protocol, Provider, Minimal surface every provider adapter must implement., Return an embedding vector per input text.          Providers without a first-pa

## Knowledge Gaps
- **12 isolated node(s):** `ankora`, `60-second quickstart (no API keys required)`, `Configuration (`ankora.yaml`)`, `OpenAI-compatible endpoints`, `Wire it into CI` (+7 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **7 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Message` connect `Message` to `models.py`, `otel.py`, `langfuse.py`, `EchoProvider`, `test_smoke.py`, `Case`, `Provider`?**
  _High betweenness centrality (0.124) - this node is a cross-community bridge._
- **Why does `Case` connect `Case` to `Case`, `models.py`, `otel.py`, `langfuse.py`, `EchoProvider`, `IngestResult`, `.make_id`, `test_smoke.py`, `test_scorers.py`, `_FakeEmbeddingProvider`, `_FakeJudgeProvider`, `ExactScorer`?**
  _High betweenness centrality (0.077) - this node is a cross-community bridge._
- **Why does `Config` connect `test_smoke.py` to `Case`, `Config`, `Message`, `models.py`, `config.py`, `EchoProvider`, `test_storage.py`, `_FakeEmbeddingProvider`, `_FakeJudgeProvider`?**
  _High betweenness centrality (0.071) - this node is a cross-community bridge._
- **Are the 24 inferred relationships involving `Message` (e.g. with `AnthropicProvider` and `Completion`) actually correct?**
  _`Message` has 24 INFERRED edges - model-reasoned connections that need verification._
- **Are the 16 inferred relationships involving `Config` (e.g. with `CaseDiff` and `CaseStatus`) actually correct?**
  _`Config` has 16 INFERRED edges - model-reasoned connections that need verification._
- **Are the 13 inferred relationships involving `Case` (e.g. with `IngestResult` and `Scorer`) actually correct?**
  _`Case` has 13 INFERRED edges - model-reasoned connections that need verification._
- **Are the 20 inferred relationships involving `OpenAIProvider` (e.g. with `Message` and `Completion`) actually correct?**
  _`OpenAIProvider` has 20 INFERRED edges - model-reasoned connections that need verification._