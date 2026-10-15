"""Deterministic narrative export of one report version (ledger spec §3 narrative; P2), and its
separate status note (plan D5, D3).

The bytes are the stored sections with their placeholders filled from the stored claims. Status
and decisions never enter, so a status change leaves the export unchanged, and an imported
version's export hashes to its content hash. The status note derives status, decisions, the
latest validation and the revalidation flags at read time and carries no narrative text.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, LiteralString

from psycopg import Cursor
from psycopg.rows import dict_row
from pydantic import BaseModel, ConfigDict

from fundamentals.contracts.ledger import ClaimState, ReportKind
from fundamentals.contracts.memory import RetrievedItem
from fundamentals.ledger import store
from fundamentals.ledger.display import narrative
from fundamentals.ledger.lifecycle import version_status

# Each version with its stock, report and chain position (root 1). A report's chain is linear
# with increasing ids (0012), so a version's position is its rank by id within its report.
_VERSIONS: LiteralString = """SELECT v.id AS version_id, r.entity_id, e.entity_key AS stock,
    r.period, r.kind AS report_kind,
    (SELECT count(*) FROM eqos.report_versions p WHERE p.report_id = v.report_id AND p.id <= v.id)
        AS position
FROM eqos.report_versions v JOIN eqos.reports r ON r.id = v.report_id
JOIN eqos.reporting_entities e ON e.id = r.entity_id
WHERE r.entity_id = %s ORDER BY r.period, r.kind, position"""
_ENTITY: LiteralString = "SELECT id FROM eqos.reporting_entities WHERE entity_key = %s"
_DECISIONS: LiteralString = (
    "SELECT kind, decider, recorded_at FROM eqos.decisions "
    "WHERE subject_kind = 'REPORT_VERSION' AND subject_id = %s ORDER BY sequence"
)
_CREATOR: LiteralString = "SELECT creator FROM eqos.validations WHERE id = %s"
_UNKNOWN = "unknown stock {stock!r}"
_NONE = "none"
_TITLE = "# {stock} {period} {report_kind} v{position}"
_IDENTITY = "- version: {version_id}\n- chain position: {position}\n- status: {status}"
_DECISION = "{n}. {kind} by {decider} at {recorded_at}"
_VALIDATION = "- id: {id}\n- mode: {mode}\n- creator: {creator}\n- version-level states: {states}"
_CLAIM = "- {key}: {state}"
_FLAG = "- memory item {id}: {statement}"
_SECTION = "## {heading}\n\n{body}"
_HEADINGS = ("Decisions", "Latest validation", "Untrusted claims", "Revalidation flags")


class VersionIdentity(BaseModel):
    """A report version's stock, report and chain position (root 1)."""

    model_config = ConfigDict(frozen=True)

    version_id: int
    entity_id: int
    stock: str
    period: str
    report_kind: ReportKind
    position: int


def export_version(cursor: Cursor[Any], version_id: int) -> bytes:
    """The version's narrative bytes, as its content hash was computed."""
    draft = store.read_version(cursor, version_id)
    return narrative(draft.sections, draft.claims)


def stock_entity(cursor: Cursor[Any], stock: str) -> int:
    """The stock's reporting entity id; an unknown stock raises ``LookupError``."""
    found = cursor.execute(_ENTITY, (stock,)).fetchall()
    if not found:
        raise LookupError(_UNKNOWN.format(stock=stock))
    return int(found[0][0])


def stock_versions(cursor: Cursor[Any], entity_id: int) -> tuple[VersionIdentity, ...]:
    """Every version of the entity's reports, by period, kind and chain position."""
    with cursor.connection.cursor(row_factory=dict_row) as own:
        rows = own.execute(_VERSIONS, (entity_id,)).fetchall()
    return tuple(VersionIdentity.model_validate(row) for row in rows)


def status_note(
    cursor: Cursor[Any], identity: VersionIdentity, promoted: Sequence[RetrievedItem]
) -> str:
    """The version's Markdown status note: identity, derived status, decisions in order, latest
    validation, untrusted claims and the ``promoted`` items citing it that need revalidation."""
    version_id = identity.version_id
    status = version_status(cursor, version_id)
    with cursor.connection.cursor(row_factory=dict_row) as own:
        decisions = own.execute(_DECISIONS, (version_id,)).fetchall()
    check = store.latest_validation(cursor, version_id)
    validation, untrusted = [_NONE], [_NONE]
    if check is not None:
        ((creator,),) = cursor.execute(_CREATOR, (check.id,)).fetchall()
        states = ", ".join(check.version_states) or _NONE
        validation = [
            _VALIDATION.format(id=check.id, mode=check.mode, creator=creator, states=states)
        ]
        untrusted = [
            _CLAIM.format(key=key, state=state)
            for key, state in check.claim_states
            if state is not ClaimState.MATCH
        ] or [_NONE]
    flags = [
        _FLAG.format(id=item.id, statement=item.statement)
        for item in promoted
        if item.needs_revalidation and any(ref.version_id == version_id for ref in item.supports)
    ] or [_NONE]
    bodies = (
        [_DECISION.format(n=n, **row) for n, row in enumerate(decisions, 1)] or [_NONE],
        validation,
        untrusted,
        flags,
    )
    parts = [
        _TITLE.format(**identity.model_dump()),
        _IDENTITY.format(status=status, **identity.model_dump()),
        *(
            _SECTION.format(heading=h, body="\n".join(b))
            for h, b in zip(_HEADINGS, bodies, strict=True)
        ),
    ]
    return "\n\n".join(parts) + "\n"
