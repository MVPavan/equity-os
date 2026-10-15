"""Report version lifecycle: status, submit, claim check and decisions (ledger spec §1; plan D3,
D4, D12).

Status is derived from the decision log, never stored (P1). Each command runs in one
transaction that takes the subject lock before any read it decides on; the checks here give a
readable refusal, and the decision trigger stays authoritative.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from functools import partial
from typing import Any, LiteralString

from psycopg import Cursor
from psycopg_pool import ConnectionPool

from fundamentals.compare.queue import overlay_boundary
from fundamentals.contracts.evidence import RunMode
from fundamentals.contracts.ledger import (
    ClaimState,
    DeciderRole,
    DecisionKind,
    DecisionRecord,
    PolicyValue,
    ResolvedCitation,
    SubjectKind,
    Validation,
    VersionStatus,
)
from fundamentals.contracts.snapshot import canonical_sha256
from fundamentals.contracts.source_catalog import SourceCatalog
from fundamentals.ledger import store
from fundamentals.ledger.citations import resolve_citation, resolve_location
from fundamentals.ledger.claim_check import check_claim
from fundamentals.ledger.display import content_hash
from fundamentals.ledger.numeral_scan import scan_section
from fundamentals.store.snapshot_store import SnapshotStore

CHECKER_VERSION = "ledger-claim-check-v1"
V = SubjectKind.REPORT_VERSION
_DECIDERS = frozenset({DeciderRole.PANEL, DeciderRole.OWNER})
_ANY_HEAD = frozenset({None, *DecisionKind})
# D3: who may make each decision, after which chain head. The trigger also holds the import
# rules (import sources, same transaction) and refuses WITHDRAW after IMPORT_SEAL unless the
# version is superseded.
TRANSITIONS: dict[
    tuple[SubjectKind, DecisionKind], tuple[frozenset[DeciderRole], frozenset[DecisionKind | None]]
] = {
    (V, DecisionKind.SUBMIT): (frozenset({DeciderRole.RUNTIME}), frozenset({None})),
    (V, DecisionKind.IMPORT_SEAL): (frozenset({DeciderRole.PANEL}), frozenset({None})),
    (V, DecisionKind.IMPORTED_APPROVAL): (
        frozenset({DeciderRole.PANEL}),
        frozenset({DecisionKind.IMPORT_SEAL}),
    ),
    **{
        (V, kind): (_DECIDERS, frozenset({DecisionKind.SUBMIT}))
        for kind in (DecisionKind.APPROVE, DecisionKind.REQUEST_CHANGES, DecisionKind.REJECT)
    },
    (V, DecisionKind.WITHDRAW): (
        frozenset({DeciderRole.OWNER}),
        frozenset({DecisionKind.APPROVE, DecisionKind.IMPORTED_APPROVAL, DecisionKind.IMPORT_SEAL}),
    ),
    (SubjectKind.REPORT, DecisionKind.SET_POLICY): (frozenset({DeciderRole.OWNER}), _ANY_HEAD),
}
_HEAD_STATUS = {
    None: VersionStatus.DRAFT,
    DecisionKind.SUBMIT: VersionStatus.IN_REVIEW,
    DecisionKind.IMPORT_SEAL: VersionStatus.HISTORICAL,
    DecisionKind.IMPORTED_APPROVAL: VersionStatus.APPROVED,
    DecisionKind.APPROVE: VersionStatus.APPROVED,
    DecisionKind.REQUEST_CHANGES: VersionStatus.CHANGES_REQUESTED,
    DecisionKind.REJECT: VersionStatus.REJECTED,
    DecisionKind.WITHDRAW: VersionStatus.WITHDRAWN,
}
SUPERSEDABLE = frozenset({VersionStatus.APPROVED, VersionStatus.HISTORICAL})
OPEN = frozenset({VersionStatus.DRAFT, VersionStatus.IN_REVIEW})
PASSING = frozenset({ClaimState.MATCH, ClaimState.MATCH_UNTRUSTED})
_ROLES = {
    "eqos_runtime": DeciderRole.RUNTIME,
    "eqos_panel": DeciderRole.PANEL,
    "eqos_owner": DeciderRole.OWNER,
}
_LOCK: LiteralString = "SELECT eqos.lock_subject(%s, %s)"
_ROLE: LiteralString = "SELECT current_user"
_ENTITY: LiteralString = "SELECT entity_id FROM eqos.reports WHERE id = %s"
# The version's head and whether a descendant's chain holds an approval, both as of a time.
_STATUS: LiteralString = """WITH RECURSIVE descendants (id) AS (
    SELECT id FROM eqos.report_versions WHERE predecessor_id = %(version)s
    UNION ALL
    SELECT v.id FROM eqos.report_versions v JOIN descendants d ON v.predecessor_id = d.id
), known AS (
    SELECT * FROM eqos.decisions WHERE subject_kind = 'REPORT_VERSION'
        AND (%(as_of)s::timestamptz IS NULL OR recorded_at <= %(as_of)s::timestamptz)
)
SELECT (SELECT kind FROM known WHERE subject_id = %(version)s ORDER BY sequence DESC LIMIT 1),
    EXISTS (SELECT 1 FROM known WHERE kind IN ('APPROVE', 'IMPORTED_APPROVAL')
            AND subject_id IN (SELECT id FROM descendants))"""
_ILLEGAL = "illegal decision: {kind} by {role} on {subject_kind} {subject_id} after {head}"
_UNBOUND = "approval must bind the latest passing AS_KNOWN validation of version {version_id}"
_STALE_HASH = "version {version_id} content hash does not match its narrative"
_OPEN_PREDECESSOR = "version {version_id}'s predecessor {predecessor_id} is {status}"
_BLOCKED = "version {version_id} has version-level findings: {states}"


class DecisionRefusedError(ValueError):
    """A lifecycle command refused before writing: illegal, unbound or blocked."""


def version_status(
    cursor: Cursor[Any], version_id: int, *, as_of: datetime | None = None
) -> VersionStatus:
    """The version's status from the decision log, as of ``as_of`` (default: now)."""
    row = cursor.execute(_STATUS, {"version": version_id, "as_of": as_of}).fetchone()
    assert row is not None
    status = _HEAD_STATUS[None if row[0] is None else DecisionKind(row[0])]
    return VersionStatus.SUPERSEDED if row[1] and status in SUPERSEDABLE else status


def submit(
    pool: ConnectionPool, version_id: int, *, catalog: SourceCatalog, snapshots: SnapshotStore
) -> DecisionRecord:
    """Seal a draft for review: its content hash holds, its predecessor is terminal and no
    section raises a version-level state."""
    with pool.connection() as conn, conn.transaction(), conn.cursor() as cursor:
        cursor.execute(_LOCK, (V.value, version_id))
        draft = store.read_version(cursor, version_id)
        if content_hash(draft.sections, draft.claims) != draft.content_hash:
            raise DecisionRefusedError(_STALE_HASH.format(version_id=version_id))
        if draft.predecessor_id is not None:
            status = version_status(cursor, draft.predecessor_id)
            if status in OPEN:
                raise DecisionRefusedError(
                    _OPEN_PREDECESSOR.format(
                        version_id=version_id, predecessor_id=draft.predecessor_id, status=status
                    )
                )
        resolves = partial(resolve_location, cursor, catalog=catalog, snapshots=snapshots)
        found = {state for s in draft.sections for state in scan_section(s.body, resolves=resolves)}
        if found:
            states = ", ".join(sorted(found))
            raise DecisionRefusedError(_BLOCKED.format(version_id=version_id, states=states))
        return _decide(cursor, V, version_id, DecisionKind.SUBMIT)


def validate(
    pool: ConnectionPool,
    version_id: int,
    *,
    mode: RunMode,
    catalog: SourceCatalog,
    snapshots: SnapshotStore,
    bound: Mapping[str, ResolvedCitation] | None = None,
) -> Validation:
    """Check every claim at the current overlay boundary and append the validation. ``bound``
    (imports only) replaces, per claim key, the resolved fields its source binds: a quote's
    parsed guidance contract, a self-cited policy's parsed source field."""
    boundary = overlay_boundary(pool)
    with pool.connection() as conn, conn.transaction(), conn.cursor() as cursor:
        cursor.execute(_LOCK, (V.value, version_id))
        draft = store.read_version(cursor, version_id)
        row = cursor.execute(_ENTITY, (draft.report_id,)).fetchone()
        assert row is not None
        imported = bool(draft.import_sources)
        resolved = {
            claim.claim_key: _bind(
                resolve_citation(
                    cursor,
                    claim,
                    entity_id=row[0],
                    overlay_position=boundary,
                    catalog=catalog,
                    snapshots=snapshots,
                ),
                (bound or {}).get(claim.claim_key),
            )
            for claim in draft.claims
        }
        resolves = partial(resolve_location, cursor, catalog=catalog, snapshots=snapshots)
        found = (
            set()
            if imported
            else {
                state for s in draft.sections for state in scan_section(s.body, resolves=resolves)
            }
        )
        validation = Validation(
            version_id=version_id,
            checker_version=CHECKER_VERSION,
            mode=mode,
            overlay_position=boundary,
            pinned_input_sha256=canonical_sha256(
                {k: None if r is None else r.model_dump(mode="json") for k, r in resolved.items()}
            ),
            sealed_digest=store.sealed_digest(cursor, version_id),
            claim_states=tuple(
                (
                    claim.claim_key,
                    check_claim(
                        claim,
                        resolved[claim.claim_key],
                        mode=mode,
                        cutoff=draft.knowledge_cutoff,
                        imported=imported,
                    ),
                )
                for claim in draft.claims
            ),
            version_states=tuple(sorted(found)),
        )
        validation_id = store.insert_validation(cursor, validation)
        stored = store.latest_validation(cursor, version_id)
    assert stored is not None and stored.id == validation_id
    return stored


def _bind(
    resolved: ResolvedCitation | None, bound: ResolvedCitation | None
) -> ResolvedCitation | None:
    """``resolved`` with the fields ``bound`` sets; an unresolved citation stays unresolved."""
    if resolved is None or bound is None:
        return resolved
    return resolved.model_copy(update={k: getattr(bound, k) for k in bound.model_fields_set})


def decide(
    pool: ConnectionPool,
    *,
    subject_kind: SubjectKind,
    subject_id: int,
    kind: DecisionKind,
    ruling: str,
    policy: PolicyValue | None = None,
) -> DecisionRecord:
    """Record one decision with its verbatim ruling as the pool's role; an ``APPROVE`` binds
    the version's latest validation, which must pass (D4)."""
    with pool.connection() as conn, conn.transaction(), conn.cursor() as cursor:
        return _decide(cursor, subject_kind, subject_id, kind, ruling=ruling, policy=policy)


def _decide(
    cursor: Cursor[Any],
    subject_kind: SubjectKind,
    subject_id: int,
    kind: DecisionKind,
    **fields: Any,
) -> DecisionRecord:
    """Pre-check D3 (and D4 for an approval) under the subject lock, then insert."""
    cursor.execute(_LOCK, (subject_kind.value, subject_id))
    head = store.chain_head(cursor, subject_kind, subject_id)
    head_kind = None if head is None else head.kind
    role_row = cursor.execute(_ROLE).fetchone()
    role = None if role_row is None else _ROLES.get(role_row[0])
    roles, heads = TRANSITIONS.get((subject_kind, kind), (frozenset(), frozenset()))
    unsuperseded_seal = (
        head_kind is DecisionKind.IMPORT_SEAL
        and kind is DecisionKind.WITHDRAW
        and version_status(cursor, subject_id) is not VersionStatus.SUPERSEDED
    )
    if role not in roles or head_kind not in heads or unsuperseded_seal:
        raise DecisionRefusedError(
            _ILLEGAL.format(
                kind=kind,
                role=role,
                subject_kind=subject_kind,
                subject_id=subject_id,
                head=head_kind or "nothing",
            )
        )
    if subject_kind is V:
        fields["sealed_digest"] = store.sealed_digest(cursor, subject_id)
    if subject_kind is V and kind is DecisionKind.APPROVE:
        fields["validation_id"] = _bound_validation(cursor, subject_id, fields["sealed_digest"])
    return store.insert_decision(
        cursor,
        subject_kind=subject_kind,
        subject_id=subject_id,
        kind=kind,
        predecessor_id=None if head is None else head.id,
        **fields,
    )


def _bound_validation(cursor: Cursor[Any], version_id: int, digest: str) -> int:
    """The latest validation's id if it can bind an approval (D4), else refuse."""
    latest = store.latest_validation(cursor, version_id)
    claims = {claim.claim_key for claim in store.read_version(cursor, version_id).claims}
    states = dict(latest.claim_states) if latest else {}
    if (
        latest is None
        or latest.id is None
        or latest.mode is not RunMode.AS_KNOWN
        or latest.sealed_digest != digest
        or latest.version_states
        or states.keys() != claims
        or not set(states.values()) <= PASSING
    ):
        raise DecisionRefusedError(_UNBOUND.format(version_id=version_id))
    return latest.id
