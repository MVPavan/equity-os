"""Fundamentals store layer — append-only, revision-aware fact store."""

from fundamentals.store.fact_store import (
    FactStore,
    StoredRevision,
    UnprovenancedFactError,
)

__all__ = [
    "FactStore",
    "StoredRevision",
    "UnprovenancedFactError",
]
