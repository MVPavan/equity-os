"""Constructed packages, occurrences and interpretations for selection unit tests (D1a Task 6).

Unit tests of pure selection functions may use constructed operands and constructed
timestamps (plan Constraints); nothing here is a filed value.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from fractions import Fraction

from equity_os.contracts.measurement.canonical import (
    Basis,
    PeriodKind,
    Representation,
    StatementFamily,
    ValueKind,
)
from equity_os.contracts.measurement.evidence import (
    CaptureReference,
    FilingFamily,
    FilingPackage,
    Interpretation,
    InterpretationOrigin,
    InterpretationStatus,
    InterpretationTriple,
    KnowledgeTimeStatus,
    MissingValueState,
    Occurrence,
    PackageMember,
    PrecisionKind,
    RevisionCause,
)
from equity_os.contracts.measurement.evidence_tier import EvidenceTier
from equity_os.contracts.measurement.interval import Interval
from equity_os.contracts.measurement.measurement_key import (
    DimensionSet,
    MeasurementKey,
    PeriodInterval,
)
from equity_os.contracts.measurement.observation import AccountingFramework

ENTITY = 1
PERIOD_END = date(2025, 9, 30)
QUARTER = PeriodInterval.duration(date(2025, 7, 1), PERIOD_END)
EXTRACTOR = "x1"
TRIPLE = InterpretationTriple(
    mapping_set="v1", normalisation_policy="v1", extractor_xbrl=EXTRACTOR, extractor_pdf=EXTRACTOR
)
CRORE = Decimal(10) ** 7


def at(day: int, hour: int = 0) -> datetime:
    """A constructed UTC instant in October 2025."""
    return datetime(2025, 10, day, hour, tzinfo=UTC)


def key(
    canonical_id: str = "revenue_from_operations", period: PeriodInterval = QUARTER
) -> MeasurementKey:
    """A consolidated INR key for Apar-like entity 1."""
    return MeasurementKey(
        entity_id=ENTITY,
        canonical_id=canonical_id,
        period=period,
        basis=Basis.CONSOLIDATED,
        framework=AccountingFramework.IND_AS,
        currency="INR",
        value_kind=ValueKind.CURRENCY_AMOUNT,
        dimensions=DimensionSet(),
    )


def capture(capture_ref_id: int, first_seen: datetime) -> CaptureReference:
    """A stored capture registered at ``first_seen``."""
    return CaptureReference(
        capture_ref_id=capture_ref_id,
        source_id=f"source-{capture_ref_id}",
        surface="NSE_XBRL_INSTANCE",
        request_key=f"request-{capture_ref_id}",
        capture_id=f"capture-{capture_ref_id}",
        blob_sha256=f"{capture_ref_id:064x}",
        record_sha256=f"{capture_ref_id:064x}",
        registered_at=first_seen,
        first_seen_at=first_seen,
    )


def member(
    representation: Representation, capture_ref_id: int, knowledge: datetime, first_seen: datetime
) -> PackageMember:
    """One package member with its own knowledge time."""
    return PackageMember(
        representation=representation,
        capture=capture(capture_ref_id, first_seen),
        knowledge_time=knowledge,
        knowledge_time_raw=knowledge.isoformat(),
        knowledge_time_status=KnowledgeTimeStatus.KNOWN,
    )


def package(
    package_id: int,
    *members: PackageMember,
    family: FilingFamily = FilingFamily.FINANCIAL_RESULTS,
    period_end: date = PERIOD_END,
    supersedes: int | None = None,
    replaced: frozenset[StatementFamily] = frozenset(),
) -> FilingPackage:
    """A package whose knowledge time is its latest member's."""
    return FilingPackage(
        package_id=package_id,
        entity_id=ENTITY,
        family=family,
        reporting_period_end=period_end,
        basis=Basis.CONSOLIDATED,
        framework=AccountingFramework.IND_AS,
        reporting_kind=PeriodKind.HALF_YEAR,
        knowledge_time=max(item.knowledge_time for item in members),
        supersedes_package_id=supersedes,
        replaced_statements=replaced,
        statements_present=frozenset({StatementFamily.PL, StatementFamily.BALANCE_SHEET}),
        members={item.representation: item for item in members},
        evidence_sha256=f"{package_id:064x}",
    )


def occurrence(
    occurrence_id: int,
    owner: PackageMember,
    *,
    period: PeriodInterval = QUARTER,
    extractor: str = EXTRACTOR,
) -> Occurrence:
    """An occurrence owned by a member's capture with the member's knowledge time."""
    return Occurrence(
        occurrence_id=occurrence_id,
        capture=owner.capture,
        representation=owner.representation,
        extractor_version=extractor,
        native_field="RevenueFromOperations",
        raw_value_text="1",
        raw_unit="INR",
        raw_scale=0,
        raw_sign=1,
        precision_kind=PrecisionKind.EXACT,
        declared_precision=None,
        native_context={},
        period=period,
        missing_state=MissingValueState.VALUE,
        disclosure={},
        anchor={},
        anchor_key=f"anchor-{occurrence_id}",
        knowledge_time=owner.knowledge_time,
        knowledge_time_status=KnowledgeTimeStatus.KNOWN,
        first_seen_at=owner.capture.first_seen_at,
        revision_cause=RevisionCause.ORIGINAL,
    )


def interpretation(
    interpretation_id: int,
    owner: PackageMember,
    *,
    measurement: MeasurementKey | None = None,
    crore: str | None = "100.00",
    recorded_at: datetime | None = None,
    mapping_set: str = "v1",
    extractor: str = EXTRACTOR,
    status: InterpretationStatus = InterpretationStatus.MAPPED,
    cause: RevisionCause = RevisionCause.ORIGINAL,
    supersedes: int | None = None,
) -> Interpretation:
    """A direct interpretation of a crore value printed to two places (± 0.005 crore)."""
    measurement = measurement or key()
    value = None if crore is None else Decimal(crore) * CRORE
    interval = (
        None
        if value is None
        else Interval(
            lower=Fraction(value) - Fraction(CRORE) / 200,
            upper=Fraction(value) + Fraction(CRORE) / 200,
        )
    )
    return Interpretation(
        interpretation_id=interpretation_id,
        origin=InterpretationOrigin.DIRECT,
        occurrence_id=interpretation_id,
        capture_ref_id=owner.capture.capture_ref_id or 0,
        representation=owner.representation,
        construction_rule_id=None,
        operand_interpretation_ids=(),
        input_digest="",
        status=status,
        entity_id=ENTITY,
        basis=Basis.CONSOLIDATED,
        framework=AccountingFramework.IND_AS,
        canonical_id=measurement.canonical_id,
        period=measurement.period,
        dictionary_version="v1",
        key=measurement,
        value=value,
        interval=interval,
        tier=EvidenceTier.EQUIVALENCE_UNPROVEN,
        mapping_set_version=mapping_set,
        mapping_entry_id="entry",
        qualification_ref=None,
        condition_evidence=(),
        normalisation_policy_version="v1",
        extractor_version=extractor,
        transform_trace={},
        reason=None,
        revision_cause=cause,
        supersedes_interpretation_id=supersedes,
        recorded_at=recorded_at or owner.capture.first_seen_at,
    )
