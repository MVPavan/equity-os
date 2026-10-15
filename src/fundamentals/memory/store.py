"""The engine-neutral ``MemoryStore`` interface (ledger spec §2, D-01; plan D4, M7).

The spec's promote and retire are ``decide`` kinds, correct is ``stage`` with
``supersedes_item_id``, and export is D5.1.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from fundamentals.contracts.ledger import DecisionKind, DecisionRecord
from fundamentals.contracts.memory import (
    MemoryItemDraft,
    MemoryKind,
    MemoryStatus,
    RetrievedItem,
)
from fundamentals.ledger.panel import Reviewer


class MemoryStore(Protocol):
    """Stage, decide, retrieve and trace memory items."""

    def stage(self, draft: MemoryItemDraft) -> int:
        """Stage a candidate with its supports; returns its id."""
        ...

    def decide(
        self,
        item_id: int,
        kind: DecisionKind,
        *,
        reviewer: Reviewer | None = None,
        ruling: str | None = None,
    ) -> DecisionRecord:
        """Promote, reject or retire an item: the panel by a reviewer, the owner by a ruling."""
        ...

    def retrieve(
        self,
        query: str,
        *,
        stock: int,
        kinds: frozenset[MemoryKind] | None,
        statuses: frozenset[MemoryStatus],
        cutoff: datetime | None,
    ) -> tuple[RetrievedItem, ...]:
        """The stock's items matching ``query`` as known at ``cutoff``, with supports and
        flags."""
        ...

    def provenance(self, item_id: int) -> tuple[RetrievedItem, ...]:
        """The item and its supersession lineage, each with its supports."""
        ...
