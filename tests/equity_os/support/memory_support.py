"""Memory test support: a ledger with one approved, trusted-valid version, a runtime stager and
memory decisions over the real role pools (plan D4, M1, M2, M7).

The approved version is drafted with one claim, submitted, and approved by the owner binding
the owner's own ``AS_KNOWN`` all-``MATCH`` validation, so it is the trusted-valid support the
support predicate (D4.2) accepts. Status derives from SQL's inputs through ``derive_status``.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import date
from typing import Any

import pytest
from ledger_support import RULING, SECTION, Ledger, claim, validation
from psycopg import Cursor

from equity_os.contracts.measurement.guidance_claim import EpistemicClass
from equity_os.contracts.publication.ledger import (
    ClaimState,
    DecisionKind,
    DecisionRecord,
    SubjectKind,
    VersionState,
)
from equity_os.contracts.storage.memory import (
    MemoryItemDraft,
    MemoryKind,
    MemoryStatus,
    SupportDraft,
    SupportTarget,
)
from equity_os.contracts.verification.review_queue import DispositionKind
from equity_os.publication.drafting.display import content_hash
from equity_os.storage.database.settings import PgRole
from equity_os.storage.memory.pg_store import PgMemoryStore
from equity_os.storage.memory.status import derive_status
from equity_os.storage.records import store
from equity_os.verification.review_queue.queue import insert_disposition

STATEMENT = "Cables and wires grew their share of consolidated revenue"
# The three derive_status inputs, as of now.
_STATUS = """SELECT (SELECT kind FROM eqos.decisions WHERE subject_kind = 'MEMORY_ITEM'
        AND subject_id = i.id ORDER BY sequence DESC LIMIT 1),
    eqos.memory_promoted_successor(i.id), eqos.memory_item_supported(i.id, NULL)
FROM eqos.memory_items i WHERE i.id = %s"""
# The writes that can falsify a version support (plan D4, M4); "redispose" a disposition's.
VERSION_WRITERS = ("withdraw", "supersede", "non_match", "version_level")
SNAPSHOT = (
    "SELECT to_jsonb(i) FROM eqos.memory_items i",
    "SELECT to_jsonb(s) FROM eqos.memory_supports s",
    "SELECT to_jsonb(d) FROM eqos.decisions d WHERE d.subject_kind = 'MEMORY_ITEM'",
)


class Memory:
    """One seeded ledger's memory: an approved version (its narrative hashing to its content
    hash), a stager and decisions by role."""

    def __init__(self, ledger: Ledger) -> None:
        self.ledger = ledger
        hashed = content_hash((SECTION,), (claim(ledger.trace_id),))
        self.version_id = ledger.draft(ledger.report(), content_hash=hashed)
        ledger.submit(self.version_id)
        ledger.approve(self.version_id)
        self.claim_id = self.one(
            "SELECT id FROM eqos.numeric_claims WHERE version_id = %s", self.version_id
        )
        self.store = PgMemoryStore(ledger.pools[PgRole.RUNTIME])

    def approved(
        self, report_id: int | None = None, predecessor_id: int | None = None, **update: Any
    ) -> int:
        """A runtime draft (on a new report, unless a successor; its stock covered first)
        submitted and approved by the owner binding its own all-``MATCH`` check."""
        if report_id is None:
            report_id = self.ledger.report()
        self.ledger.cover(self.one("SELECT entity_id FROM eqos.reports WHERE id = %s", report_id))
        version_id = self.ledger.draft(report_id, predecessor_id, **update)
        self.ledger.submit(version_id)
        self.ledger.approve(version_id)
        return version_id

    def successor(self, version_id: int) -> int:
        """A submitted successor draft of ``version_id``, ready to approve."""
        report_id = self.one("SELECT report_id FROM eqos.report_versions WHERE id = %s", version_id)
        successor = self.ledger.draft(report_id, version_id)
        self.ledger.submit(successor)
        return successor

    def writer(self, name: str, target_id: int) -> Callable[[Cursor[Any]], object]:
        """An owner write in the caller's transaction falsifying a support on ``target_id``: a
        version for :data:`VERSION_WRITERS`, a disposition for ``redispose``. Setup runs now."""
        ledger, owner = self.ledger, PgRole.OWNER
        if name == "withdraw":
            return lambda cursor: ledger._decide(cursor, owner, target_id, DecisionKind.WITHDRAW)
        if name == "supersede":
            successor = self.successor(target_id)
            return lambda cursor: ledger._decide(
                cursor,
                owner,
                successor,
                DecisionKind.APPROVE,
                validation_id=validation(cursor, successor),
            )
        if name == "non_match":
            return lambda cursor: validation(cursor, target_id, state=ClaimState.VALUE_MISMATCH)
        if name == "version_level":
            states = (VersionState.UNCITED_PROSE,)
            return lambda cursor: validation(cursor, target_id, version_states=states)
        item = self.one("SELECT item_id FROM eqos.queue_dispositions WHERE id = %s", target_id)
        return lambda cursor: insert_disposition(
            cursor,
            item_id=item,
            kind=DispositionKind.DISMISSED,
            reason="fixture redisposition",
            decider="owner",
            evidence_ref="fixture",
            explained_amount=None,
        )

    def status(self, item_id: int) -> tuple[MemoryStatus, bool]:
        """The item's status and revalidation flag now."""
        ((head, retired, supported),) = self.rows(_STATUS, item_id)
        return derive_status(None if head is None else DecisionKind(head), retired, supported)

    def snapshot(self) -> list[list[tuple[Any, ...]]]:
        """Every memory item, support and memory decision row."""
        return [sorted(self.rows(query), key=str) for query in SNAPSHOT]

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


def promote(cursor: Cursor[Any], item_id: int) -> DecisionRecord:
    """The owner's PROMOTE of a candidate in the caller's transaction."""
    return store.insert_decision(
        cursor,
        subject_kind=SubjectKind.MEMORY_ITEM,
        subject_id=item_id,
        kind=DecisionKind.PROMOTE,
        predecessor_id=None,
        sealed_digest=store.subject_digest(cursor, SubjectKind.MEMORY_ITEM, item_id),
        ruling=RULING,
    )


@pytest.fixture
def memory(ledger: Ledger) -> Iterator[Memory]:
    """The memory of a seeded ledger with one approved version."""
    yield Memory(ledger)
