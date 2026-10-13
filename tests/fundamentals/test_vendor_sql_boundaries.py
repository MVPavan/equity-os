"""Task2 SQL refuses relabelled first-party traces, unreviewed amounts and clock access."""

import hashlib
from decimal import Decimal

import psycopg
import pytest
from pg_evidence_schema_support import _insert, _read, migrator, runtime, seeded
from psycopg import errors
from psycopg.types.json import Jsonb

from fundamentals.compare.approval_receipts import proposal_digest, subject_digest

__all__ = ["runtime", "migrator", "seeded"]
pytestmark = pytest.mark.pg


def test_vendor_value_cannot_relabel_a_first_party_computed_trace(
    seeded: dict[str, int],
    migrator: psycopg.Connection,
) -> None:
    capture = _read(migrator, "capture_refs", seeded["capture_refs"])
    with pytest.raises(errors.CheckViolation, match="source/surface"):
        _insert(
            migrator,
            "result_source_values",
            {
                "result_id": seeded["results"],
                "source_role": "INDEPENDENT_VENDOR",
                "representation": "HTML",
                "source_id": capture["source_id"],
                "surface": capture["surface"],
                "source_state": "VALUE",
                "value": Decimal("12.34"),
                "calculation_trace_id": seeded["calculation_traces"],
            },
        )


def test_accepted_amount_free_proposal_cannot_gain_an_unreviewed_code_amount(
    seeded: dict[str, int],
    migrator: psycopg.Connection,
) -> None:
    """Constructed protected SQL rows test binding only; they never establish actual approval."""
    item = seeded["queue_items"]
    body = {
        "item_id": item,
        "kind": "MAPPING_FIX",
        "reason": "second constructed binding fixture",
        "proposer": "constructed-author",
        "evidence_ref": "constructed-only",
        "subject_sha256": subject_digest(_read(migrator, "queue_items", item)),
        "explained_amount": None,
        "amount_trace_id": None,
    }
    body["proposal_sha256"] = proposal_digest(body)
    proposal = _insert(migrator, "queue_disposition_proposals", body)
    raw = b"constructed SQL binding test, not actual reviewer approval"
    sha = hashlib.sha256(raw).hexdigest()
    bound = {
        "subject_kind": "QUEUE_DISPOSITION",
        "subject_id": item,
        "proposal_id": proposal,
        "proposal_sha256": body["proposal_sha256"],
        "subject_sha256": body["subject_sha256"],
        "decision": "ACCEPT",
        "decider": "constructed-peer",
    }
    evidence = _insert(
        migrator,
        "approval_review_evidence",
        {
            **bound,
            "evidence_sha256": sha,
            "raw_evidence": raw,
            "evidence_document": Jsonb({"fixture": "SQL binding only"}),
            "evidence_origin": "INDEPENDENT_REVIEW",
        },
    )
    receipt = _insert(
        migrator,
        "approval_receipts",
        {
            **bound,
            "review_evidence_id": evidence,
            "review_evidence_sha256": sha,
        },
    )
    with pytest.raises(errors.CheckViolation, match="sealed"):
        _insert(
            migrator,
            "queue_dispositions",
            {
                "item_id": item,
                "proposal_id": proposal,
                "approval_receipt_id": receipt,
                "kind": body["kind"],
                "reason": body["reason"],
                "proposer": body["proposer"],
                "decider": bound["decider"],
                "evidence_ref": body["evidence_ref"],
                "explained_amount": Decimal("12.34"),
                "amount_trace_id": seeded["calculation_traces"],
            },
        )


def test_runtime_cannot_advance_the_protected_store_clock_sequence(
    runtime: psycopg.Connection,
) -> None:
    with pytest.raises(errors.InsufficientPrivilege):
        runtime.execute("SELECT nextval('eqos.store_clock_us')")


@pytest.mark.parametrize("role", ["FIRST_PARTY", "REPORTED_COUNTERPART"])
def test_first_party_sql_side_cannot_use_a_vendor_representation(
    role: str,
    seeded: dict[str, int],
    runtime: psycopg.Connection,
) -> None:
    with pytest.raises(errors.CheckViolation):
        _insert(
            runtime,
            "result_source_values",
            {
                "result_id": seeded["results"],
                "source_role": role,
                "representation": "HTML",
                "source_state": "NO_VALUE",
            },
        )
