"""Report version lifecycle: status, submit, claim check and decisions (ledger spec §1; plan D3,
D4, D11, D12).

Status is derived from the decision log, never stored (P1). Each command runs in one
transaction that takes the subject lock (after the queue lock, for a disposition proposal, a
memory item, an approval, a withdrawal or a validation; plan D4 M4) before any read it decides
on; the checks here give a readable refusal, and the decision trigger stays authoritative. An
approval binds only the check its decider makes in the deciding transaction; a runtime
``validate`` is advisory. Accepting a proposal appends its disposition with the stored amount.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime
from functools import partial
from typing import Any, LiteralString

from psycopg import Cursor
from psycopg_pool import ConnectionPool

from fundamentals.compare.queue import insert_disposition, lock_queue, overlay_boundary
from fundamentals.contracts.evidence import RunMode
from fundamentals.contracts.ledger import (
    CitationKind,
    ClaimState,
    DeciderRole,
    DecisionKind,
    DecisionRecord,
    GuidanceContract,
    PolicyValue,
    ResolvedCitation,
    SubjectKind,
    Validation,
    VersionDraft,
    VersionStatus,
)
from fundamentals.contracts.review_queue import DispositionKind
from fundamentals.contracts.snapshot import canonical_sha256
from fundamentals.contracts.source_catalog import SourceCatalog
from fundamentals.ledger import store
from fundamentals.ledger.citations import bound_contract, resolve_citation, resolve_location
from fundamentals.ledger.claim_check import check_claim
from fundamentals.ledger.display import content_hash
from fundamentals.ledger.numeral_scan import scan_section
from fundamentals.store.snapshot_store import SnapshotStore

CHECKER_VERSION = "ledger-claim-check-v1"
V, P = SubjectKind.REPORT_VERSION, SubjectKind.DISPOSITION_PROPOSAL
M, W = SubjectKind.MEMORY_ITEM, SubjectKind.WATCHLIST
DECISION_REF = "decision:{decision_id}"
_DECIDERS = frozenset({DeciderRole.PANEL, DeciderRole.OWNER})
_ANY_HEAD = frozenset({None, *DecisionKind})
_SETTLE = (DecisionKind.ACCEPT, DecisionKind.REJECT)
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
    # 0013: one decision per proposal (panel or owner) and per interpretation (owner only).
    **{(P, kind): (_DECIDERS, frozenset({None})) for kind in _SETTLE},
    **{
        (SubjectKind.INTERPRETATION, kind): (frozenset({DeciderRole.OWNER}), frozenset({None}))
        for kind in _SETTLE
    },
    # 0016 (plan D4, M2): promotion or rejection of a candidate; retirement by the owner only.
    **{
        (M, kind): (_DECIDERS, frozenset({None}))
        for kind in (DecisionKind.PROMOTE, DecisionKind.REJECT_CANDIDATE)
    },
    (M, DecisionKind.RETIRE): (frozenset({DeciderRole.OWNER}), frozenset({DecisionKind.PROMOTE})),
    # 0026 (plan D7, O10): the owner adds a stock, removes it, and may add it again.
    (W, DecisionKind.ADD): (frozenset({DeciderRole.OWNER}), frozenset({None, DecisionKind.REMOVE})),
    (W, DecisionKind.REMOVE): (frozenset({DeciderRole.OWNER}), frozenset({DecisionKind.ADD})),
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
_NOW: LiteralString = "SELECT eqos.store_now()"
_ROLE: LiteralString = "SELECT current_user"
_ENTITY: LiteralString = "SELECT entity_id FROM eqos.reports WHERE id = %s"
_PROPOSAL: LiteralString = (
    "SELECT item_id, kind, reason, eqos.proposal_amount(id) FROM eqos.disposition_proposals "
    "WHERE id = %s"
)
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
_UNBOUND = "approval must bind a passing AS_KNOWN check of version {version_id} by its decider"
_STALE_HASH = "version {version_id} content hash does not match its narrative"
_OPEN_PREDECESSOR = "version {version_id}'s predecessor {predecessor_id} is {status}"
_BLOCKED = "version {version_id} has version-level findings: {states}"
_UNBINDABLE = "version {version_id}: only an import binds guidance, and only to its quote claims"


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
        draft = _sound(cursor, version_id)
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
        return append_decision(cursor, V, version_id, DecisionKind.SUBMIT)


def validate(
    pool: ConnectionPool,
    version_id: int,
    *,
    mode: RunMode,
    catalog: SourceCatalog,
    snapshots: SnapshotStore,
    bound: Mapping[str, GuidanceContract] | None = None,
) -> Validation:
    """Check every claim at the current overlay boundary and append the validation (advisory:
    no approval binds it). ``bound`` (imports only) is, per quote claim key, the guidance
    contract its import sources bind."""
    boundary = overlay_boundary(pool)
    with pool.connection() as conn, conn.transaction(), conn.cursor() as cursor:
        lock_queue(cursor)
        cursor.execute(_LOCK, (V.value, version_id))
        validation = check_version(
            cursor,
            version_id,
            mode=mode,
            boundary=boundary,
            catalog=catalog,
            snapshots=snapshots,
            bound=bound,
        )
        validation_id = store.insert_validation(cursor, validation)
        stored = store.latest_validation(cursor, version_id)
    assert stored is not None and stored.id == validation_id
    return stored


def approval_check(
    cursor: Cursor[Any], version_id: int, *, catalog: SourceCatalog, snapshots: SnapshotStore
) -> Validation:
    """The ``AS_KNOWN`` check an approval binds (D4), made in the deciding transaction under
    the queue and subject locks at that store-clock time; refuses a narrative that does not
    reproduce the version's content hash."""
    lock_queue(cursor)
    cursor.execute(_LOCK, (V.value, version_id))
    row = cursor.execute(_NOW).fetchone()
    assert row is not None
    _sound(cursor, version_id)
    return check_version(
        cursor,
        version_id,
        mode=RunMode.AS_KNOWN,
        boundary=row[0],
        catalog=catalog,
        snapshots=snapshots,
    )


def passes(validation: Validation, digest: str) -> bool:
    """Whether a check of the version sealed as ``digest`` can bind its approval (D4)."""
    return (
        validation.sealed_digest == digest
        and not validation.version_states
        and all(state in PASSING for _, state in validation.claim_states)
    )


def check_version(
    cursor: Cursor[Any],
    version_id: int,
    *,
    mode: RunMode,
    boundary: datetime,
    catalog: SourceCatalog,
    snapshots: SnapshotStore,
    bound: Mapping[str, GuidanceContract] | None = None,
) -> Validation:
    """Every claim's state and the sections' version-level states at ``boundary``, in the
    caller's transaction under its subject lock; nothing is written. A drafted quote claim is
    compared with the contract a sealed import binds to its quote (plan D4, M9)."""
    bound = bound or {}
    draft = store.read_version(cursor, version_id)
    row = cursor.execute(_ENTITY, (draft.report_id,)).fetchone()
    assert row is not None
    imported = bool(draft.import_sources)
    quotes = {c.claim_key for c in draft.claims if c.citation.kind is CitationKind.SOURCE_QUOTE}
    if bound and (not imported or bound.keys() - quotes):
        raise DecisionRefusedError(_UNBINDABLE.format(version_id=version_id))
    resolved = {
        claim.claim_key: _bind(
            resolve_citation(
                cursor,
                claim,
                entity_id=row[0],
                overlay_position=boundary,
                catalog=catalog,
                snapshots=snapshots,
                run_ids=draft.pinned_run_ids,
            ),
            bound.get(claim.claim_key)
            if imported or claim.citation.kind is not CitationKind.SOURCE_QUOTE
            else bound_contract(cursor, claim, row[0]),
        )
        for claim in draft.claims
    }
    resolves = partial(resolve_location, cursor, catalog=catalog, snapshots=snapshots)
    found = (
        set()
        if imported
        else {state for s in draft.sections for state in scan_section(s.body, resolves=resolves)}
    )
    return Validation(
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


def _sound(cursor: Cursor[Any], version_id: int) -> VersionDraft:
    """The stored version, if its narrative reproduces its declared content hash; else refuse."""
    draft = store.read_version(cursor, version_id)
    if content_hash(draft.sections, draft.claims) != draft.content_hash:
        raise DecisionRefusedError(_STALE_HASH.format(version_id=version_id))
    return draft


def _bind(
    resolved: ResolvedCitation | None, contract: GuidanceContract | None
) -> ResolvedCitation | None:
    """``resolved`` with its bound guidance contract; an unresolved citation stays unresolved."""
    if resolved is None or contract is None:
        return resolved
    return resolved.model_copy(update={"guidance": contract})


def decide(
    pool: ConnectionPool,
    *,
    subject_kind: SubjectKind,
    subject_id: int,
    kind: DecisionKind,
    ruling: str,
    policy: PolicyValue | None = None,
    catalog: SourceCatalog | None = None,
    snapshots: SnapshotStore | None = None,
    claims: tuple[str, ...] = (),
) -> DecisionRecord:
    """Record one decision with its verbatim ruling as the pool's role; an ``APPROVE`` of a
    version binds the check this transaction makes with ``catalog`` and ``snapshots``, which
    must pass (D4); ``claims`` are the keys a ``REQUEST_CHANGES`` rejects (PREP-5)."""
    with pool.connection() as conn, conn.transaction(), conn.cursor() as cursor:
        return record_decision(
            cursor,
            subject_kind=subject_kind,
            subject_id=subject_id,
            kind=kind,
            ruling=ruling,
            policy=policy,
            catalog=catalog,
            snapshots=snapshots,
            claims=claims,
        )


def record_decision(
    cursor: Cursor[Any],
    *,
    subject_kind: SubjectKind,
    subject_id: int,
    kind: DecisionKind,
    ruling: str,
    policy: PolicyValue | None = None,
    catalog: SourceCatalog | None = None,
    snapshots: SnapshotStore | None = None,
    claims: tuple[str, ...] = (),
    before_insert: Callable[[], None] = lambda: None,
) -> DecisionRecord:
    """``decide`` in the caller's transaction, so later inserts share the decision's commit;
    ``before_insert`` runs after every check, just before the first insert."""
    approving = subject_kind is V and kind is DecisionKind.APPROVE
    validation = (
        approval_check(cursor, subject_id, catalog=catalog, snapshots=snapshots)
        if approving and catalog is not None and snapshots is not None
        else None
    )
    return append_decision(
        cursor,
        subject_kind,
        subject_id,
        kind,
        validation=validation,
        ruling=ruling,
        policy=policy,
        rejected_claims=claims,
        before_insert=before_insert,
    )


def append_decision(
    cursor: Cursor[Any],
    subject_kind: SubjectKind,
    subject_id: int,
    kind: DecisionKind,
    *,
    validation: Validation | None = None,
    before_insert: Callable[[], None] = lambda: None,
    **fields: Any,
) -> DecisionRecord:
    """Pre-check D3 under the queue lock (proposals, memory items, withdrawals) and the subject
    lock, then insert; an ``APPROVE`` first appends ``validation``, the decider's own passing
    check (D4), and an ``ACCEPT`` on a proposal appends its disposition (D11)."""
    if subject_kind in (P, M) or kind is DecisionKind.WITHDRAW:
        lock_queue(cursor)
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
    if subject_kind is not SubjectKind.REPORT:
        fields["sealed_digest"] = store.subject_digest(cursor, subject_kind, subject_id)
    approving = subject_kind is V and kind is DecisionKind.APPROVE
    if approving and (validation is None or not passes(validation, fields["sealed_digest"])):
        raise DecisionRefusedError(_UNBOUND.format(version_id=subject_id))
    before_insert()
    if approving and validation is not None:
        fields["validation_id"] = store.insert_validation(cursor, validation)
    decision = store.insert_decision(
        cursor,
        subject_kind=subject_kind,
        subject_id=subject_id,
        kind=kind,
        predecessor_id=None if head is None else head.id,
        **fields,
    )
    if subject_kind is P and kind is DecisionKind.ACCEPT:
        row = cursor.execute(_PROPOSAL, (subject_id,)).fetchone()
        assert row is not None
        insert_disposition(
            cursor,
            item_id=row[0],
            kind=DispositionKind(row[1]),
            reason=row[2],
            decider=decision.decider.value,
            evidence_ref=DECISION_REF.format(decision_id=decision.id),
            explained_amount=row[3],
        )
    return decision
