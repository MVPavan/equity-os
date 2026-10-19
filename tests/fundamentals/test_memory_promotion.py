"""D4.2 acceptance: the support predicate at staging and PROMOTE, a PROMOTE's own transaction,
promotion by the panel and the owner, supersession and status (ledger spec §2, amendment A1;
plan D4, M2-M5, M9). Races between transactions are in ``test_memory_races.py``.

Every case runs on its own ``eqos_test_*`` database through the real role logins. The base
version is approved by the owner binding its own ``AS_KNOWN`` all-``MATCH`` check; the triggers
are authoritative, so each refusal is provoked by the stager, the store or a direct insert.
"""

from __future__ import annotations

import json
from datetime import timedelta
from typing import Any

import psycopg
import pytest
from ledger_support import RULING, SECTION, claim, ledger, validation
from memory_support import Memory, memory, promote
from pg_evidence_schema_support import SHA_A, _capture, _insert, runtime, seeded
from pg_support import PgTestDatabase
from psycopg import errors, sql
from test_ledger_claim_check import ANCHOR, CONTRACT, QUOTE, QUOTED, import_quote
from test_ledger_lifecycle import POLICY
from test_ledger_panel import FakeReviewer

from fundamentals.contracts.evidence import RunMode
from fundamentals.contracts.ledger import (
    ClaimState,
    DecisionKind,
    NumericClaim,
    ReportKind,
    SubjectKind,
    VersionStatus,
)
from fundamentals.contracts.memory import (
    MemoryKind,
    MemoryStatus,
    SupportDraft,
    SupportTarget,
)
from fundamentals.ledger import lifecycle, store
from fundamentals.ledger.panel import ReviewStaleError
from fundamentals.memory.pg_store import PgMemoryStore
from fundamentals.memory.retrieval import support_refs
from fundamentals.pg.settings import PgRole

__all__ = ["ledger", "memory", "runtime", "seeded"]
pytestmark = pytest.mark.pg

OWNER, RUNTIME = PgRole.OWNER, PgRole.RUNTIME
CLAIM, VERSION = SupportTarget.CLAIM, SupportTarget.VERSION
REFUSED = "fails its support predicate"
MTR = MemoryKind.MANAGEMENT_TRACK_RECORD
# A second item's statement: identical columns stage the same item (0041's natural key).
OTHER = "Railway wires grew their share of consolidated revenue"


def cites(*targets: tuple[SupportTarget, int]) -> tuple[SupportDraft, ...]:
    """Supports on each (target, id)."""
    return tuple(SupportDraft(target=target, target_id=id_) for target, id_ in targets)


def quoted(capture: int, key: str = "ledger.q1", anchor: str = ANCHOR) -> NumericClaim:
    """:data:`QUOTED` in the fixture section, cited to ``capture`` at ``anchor``."""
    citation = QUOTED.citation.model_copy(update={"capture_ref_id": capture, "anchor": anchor})
    update = {"claim_key": key, "section_key": SECTION.section_key, "citation": citation}
    return QUOTED.model_copy(update=update)


def capture_of_blob(memory: Memory) -> int:
    """The seeded capture of the quote's blob."""
    return int(memory.one("SELECT min(id) FROM eqos.capture_refs WHERE blob_sha256 = %s", SHA_A))


def claim_ids(memory: Memory, version_id: int) -> list[int]:
    """The version's claim ids in id order."""
    rows = memory.rows(
        "SELECT id FROM eqos.numeric_claims WHERE version_id = %s ORDER BY id", version_id
    )
    return [row[0] for row in rows]


def no_promotion(memory: Memory, item_id: int) -> bool:
    """Whether the item has no decision row."""
    query = (
        "SELECT count(*) FROM eqos.decisions WHERE subject_kind = 'MEMORY_ITEM' AND subject_id = %s"
    )
    return bool(memory.one(query, item_id) == 0)


def stage_open(
    cursor: psycopg.Cursor[Any], memory: Memory, support: tuple[str, int], **update: Any
) -> int:
    """Insert :meth:`Memory.draft`'s item with one ``(column, target)`` support in the caller's
    open runtime transaction; returns the item id."""
    draft = memory.draft(**update)
    row = cursor.execute(
        "INSERT INTO eqos.memory_items (entity_id, kind, statement, epistemic_class, valid_from) "
        "VALUES (%s, %s, %s, %s, %s) RETURNING id",
        (draft.entity_id, draft.kind, draft.statement, draft.epistemic_class, draft.valid_from),
    ).fetchone()
    assert row is not None
    column, target = support
    add_support(cursor, int(row[0]), column, target)
    return int(row[0])


def add_support(cursor: psycopg.Cursor[Any], item_id: int, column: str, target: int) -> None:
    """A support on ``column``'s ``target`` in the caller's transaction."""
    statement = sql.SQL("INSERT INTO eqos.memory_supports (item_id, {}) VALUES (%s, %s)")
    cursor.execute(statement.format(sql.Identifier(column)), (item_id, target))


# --- the support predicate at staging (M3)


def test_staging_refuses_a_historical_version(memory: Memory) -> None:
    """An imported version sealed but never approved is HISTORICAL and fails V at commit."""
    historical = memory.ledger.imported(memory.ledger.report())
    with pytest.raises(errors.CheckViolation, match=REFUSED):
        memory.stage(supports=cites((VERSION, historical)))


@pytest.mark.parametrize("appended", ["capture", "historical", "non_match"])
def test_a_support_appended_after_the_items_check_ran_is_checked(
    memory: Memory, appended: str
) -> None:
    """A forbidden support appended after SET CONSTRAINTS ALL IMMEDIATE ran the item's check is
    refused: a capture on a company-understanding item, a HISTORICAL or a non-MATCH version."""
    if appended == "capture":
        column, target = "capture_ref_id", capture_of_blob(memory)
    elif appended == "historical":
        column, target = "version_id", memory.ledger.imported(memory.ledger.report())
    else:
        column, target = "version_id", memory.approved()
        memory.ledger.validate(target, state=ClaimState.VALUE_MISMATCH)
    with (
        pytest.raises(errors.CheckViolation, match=REFUSED),
        memory.ledger._cursor(RUNTIME) as cursor,
    ):
        item = stage_open(cursor, memory, ("version_id", memory.version_id))
        cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")
        add_support(cursor, item, column, target)
    assert memory.one("SELECT count(*) FROM eqos.memory_items") == 0


def test_a_support_recorded_after_its_item_is_refused(memory: Memory) -> None:
    """An owner ruling item cites an owner decision recorded before it, but not the owner's
    SET_POLICY another transaction commits after the item's store time: an item known at a
    cutoff rests only on targets known by then (M3)."""
    earlier = memory.ledger.head(memory.version_id).id
    report = memory.ledger.report()
    with (
        pytest.raises(errors.CheckViolation, match="predates its support target"),
        memory.ledger._cursor(RUNTIME) as cursor,
    ):
        item = stage_open(
            cursor, memory, ("decision_id", earlier), kind=MemoryKind.OWNER_RULING, entity_id=None
        )
        later = memory.ledger.decide(
            OWNER,
            report,
            DecisionKind.SET_POLICY,
            subject_kind=SubjectKind.REPORT,
            policy=POLICY,
            ruling="future knowledge",
        )
        add_support(cursor, item, "decision_id", later.id)
    assert memory.one("SELECT count(*) FROM eqos.memory_items") == 0


@pytest.mark.parametrize("column", ["claim_id", "version_id"])
def test_a_claim_appended_to_a_version_after_its_item_is_refused(
    memory: Memory, column: str
) -> None:
    """A claim another transaction appends to an unsealed version after the item's store time,
    and that version, are known only from its SUBMIT, so neither supports the item even once the
    version is approved (M3)."""
    version = memory.ledger.draft(memory.ledger.report())
    section = memory.one("SELECT id FROM eqos.report_sections WHERE version_id = %s", version)
    with (
        pytest.raises(errors.CheckViolation, match="predates its support target"),
        memory.ledger._cursor(RUNTIME) as cursor,
    ):
        item = stage_open(cursor, memory, ("version_id", memory.version_id))
        with memory.ledger._cursor(RUNTIME) as other:
            row = store._claim_row(
                claim(memory.ledger.trace_id, "future.claim"),
                version,
                {SECTION.section_key: section},
            )
            future = store._insert(other, "numeric_claims", row)
        memory.ledger.submit(version)
        memory.ledger.approve(version)
        add_support(cursor, item, column, future if column == "claim_id" else version)
    assert memory.one("SELECT count(*) FROM eqos.memory_items") == 0


def test_a_capture_first_seen_after_its_item_is_refused(memory: Memory) -> None:
    """A capture registered before the item's store time but first seen after it is known only
    from first sight, as the evidence layer selects it (M3)."""
    with (
        pytest.raises(errors.CheckViolation, match="predates its support target"),
        memory.ledger._cursor(RUNTIME) as cursor,
    ):
        item = stage_open(
            cursor,
            memory,
            ("capture_ref_id", capture_of_blob(memory)),
            kind=MemoryKind.SOURCE_QUIRK,
            entity_id=None,
        )
        query = "SELECT recorded_at FROM eqos.memory_items WHERE id = %s"
        (known,) = cursor.execute(query, (item,)).fetchone() or ()
        with memory.ledger._cursor(RUNTIME) as other:
            (seen,) = other.execute("SELECT eqos.store_now()").fetchone() or ()
            row = _capture("cap-late") | {
                "registered_at": known - timedelta(days=1),
                "first_seen_at": seen,
            }
            late = _insert(other.connection, "capture_refs", row)
        add_support(cursor, item, "capture_ref_id", late)
    assert memory.one("SELECT count(*) FROM eqos.memory_items") == 0


@pytest.mark.parametrize(
    "later",
    [
        pytest.param([{"mode": RunMode.RETROSPECTIVE}], id="retrospective"),
        pytest.param([{"state": None}], id="incomplete"),
        pytest.param(
            [{"state": ClaimState.VALUE_MISMATCH}, {"state": ClaimState.MATCH}],
            id="runtime-pass-after-a-failure",
        ),
    ],
)
def test_every_validation_after_the_trusted_pass_must_pass(
    memory: Memory, later: list[dict[str, Any]]
) -> None:
    """V: after the owner's trusted pass, a later RETROSPECTIVE, incomplete (no claim row) or
    failing validation fails the claim support, and a runtime pass cannot rescue it."""
    memory.stage(supports=cites((CLAIM, memory.claim_id)))
    for result in later:
        memory.ledger.validate(memory.version_id, **result)
    with pytest.raises(errors.CheckViolation, match=REFUSED):
        memory.stage(statement=OTHER, supports=cites((CLAIM, memory.claim_id)))


def test_a_match_untrusted_claim_fails_p(memory: Memory) -> None:
    """Approval accepts MATCH_UNTRUSTED; the support predicate does not."""
    version = memory.ledger.draft(memory.ledger.report())
    memory.ledger.submit(version)
    memory.ledger.approve(version, state=ClaimState.MATCH_UNTRUSTED)
    (claim_id,) = claim_ids(memory, version)
    for target in ((CLAIM, claim_id), (VERSION, version)):
        with pytest.raises(errors.CheckViolation, match=REFUSED):
            memory.stage(supports=cites(target))


def test_an_imported_approval_needs_a_trusted_as_known_validation(memory: Memory) -> None:
    """G3: an imported APPROVED version supports nothing until the owner validates it AS_KNOWN;
    a runtime check confers nothing."""
    imported = memory.ledger.imported(memory.ledger.report(), approve=True)
    memory.ledger.validate(imported)
    with pytest.raises(errors.CheckViolation, match=REFUSED):
        memory.stage(supports=cites((VERSION, imported)))
    memory.ledger.validate(imported, role=OWNER)
    assert memory.stage(supports=cites((VERSION, imported)))


def test_a_stocks_item_cites_only_its_own_stock(memory: Memory) -> None:
    """E: another entity's claim or version is refused for a stock's item; a cross-stock
    SOURCE_QUIRK citing a capture is accepted."""
    with memory.ledger._cursor(RUNTIME) as cursor:
        cursor.execute(
            "INSERT INTO eqos.reporting_entities (entity_key, market, display_name, "
            "evidence_input_id) SELECT 'other-stock', market, 'Other', evidence_input_id "
            "FROM eqos.reporting_entities WHERE id = %s RETURNING id",
            (memory.ledger.entity_id,),
        )
        (other,) = cursor.fetchone() or ()
        kind = ReportKind.EARNINGS_UPDATE
        foreign_report = store.create_report(cursor, entity_id=other, period="FY27_Q1", kind=kind)
    foreign = memory.approved(foreign_report)
    (foreign_claim,) = claim_ids(memory, foreign)
    for target in ((CLAIM, foreign_claim), (VERSION, foreign)):
        with pytest.raises(errors.CheckViolation, match=REFUSED):
            memory.stage(supports=cites(target))
    quirk = {"kind": MemoryKind.SOURCE_QUIRK, "entity_id": None}
    capture = capture_of_blob(memory)
    assert memory.stage(**quirk, supports=cites((SupportTarget.CAPTURE, capture)))


@pytest.mark.parametrize(
    ("second", "accepted"),
    [
        pytest.param("same", False, id="same-capture-and-anchor"),
        pytest.param("duplicate-capture", False, id="two-captures-of-one-blob"),
        pytest.param("respelled", False, id="equivalent-anchor-spelling"),
        pytest.param("other-quote", True, id="two-distinct-quotes"),
        pytest.param("figure", True, id="a-quote-and-a-figure"),
    ],
)
def test_a_track_record_needs_two_claims_at_distinct_quote_locations(
    memory: Memory, second: str, accepted: bool
) -> None:
    """L: two quote claims at one location (one capture, two capture rows of one blob, or an
    equivalent anchor spelling) are one quote; two quotes, or a quote and a figure, hold."""
    capture = capture_of_blob(memory)
    with memory.ledger._cursor(RUNTIME) as cursor:
        duplicate = _insert(cursor.connection, "capture_refs", _capture("cap-duplicate"))
    claims = {
        "same": quoted(capture, "ledger.q2"),
        "duplicate-capture": quoted(duplicate, "ledger.q2"),
        "respelled": quoted(capture, "ledger.q2", anchor="p001.b000.000:023"),
        "other-quote": quoted(capture, "ledger.q2", anchor="p2.b0.0:23"),
        "figure": claim(memory.ledger.trace_id),
    }
    version = memory.approved(claims=(quoted(capture), claims[second]))
    supports = cites(*((CLAIM, id_) for id_ in claim_ids(memory, version)))
    if accepted:
        assert memory.stage(kind=MTR, supports=supports)
        return
    with pytest.raises(errors.CheckViolation, match=REFUSED):
        memory.stage(kind=MTR, supports=supports)
    with pytest.raises(errors.CheckViolation, match=REFUSED):
        memory.stage(kind=MTR, supports=supports[:1])


def test_a_lesson_cites_a_rejected_version_but_never_its_claims(memory: Memory) -> None:
    """R: a LESSON may cite a version whose head is REJECT and whose latest check failed, shown
    as REJECTED; a company understanding citing it, or a LESSON citing its claim, is refused."""
    version = memory.ledger.draft(memory.ledger.report())
    memory.ledger.submit(version)
    memory.ledger.validate(version, state=ClaimState.VALUE_MISMATCH)
    memory.ledger.decide(OWNER, version, DecisionKind.REJECT)
    (claim_id,) = claim_ids(memory, version)
    lesson = {"kind": MemoryKind.LESSON, "entity_id": None}
    item = memory.stage(**lesson, supports=cites((VERSION, version)))
    with memory.ledger._cursor(RUNTIME) as cursor:
        (ref,) = support_refs(cursor, item, None)
    assert ref.version_status is VersionStatus.REJECTED
    for update in (
        {"supports": cites((VERSION, version))},
        lesson | {"statement": OTHER, "supports": cites((CLAIM, claim_id))},
    ):
        with pytest.raises(errors.CheckViolation, match=REFUSED):
            memory.stage(**update)


# --- the panel and the owner decide (M2, M9)


def test_the_reviewer_reads_each_support_resolved(memory: Memory) -> None:
    """The panel's reviewer reads the item and, per quote claim, its quote, bounds, qualifiers,
    contract and the contract a sealed import binds (with its binding), its stock, period and
    status, capture blob and anchor; a version support adds its narrative and claims."""
    import_quote(memory.ledger, CONTRACT)
    capture = capture_of_blob(memory)
    version = memory.approved(claims=(quoted(capture),))
    (quote_claim,) = claim_ids(memory, version)
    item = memory.stage(supports=cites((CLAIM, quote_claim), (VERSION, memory.version_id)))
    reviewer = FakeReviewer()
    decision = PgMemoryStore(memory.ledger.pools[PgRole.PANEL]).decide(
        item, DecisionKind.PROMOTE, reviewer=reviewer
    )
    assert decision.kind is DecisionKind.PROMOTE
    ((text, digest),) = reviewer.calls
    assert digest == decision.sealed_digest
    shown = json.loads(text)
    assert shown["item"]["id"] == item
    quote, base = shown["supports"]
    citation = quote["citation"]
    assert (citation["quote"], citation["anchor"], citation["capture_ref_id"]) == (
        QUOTE,
        ANCHOR,
        capture,
    )
    assert (quote["lower_bound"], quote["upper_bound"]) == ("9.5", "10")
    assert quote["qualifiers"] == ["about"] and quote["blob_sha256"] == SHA_A
    assert quote["contract"] == quote["bound_contract"] == CONTRACT.model_dump(mode="json")
    assert [b["contract"] for b in quote["bindings"]] == [CONTRACT.model_dump(mode="json")]
    assert (quote["stock"], quote["version_status"]) == (base["stock"], VersionStatus.APPROVED)
    assert quote["period"] and quote["report_kind"]
    assert base["narrative"] and [c["target_id"] for c in base["claims"]] == [memory.claim_id]


@pytest.mark.parametrize("falls", ["withdraw", "non_match"])
def test_a_support_falling_during_the_review_makes_it_stale(memory: Memory, falls: str) -> None:
    """A withdrawal or failing validation committed during the reviewer's call refuses the
    decision under the lock, with no review or decision row."""
    item = memory.stage()
    write = memory.writer(falls, memory.version_id)

    def during() -> None:
        with memory.ledger._cursor(OWNER) as cursor:
            write(cursor)

    with pytest.raises(ReviewStaleError):
        PgMemoryStore(memory.ledger.pools[PgRole.PANEL]).decide(
            item, DecisionKind.PROMOTE, reviewer=FakeReviewer(during=during)
        )
    assert no_promotion(memory, item)
    assert memory.one("SELECT count(*) FROM eqos.panel_reviews WHERE subject_id = %s", item) == 0


@pytest.mark.parametrize("kind", [DecisionKind.RETIRE, DecisionKind.APPROVE])
def test_a_reviewer_decides_only_a_candidates_review(memory: Memory, kind: DecisionKind) -> None:
    """A reviewer's verdict maps to PROMOTE or REJECT_CANDIDATE; asking it for any other kind
    is refused before the reviewer runs, leaving no review or decision."""
    item, reviewer = memory.stage(), FakeReviewer()
    with pytest.raises(lifecycle.DecisionRefusedError, match=kind.value):
        PgMemoryStore(memory.ledger.pools[PgRole.PANEL]).decide(item, kind, reviewer=reviewer)
    assert reviewer.calls == [] and no_promotion(memory, item)
    assert memory.one("SELECT count(*) FROM eqos.panel_reviews WHERE subject_id = %s", item) == 0


def test_the_owner_promotes_and_retires_with_a_ruling(memory: Memory) -> None:
    """The owner's PROMOTE then RETIRE through the store; a decision needs a reviewer or a
    ruling."""
    item, owner = memory.stage(), PgMemoryStore(memory.ledger.pools[OWNER])
    with pytest.raises(ValueError, match="reviewer"):
        owner.decide(item, DecisionKind.PROMOTE)
    owner.decide(item, DecisionKind.PROMOTE, ruling=RULING)
    assert memory.status(item) == (MemoryStatus.PROMOTED, False)
    owner.decide(item, DecisionKind.RETIRE, ruling=RULING)
    assert memory.status(item) == (MemoryStatus.RETIRED, False)


def test_a_promoted_successor_retires_its_predecessor(memory: Memory) -> None:
    """The successor's one PROMOTE retires its predecessor; both rows remain. A second
    successor's refusal is D4.1's ``test_a_successor_promotes_only_over_a_promoted_predecessor``.
    """
    earlier = memory.stage()
    memory.decide(OWNER, earlier, DecisionKind.PROMOTE)
    later = memory.stage(supersedes_item_id=earlier)
    assert memory.status(earlier) == (MemoryStatus.PROMOTED, False)
    memory.decide(OWNER, later, DecisionKind.PROMOTE)
    assert memory.status(earlier) == (MemoryStatus.RETIRED, False)
    assert memory.status(later) == (MemoryStatus.PROMOTED, False)
    assert (
        memory.one("SELECT count(*) FROM eqos.memory_items WHERE id IN (%s, %s)", earlier, later)
        == 2
    )


def test_approving_a_ledger_version_changes_no_memory_row(memory: Memory) -> None:
    """An unrelated approval and a superseding approval of a support write no memory row; the
    superseded support only derives a flag."""
    item = memory.stage()
    memory.decide(OWNER, item, DecisionKind.PROMOTE)
    before = memory.snapshot()
    memory.approved()
    successor = memory.successor(memory.version_id)
    memory.ledger.approve(successor)
    assert memory.snapshot() == before
    assert memory.status(item) == (MemoryStatus.PROMOTED, True)


# --- the lock and the PROMOTE's own transaction (M4)


@pytest.mark.parametrize("writer", ["supersede", "non_match", "withdraw"])
def test_a_support_writer_after_a_clock_read_is_refused(memory: Memory, writer: str) -> None:
    """A superseding approval, a validation and a WITHDRAW take the queue lock before the
    transaction's first store-clock read, so one after it fails with 55000."""
    write = memory.writer(writer, memory.version_id)
    with pytest.raises(errors.ObjectNotInPrerequisiteState), memory.ledger._cursor(OWNER) as cursor:
        cursor.execute("SELECT eqos.store_now()")
        write(cursor)


def _flush(cursor: psycopg.Cursor[Any], flushed: bool) -> None:
    """Fire the deferred triggers now when ``flushed``."""
    if flushed:
        cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")


@pytest.mark.parametrize("flushed", [False, True], ids=["deferred", "flushed"])
@pytest.mark.parametrize("writer", ["withdraw", "non_match", "supersede"])
def test_no_falsifying_write_follows_promote_in_its_transaction(
    memory: Memory, writer: str, flushed: bool
) -> None:
    """A withdrawal, failing validation or supersession after PROMOTE in one transaction is
    refused, also with the deferred re-check fired early, and nothing is left."""
    item = memory.stage()
    write = memory.writer(writer, memory.version_id)
    with pytest.raises(errors.CheckViolation), memory.ledger._cursor(OWNER) as cursor:
        _flush(cursor, flushed)
        promote(cursor, item)
        _flush(cursor, flushed)
        write(cursor)
    assert no_promotion(memory, item)
    assert memory.status(item) == (MemoryStatus.CANDIDATE, False)


def test_a_disposition_or_a_state_after_promote_is_refused_with_constraints_flushed(
    memory: Memory,
) -> None:
    """A replacement disposition of a disposition support, and a version-level state appended
    to a trusted validation written earlier in the transaction, are refused after PROMOTE; a
    PROMOTE with no later write commits."""
    disposition = memory.one("SELECT max(id) FROM eqos.queue_dispositions")
    quirk = memory.stage(
        kind=MemoryKind.SOURCE_QUIRK,
        entity_id=None,
        supports=cites((SupportTarget.DISPOSITION, disposition)),
    )
    redispose = memory.writer("redispose", disposition)
    with pytest.raises(errors.CheckViolation), memory.ledger._cursor(OWNER) as cursor:
        _flush(cursor, True)
        promote(cursor, quirk)
        _flush(cursor, True)
        redispose(cursor)
    item = memory.stage()
    with pytest.raises(errors.CheckViolation), memory.ledger._cursor(OWNER) as cursor:
        trusted = validation(cursor, memory.version_id)
        _flush(cursor, True)
        promote(cursor, item)
        _flush(cursor, True)
        cursor.execute(
            "INSERT INTO eqos.validation_claim_states (validation_id, version_id, state) "
            "VALUES (%s, %s, 'UNCITED_PROSE')",
            (trusted, memory.version_id),
        )
    assert no_promotion(memory, quirk) and no_promotion(memory, item)
    with memory.ledger._cursor(OWNER) as cursor:
        _flush(cursor, True)
        promote(cursor, item)
    assert memory.status(item) == (MemoryStatus.PROMOTED, False)


@pytest.mark.parametrize("flushed", [False, True], ids=["deferred", "flushed"])
def test_no_decision_follows_promote_in_its_transaction(memory: Memory, flushed: bool) -> None:
    """A1: PROMOTE is the last ledger or queue write of its transaction, so the owner's RETIRE
    of the item it just promoted is refused, also with the deferred checks fired early."""
    item = memory.stage()
    with (
        pytest.raises(errors.CheckViolation, match="follow a memory PROMOTE"),
        memory.ledger._cursor(OWNER) as cursor,
    ):
        _flush(cursor, flushed)
        promotion = promote(cursor, item)
        _flush(cursor, flushed)
        store.insert_decision(
            cursor,
            subject_kind=SubjectKind.MEMORY_ITEM,
            subject_id=item,
            kind=DecisionKind.RETIRE,
            predecessor_id=promotion.id,
            sealed_digest=promotion.sealed_digest,
            ruling=RULING,
        )
    assert no_promotion(memory, item)


@pytest.mark.parametrize("immediate", [True, False], ids=["at-insert", "at-commit"])
def test_promote_on_a_fallen_support_is_refused_at_insert_and_again_at_commit(
    memory: Memory, pg_db: PgTestDatabase, immediate: bool
) -> None:
    """The BEFORE-insert check refuses the PROMOTE statement itself; with it dropped (on this
    test database only) the deferred re-check still refuses the transaction at commit."""
    item = memory.stage()
    with memory.ledger._cursor(OWNER) as cursor:
        memory.writer("withdraw", memory.version_id)(cursor)
    if not immediate:
        with pg_db.migrator_connection() as migrator:
            migrator.execute("DROP TRIGGER check_memory_promotion ON eqos.decisions")
    inserted: list[int] = []
    with (
        pytest.raises(errors.CheckViolation, match=REFUSED),
        memory.ledger._cursor(OWNER) as cursor,
    ):
        promote(cursor, item)
        inserted.append(item)
    assert inserted == ([] if immediate else [item])
    assert no_promotion(memory, item)
