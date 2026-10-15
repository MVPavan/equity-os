"""Deterministic narrative export of one report version (ledger spec §3 narrative; P2).

The bytes are the stored sections with their placeholders filled from the stored claims. Status
and decisions never enter, so a status change leaves the export unchanged, and an imported
version's export hashes to its content hash.
"""

from __future__ import annotations

from typing import Any

from psycopg import Cursor

from fundamentals.ledger import store
from fundamentals.ledger.display import narrative


def export_version(cursor: Cursor[Any], version_id: int) -> bytes:
    """The version's narrative bytes, as its content hash was computed."""
    draft = store.read_version(cursor, version_id)
    return narrative(draft.sections, draft.claims)
