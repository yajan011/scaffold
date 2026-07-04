"""Read a Langfuse JSON export into Cases (the second-priority reader).

Logic is stubbed for v1 scaffolding.
"""

from __future__ import annotations

from pathlib import Path

from evalgate.models import Case


def ingest_langfuse(export_file: str | Path) -> list[Case]:
    """Parse a Langfuse export into a list of Cases.

    Not yet implemented — placeholder for v1 scaffolding.
    """
    raise NotImplementedError("ingest.langfuse.ingest_langfuse is not implemented yet")
