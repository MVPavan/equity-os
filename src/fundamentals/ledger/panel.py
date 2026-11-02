"""The approval panel: one reviewer's verdict decides a sealed subject (ledger spec §1; plan D10).

``review`` runs the deterministic gates, calls the reviewer outside any transaction only if they
pass, then re-runs them in the deciding transaction under the queue lock and the subject lock
and inserts the review and its decision there; a change between the two runs refuses with no
row. A version's gate is the panel's own claim check, which its approval binds (D4). The
reviewer returns a verdict and rationale, never an amount (D11). The panel decides report
versions, disposition proposals and memory candidates (plan D4, M2), whose text the caller's
``describe`` renders; interpretations are owner-only.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from functools import partial
from typing import Any, LiteralString, Protocol

from psycopg import Cursor
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from fundamentals.compare.queue import lock_queue, overlay_at, overlay_boundary
from fundamentals.contracts.ledger import (
    DecisionKind,
    DecisionRecord,
    PanelReview,
    ReviewOutput,
    SubjectKind,
    Validation,
    Verdict,
)
from fundamentals.contracts.snapshot import canonical_json
from fundamentals.contracts.source_catalog import SourceCatalog
from fundamentals.ledger import store
from fundamentals.ledger.evidence_bundle import BundleLimits, panel_text
from fundamentals.ledger.lifecycle import (
    DecisionRefusedError,
    append_decision,
    approval_check,
    passes,
)
from fundamentals.store.snapshot_store import SnapshotStore

V, P = SubjectKind.REPORT_VERSION, SubjectKind.DISPOSITION_PROPOSAL
M = SubjectKind.MEMORY_ITEM
_VERDICTS = {
    V: {verdict: DecisionKind(verdict.value) for verdict in Verdict},
    P: {Verdict.APPROVE: DecisionKind.ACCEPT, Verdict.REJECT: DecisionKind.REJECT},
    M: {Verdict.APPROVE: DecisionKind.PROMOTE, Verdict.REJECT: DecisionKind.REJECT_CANDIDATE},
}
_REVIEWER_DATA = ("provider", "model", "effort", "brief_version")
_LOCK: LiteralString = "SELECT eqos.lock_subject(%s, %s)"
_NOW: LiteralString = "SELECT eqos.store_now()"
_PROPOSAL: LiteralString = """SELECT to_jsonb(p) AS proposal, to_jsonb(q) AS item,
    to_jsonb(o) AS pair, q.run_id,
    p.pair_outcome_id IS NULL OR eqos.proposal_amount(p.id) > 0 AS amount_valid,
    EXISTS (SELECT 1 FROM eqos.decisions d JOIN eqos.disposition_proposals s ON s.id = d.subject_id
            WHERE d.subject_kind = 'DISPOSITION_PROPOSAL' AND d.decider = 'OWNER'
              AND s.item_id = p.item_id) AS owner_decided
FROM eqos.disposition_proposals p JOIN eqos.queue_items q ON q.id = p.item_id
LEFT JOIN eqos.pair_outcomes o ON o.id = p.pair_outcome_id WHERE p.id = %s"""
# A candidate's support predicate (0017) and whether its predecessor, if any, is still promoted.
_MEMORY: LiteralString = """SELECT eqos.memory_item_supported(i.id, NULL),
    i.supersedes_item_id IS NULL OR (coalesce((SELECT kind FROM eqos.decisions
        WHERE subject_kind = 'MEMORY_ITEM' AND subject_id = i.supersedes_item_id
        ORDER BY sequence DESC LIMIT 1) = 'PROMOTE', false)
        AND NOT eqos.memory_promoted_successor(i.supersedes_item_id))
FROM eqos.memory_items i WHERE i.id = %s"""
_NOT_PANEL = "the panel does not decide {subject_kind} subjects"
_NEEDS = "{subject_kind} reviews need {what}"
_NO_VERDICT = "verdict {verdict} has no decision on {subject_kind}"
_GATE = "{kind} {id} fails its panel gate: {reason}"
_STALE = "{subject_kind} {subject_id} changed during its review"
_NOT_SUBMITTED = "its head is not SUBMIT"
_FAILS = "its AS_KNOWN claim check does not pass"
_SETTLED = "it is decided, its item has an owner decision, or its amount source is invalid"
_NOT_OPEN = "its queue item is not open"
_DECIDED = "it is already decided"
_UNSUPPORTED = "a support fails its predicate"
_PREDECESSOR = "its predecessor is not promoted"


class Reviewer(Protocol):
    """One reviewer; its provider, model, effort and brief version are recorded as data."""

    provider: str
    model: str
    effort: str
    brief_version: str

    def review(self, subject_text: str, sealed_digest: str) -> ReviewOutput:
        """The verdict on the sealed subject's text."""
        ...


class ReviewStaleError(DecisionRefusedError):
    """The subject or its gates changed while the reviewer ran; nothing was written."""


def verdict_decision(subject_kind: SubjectKind, verdict: Verdict) -> DecisionKind:
    """The decision a verdict makes on a subject kind (D10); anything else is refused."""
    kinds = _VERDICTS.get(subject_kind, {})
    if verdict not in kinds:
        raise DecisionRefusedError(_NO_VERDICT.format(verdict=verdict, subject_kind=subject_kind))
    return kinds[verdict]


def review(
    pool: ConnectionPool,
    *,
    subject_kind: SubjectKind,
    subject_id: int,
    reviewer: Reviewer,
    catalog: SourceCatalog | None = None,
    snapshots: SnapshotStore | None = None,
    describe: Callable[[Cursor[Any], int], str] | None = None,
    limits: BundleLimits | None = None,
) -> DecisionRecord:
    """Decide one report version, disposition proposal or memory candidate by the reviewer's
    verdict, as the pool's (panel) role; a version's claims are checked with ``catalog`` and
    ``snapshots``, a narrated version's bundle is rebuilt under ``limits``, and a candidate's text
    is ``describe(cursor, item_id)``."""
    if subject_kind not in _VERDICTS:
        raise DecisionRefusedError(_NOT_PANEL.format(subject_kind=subject_kind))
    check = None
    if catalog is not None and snapshots is not None:
        check = partial(approval_check, catalog=catalog, snapshots=snapshots)
    if subject_kind is V and check is None:
        raise DecisionRefusedError(_NEEDS.format(subject_kind=V, what="catalog and snapshots"))
    if subject_kind is M and describe is None:
        raise DecisionRefusedError(_NEEDS.format(subject_kind=M, what="describe"))
    gate = partial(_gate, check=check, describe=describe, limits=limits)
    as_of = overlay_boundary(pool) if subject_kind is P else None
    with pool.connection() as conn, conn.cursor() as cursor:
        text, gated, _ = gate(cursor, subject_kind, subject_id, as_of)
    output = reviewer.review(text, gated[0])
    kind = verdict_decision(subject_kind, output.verdict)
    with pool.connection() as conn, conn.transaction(), conn.cursor() as cursor:
        lock_queue(cursor)
        cursor.execute(_LOCK, (subject_kind.value, subject_id))
        now = cursor.execute(_NOW).fetchone()
        assert now is not None
        try:
            _, final, validation = gate(cursor, subject_kind, subject_id, now[0])
        except DecisionRefusedError as refused:
            raise ReviewStaleError(str(refused)) from refused
        if final != gated:
            raise ReviewStaleError(_STALE.format(subject_kind=subject_kind, subject_id=subject_id))
        recorded = PanelReview(
            subject_kind=subject_kind,
            subject_id=subject_id,
            sealed_digest=gated[0],
            **output.model_dump(),
            **{name: getattr(reviewer, name) for name in _REVIEWER_DATA},
        )
        review_id = store.insert_panel_review(cursor, recorded)
        return append_decision(
            cursor, subject_kind, subject_id, kind, validation=validation, panel_review_id=review_id
        )


def _gate(
    cursor: Cursor[Any],
    subject_kind: SubjectKind,
    subject_id: int,
    as_of: datetime | None,
    *,
    check: Callable[[Cursor[Any], int], Validation] | None,
    describe: Callable[[Cursor[Any], int], str] | None,
    limits: BundleLimits | None,
) -> tuple[str, tuple[str, object], Validation | None]:
    """The reviewed text, the gated state (digest, a version's check result or a candidate's
    text) and a version's passing check if every D10 gate holds, else refuse. A proposal's
    overlay is read at ``as_of``."""
    digest = store.subject_digest(cursor, subject_kind, subject_id)
    head = store.chain_head(cursor, subject_kind, subject_id)
    if subject_kind is M:
        assert describe is not None
        row = cursor.execute(_MEMORY, (subject_id,)).fetchone()
        assert row is not None
        if head is not None:
            raise _refused(subject_kind, subject_id, _DECIDED)
        if not row[0]:
            raise _refused(subject_kind, subject_id, _UNSUPPORTED)
        if not row[1]:
            raise _refused(subject_kind, subject_id, _PREDECESSOR)
        text = describe(cursor, subject_id)
        return text, (digest, text), None
    if subject_kind is V:
        if head is None or head.kind is not DecisionKind.SUBMIT:
            raise _refused(subject_kind, subject_id, _NOT_SUBMITTED)
        assert check is not None
        validation = check(cursor, subject_id)
        if not passes(validation, digest):
            raise _refused(subject_kind, subject_id, _FAILS)
        draft = store.read_version(cursor, subject_id)
        result = validation.model_dump(exclude={"overlay_position"})
        return panel_text(cursor, draft, limits), (digest, result), validation
    with cursor.connection.cursor(row_factory=dict_row) as own:
        row = own.execute(_PROPOSAL, (subject_id,)).fetchone()
    assert row is not None and as_of is not None
    overlay = overlay_at(cursor, run_id=row["run_id"], as_of=as_of)
    open_ids = {item.item_id for item in overlay.open_items}
    if head is not None or row["owner_decided"] or not row["amount_valid"]:
        raise _refused(subject_kind, subject_id, _SETTLED)
    if row["proposal"]["item_id"] not in open_ids:
        raise _refused(subject_kind, subject_id, _NOT_OPEN)
    payload = {key: row[key] for key in ("proposal", "item", "pair")}
    return canonical_json(payload), (digest, None), None


def _refused(subject_kind: SubjectKind, subject_id: int, reason: str) -> DecisionRefusedError:
    """A gate refusal naming the subject."""
    return DecisionRefusedError(_GATE.format(kind=subject_kind, id=subject_id, reason=reason))
