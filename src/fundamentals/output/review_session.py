"""Immutable review-session telemetry for an earnings-update artifact."""

from __future__ import annotations

import os
import re
import tempfile
from collections.abc import Callable
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, model_validator

from fundamentals.contracts.comparative import ConceptComparative
from fundamentals.contracts.provenance import Provenance
from fundamentals.output.earnings_update import EarningsUpdate, anchor_label


class ClaimKind(StrEnum):
    """The report claim groups reviewed in their rendered order."""

    FACT = "fact"
    COMPARATIVE = "comparative"
    GUIDANCE = "guidance"
    CALCULATION = "calculation"


class Disposition(StrEnum):
    """The reviewer's decision for one report claim."""

    ACCEPTED = "accepted"
    EDITED = "edited"
    REJECTED = "rejected"
    DEFERRED = "deferred"


class CorrectionCategory(StrEnum):
    """The reason a claim was changed or rejected."""

    NONE = "none"
    WRONG_VALUE = "wrong_value"
    WRONG_SOURCE = "wrong_source"
    MISSING_CONTEXT = "missing_context"
    CALCULATION = "calculation"
    WORDING = "wording"
    OTHER = "other"


class ApprovalState(StrEnum):
    """The final approval state for a completed review."""

    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class ReviewClaim(BaseModel):
    """One deterministically enumerated claim in an artifact."""

    model_config = ConfigDict(frozen=True)

    claim_id: str
    kind: ClaimKind
    text: str
    sources: tuple[str, ...]


class ClaimReview(BaseModel):
    """One current human disposition of a claim."""

    model_config = ConfigDict(frozen=True)

    claim_id: str
    disposition: Disposition
    category: CorrectionCategory
    seconds: int | None = None
    note: str | None = None
    recorded_at: datetime

    @model_validator(mode="after")
    def _require_matching_category(self) -> ClaimReview:
        if (
            self.disposition is Disposition.ACCEPTED
            and self.category is not CorrectionCategory.NONE
        ):
            raise ValueError("accepted reviews require category none")
        if self.disposition in (Disposition.EDITED, Disposition.REJECTED) and (
            self.category is CorrectionCategory.NONE
        ):
            raise ValueError("edited and rejected reviews require a correction category")
        return self


class ApprovalDecision(BaseModel):
    """The human decision attached when a session is finished."""

    model_config = ConfigDict(frozen=True)

    state: ApprovalState
    decider: str
    verbatim: str
    decided_at: datetime


class ReviewSession(BaseModel):
    """The append-preserving record for one analyst review."""

    model_config = ConfigDict(frozen=True)

    session_id: str
    report_json_sha256: str
    symbol: str
    issuer_quarter: str
    started_at: datetime
    finished_at: datetime | None = None
    claims: tuple[ReviewClaim, ...]
    reviews: tuple[ClaimReview, ...] = ()
    superseded: tuple[ClaimReview, ...] = ()
    instrumentation_seconds: float = 0.0
    decision: ApprovalDecision | None = None


class ReviewSummary(BaseModel):
    """Totals only: small review samples do not support distribution statistics."""

    model_config = ConfigDict(frozen=True)

    report_json_sha256: str
    symbol: str
    issuer_quarter: str
    total_minutes: float
    claim_count: int
    disposition_counts: dict[Disposition, int]
    category_counts: dict[CorrectionCategory, int]
    seconds_recorded: int
    instrumentation_seconds: float


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _local_name(qname: str) -> str:
    return qname.rsplit(":", maxsplit=1)[-1]


def _sources(*groups: tuple[Provenance, ...]) -> tuple[str, ...]:
    labels: list[str] = []
    for group in groups:
        for source in group:
            label = anchor_label(source)
            if label not in labels:
                labels.append(label)
    return tuple(labels)


def _comparative_claims(comparative: ConceptComparative) -> tuple[ReviewClaim, ...]:
    claims: list[ReviewClaim] = []
    for change in (comparative.qoq, comparative.yoy):
        if not change.available:
            continue
        assert comparative.current_value is not None
        assert comparative.unit is not None
        assert change.prior_value is not None
        assert change.absolute_change is not None
        assert change.prior_source is not None
        kind = change.kind.name.lower()
        local_name = _local_name(comparative.concept_qname)
        percent = "" if change.percent_change is None else f"; percent {change.percent_change}"
        trace = "" if change.absolute_trace is None else f"; trace {change.absolute_trace}"
        claims.append(
            ReviewClaim(
                claim_id=f"comparative:{local_name}:{kind}",
                kind=ClaimKind.COMPARATIVE,
                text=(
                    f"{local_name} {kind}: {comparative.current_value} {comparative.unit}; "
                    f"prior {change.prior_value}; change {change.absolute_change}{percent}{trace}"
                ),
                sources=_sources(comparative.current_sources, (change.prior_source,)),
            )
        )
    return tuple(claims)


def _calculation_slug(label: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")


def enumerate_claims(update: EarningsUpdate) -> tuple[ReviewClaim, ...]:
    """Return the stable fact, comparative, guidance, and calculation claim sequence."""
    claims = [
        ReviewClaim(
            claim_id=f"fact:{_local_name(fact.concept_qname)}",
            kind=ClaimKind.FACT,
            text=f"{_local_name(fact.concept_qname)}: {fact.value} {fact.unit}",
            sources=_sources(fact.sources),
        )
        for fact in update.facts
    ]
    for comparative in update.comparatives:
        claims.extend(_comparative_claims(comparative))
    claims.extend(
        ReviewClaim(
            # Missing/null metrics retain the artifact's legacy label-based identity.
            claim_id=(
                f"guidance:{guidance.metric}:{guidance.horizon}"
                if guidance.metric is not None
                else f"guidance:{guidance.metric_label}:{guidance.horizon}"
            ),
            kind=ClaimKind.GUIDANCE,
            text=(
                f"{guidance.metric_label}: {guidance.lower_bound} to {guidance.upper_bound} "
                f"{guidance.unit}; horizon {guidance.horizon}; {guidance.quote}"
            ),
            sources=_sources((guidance.source,)),
        )
        for guidance in update.guidance
    )
    calculation_sources = _sources(*(fact.sources for fact in update.facts))
    claims.extend(
        ReviewClaim(
            claim_id=f"calc:{_calculation_slug(calculation.label)}",
            kind=ClaimKind.CALCULATION,
            text=f"{calculation.label}: {calculation.result}; trace {calculation.trace}",
            sources=calculation_sources,
        )
        for calculation in update.calculations
    )
    return tuple(claims)


def start_session(
    update: EarningsUpdate,
    *,
    report_json_sha256: str,
    clock: Callable[[], datetime] = _utc_now,
) -> ReviewSession:
    """Create a new immutable review session for one exact report artifact."""
    return ReviewSession(
        session_id=str(uuid4()),
        report_json_sha256=report_json_sha256,
        symbol=update.nse_symbol,
        issuer_quarter=update.issuer_quarter_label,
        started_at=clock(),
        claims=enumerate_claims(update),
    )


def record_review(session: ReviewSession, review: ClaimReview) -> ReviewSession:
    """Record a review, preserving the replaced current entry as lineage."""
    if review.claim_id not in {claim.claim_id for claim in session.claims}:
        raise ValueError(f"unknown claim id: {review.claim_id}")
    prior = next((item for item in session.reviews if item.claim_id == review.claim_id), None)
    reviews = tuple(item for item in session.reviews if item.claim_id != review.claim_id) + (
        review,
    )
    superseded = session.superseded if prior is None else session.superseded + (prior,)
    return session.model_copy(update={"reviews": reviews, "superseded": superseded})


def finish_session(
    session: ReviewSession,
    decision: ApprovalDecision,
    *,
    clock: Callable[[], datetime] = _utc_now,
) -> ReviewSession:
    """Finish a fully reviewed session and attach its human approval decision."""
    reviewed = {review.claim_id for review in session.reviews}
    missing = [claim.claim_id for claim in session.claims if claim.claim_id not in reviewed]
    if missing:
        raise ValueError(f"cannot finish review; missing claim reviews: {', '.join(missing)}")
    return session.model_copy(update={"finished_at": clock(), "decision": decision})


def summarize_session(session: ReviewSession) -> ReviewSummary:
    """Calculate the required review totals from a finished session."""
    if session.finished_at is None:
        raise ValueError("cannot summarize an unfinished review session")
    disposition_counts = {disposition: 0 for disposition in Disposition}
    category_counts = {category: 0 for category in CorrectionCategory}
    for review in session.reviews:
        disposition_counts[review.disposition] += 1
        category_counts[review.category] += 1
    return ReviewSummary(
        report_json_sha256=session.report_json_sha256,
        symbol=session.symbol,
        issuer_quarter=session.issuer_quarter,
        total_minutes=(session.finished_at - session.started_at).total_seconds() / 60,
        claim_count=len(session.claims),
        disposition_counts=disposition_counts,
        category_counts=category_counts,
        seconds_recorded=sum(review.seconds or 0 for review in session.reviews),
        instrumentation_seconds=session.instrumentation_seconds,
    )


def save_session(session: ReviewSession, directory: Path) -> None:
    """Atomically replace ``session.json`` in an existing session directory."""
    if not directory.is_dir():
        raise ValueError(f"session directory does not exist: {directory}")
    descriptor, temporary_name = tempfile.mkstemp(prefix=".session-", suffix=".tmp", dir=directory)
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as temporary:
            temporary.write(session.model_dump_json(indent=2).encode("utf-8"))
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_path, directory / "session.json")
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def load_session(directory: Path) -> ReviewSession:
    """Load the current session record from its directory."""
    return ReviewSession.model_validate_json((directory / "session.json").read_bytes())


def approval_record_markdown(summary: ReviewSummary, decision: ApprovalDecision) -> str:
    """Render the compact approval record attached to a completed review session."""
    return "\n".join(
        (
            "## Approval record",
            "",
            "| Approval | Authority | State |",
            "| --- | --- | --- |",
            f"| Earnings-update review | {decision.decider} | {decision.state.value} |",
            "",
            f"- Decision date: {decision.decided_at.date().isoformat()}",
            f"- Verbatim: {decision.verbatim}",
            f"- Report sha256: {summary.report_json_sha256}",
            f"- Claims reviewed: {summary.claim_count}",
            f"- Seconds recorded: {summary.seconds_recorded}",
            f"- Total review minutes: {summary.total_minutes}",
            f"- Instrumentation seconds: {summary.instrumentation_seconds}",
            "",
        )
    )
