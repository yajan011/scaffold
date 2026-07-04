"""Read OpenTelemetry GenAI-semantic-convention traces into Cases.

This is the canonical input format (``gen_ai.*`` attributes). Logic is stubbed
for v1 scaffolding.
"""

from __future__ import annotations

from pathlib import Path

from evalgate.models import Case


def ingest_otel(trace_file: str | Path) -> list[Case]:
    """Parse an OTel GenAI trace export into a list of Cases.

    Not yet implemented — placeholder for v1 scaffolding.
    """
    raise NotImplementedError("ingest.otel.ingest_otel is not implemented yet")
