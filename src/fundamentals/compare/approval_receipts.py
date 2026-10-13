"""Protected receipt producer/consumer; caller claims are never authenticated decisions.

The Task7 trusted composition root must supply an authenticator for actual external review
or an owner ruling. There is no default authenticator and no actor/path/owner-flag shortcut.
Database producer identity and times are recorded by SQL from session_user/store_now.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Protocol

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from fundamentals.contracts.review_queue import (
    ApprovalDecision,
    ApprovalReceipt,
    ApprovalSubject,
    QueueDisposition,
)
from fundamentals.pg.settings import MIGRATOR_ROLE_NAME


class ApprovalRefusedError(ValueError):
    """The decision is unverified, unprivileged, or belongs to another sealed proposal."""


class AuthenticatedDecision(BaseModel):
    """The trusted external authenticator's result; never a CLI JSON input contract."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    origin: str
    authenticated_producer_identity: str = Field(min_length=1)
    evidence_ref: str = Field(min_length=1)
    decider: str = Field(min_length=1)
    author: str = Field(min_length=1)
    decision: ApprovalDecision
    subject_sha256: str
    proposal_sha256: str
    owner_amount: Decimal | None = None
    verbatim_owner_ruling: str | None = None

    @model_validator(mode="after")
    def _actual_decider(self) -> AuthenticatedDecision:
        if self.origin == "INDEPENDENT_REVIEW":
            if self.author == self.decider or self.owner_amount is not None:
                raise ValueError(
                    "an independent reviewer differs from the author and authors no amount"
                )
        elif self.origin == "OWNER_RULING":
            if not self.verbatim_owner_ruling:
                raise ValueError("owner authority requires the exact authenticated owner ruling")
        else:
            raise ValueError("decision origin is authenticated independent review or owner ruling")
        return self


class DecisionEvidenceAuthenticator(Protocol):
    """Trusted local composition dependency authenticating the actual external producer."""

    def authenticate(self, raw_evidence: bytes) -> AuthenticatedDecision: ...


@dataclass(frozen=True, init=False)
class VerifiedDecisionEvidence:
    decision: AuthenticatedDecision
    evidence_sha256: str
    raw_evidence: bytes

    def __init__(self) -> None:
        raise ApprovalRefusedError("decision evidence requires an actual trusted authenticator")


@dataclass(frozen=True, init=False)
class VerifiedApprovalReceipt:
    receipt: ApprovalReceipt

    def __init__(self) -> None:
        raise ApprovalRefusedError(
            "verified approval receipts are reloaded from protected SQL rows"
        )


def verify_decision_evidence(
    raw_evidence: bytes,
    *,
    authenticator: DecisionEvidenceAuthenticator,
    subject_sha256: str,
    proposal_sha256: str,
) -> VerifiedDecisionEvidence:
    """Authenticate actual evidence outside caller claims, then bind it to the reviewed subject."""
    if not raw_evidence:
        raise ApprovalRefusedError("approval evidence is missing")
    decision = authenticator.authenticate(raw_evidence)
    if (decision.subject_sha256, decision.proposal_sha256) != (subject_sha256, proposal_sha256):
        raise ApprovalRefusedError("authenticated review names another subject or proposal")
    result = object.__new__(VerifiedDecisionEvidence)
    object.__setattr__(result, "decision", decision)
    object.__setattr__(result, "evidence_sha256", hashlib.sha256(raw_evidence).hexdigest())
    object.__setattr__(result, "raw_evidence", raw_evidence)
    return result


def subject_digest(row: Mapping[str, Any]) -> str:
    """Seal the immutable queue subject actually reloaded from the store."""
    return _digest(
        {
            name: row[name]
            for name in (
                "id",
                "key_digest",
                "measurement_key",
                "pair_identity",
                "outcome",
                "input_sha256",
                "severity",
                "diagnostic",
                "routing_reason",
                "reason_code",
                "source_refs",
                "predecessor_item_id",
            )
        }
    )


def proposal_digest(row: Mapping[str, Any]) -> str:
    """Seal the proposed body, not a caller's actor or self-reported hash."""
    return _digest(
        {
            name: row[name]
            for name in (
                "item_id",
                "kind",
                "reason",
                "proposer",
                "evidence_ref",
                "subject_sha256",
                "explained_amount",
                "amount_trace_id",
            )
        }
    )


def _privileged(conn: psycopg.Connection[Any]) -> None:
    row = conn.execute("SELECT session_user").fetchone()
    if row is None or row[0] != MIGRATOR_ROLE_NAME:
        raise ApprovalRefusedError("authenticated migrator connection required for final decisions")


def _proposal(conn: psycopg.Connection[Any], proposal_id: int) -> dict[str, Any]:
    with conn.cursor(row_factory=dict_row) as cursor:
        proposed = cursor.execute(
            "SELECT * FROM eqos.queue_disposition_proposals WHERE id=%s", (proposal_id,)
        ).fetchone()
        if proposed is None:
            raise ApprovalRefusedError("approval proposal is not stored")
        subject = cursor.execute(
            "SELECT * FROM eqos.queue_items WHERE id=%s", (proposed["item_id"],)
        ).fetchone()
    if subject is None or subject_digest(subject) != proposed["subject_sha256"]:
        raise ApprovalRefusedError("proposal subject seal differs from actual stored queue item")
    if proposal_digest(proposed) != proposed["proposal_sha256"]:
        raise ApprovalRefusedError("proposal body differs from its seal")
    return proposed


def produce_receipt(
    conn: psycopg.Connection[Any],
    *,
    proposal_id: int,
    evidence: VerifiedDecisionEvidence,
) -> VerifiedApprovalReceipt:
    """Privileged coordinator producer; arbitrary strings/models cannot create an approval."""
    _privileged(conn)
    if not isinstance(evidence, VerifiedDecisionEvidence):
        raise ApprovalRefusedError("actual verified review evidence required, not caller claims")
    with conn.transaction(), conn.cursor(row_factory=dict_row) as cursor:
        proposed = _proposal(conn, proposal_id)
        decision = evidence.decision
        if (decision.subject_sha256, decision.proposal_sha256) != (
            proposed["subject_sha256"],
            proposed["proposal_sha256"],
        ):
            raise ApprovalRefusedError("authenticated evidence belongs to another stored proposal")
        row = cursor.execute(
            "INSERT INTO eqos.approval_review_evidence (subject_kind,subject_id,proposal_id,"
            "proposal_sha256,subject_sha256,evidence_sha256,evidence_document,evidence_origin,"
            "decision,decider,owner_amount,raw_evidence) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
            (
                ApprovalSubject.QUEUE_DISPOSITION.value,
                proposed["item_id"],
                proposal_id,
                decision.proposal_sha256,
                decision.subject_sha256,
                evidence.evidence_sha256,
                Jsonb(decision.model_dump(mode="json")),
                decision.origin,
                decision.decision.value,
                decision.decider,
                decision.owner_amount,
                evidence.raw_evidence,
            ),
        ).fetchone()
        assert row is not None
        receipt = cursor.execute(
            "INSERT INTO eqos.approval_receipts (subject_kind,subject_id,proposal_id,"
            "proposal_sha256,"
            "subject_sha256,decision,review_evidence_id,review_evidence_sha256,decider) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
            (
                ApprovalSubject.QUEUE_DISPOSITION.value,
                proposed["item_id"],
                proposal_id,
                decision.proposal_sha256,
                decision.subject_sha256,
                decision.decision.value,
                row["id"],
                evidence.evidence_sha256,
                decision.decider,
            ),
        ).fetchone()
        assert receipt is not None
    return reload_verified_receipt(conn, receipt["id"])


def reload_verified_receipt(
    conn: psycopg.Connection[Any], receipt_id: int
) -> VerifiedApprovalReceipt:
    """Verify a protected stored receipt against its actual evidence and sealed proposal."""
    with conn.cursor(row_factory=dict_row) as cursor:
        row = cursor.execute(
            "SELECT * FROM eqos.approval_receipts WHERE id=%s", (receipt_id,)
        ).fetchone()
        if row is None or row["producer_database_identity"] != MIGRATOR_ROLE_NAME:
            raise ApprovalRefusedError("no protected authenticated producer receipt")
        proof = cursor.execute(
            "SELECT * FROM eqos.approval_review_evidence WHERE id=%s", (row["review_evidence_id"],)
        ).fetchone()
    proposed = _proposal(conn, row["proposal_id"])
    if (
        proof is None
        or proof["producer_database_identity"] != MIGRATOR_ROLE_NAME
        or any(
            row[name] != proof[name]
            for name in (
                "subject_kind",
                "subject_id",
                "proposal_id",
                "proposal_sha256",
                "subject_sha256",
                "decision",
                "decider",
            )
        )
        or proof["evidence_sha256"] != row["review_evidence_sha256"]
    ):
        raise ApprovalRefusedError("protected receipt differs from authenticated review evidence")
    if hashlib.sha256(bytes(proof["raw_evidence"])).hexdigest() != proof["evidence_sha256"]:
        raise ApprovalRefusedError("protected raw review evidence differs from its hash")
    try:
        authenticated = AuthenticatedDecision.model_validate(proof["evidence_document"])
    except ValidationError as error:
        raise ApprovalRefusedError("protected review row lacks authenticated provenance") from error
    if (
        authenticated.subject_sha256,
        authenticated.proposal_sha256,
        authenticated.decision.value,
        authenticated.decider,
        authenticated.origin,
    ) != (
        row["subject_sha256"],
        row["proposal_sha256"],
        row["decision"],
        row["decider"],
        proof["evidence_origin"],
    ):
        raise ApprovalRefusedError("authenticated decision document differs from protected row")
    if (row["subject_id"], row["subject_sha256"], row["proposal_sha256"]) != (
        proposed["item_id"],
        proposed["subject_sha256"],
        proposed["proposal_sha256"],
    ):
        raise ApprovalRefusedError("receipt names another sealed subject/proposal")
    verified = object.__new__(VerifiedApprovalReceipt)
    object.__setattr__(
        verified,
        "receipt",
        ApprovalReceipt.model_validate(
            {
                **{key: value for key, value in row.items() if key != "id"},
                "receipt_id": row["id"],
            }
        ),
    )
    return verified


def finalize_disposition(
    conn: psycopg.Connection[Any],
    *,
    approval: VerifiedApprovalReceipt,
) -> QueueDisposition:
    """Append a matching ACCEPT disposition; runtime never supplies final records or amounts."""
    _privileged(conn)
    if not isinstance(approval, VerifiedApprovalReceipt):
        raise ApprovalRefusedError("final disposition requires reloaded protected receipt")
    actual = reload_verified_receipt(conn, approval.receipt.receipt_id).receipt
    if actual != approval.receipt or actual.decision is not ApprovalDecision.ACCEPT:
        raise ApprovalRefusedError("receipt is different or did not accept the proposal")
    proposed = _proposal(conn, actual.proposal_id)
    with conn.transaction(), conn.cursor(row_factory=dict_row) as cursor:
        row = cursor.execute(
            "INSERT INTO eqos.queue_dispositions (item_id,proposal_id,approval_receipt_id,"
            "kind,reason,"
            "proposer,decider,evidence_ref,explained_amount,amount_trace_id) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *",
            (
                actual.subject_id,
                actual.proposal_id,
                actual.receipt_id,
                proposed["kind"],
                proposed["reason"],
                proposed["proposer"],
                actual.decider,
                proposed["evidence_ref"],
                proposed["explained_amount"],
                proposed["amount_trace_id"],
            ),
        ).fetchone()
    assert row is not None
    return QueueDisposition.model_validate(
        {
            **{
                key: value
                for key, value in row.items()
                if key not in {"id", "proposal_id", "producer_database_identity"}
            },
            "disposition_id": row["id"],
        }
    )


def _digest(payload: Mapping[str, Any]) -> str:
    def encode(value: object) -> str:
        if isinstance(value, (datetime, date)):
            return value.isoformat()
        if isinstance(value, Decimal):
            return str(value)
        raise TypeError(type(value).__name__)

    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), default=encode).encode("utf-8")
    ).hexdigest()
