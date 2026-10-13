"""D1b Task 3 queue publication and temporal overlay integration tests."""

from __future__ import annotations

import hashlib
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta
from typing import Any

import psycopg
import pytest
from pg_evidence_schema_support import (
    NOW,
    _attempt,
    _insert,
    _interpretation,
    _occurrence,
    _read,
    _run_input,
    migrator,
    runtime,
    seeded,
)
from pg_support import PgTestDatabase
from psycopg import sql
from psycopg.types.json import Jsonb
from pydantic import ValidationError

from fundamentals.compare.approval_receipts import proposal_digest, subject_digest
from fundamentals.contracts.canonical import Basis, Representation, ValueKind
from fundamentals.contracts.comparison import ReasonCode, SourceRef, SourceRole
from fundamentals.contracts.measurement_key import DimensionSet, MeasurementKey, PeriodInterval
from fundamentals.contracts.observation import AccountingFramework
from fundamentals.contracts.review_queue import (
    QueueItemDraft,
    QueueOverlay,
    QueueSeverity,
)

__all__ = ["migrator", "runtime", "seeded"]

_QUEUE_TABLES = ("queue_items", "queue_item_inputs", "queue_run_items")


def _key(entity_id: int) -> MeasurementKey:
    return MeasurementKey(
        entity_id=entity_id,
        canonical_id="synthetic_metric",
        period=PeriodInterval.duration(date(2025, 7, 1), date(2025, 9, 30)),
        basis=Basis.CONSOLIDATED,
        framework=AccountingFramework.IND_AS,
        currency="INR",
        value_kind=ValueKind.CURRENCY_AMOUNT,
        dimensions=DimensionSet(),
    )


def _refs() -> tuple[SourceRef, ...]:
    return (
        SourceRef(source_role=SourceRole.FIRST_PARTY, representation=Representation.XBRL),
        SourceRef(source_role=SourceRole.REPORTED_COUNTERPART, representation=Representation.PDF),
    )


def _draft(
    ids: dict[str, int],
    *,
    pair_identity: str = "synthetic-pair",
    occurrence_ids: tuple[int, ...] = (),
    interpretation_ids: tuple[int, ...] | None = None,
    attempt_ids: tuple[int, ...] = (),
) -> QueueItemDraft:
    return QueueItemDraft(
        key=_key(ids["_entity"]),
        pair_identity=pair_identity,
        outcome="MISMATCH",
        severity=QueueSeverity.HIGH,
        routing_reason="SYNTHETIC_REVIEW",
        source_refs=_refs(),
        attempt_ids=attempt_ids,
        evidence_interpretation_ids=(
            (ids["interpretations"],) if interpretation_ids is None else interpretation_ids
        ),
        evidence_occurrence_ids=occurrence_ids,
    )


def _publish(
    conn: psycopg.Connection[Any], run_id: int, drafts: tuple[QueueItemDraft, ...]
) -> tuple[Any, ...]:
    from fundamentals.compare.queue import publish_queue_drafts

    with conn.transaction(), conn.cursor() as cursor:
        return publish_queue_drafts(cursor, run_id=run_id, drafts=drafts)


def _counts(conn: psycopg.Connection[Any]) -> tuple[int, ...]:
    counts = []
    for table in _QUEUE_TABLES:
        query = sql.SQL("SELECT count(*) FROM eqos.{}").format(sql.Identifier(table))
        row = conn.execute(query).fetchone()
        assert row is not None
        counts.append(int(row[0]))
    return tuple(counts)


def _add_run_inputs(
    conn: psycopg.Connection[Any],
    ids: dict[str, int],
    *,
    run_id: int | None = None,
) -> dict[str, int]:
    owner_run = ids["runs"] if run_id is None else run_id
    existing_occurrence = ids["occurrences"]
    existing_attempt = ids["acquisition_attempts"]
    if run_id is None:
        _insert(
            conn,
            "run_inputs",
            _run_input(owner_run, "OCCURRENCE", occurrence_id=existing_occurrence),
        )
        _insert(
            conn,
            "run_inputs",
            _run_input(owner_run, "ATTEMPT", attempt_id=existing_attempt),
        )
    else:
        for kind, column, evidence_id in (
            ("OCCURRENCE", "occurrence_id", existing_occurrence),
            ("INTERPRETATION", "interpretation_id", ids["interpretations"]),
            ("ATTEMPT", "attempt_id", existing_attempt),
        ):
            _insert(conn, "run_inputs", _run_input(owner_run, kind, **{column: evidence_id}))
    occurrence = _insert(
        conn,
        "occurrences",
        _occurrence(
            ids["_capture"],
            f"queue-evidence-{owner_run}",
            first_seen_at=NOW + timedelta(microseconds=2),
        ),
    )
    interpretation = _insert(
        conn,
        "interpretations",
        _interpretation(
            ids["_entity"],
            ids["_capture"],
            occurrence,
            input_digest=f"queue-interpretation-{owner_run}",
            canonical_id="synthetic_metric",
            mapping_entry_id=f"synthetic-entry-{owner_run}",
        ),
    )
    attempt_body = _attempt(ids["_entity"], ids["_capture"])
    attempt_body["input_sha256"] = hashlib.sha256(f"queue-attempt-{owner_run}".encode()).hexdigest()
    attempt = _insert(conn, "acquisition_attempts", attempt_body)
    for kind, column, evidence_id in (
        ("OCCURRENCE", "occurrence_id", occurrence),
        ("INTERPRETATION", "interpretation_id", interpretation),
        ("ATTEMPT", "attempt_id", attempt),
    ):
        _insert(conn, "run_inputs", _run_input(owner_run, kind, **{column: evidence_id}))
    return {
        "occurrence": occurrence,
        "interpretation": interpretation,
        "attempt": attempt,
    }


def _new_run(conn: psycopg.Connection[Any], label: str) -> int:
    digest = hashlib.sha256(label.encode()).hexdigest()
    return _insert(
        conn,
        "runs",
        {
            "identity_hash": digest,
            "cutoff": NOW,
            "mode": "AS_KNOWN",
            "status": "COMPLETE",
            "code_version": "queue-fixture",
            "manifest": Jsonb({"fixture": label}),
            "manifest_sha256": hashlib.sha256(f"manifest:{label}".encode()).hexdigest(),
        },
    )


def _link_existing_evidence(
    conn: psycopg.Connection[Any], ids: dict[str, int], run_id: int
) -> None:
    for kind, column, evidence_id in (
        ("OCCURRENCE", "occurrence_id", ids["occurrences"]),
        ("INTERPRETATION", "interpretation_id", ids["interpretations"]),
        ("ATTEMPT", "attempt_id", ids["acquisition_attempts"]),
    ):
        _insert(conn, "run_inputs", _run_input(run_id, kind, **{column: evidence_id}))


def _seed_rejected_receipt(conn: psycopg.Connection[Any], item_id: int) -> int:
    subject = _read(conn, "queue_items", item_id)
    proposed: dict[str, Any] = {
        "item_id": item_id,
        "kind": "MAPPING_FIX",
        "reason": "constructed rejection fixture",
        "proposer": "constructed-author",
        "evidence_ref": "constructed-only",
        "subject_sha256": subject_digest(subject),
        "explained_amount": None,
        "amount_trace_id": None,
    }
    proposed["proposal_sha256"] = proposal_digest(proposed)
    proposal_id = _insert(conn, "queue_disposition_proposals", proposed)
    raw = b"constructed rejection binding fixture, not an actual review or owner approval"
    evidence_sha = hashlib.sha256(raw).hexdigest()
    bound = {
        "subject_kind": "QUEUE_DISPOSITION",
        "subject_id": item_id,
        "proposal_id": proposal_id,
        "proposal_sha256": proposed["proposal_sha256"],
        "subject_sha256": proposed["subject_sha256"],
        "decision": "REJECT",
        "decider": "constructed-peer",
    }
    evidence_id = _insert(
        conn,
        "approval_review_evidence",
        {
            **bound,
            "evidence_sha256": evidence_sha,
            "evidence_document": Jsonb({"fixture": "SQL rejection binding only"}),
            "raw_evidence": raw,
            "evidence_origin": "INDEPENDENT_REVIEW",
        },
    )
    return _insert(
        conn,
        "approval_receipts",
        {
            **bound,
            "review_evidence_id": evidence_id,
            "review_evidence_sha256": evidence_sha,
        },
    )


def _seed_verified_synthetic_accept(
    conn: psycopg.Connection[Any],
    item_id: int,
    *,
    invalid_proof: str | None = None,
) -> int:
    """Create synthetic ACCEPT mechanics, optionally corrupting one verifier boundary."""
    subject = _read(conn, "queue_items", item_id)
    proposed: dict[str, Any] = {
        "item_id": item_id,
        "kind": "MAPPING_FIX",
        "reason": "constructed verifier-valid acceptance fixture",
        "proposer": "constructed-author",
        "evidence_ref": "constructed-verifier-only",
        "subject_sha256": subject_digest(subject),
        "explained_amount": None,
        "amount_trace_id": None,
    }
    if invalid_proof == "subject":
        proposed["subject_sha256"] = "0" * 64
    proposed["proposal_sha256"] = proposal_digest(proposed)
    if invalid_proof == "proposal":
        proposed["proposal_sha256"] = "1" * 64
    proposal_id = _insert(conn, "queue_disposition_proposals", proposed)
    raw = b"constructed verifier-valid binding; not an actual review or owner approval"
    evidence_sha = hashlib.sha256(
        b"different constructed bytes" if invalid_proof == "raw" else raw
    ).hexdigest()
    bound = {
        "subject_kind": "QUEUE_DISPOSITION",
        "subject_id": item_id,
        "proposal_id": proposal_id,
        "proposal_sha256": proposed["proposal_sha256"],
        "subject_sha256": proposed["subject_sha256"],
        "decision": "ACCEPT",
        "decider": "constructed-peer",
    }
    evidence_id = _insert(
        conn,
        "approval_review_evidence",
        {
            **bound,
            "evidence_sha256": evidence_sha,
            "evidence_document": Jsonb(
                {"fixture": "invalid authenticated document"}
                if invalid_proof == "document"
                else {
                    "origin": "INDEPENDENT_REVIEW",
                    "authenticated_producer_identity": "constructed-test-authenticator",
                    "evidence_ref": "constructed-verifier-only",
                    "decider": "constructed-peer",
                    "author": "constructed-author",
                    "decision": "ACCEPT",
                    "subject_sha256": proposed["subject_sha256"],
                    "proposal_sha256": proposed["proposal_sha256"],
                    "owner_amount": None,
                    "verbatim_owner_ruling": None,
                }
            ),
            "raw_evidence": raw,
            "evidence_origin": "INDEPENDENT_REVIEW",
        },
    )
    receipt_id = _insert(
        conn,
        "approval_receipts",
        {
            **bound,
            "review_evidence_id": evidence_id,
            "review_evidence_sha256": evidence_sha,
        },
    )
    return _insert(
        conn,
        "queue_dispositions",
        {
            "item_id": item_id,
            "proposal_id": proposal_id,
            "approval_receipt_id": receipt_id,
            "kind": proposed["kind"],
            "reason": proposed["reason"],
            "proposer": proposed["proposer"],
            "decider": "constructed-peer",
            "evidence_ref": proposed["evidence_ref"],
            "explained_amount": None,
            "amount_trace_id": None,
        },
    )


def _canonical_sha(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _clock(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="microseconds")


def test_queue_contract_defaults_keep_legacy_overlay_dump_and_require_evidence() -> None:
    overlay = QueueOverlay(
        run_id=1,
        recorded_position=0,
        as_of=datetime(2026, 1, 1, tzinfo=UTC),
    )

    legacy_document = overlay.model_dump(mode="json")
    assert "memberships" not in legacy_document
    assert "closure_failures" not in legacy_document
    with pytest.raises(ValidationError, match="typed evidence"):
        QueueItemDraft(
            key=_key(1),
            pair_identity="synthetic-pair",
            outcome="MISMATCH",
            severity=QueueSeverity.HIGH,
        )


@pytest.mark.pg
def test_digest_binds_full_payload_and_authoritative_interpretation_clock(
    seeded: dict[str, int], runtime: psycopg.Connection[Any]
) -> None:
    draft = _draft(seeded)
    (stored,) = _publish(runtime, seeded["runs"], (draft,))
    interpretation = _read(runtime, "interpretations", seeded["interpretations"])
    capture = _read(runtime, "capture_refs", interpretation["capture_ref_id"])
    refs = sorted(
        (ref.model_dump(mode="json") for ref in draft.source_refs),
        key=lambda value: json.dumps(value, sort_keys=True, separators=(",", ":")),
    )
    expected_document = {
        "schema": "eqos.queue-item-input.v2",
        "base": {
            "key_digest": draft.key.digest() if draft.key is not None else None,
            "measurement_key": (
                draft.key.model_dump(mode="json") if draft.key is not None else None
            ),
            "pair_identity": draft.pair_identity,
            "outcome": draft.outcome,
        },
        "payload": {
            "severity": draft.severity.value,
            "diagnostic": draft.diagnostic,
            "routing_reason": draft.routing_reason,
            "reason_code": None,
            "source_refs": refs,
        },
        "inputs": [
            {
                "kind": "INTERPRETATION",
                "id": seeded["interpretations"],
                "source_id": capture["source_id"],
                "surface": capture["surface"],
                "representation": interpretation["representation"],
                "recorded_at": _clock(interpretation["recorded_at"]),
            }
        ],
    }

    assert stored.input_sha256 == _canonical_sha(expected_document)


@pytest.mark.pg
def test_reordered_draft_exactly_reuses_item_inputs_and_origin_membership(
    seeded: dict[str, int], runtime: psycopg.Connection[Any]
) -> None:
    extra = _add_run_inputs(runtime, seeded)
    first = _draft(
        seeded,
        occurrence_ids=(seeded["occurrences"], extra["occurrence"]),
        interpretation_ids=(seeded["interpretations"], extra["interpretation"]),
        attempt_ids=(seeded["acquisition_attempts"], extra["attempt"]),
    )
    (origin,) = _publish(runtime, seeded["runs"], (first,))
    reused_run = _new_run(runtime, "queue-reuse-run")
    _link_existing_evidence(runtime, seeded, reused_run)
    for kind, column in (
        ("OCCURRENCE", "occurrence_id"),
        ("INTERPRETATION", "interpretation_id"),
        ("ATTEMPT", "attempt_id"),
    ):
        evidence_id = extra[kind.lower()]
        _insert(runtime, "run_inputs", _run_input(reused_run, kind, **{column: evidence_id}))
    reordered = first.model_copy(
        update={
            "source_refs": tuple(reversed(first.source_refs)),
            "evidence_occurrence_ids": tuple(reversed(first.evidence_occurrence_ids)),
            "evidence_interpretation_ids": tuple(reversed(first.evidence_interpretation_ids)),
            "attempt_ids": tuple(reversed(first.attempt_ids)),
        }
    )
    before = _counts(runtime)
    (reused,) = _publish(runtime, reused_run, (reordered,))

    assert reused.item_id == origin.item_id
    assert reused.run_id == seeded["runs"]
    assert _counts(runtime) == (before[0], before[1], before[2] + 1)


@pytest.mark.pg
def test_every_payload_or_typed_evidence_change_links_latest_predecessor(
    seeded: dict[str, int], runtime: psycopg.Connection[Any]
) -> None:
    extra = _add_run_inputs(runtime, seeded)
    drafts = [_draft(seeded)]
    drafts.append(drafts[-1].model_copy(update={"severity": QueueSeverity.MEDIUM}))
    drafts.append(drafts[-1].model_copy(update={"diagnostic": True}))
    drafts.append(drafts[-1].model_copy(update={"routing_reason": "SECOND_REVIEW"}))
    drafts.append(drafts[-1].model_copy(update={"reason_code": ReasonCode.PERIOD_MISMATCH}))
    drafts.append(drafts[-1].model_copy(update={"source_refs": (drafts[-1].source_refs[0],)}))
    drafts.append(drafts[-1].model_copy(update={"evidence_occurrence_ids": (extra["occurrence"],)}))
    drafts.append(
        drafts[-1].model_copy(
            update={
                "evidence_interpretation_ids": (
                    seeded["interpretations"],
                    extra["interpretation"],
                )
            }
        )
    )
    drafts.append(drafts[-1].model_copy(update={"attempt_ids": (extra["attempt"],)}))

    stored = [_publish(runtime, seeded["runs"], (draft,))[0] for draft in drafts]

    assert len({item.item_id for item in stored}) == len(drafts)
    assert [item.predecessor_item_id for item in stored] == [
        None,
        *(item.item_id for item in stored[:-1]),
    ]


@pytest.mark.pg
def test_unknown_mistyped_cross_run_and_unknown_run_evidence_are_guarded_before_dml(
    seeded: dict[str, int], runtime: psycopg.Connection[Any]
) -> None:
    from fundamentals.compare.queue import QueuePublicationError

    empty_run = _new_run(runtime, "queue-empty-run")
    mistyped_occurrence = _insert(
        runtime,
        "occurrences",
        _occurrence(seeded["_capture"], "mistyped-queue-evidence"),
    )
    _insert(
        runtime,
        "run_inputs",
        _run_input(seeded["runs"], "OCCURRENCE", occurrence_id=mistyped_occurrence),
    )
    baseline = _counts(runtime)
    cases = (
        (
            seeded["runs"],
            _draft(seeded, attempt_ids=(seeded["acquisition_attempts"] + 10_000_000,)),
        ),
        (
            seeded["runs"],
            _draft(seeded, attempt_ids=(mistyped_occurrence,)),
        ),
        (empty_run, _draft(seeded)),
        (seeded["runs"] + 10_000_000, _draft(seeded)),
    )
    for run_id, draft in cases:
        with pytest.raises(QueuePublicationError):
            _publish(runtime, run_id, (draft,))

    assert _counts(runtime) == baseline


@pytest.mark.pg
def test_queue_publication_rolls_back_with_its_calling_cursor(
    seeded: dict[str, int], runtime: psycopg.Connection[Any]
) -> None:
    from fundamentals.compare.queue import publish_queue_drafts

    baseline = _counts(runtime)
    with pytest.raises(RuntimeError, match="rollback fixture"):
        with runtime.transaction(), runtime.cursor() as cursor:
            publish_queue_drafts(
                cursor,
                run_id=seeded["runs"],
                drafts=(_draft(seeded, pair_identity="rollback-pair"),),
            )
            raise RuntimeError("rollback fixture")

    assert _counts(runtime) == baseline


@pytest.mark.pg
def test_concurrent_identical_draft_reuses_one_item_and_link(
    seeded: dict[str, int], pg_db: PgTestDatabase
) -> None:
    barrier = threading.Barrier(2)
    draft = _draft(seeded, pair_identity="concurrent-pair")

    with pg_db.runtime_pool() as pool:

        def publish() -> int | None:
            with pool.connection() as conn, conn.transaction(), conn.cursor() as cursor:
                barrier.wait()
                from fundamentals.compare.queue import publish_queue_drafts

                return publish_queue_drafts(cursor, run_id=seeded["runs"], drafts=(draft,))[
                    0
                ].item_id

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = (executor.submit(publish), executor.submit(publish))
            item_ids = [future.result() for future in futures]
        with pool.connection() as conn:
            item_count = conn.execute(
                "SELECT count(*) FROM eqos.queue_items WHERE pair_identity=%s",
                (draft.pair_identity,),
            ).fetchone()
            link_count = conn.execute(
                "SELECT count(*) FROM eqos.queue_run_items q "
                "JOIN eqos.queue_items i ON i.id=q.item_id WHERE i.pair_identity=%s",
                (draft.pair_identity,),
            ).fetchone()

    assert len(set(item_ids)) == 1
    assert item_count == (1,)
    assert link_count == (1,)


@pytest.mark.pg
def test_reversed_concurrent_multi_item_batches_share_items_without_deadlock(
    seeded: dict[str, int], pg_db: PgTestDatabase
) -> None:
    barrier = threading.Barrier(2)
    first = _draft(seeded, pair_identity="multi-a")
    second = _draft(seeded, pair_identity="multi-b")

    with pg_db.runtime_pool() as pool:

        def publish(drafts: tuple[QueueItemDraft, ...]) -> tuple[int | None, ...]:
            with pool.connection() as conn, conn.transaction(), conn.cursor() as cursor:
                barrier.wait()
                from fundamentals.compare.queue import publish_queue_drafts

                return tuple(
                    item.item_id
                    for item in publish_queue_drafts(cursor, run_id=seeded["runs"], drafts=drafts)
                )

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = (
                executor.submit(publish, (first, second)),
                executor.submit(publish, (second, first)),
            )
            results = [future.result() for future in futures]
        with pool.connection() as conn:
            item_count = conn.execute(
                "SELECT count(*) FROM eqos.queue_items WHERE pair_identity=ANY(%s)",
                ([first.pair_identity, second.pair_identity],),
            ).fetchone()
            link_count = conn.execute(
                "SELECT count(*) FROM eqos.queue_run_items q "
                "JOIN eqos.queue_items i ON i.id=q.item_id "
                "WHERE i.pair_identity=ANY(%s)",
                ([first.pair_identity, second.pair_identity],),
            ).fetchone()

    assert results[0] == results[1]
    assert item_count == (2,)
    assert link_count == (2,)


@pytest.mark.pg
def test_overlay_store_clock_exact_reread_and_reused_origin(
    seeded: dict[str, int],
    runtime: psycopg.Connection[Any],
    pg_db: PgTestDatabase,
) -> None:
    from fundamentals.compare.queue import (
        QueueOverlayReadError,
        capture_queue_overlay,
        read_queue_overlay,
    )

    draft = _draft(seeded, pair_identity="origin-pair")
    (origin,) = _publish(runtime, seeded["runs"], (draft,))
    reused_run = _new_run(runtime, "overlay-reused-run")
    _link_existing_evidence(runtime, seeded, reused_run)
    (reused,) = _publish(runtime, reused_run, (draft,))
    assert reused.item_id == origin.item_id

    with pg_db.runtime_pool() as pool:
        overlay = capture_queue_overlay(pool, run_id=reused_run)
        replayed = read_queue_overlay(
            pool,
            run_id=reused_run,
            as_of=overlay.as_of,
            recorded_position=overlay.recorded_position,
        )
        with pytest.raises(QueueOverlayReadError, match="position"):
            read_queue_overlay(
                pool,
                run_id=reused_run,
                as_of=overlay.as_of,
                recorded_position=overlay.recorded_position + 1,
            )

    epoch_microseconds = (overlay.as_of - datetime(1970, 1, 1, tzinfo=UTC)) // timedelta(
        microseconds=1
    )
    assert overlay.recorded_position == epoch_microseconds
    assert replayed == overlay
    assert [item.item_id for item in overlay.open_items] == [origin.item_id]
    assert overlay.open_items[0].run_id == seeded["runs"]
    assert overlay.memberships[0].origin_run_id == seeded["runs"]
    assert overlay.memberships[0].run_id == reused_run


@pytest.mark.pg
def test_accept_receipt_closes_item_while_reject_receipt_leaves_item_open(
    seeded: dict[str, int],
    runtime: psycopg.Connection[Any],
    migrator: psycopg.Connection[Any],
    pg_db: PgTestDatabase,
) -> None:
    from fundamentals.compare.queue import capture_queue_overlay

    (rejected_item,) = _publish(
        runtime,
        seeded["runs"],
        (_draft(seeded, pair_identity="rejected-proposal-pair"),),
    )
    assert rejected_item.item_id is not None
    _seed_rejected_receipt(migrator, rejected_item.item_id)
    (accepted_item,) = _publish(
        runtime,
        seeded["runs"],
        (_draft(seeded, pair_identity="verified-synthetic-accept-pair"),),
    )
    assert accepted_item.item_id is not None
    _seed_verified_synthetic_accept(migrator, accepted_item.item_id)

    with pg_db.runtime_pool() as pool:
        overlay = capture_queue_overlay(pool, run_id=seeded["runs"])

    assert rejected_item.item_id in {item.item_id for item in overlay.open_items}
    assert seeded["queue_items"] in {item.item_id for item in overlay.open_items}
    assert seeded["queue_items"] not in {
        disposition.item_id for disposition in overlay.accepted_dispositions
    }
    assert seeded["queue_dispositions"] in {
        failure.disposition_id for failure in overlay.closure_failures
    }
    assert accepted_item.item_id not in {item.item_id for item in overlay.open_items}
    assert accepted_item.item_id in {
        disposition.item_id for disposition in overlay.accepted_dispositions
    }
