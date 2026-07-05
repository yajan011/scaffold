"""Trace readers that turn recorded interactions into Cases.

Two readers are supported — OpenTelemetry GenAI (``otel``) and Langfuse
(``langfuse``) — behind a shared :class:`IngestResult` and a format
auto-detector.

Auto-detection (``ingest_traces(path, "auto")``) is structural and, per the
project's "OTel first" stance, checks OTel before Langfuse:

1. If the JSON looks like OTel (``resourceSpans``/``scopeSpans``/``spans``, a
   bare span with ``attributes``/``spanId``, or a list of such spans) -> OTel.
2. Else if it looks like Langfuse (a trace with ``observations``, a
   ``{"data": [...]}`` list, or observation objects carrying ``type`` /
   ``modelParameters`` / ``model``+``input``/``output``) -> Langfuse.
3. Else, as a fallback, try the OTel reader; if it yields any Cases use it,
   otherwise fall back to the Langfuse reader.

The two shapes are cleanly distinguishable because OTel spans carry
``attributes``/``spanId`` while Langfuse observations never do.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from ankora.models import Case


class IngestResult(BaseModel):
    """Summary of an ingest run: the Cases produced plus record accounting.

    ``total`` counts the records seen (OTel spans or Langfuse observations);
    ``skipped`` counts those that produced no usable Case.
    """

    cases: list[Case] = Field(default_factory=list)
    total: int = 0
    skipped: int = 0


def detect_format(data: Any) -> str:
    """Return ``"otel"``, ``"langfuse"``, or ``"unknown"`` for parsed JSON."""
    from ankora.ingest.langfuse import is_langfuse_shape
    from ankora.ingest.otel import is_otel_shape

    if is_otel_shape(data):
        return "otel"
    if is_langfuse_shape(data):
        return "langfuse"
    return "unknown"


def ingest_traces(trace_file: str | Path, fmt: str = "auto") -> tuple[IngestResult, str]:
    """Ingest a trace file, returning ``(result, detected_format)``.

    ``fmt`` is one of ``"auto"``, ``"otel"``, ``"langfuse"``. Raises
    ``FileNotFoundError`` / ``json.JSONDecodeError`` for the caller to render.
    """
    from ankora.ingest.langfuse import ingest_langfuse
    from ankora.ingest.otel import ingest_otel

    path = Path(trace_file)
    if fmt == "otel":
        return ingest_otel(path), "otel"
    if fmt == "langfuse":
        return ingest_langfuse(path), "langfuse"

    data = json.loads(path.read_text(encoding="utf-8"))
    detected = detect_format(data)
    if detected == "otel":
        return ingest_otel(path), "otel"
    if detected == "langfuse":
        return ingest_langfuse(path), "langfuse"

    # Ambiguous: try OTel gen_ai spans first, then Langfuse.
    otel_result = ingest_otel(path)
    if otel_result.cases:
        return otel_result, "otel"
    return ingest_langfuse(path), "langfuse"
