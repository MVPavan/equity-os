"""Evidence contracts: captures, packages, occurrences, interpretations and attempts (data spec §4).

An occurrence is what a source said, lossless and owned by its capture; an interpretation
maps one occurrence (or a source-scoped construction) into a measurement key under pinned
mapping, normalisation-policy and extractor versions. Every model is frozen; ids are
``None`` until the row is stored.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from fractions import Fraction
from types import MappingProxyType
from typing import Annotated, Any

from pydantic import AfterValidator, BaseModel, ConfigDict, PlainSerializer, model_validator

from fundamentals.contracts.acquisition_outcome import ExtractionOutcome
from fundamentals.contracts.canonical import Basis, PeriodKind, Representation, StatementFamily
from fundamentals.contracts.comparison import SelectionSource, SourceState
from fundamentals.contracts.evidence_tier import EvidenceTier
from fundamentals.contracts.interval import Interval
from fundamentals.contracts.measurement_key import MeasurementKey, PeriodInterval
from fundamentals.contracts.observation import AccountingFramework
from fundamentals.contracts.qualification import ProvenCondition

_NOT_TERMINATING = "{value} has no exact decimal form"
_PRECISION_SHAPE = "declared_precision is set exactly when precision_kind is FINITE"
_MEMBER_COUNT = "a package has one or two members, got {count}"
_MEMBER_KEYS = "member keyed {key} is a {representation} member"


class MissingValueState(StrEnum):
    """Why an occurrence does or does not carry a value (data spec §1)."""

    VALUE = "VALUE"
    ZERO_PRINTED = "ZERO_PRINTED"
    NIL = "NIL"
    DASH = "DASH"
    BLANK = "BLANK"
    NOT_PRESENTED = "NOT_PRESENTED"
    SOURCE_NULL = "SOURCE_NULL"


class PrecisionKind(StrEnum):
    """How precisely a value was declared."""

    EXACT = "EXACT"
    FINITE = "FINITE"
    UNSUPPORTED = "UNSUPPORTED"


class RevisionCause(StrEnum):
    """Why a record exists alongside an earlier one (design decision 10)."""

    ORIGINAL = "ORIGINAL"
    ISSUER_RESTATEMENT = "ISSUER_RESTATEMENT"
    ISSUER_CORRECTION = "ISSUER_CORRECTION"
    COMPARATIVE_RESTATEMENT = "COMPARATIVE_RESTATEMENT"
    VENDOR_UPDATE = "VENDOR_UPDATE"
    PARSER_REEXTRACTION = "PARSER_REEXTRACTION"
    MANUAL_CORRECTION = "MANUAL_CORRECTION"
    NORMALISATION_POLICY_CHANGE = "NORMALISATION_POLICY_CHANGE"


class KnowledgeTimeStatus(StrEnum):
    """Whether a knowledge time is evidenced."""

    KNOWN = "KNOWN"
    UNKNOWN = "UNKNOWN"


class FilingFamily(StrEnum):
    """Which kind of filing a package is; packages supersede only within a family."""

    FINANCIAL_RESULTS = "FINANCIAL_RESULTS"
    SHAREHOLDING = "SHAREHOLDING"


class InterpretationStatus(StrEnum):
    """Outcome of interpreting one occurrence or construction."""

    MAPPED = "MAPPED"
    UNMAPPED = "UNMAPPED"
    PERIOD_AMBIGUOUS = "PERIOD_AMBIGUOUS"
    INVALID = "INVALID"


class InterpretationOrigin(StrEnum):
    """A direct mapping of one occurrence, or a source-scoped construction."""

    DIRECT = "DIRECT"
    CONSTRUCTED = "CONSTRUCTED"


class InterpretationReason(StrEnum):
    """Why an interpretation is ``INVALID``.

    ``INTERPRETATION_AMBIGUOUS``: two mapping entries match one native field, or one
    construction operand is matched twice in one group (fail closed, never first match).
    """

    UNREADABLE_CELL = "UNREADABLE_CELL"
    PRECISION_UNSUPPORTED = "PRECISION_UNSUPPORTED"
    UNIT_MISMATCH = "UNIT_MISMATCH"
    INTERPRETATION_AMBIGUOUS = "INTERPRETATION_AMBIGUOUS"


class StatementRole(StrEnum):
    """Whether a package presents a statement or replaces an earlier package's."""

    PRESENT = "PRESENT"
    REPLACED = "REPLACED"


class AttemptStage(StrEnum):
    """Acquisition (authority, staging, pin) or one adapter invocation."""

    ACQUISITION = "ACQUISITION"
    EXTRACTION = "EXTRACTION"


def _read_only(value: Mapping[Any, Any]) -> Mapping[Any, Any]:
    """Copy a mapping into a read-only view so a frozen model stays frozen."""
    return MappingProxyType(dict(value))


ReadOnlyJson = Annotated[Mapping[str, object], AfterValidator(_read_only), PlainSerializer(dict)]


def exact_decimal(value: Fraction) -> Decimal:
    """The exact decimal of a terminating rational; refuses any other value.

    Built from sign, digits and exponent, so no Decimal context precision ever applies.
    """
    numerator, denominator = value.numerator, value.denominator
    twos = fives = 0
    while denominator % 2 == 0:
        denominator //= 2
        twos += 1
    while denominator % 5 == 0:
        denominator //= 5
        fives += 1
    if denominator != 1:
        raise ValueError(_NOT_TERMINATING.format(value=value))
    places = max(twos, fives)
    scaled = numerator * (2 ** (places - twos)) * (5 ** (places - fives))
    digits = tuple(int(digit) for digit in str(abs(scaled)))
    return Decimal((1 if scaled < 0 else 0, digits, -places))


class EligibilityBoundary(BaseModel):
    """The two clocks a record must be at or before to be eligible (design decision 5)."""

    model_config = ConfigDict(frozen=True)

    knowledge_cutoff: datetime
    first_seen_cutoff: datetime

    @classmethod
    def at(cls, cutoff: datetime) -> EligibilityBoundary:
        """Both clocks at one cutoff, as a run uses."""
        return cls(knowledge_cutoff=cutoff, first_seen_cutoff=cutoff)

    @classmethod
    def for_ingest(
        cls, package_knowledge_time: datetime, registered_at: datetime
    ) -> EligibilityBoundary:
        """The honest ingest-time boundary: filed no later, and already stored."""
        return cls(knowledge_cutoff=package_knowledge_time, first_seen_cutoff=registered_at)


class CaptureReference(BaseModel):
    """A stored capture: its snapshot-store identity and the store's own clocks."""

    model_config = ConfigDict(frozen=True)

    capture_ref_id: int | None
    source_id: str
    surface: str
    request_key: str
    capture_id: str
    blob_sha256: str
    record_sha256: str
    registered_at: datetime
    first_seen_at: datetime


class PackageMember(BaseModel):
    """One representation of a filing with its own knowledge time."""

    model_config = ConfigDict(frozen=True)

    representation: Representation
    capture: CaptureReference
    knowledge_time: datetime
    knowledge_time_raw: str
    knowledge_time_status: KnowledgeTimeStatus


def _members(value: Mapping[Representation, PackageMember]) -> Mapping[Any, Any]:
    """Check a package's members and freeze them."""
    if not 1 <= len(value) <= 2:
        raise ValueError(_MEMBER_COUNT.format(count=len(value)))
    for key, member in value.items():
        if member.representation is not key:
            raise ValueError(_MEMBER_KEYS.format(key=key, representation=member.representation))
    return _read_only(value)


class FilingPackage(BaseModel):
    """One filing submission: its members, statements and package knowledge time."""

    model_config = ConfigDict(frozen=True)

    package_id: int | None
    entity_id: int
    family: FilingFamily
    reporting_period_end: date
    basis: Basis
    framework: AccountingFramework
    reporting_kind: PeriodKind
    knowledge_time: datetime
    supersedes_package_id: int | None
    replaced_statements: frozenset[StatementFamily]
    statements_present: frozenset[StatementFamily]
    members: Annotated[
        Mapping[Representation, PackageMember], AfterValidator(_members), PlainSerializer(dict)
    ]
    evidence_sha256: str

    def eligible(self, boundary: EligibilityBoundary) -> bool:
        """Filed by the knowledge cutoff, with every member stored by the first-seen cutoff."""
        return self.knowledge_time <= boundary.knowledge_cutoff and all(
            member.capture.first_seen_at <= boundary.first_seen_cutoff
            for member in self.members.values()
        )


class Occurrence(BaseModel):
    """What one source said at one anchor, exactly as printed or filed."""

    model_config = ConfigDict(frozen=True)

    occurrence_id: int | None
    capture: CaptureReference
    representation: Representation
    extractor_version: str
    native_field: str
    raw_value_text: str | None
    raw_unit: str
    raw_scale: int
    raw_sign: int
    precision_kind: PrecisionKind
    declared_precision: int | None
    native_context: ReadOnlyJson
    period: PeriodInterval | None
    missing_state: MissingValueState
    disclosure: ReadOnlyJson
    anchor: ReadOnlyJson
    anchor_key: str
    knowledge_time: datetime | None
    knowledge_time_status: KnowledgeTimeStatus
    first_seen_at: datetime
    revision_cause: RevisionCause

    @model_validator(mode="after")
    def _precision_shape(self) -> Occurrence:
        """A declared precision exists exactly for ``FINITE``."""
        if (self.declared_precision is not None) != (self.precision_kind is PrecisionKind.FINITE):
            raise ValueError(_PRECISION_SHAPE)
        return self

    @property
    def valid_time(self) -> date | None:
        """The fact store's valid time: the period end, or the instant."""
        if self.period is None:
            return None
        return self.period.instant if self.period.instant is not None else self.period.end


class Interpretation(BaseModel):
    """One occurrence or construction mapped into a measurement key under pinned versions.

    ``canonical_id`` and ``period`` stay set when a mapping matched but the key could not
    be completed (``PERIOD_AMBIGUOUS``); ``entity_id``, ``basis`` and ``framework`` are
    always the package's, so an ``UNMAPPED`` row still records its scope.
    """

    model_config = ConfigDict(frozen=True)

    interpretation_id: int | None
    origin: InterpretationOrigin
    occurrence_id: int | None
    capture_ref_id: int
    representation: Representation
    construction_rule_id: str | None
    operand_interpretation_ids: tuple[int, ...]
    input_digest: str
    status: InterpretationStatus
    entity_id: int
    basis: Basis
    framework: AccountingFramework
    canonical_id: str | None
    period: PeriodInterval | None
    dictionary_version: str
    key: MeasurementKey | None
    value: Decimal | None
    interval: Interval | None
    tier: EvidenceTier
    mapping_set_version: str
    mapping_entry_id: str | None
    qualification_ref: str | None
    condition_evidence: tuple[ProvenCondition, ...]
    normalisation_policy_version: str
    extractor_version: str
    transform_trace: ReadOnlyJson
    reason: InterpretationReason | None
    revision_cause: RevisionCause
    supersedes_interpretation_id: int | None
    recorded_at: datetime


class AcquisitionAttempt(BaseModel):
    """One acquisition or extraction attempt with its full request identity and outcome."""

    model_config = ConfigDict(frozen=True)

    attempt_id: int | None
    stage: AttemptStage
    source_id: str
    surface: str
    entity_id: int
    period_end: date
    basis: Basis
    framework: AccountingFramework
    representation: Representation
    statement_family: StatementFamily | None
    package_id: int | None
    outcome: ExtractionOutcome
    reason: str | None
    capture: CaptureReference | None
    input_sha256: str
    extractor_version: str
    attempted_at: datetime | None


class RunMode(StrEnum):
    """Whether a run sees interpretations as recorded by its cutoff, or the latest ones."""

    AS_KNOWN = "AS_KNOWN"
    RETROSPECTIVE = "RETROSPECTIVE"


class VersionPin(BaseModel):
    """One pinned artifact version with the SHA-256 of its resolved content."""

    model_config = ConfigDict(frozen=True)

    version: str
    content_sha256: str


class InterpretationTriple(BaseModel):
    """The (mapping set, normalisation policy, extractor) versions an interpretation is under.

    Selection reads only these versions, so ingest's comparative check can select under its
    own versions without pinning artifacts it never loaded.
    """

    model_config = ConfigDict(frozen=True)

    mapping_set: str
    normalisation_policy: str
    extractor_xbrl: str
    extractor_pdf: str

    def extractor(self, representation: Representation) -> str:
        """The extractor version for one representation."""
        if representation is Representation.XBRL:
            return self.extractor_xbrl
        return self.extractor_pdf


class PinnedVersions(BaseModel):
    """Every versioned artifact a run pins (design decision 7)."""

    model_config = ConfigDict(frozen=True)

    dictionary: VersionPin
    formula_set: VersionPin
    mapping_set: VersionPin
    normalisation_policy: VersionPin
    extractor_xbrl: VersionPin
    extractor_pdf: VersionPin
    rounding_policy: VersionPin
    definition_set: VersionPin
    comparison_policy: VersionPin
    alignment_rules: VersionPin

    def triple(self) -> InterpretationTriple:
        """The interpretation versions selection filters by."""
        return InterpretationTriple(
            mapping_set=self.mapping_set.version,
            normalisation_policy=self.normalisation_policy.version,
            extractor_xbrl=self.extractor_xbrl.version,
            extractor_pdf=self.extractor_pdf.version,
        )


class KeySelection(BaseModel):
    """Which interpretation (if any) supplies one key in one representation, and why."""

    model_config = ConfigDict(frozen=True)

    key: MeasurementKey
    representation: Representation
    state: SourceState
    interpretation: Interpretation | None
    package_id: int | None
    source: SelectionSource
    reason: str | None
    considered_interpretation_ids: tuple[int, ...]
    surfaced_restatements: tuple[int, ...]
