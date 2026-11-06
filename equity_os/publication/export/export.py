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

from equity_os.contracts.publication.ledger import ClaimState, ReportKind
from equity_os.contracts.storage.memory import RetrievedItem
from equity_os.contracts.verification.vendor_first import AdmissionLabel
from equity_os.publication.approval.lifecycle import version_status
from equity_os.publication.checking.citation_admission import latest
from equity_os.publication.drafting.display import narrative
from equity_os.storage.records import store

# Each sealed version with its stock, report, chain position (root 1) and stored hash. A report's
# chain is linear with increasing ids (0012), so a version's position is its rank by id within
# its report. A draft's content is not yet bound to its hash (plan D5, V6).
_VERSIONS: LiteralString = """SELECT v.id AS version_id, r.entity_id, e.entity_key AS stock,
    r.period, r.kind AS report_kind, v.content_hash,
    (SELECT count(*) FROM eqos.report_versions p WHERE p.report_id = v.report_id AND p.id <= v.id)
        AS position
FROM eqos.report_versions v JOIN eqos.reports r ON r.id = v.report_id
JOIN eqos.reporting_entities e ON e.id = r.entity_id
WHERE r.entity_id = %s AND EXISTS (SELECT 1 FROM eqos.decisions d
    WHERE d.subject_kind = 'REPORT_VERSION' AND d.subject_id = v.id
        AND d.kind IN ('SUBMIT', 'IMPORT_SEAL'))
ORDER BY r.period, r.kind, position"""
_ENTITY: LiteralString = "SELECT id FROM eqos.reporting_entities WHERE entity_key = %s"
_DECISIONS: LiteralString = (
    "SELECT kind, decider, recorded_at FROM eqos.decisions "
    "WHERE subject_kind = 'REPORT_VERSION' AND subject_id = %s ORDER BY sequence"
)
_CREATOR: LiteralString = "SELECT creator FROM eqos.validations WHERE id = %s"
# Each claim's vendor capture that is no longer held (expired, or its vendor's licence ended), at
# its earliest date (VENDOR-1 §6.9).
_EXPIRED: LiteralString = """SELECT claim_key, 'vendor source expired' AS note, min(at) AS at
FROM (SELECT k.claim_key, least(l.ended_at, s.recorded_at) AS at FROM eqos.numeric_claims k
    CROSS JOIN LATERAL unnest(eqos.row_captures('numeric_claims', to_jsonb(k))) x(capture)
    JOIN eqos.capture_refs c ON c.id = x.capture
    LEFT JOIN eqos.licence_ends l ON l.source_id = c.source_id
    LEFT JOIN LATERAL (SELECT state, recorded_at FROM eqos.capture_states
        WHERE capture_ref_id = c.id ORDER BY id DESC LIMIT 1) s
        ON s.state NOT IN ('RETAINED', 'RESTORED')
    WHERE k.version_id = %(version)s AND eqos.is_vendor_source(c.source_id)) expired
WHERE at IS NOT NULL GROUP BY claim_key"""
# Each claim's admissions under the version's pinned runs, of its fact (operand null) or of an
# operand its trace reaches, with the version's cutoff and their class's earliest counterexample.
_ADMISSIONS: LiteralString = """WITH RECURSIVE reach(claim_key, trace) AS (
    SELECT claim_key, calculation_trace_id FROM eqos.numeric_claims
        WHERE version_id = %(version)s AND calculation_trace_id IS NOT NULL
    UNION SELECT r.claim_key, o.operand_trace_id FROM reach r
        JOIN eqos.calculation_trace_operands o ON o.calculation_trace_id = r.trace
        WHERE o.operand_trace_id IS NOT NULL)
SELECT DISTINCT k.claim_key, o.interpretation_id AS operand, a.id, a.overlay_position, a.label,
    v.knowledge_cutoff, (SELECT min(x.recorded_at) FROM eqos.vendor_counterexamples x
        WHERE x.class_digest = a.class_digest) AS contradicted
FROM eqos.numeric_claims k JOIN eqos.report_versions v ON v.id = k.version_id
JOIN eqos.fact_admissions a ON a.run_id = ANY(v.pinned_run_ids)
LEFT JOIN (reach r JOIN eqos.calculation_trace_operands o ON o.calculation_trace_id = r.trace)
    ON r.claim_key = k.claim_key AND o.interpretation_id = a.interpretation_id
WHERE k.version_id = %(version)s AND ((a.fact_origin, a.fact_origin_id)
    = (k.fact_origin, k.fact_origin_id) OR o.interpretation_id IS NOT NULL)"""
_CONTRADICTED = "class later contradicted by a filing on"
_UNKNOWN = "unknown stock {stock!r}"
_NONE = "none"
_TITLE = "# {stock} {period} {report_kind} v{position}"
_IDENTITY = "- version: {version_id}\n- chain position: {position}\n- status: {status}"
_DECISION = "{n}. {kind} by {decider} at {recorded_at}"
_VALIDATION = "- id: {id}\n- mode: {mode}\n- creator: {creator}\n- version-level states: {states}"
_CLAIM = "- {key}: {state}"
_FLAG = "- memory item {id}: {statement}"
_NOTE = "- {claim_key}: {note} {at}"
_SECTION = "## {heading}\n\n{body}"
_HEADINGS = (
    "Decisions",
    "Latest validation",
    "Untrusted claims",
    "Revalidation flags",
    "Source notes",
)


class VersionIdentity(BaseModel):
    """A report version's stock, report, chain position (root 1) and stored content hash."""

    model_config = ConfigDict(frozen=True)

    version_id: int
    entity_id: int
    stock: str
    period: str
    report_kind: ReportKind
    position: int
    content_hash: str


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
    """Every sealed version of the entity's reports, by period, kind and chain position."""
    with cursor.connection.cursor(row_factory=dict_row) as own:
        rows = own.execute(_VERSIONS, (entity_id,)).fetchall()
    return tuple(VersionIdentity.model_validate(row) for row in rows)


def status_note(
    cursor: Cursor[Any], identity: VersionIdentity, promoted: Sequence[RetrievedItem]
) -> str:
    """The version's Markdown status note: identity, derived status, decisions in order, latest
    validation, untrusted claims, the ``promoted`` items citing it that need revalidation and
    the later notes on its admitted facts' sources."""
    version_id = identity.version_id
    status = version_status(cursor, version_id)
    with cursor.connection.cursor(row_factory=dict_row) as own:
        decisions = own.execute(_DECISIONS, (version_id,)).fetchall()
        notes = own.execute(_EXPIRED, {"version": version_id}).fetchall()
        admissions = own.execute(_ADMISSIONS, {"version": version_id}).fetchall()
    notes = sorted(notes + _contradicted(admissions), key=lambda n: (n["claim_key"], n["note"]))
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
        [_NOTE.format(**row) for row in notes] or [_NONE],
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


def _contradicted(admissions: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """Per claim, the earliest counterexample of an unchecked class authorising its fact or an
    operand at the version's cutoff (the admission citation authority picks, ``latest``)."""
    groups: dict[tuple[str, int | None], list[dict[str, Any]]] = {}
    for row in admissions:
        groups.setdefault((row["claim_key"], row["operand"]), []).append(row)
    earliest: dict[str, Any] = {}
    for (claim_key, _), group in groups.items():
        authority = latest(group, group[0]["knowledge_cutoff"])
        if authority is None or authority["label"] == AdmissionLabel.CHECKED_AGAINST_FILING:
            continue
        if (at := authority["contradicted"]) is not None:
            earliest[claim_key] = min(at, earliest.get(claim_key, at))
    return [{"claim_key": k, "note": _CONTRADICTED, "at": at} for k, at in earliest.items()]
