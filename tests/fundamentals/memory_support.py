"""Memory test support: a ledger with one approved, trusted-valid version, a runtime stager and
memory decisions over the real role pools (plan D4, M1, M2, M7).

The approved version is drafted with one claim, submitted, and approved by the owner binding
the owner's own ``AS_KNOWN`` all-``MATCH`` validation, so it is the trusted-valid support the
support predicate (D4.2) accepts.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from typing import Any

import pytest
from ledger_support import RULING, Ledger

from fundamentals.contracts.guidance_claim import EpistemicClass
from fundamentals.contracts.ledger import DecisionKind, DecisionRecord, SubjectKind
from fundamentals.contracts.memory import (
    MemoryItemDraft,
    MemoryKind,
    SupportDraft,
    SupportTarget,
)
from fundamentals.ledger import store
from fundamentals.memory.pg_store import PgMemoryStore
from fundamentals.pg.settings import PgRole

STATEMENT = "Cables and wires grew their share of consolidated revenue"


class Memory:
    """One seeded ledger's memory: an approved version, a stager and decisions by role."""

    def __init__(self, ledger: Ledger) -> None:
        self.ledger = ledger
        self.version_id = ledger.draft(ledger.report())
        ledger.submit(self.version_id)
        ledger.approve(self.version_id)
        self.claim_id = self.one(
            "SELECT id FROM eqos.numeric_claims WHERE version_id = %s", self.version_id
        )
        self.store = PgMemoryStore(ledger.pools[PgRole.RUNTIME])

    def draft(self, **update: Any) -> MemoryItemDraft:
        """A stock's company-understanding item citing the approved version, with any field
        replaced."""
        return MemoryItemDraft(
            entity_id=self.ledger.entity_id,
            kind=MemoryKind.COMPANY_UNDERSTANDING,
            statement=STATEMENT,
            epistemic_class=EpistemicClass.OBSERVED,
            valid_from=date(2026, 4, 1),
            valid_to=None,
            supersedes_item_id=None,
            supports=(SupportDraft(target=SupportTarget.VERSION, target_id=self.version_id),),
        ).model_copy(update=update)

    def stage(self, **update: Any) -> int:
        """Stage :meth:`draft` as the runtime; returns the item id."""
        return self.store.stage(self.draft(**update))

    def decide(
        self, role: PgRole, item_id: int, kind: DecisionKind, **fields: Any
    ) -> DecisionRecord:
        """A memory decision by ``role`` naming the item's head and digest, owner decisions with
        a ruling, unless ``fields`` say otherwise."""
        with self.ledger._cursor(role) as cursor:
            head = store.chain_head(cursor, SubjectKind.MEMORY_ITEM, item_id)
            defaults: dict[str, Any] = {
                "predecessor_id": None if head is None else head.id,
                "sealed_digest": store.subject_digest(cursor, SubjectKind.MEMORY_ITEM, item_id),
                "ruling": RULING if role is PgRole.OWNER else None,
            }
            return store.insert_decision(
                cursor,
                subject_kind=SubjectKind.MEMORY_ITEM,
                subject_id=item_id,
                kind=kind,
                **(defaults | fields),
            )

    def rows(self, query: str, *params: object) -> list[tuple[Any, ...]]:
        """Every row of a read as the runtime."""
        with self.ledger._cursor(PgRole.RUNTIME) as cursor:
            return cursor.execute(query, params).fetchall()  # type: ignore[arg-type]

    def one(self, query: str, *params: object) -> Any:
        """The single value of a one-row, one-column read."""
        ((value,),) = self.rows(query, *params)
        return value


@pytest.fixture
def memory(ledger: Ledger) -> Iterator[Memory]:
    """The memory of a seeded ledger with one approved version."""
    yield Memory(ledger)
