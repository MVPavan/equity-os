"""The approval panel: one reviewer's verdict decides a sealed subject (ledger spec §1; plan D10).

``review`` runs the deterministic gates, calls the reviewer outside any transaction only if they
pass, then re-runs them in the deciding transaction under the queue lock and the subject lock
and inserts the review and its decision there; a change between the two runs refuses with no
row. A version's gate is the panel's own claim check, which its approval binds (D4). The
reviewer returns a verdict and rationale, never an amount (D11). The panel decides report
versions and disposition proposals; interpretations are owner-only.
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
from fundamentals.ledger.display import narrative
from fundamentals.ledger.lifecycle import (
    DecisionRefusedError,
    append_decision,
    approval_check,
    passes,
)
from fundamentals.store.snapshot_store import SnapshotStore

V, P = SubjectKind.REPORT_VERSION, SubjectKind.DISPOSITION_PROPOSAL
_VERDICTS = {
    V: {verdict: DecisionKind(verdict.value) for verdict in Verdict},
    P: {Verdict.APPROVE: DecisionKind.ACCEPT, Verdict.REJECT: DecisionKind.REJECT},
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
_NOT_PANEL = "the panel does not decide {subject_kind} subjects"
_NO_VERDICT = "verdict {verdict} has no decision on {subject_kind}"
_GATE = "{kind} {id} fails its panel gate: {reason}"
_STALE = "{subject_kind} {subject_id} changed during its review"
_NOT_SUBMITTED = "its head is not SUBMIT"
_FAILS = "its AS_KNOWN claim check does not pass"
_SETTLED = "it is decided, its item has an owner decision, or its amount source is invalid"
_NOT_OPEN = "its queue item is not open"


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
    catalog: SourceCatalog,
    snapshots: SnapshotStore,
) -> DecisionRecord:
    """Decide one report version or disposition proposal by the reviewer's verdict, as the
    pool's (panel) role; a version's claims are checked with ``catalog`` and ``snapshots``."""
    if subject_kind not in _VERDICTS:
        raise DecisionRefusedError(_NOT_PANEL.format(subject_kind=subject_kind))
    check = partial(approval_check, catalog=catalog, snapshots=snapshots)
    as_of = overlay_boundary(pool) if subject_kind is P else None
    with pool.connection() as conn, conn.cursor() as cursor:
        text, gated, _ = _gate(cursor, subject_kind, subject_id, as_of, check)
    output = reviewer.review(text, gated[0])
    kind = verdict_decision(subject_kind, output.verdict)
    with pool.connection() as conn, conn.transaction(), conn.cursor() as cursor:
        lock_queue(cursor)
        cursor.execute(_LOCK, (subject_kind.value, subject_id))
        now = cursor.execute(_NOW).fetchone()
        assert now is not None
        try:
            _, final, validation = _gate(cursor, subject_kind, subject_id, now[0], check)
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
    check: Callable[[Cursor[Any], int], Validation],
) -> tuple[str, tuple[str, object], Validation | None]:
    """The reviewed text, the gated state (digest, a version's check result) and a version's
    passing check if every D10 gate holds, else refuse. A proposal's overlay is read at
    ``as_of``."""
    digest = store.subject_digest(cursor, subject_kind, subject_id)
    head = store.chain_head(cursor, subject_kind, subject_id)
    if subject_kind is V:
        if head is None or head.kind is not DecisionKind.SUBMIT:
            raise _refused(subject_kind, subject_id, _NOT_SUBMITTED)
        validation = check(cursor, subject_id)
        if not passes(validation, digest):
            raise _refused(subject_kind, subject_id, _FAILS)
        draft = store.read_version(cursor, subject_id)
        result = validation.model_dump(exclude={"overlay_position"})
        return narrative(draft.sections, draft.claims).decode(), (digest, result), validation
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
