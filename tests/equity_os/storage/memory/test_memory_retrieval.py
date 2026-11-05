"""D4.3 acceptance: search, retrieval as known at a cutoff, revalidation flags and provenance
(ledger spec §2; plan D4, M5, M6).

Cutoffs are stored ``recorded_at`` values minus 1 µs, never the host clock (``eqos-bhy``).
Every as-of row type gets a before-the-event case: decisions (PROMOTE, withdrawal, approval of a
successor version, a successor item's PROMOTE), validations and dispositions.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, LiteralString

import pytest
from ledger_support import ledger
from memory_support import VERSION_WRITERS, Memory, memory, promote
from pg_evidence_schema_support import SHA_A, runtime, seeded
from psycopg import errors
from test_ledger_claim_check import ANCHOR, QUOTE
from test_memory_promotion import REFUSED, capture_of_blob, cites, claim_ids, quoted

from equity_os.contracts.publication.ledger import (
    CitationKind,
    DecisionKind,
    ReportKind,
    VersionStatus,
)
from equity_os.contracts.storage.memory import (
    MemoryKind,
    MemoryStatus,
    RetrievedItem,
    SupportTarget,
)
from equity_os.storage.database.settings import PgRole
from equity_os.storage.memory import retrieval
from equity_os.storage.memory.store import MemoryStore
from equity_os.storage.records import store

__all__ = ["ledger", "memory", "runtime", "seeded"]
pytestmark = pytest.mark.pg

OWNER = PgRole.OWNER
CLAIM, VERSION = SupportTarget.CLAIM, SupportTarget.VERSION
MARGIN = "Management raised its annual cables EBITDA margin guidance"
# A distinct item's statement: identical columns stage the same item (0041's natural key).
CUT = "Management cut its annual cables EBITDA margin guidance"
EVERY_STATUS = frozenset(MemoryStatus)
# The latest store time of any write that can falsify a support.
_LATEST: LiteralString = """SELECT max(recorded_at) - interval '1 microsecond' FROM (
    SELECT recorded_at FROM eqos.decisions UNION ALL SELECT recorded_at FROM eqos.validations
    UNION ALL SELECT recorded_at FROM eqos.queue_dispositions) t"""


def before(memory: Memory, table: str, row_id: int) -> datetime:
    """1 µs before the row's stored ``recorded_at``."""
    query = f"SELECT recorded_at - interval '1 microsecond' FROM eqos.{table} WHERE id = %s"
    return memory.one(query, row_id)  # type: ignore[no-any-return]


def promoted(memory: Memory, **update: Any) -> int:
    """A staged item the owner promotes."""
    item = memory.stage(**update)
    memory.decide(OWNER, item, DecisionKind.PROMOTE)
    return item


def found(memory: Memory, query: str = "", **filters: Any) -> dict[int, RetrievedItem]:
    """The stock's retrieved items by id."""
    filters = {"stock": memory.ledger.entity_id} | filters
    return {item.id: item for item in memory.store.retrieve(query, **filters)}


def other_stock(memory: Memory) -> int:
    """A second reporting entity with an approved version and a promoted item on it."""
    with memory.ledger._cursor(PgRole.RUNTIME) as cursor:
        cursor.execute(
            "INSERT INTO eqos.reporting_entities (entity_key, market, display_name, "
            "evidence_input_id) SELECT 'other-stock', market, 'Other', evidence_input_id "
            "FROM eqos.reporting_entities WHERE id = %s RETURNING id",
            (memory.ledger.entity_id,),
        )
        (other,) = cursor.fetchone() or ()
        kind = ReportKind.EARNINGS_UPDATE
        report = store.create_report(cursor, entity_id=other, period="FY27_Q1", kind=kind)
    version = memory.approved(report)
    promoted(memory, entity_id=other, statement=MARGIN, supports=cites((VERSION, version)))
    return int(other)


# --- search and filters


def test_search_finds_the_item_and_the_filters_select(memory: Memory) -> None:
    """The query "cables margin" finds the margin item only; the stock, kind and status filters
    each select; PgMemoryStore satisfies MemoryStore."""
    reader: MemoryStore = memory.store
    margin = promoted(memory, statement=MARGIN)
    share = promoted(memory)
    thesis = promoted(memory, kind=MemoryKind.THESIS_AND_WARNING)
    candidate = memory.stage(statement=CUT)
    other = other_stock(memory)
    (elsewhere,) = reader.retrieve("cables margin", stock=other)
    assert elsewhere.entity_id == other
    assert list(found(memory, "cables margin")) == [margin]
    assert list(found(memory)) == [margin, share, thesis]
    thesis_only = found(memory, kinds=frozenset({MemoryKind.THESIS_AND_WARNING}))
    assert list(thesis_only) == [thesis]
    candidates = found(memory, "cables margin", statuses=frozenset({MemoryStatus.CANDIDATE}))
    assert list(candidates) == [candidate]
    memory.decide(OWNER, candidate, DecisionKind.REJECT_CANDIDATE)
    memory.decide(OWNER, share, DecisionKind.RETIRE)
    statuses = {item.id: item.status for item in found(memory, statuses=EVERY_STATUS).values()}
    assert statuses == {
        margin: MemoryStatus.PROMOTED,
        share: MemoryStatus.RETIRED,
        thesis: MemoryStatus.PROMOTED,
        candidate: MemoryStatus.REJECTED,
    }


def test_stock_none_searches_the_cross_stock_items(memory: Memory) -> None:
    """A promoted null-entity source quirk is found with no stock and not with a stock id; a
    stock's item is not found with no stock (M6 correction)."""
    quirk = promoted(
        memory,
        kind=MemoryKind.SOURCE_QUIRK,
        entity_id=None,
        statement="Transcript pagination restarts each section",
        supports=cites((SupportTarget.CAPTURE, capture_of_blob(memory))),
    )
    promoted(memory)
    assert [item.id for item in memory.store.retrieve("transcript pagination", stock=None)] == [
        quirk
    ]
    assert [item.id for item in memory.store.retrieve("", stock=None)] == [quirk]
    assert found(memory, "transcript pagination") == {}


# --- cutoffs


def test_a_cutoff_before_promotion_or_recording_excludes_the_item(memory: Memory) -> None:
    """Before the PROMOTE the item is a candidate (not returned by default); before its own
    recorded_at it does not exist; before a successor's PROMOTE the predecessor is still
    promoted."""
    item = memory.stage(statement=MARGIN)
    decision = memory.decide(OWNER, item, DecisionKind.PROMOTE)
    assert list(found(memory, "cables margin")) == [item]
    at_promotion = before(memory, "decisions", decision.id)
    assert found(memory, "cables margin", cutoff=at_promotion) == {}
    early = found(memory, cutoff=at_promotion, statuses=EVERY_STATUS)
    assert early[item].status is MemoryStatus.CANDIDATE
    at_recording = before(memory, "memory_items", item)
    assert found(memory, cutoff=at_recording, statuses=EVERY_STATUS) == {}
    successor = memory.stage(statement=MARGIN, supersedes_item_id=item)
    succeeded = memory.decide(OWNER, successor, DecisionKind.PROMOTE)
    assert list(found(memory)) == [successor]
    assert list(found(memory, cutoff=before(memory, "decisions", succeeded.id))) == [item]


# --- revalidation flags


def _support(memory: Memory, event: str, target: SupportTarget) -> dict[str, Any]:
    """Stage fields citing the support ``event`` falsifies: the base version directly or through
    its claim, or for ``redispose`` the latest disposition from a stock's SOURCE_QUIRK."""
    if event == "redispose":
        disposition = memory.one("SELECT max(id) FROM eqos.queue_dispositions")
        return {"kind": MemoryKind.SOURCE_QUIRK, "supports": cites((target, disposition))}
    target_id = memory.claim_id if target is CLAIM else memory.version_id
    return {"supports": cites((target, target_id))}


EVENTS = [
    pytest.param(event, target, id=f"{event}-{target.name.lower()}")
    for event in VERSION_WRITERS
    for target in (CLAIM, VERSION)
] + [pytest.param("redispose", SupportTarget.DISPOSITION, id="redispose-disposition")]


@pytest.mark.parametrize(("event", "target"), EVENTS)
def test_an_invalidating_event_flags_the_promoted_item_and_refuses_promotion(
    memory: Memory, event: str, target: SupportTarget
) -> None:
    """A promoted P and a candidate C share a support; after the event P is flagged
    NEEDS_REVALIDATION, PROMOTE of C and staging a new item on that support are refused while an
    exact retry of P returns P with nothing written; a cutoff before the event shows P
    unflagged."""
    fields = _support(memory, event, target)
    item = promoted(memory, **fields)
    candidate = memory.stage(**fields, statement=MARGIN)
    falsified = fields["supports"][0].target_id if event == "redispose" else memory.version_id
    write = memory.writer(event, falsified)
    with memory.ledger._cursor(OWNER) as cursor:
        write(cursor)
    assert found(memory)[item].needs_revalidation
    with pytest.raises(errors.CheckViolation, match=REFUSED), memory.ledger._cursor(OWNER) as cur:
        promote(cur, candidate)
    unchanged = memory.snapshot()
    assert memory.stage(**fields) == item
    assert memory.snapshot() == unchanged
    with pytest.raises(errors.CheckViolation, match=REFUSED):
        memory.stage(**fields, statement=CUT)
    earlier = found(memory, cutoff=memory.one(_LATEST))[item]
    assert (earlier.status, earlier.needs_revalidation) == (MemoryStatus.PROMOTED, False)


def test_one_snapshot_serves_the_item_query_and_its_supports(
    memory: Memory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """F3: a WITHDRAW committed between the item query and support resolution leaves the
    response consistent (unflagged, support APPROVED); a fresh retrieve shows both changed."""
    item = promoted(memory)
    resolve = retrieval.support_refs

    def withdrawn_first(*args: Any) -> Any:
        if memory.one("SELECT count(*) FROM eqos.decisions WHERE kind = 'WITHDRAW'") == 0:
            memory.ledger.decide(OWNER, memory.version_id, DecisionKind.WITHDRAW)
        return resolve(*args)

    monkeypatch.setattr(retrieval, "support_refs", withdrawn_first)
    (seen,) = memory.store.retrieve("", stock=memory.ledger.entity_id)
    assert seen.id == item and not seen.needs_revalidation
    assert seen.supports[0].version_status is VersionStatus.APPROVED
    monkeypatch.undo()
    (fresh,) = memory.store.retrieve("", stock=memory.ledger.entity_id)
    assert fresh.needs_revalidation
    assert fresh.supports[0].version_status is VersionStatus.WITHDRAWN


# --- provenance


def test_provenance_lists_the_retired_predecessor_and_its_successor(memory: Memory) -> None:
    """From either end, the lineage holds both items with their statuses and supports."""
    earlier = promoted(memory)
    later = promoted(memory, supersedes_item_id=earlier)
    for start in (earlier, later):
        lineage = memory.store.provenance(start)
        assert [(item.id, item.status) for item in lineage] == [
            (earlier, MemoryStatus.RETIRED),
            (later, MemoryStatus.PROMOTED),
        ]
        assert all(item.supports[0].target_id == memory.version_id for item in lineage)


def test_provenance_references_reach_citations_and_captures(memory: Memory) -> None:
    """F5: a directly supporting version lists its claims with their Citations; a CALCULATION
    claim carries its trace; a quote claim its capture, anchor, quote and blob. At a cutoff
    before a later WITHDRAW the version is APPROVED; after it, WITHDRAWN, claims still listed."""
    capture = capture_of_blob(memory)
    (quote_claim,) = claim_ids(memory, memory.approved(claims=(quoted(capture),)))
    supports = cites((VERSION, memory.version_id), (CLAIM, memory.claim_id), (CLAIM, quote_claim))
    item = promoted(memory, supports=supports)
    withdrawal = memory.ledger.decide(OWNER, memory.version_id, DecisionKind.WITHDRAW)
    known = found(memory, cutoff=before(memory, "decisions", withdrawal.id))[item]
    (now,) = memory.store.provenance(item)
    for refs, status in (
        (known.supports, VersionStatus.APPROVED),
        (now.supports, VersionStatus.WITHDRAWN),
    ):
        version, calculation, quote = refs
        assert version.version_status is status
        (listed,) = version.claims
        assert listed.target_id == memory.claim_id and listed.citation is not None
        assert listed.citation.kind is CitationKind.CALCULATION
        assert calculation.citation is not None
        assert calculation.citation.calculation_trace_id == memory.ledger.trace_id
        assert quote.citation is not None and quote.blob_sha256 == SHA_A
        assert (quote.citation.capture_ref_id, quote.citation.anchor, quote.citation.quote) == (
            capture,
            ANCHOR,
            QUOTE,
        )
