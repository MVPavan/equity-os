"""Shared comparison enums: states, selection sources, pair and status outcomes (spec §5)."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, model_validator

from fundamentals.contracts.canonical import Representation


class SourceState(StrEnum):
    """One source's state for a cell (data spec §5 source states)."""

    VALUE = "VALUE"
    NO_VALUE = "NO_VALUE"
    UNAVAILABLE = "UNAVAILABLE"
    INVALID = "INVALID"


class CalculationState(StrEnum):
    """How a derived side's evaluation ended; first matching row of the spec table wins."""

    OPERAND_UNAVAILABLE = "OPERAND_UNAVAILABLE"
    OPERAND_INVALID = "OPERAND_INVALID"
    OPERAND_MISSING = "OPERAND_MISSING"
    REVISION_INCOMPATIBLE = "REVISION_INCOMPATIBLE"
    UNDEFINED = "UNDEFINED"
    COMPUTED = "COMPUTED"


class SelectionSource(StrEnum):
    """Which selection rule supplied an operand value (recorded on every trace operand)."""

    PACKAGE_AS_REPORTED = "PACKAGE_AS_REPORTED"
    PACKAGE_OPENING_DISCLOSURE = "PACKAGE_OPENING_DISCLOSURE"
    INSTANT_OWN_SELECTION = "INSTANT_OWN_SELECTION"
    HISTORICAL_PACKAGE = "HISTORICAL_PACKAGE"
    VENDOR_CAPTURE = "VENDOR_CAPTURE"


class SourceRole(StrEnum):
    """The evidentiary role of a source-qualified result side."""

    FIRST_PARTY = "FIRST_PARTY"
    REPORTED_COUNTERPART = "REPORTED_COUNTERPART"
    INDEPENDENT_VENDOR = "INDEPENDENT_VENDOR"
    DIAGNOSTIC = "DIAGNOSTIC"


class SourceRef(BaseModel):
    """Identify a side by its actual source and surface; legacy first-party refs may omit them."""

    model_config = ConfigDict(frozen=True)

    source_role: SourceRole
    representation: Representation
    source_id: str | None = None
    surface: str | None = None

    @model_validator(mode="after")
    def _source_identity(self) -> SourceRef:
        if (self.source_id is None) != (self.surface is None):
            raise ValueError("source_id and surface must be supplied together")
        if self.source_role in (SourceRole.INDEPENDENT_VENDOR, SourceRole.DIAGNOSTIC):
            if not self.source_id or not self.surface:
                raise ValueError("a vendor side names its actual source_id and surface")
            if self.representation not in (Representation.HTML, Representation.JSON):
                raise ValueError("a vendor side uses HTML or JSON representation")
        elif self.representation not in (Representation.XBRL, Representation.PDF):
            raise ValueError("a first-party side uses XBRL or PDF representation")
        return self


class PairOutcome(StrEnum):
    """One first-party side against one other side; first matching row of the pair table wins."""

    NOT_COMPARABLE = "NOT_COMPARABLE"
    AGREE = "AGREE"
    AGREE_UNQUALIFIED = "AGREE_UNQUALIFIED"
    DEFINITION_DIFFERENCE = "DEFINITION_DIFFERENCE"
    MISMATCH = "MISMATCH"
    ANOMALY = "ANOMALY"


class Triage(StrEnum):
    """Class of a ``MISMATCH`` or ``ANOMALY`` difference."""

    STRUCTURAL = "STRUCTURAL"
    MAGNITUDE = "MAGNITUDE"
    NOISE = "NOISE"


class ExtractionStatus(StrEnum):
    """XBRL against PDF of the same package, per cell (data spec §5 extraction table)."""

    NOT_APPLICABLE = "NOT_APPLICABLE"
    UNAVAILABLE = "UNAVAILABLE"
    NOT_COMPARABLE = "NOT_COMPARABLE"
    NONE = "NONE"
    ONE_SIDE_XBRL = "ONE_SIDE_XBRL"
    ONE_SIDE_PDF = "ONE_SIDE_PDF"
    AGREE = "AGREE"
    AGREE_UNQUALIFIED = "AGREE_UNQUALIFIED"
    TAGGING_DIFFERENCE = "TAGGING_DIFFERENCE"
    DISAGREE = "DISAGREE"


class CorroborationStatus(StrEnum):
    """First-party value against vendor values, per cell (the full spec set)."""

    NOT_APPLICABLE = "NOT_APPLICABLE"
    UNAVAILABLE = "UNAVAILABLE"
    NOT_COMPARABLE = "NOT_COMPARABLE"
    VENDOR_ONLY = "VENDOR_ONLY"
    NO_SOURCE = "NO_SOURCE"
    FILING_ONLY = "FILING_ONLY"
    CONFLICT = "CONFLICT"
    CORROBORATED = "CORROBORATED"
    AGREES_UNQUALIFIED = "AGREES_UNQUALIFIED"
    ANOMALY = "ANOMALY"
    DEFINITION_DIFFERENCE = "DEFINITION_DIFFERENCE"


class ReasonCode(StrEnum):
    """Why a pair or status is ``NOT_COMPARABLE``, a side ``INVALID``, or an adjustment refused."""

    CANONICAL_MISMATCH = "CANONICAL_MISMATCH"
    PERIOD_MISMATCH = "PERIOD_MISMATCH"
    BASIS_MISMATCH = "BASIS_MISMATCH"
    FRAMEWORK_MISMATCH = "FRAMEWORK_MISMATCH"
    CURRENCY_MISMATCH = "CURRENCY_MISMATCH"
    KIND_MISMATCH = "KIND_MISMATCH"
    DIMENSION_UNRESOLVED = "DIMENSION_UNRESOLVED"
    PERIOD_AMBIGUOUS = "PERIOD_AMBIGUOUS"
    PRECISION_UNSUPPORTED = "PRECISION_UNSUPPORTED"
    SIDE_INVALID = "SIDE_INVALID"
    UNREADABLE_CELL = "UNREADABLE_CELL"
    INTERPRETATION_AMBIGUOUS = "INTERPRETATION_AMBIGUOUS"
    VENDOR_INTERNAL_CONFLICT = "VENDOR_INTERNAL_CONFLICT"
    OPERAND_INVALID = "OPERAND_INVALID"
    UNDEFINED = "UNDEFINED"
    REVISION_INCOMPATIBLE = "REVISION_INCOMPATIBLE"
    ADJUSTMENT_OUT_OF_SCOPE = "ADJUSTMENT_OUT_OF_SCOPE"
    ADJUSTMENT_MISMATCH = "ADJUSTMENT_MISMATCH"


class PairKind(StrEnum):
    """Which comparison a stored pair outcome belongs to."""

    EXTRACTION = "EXTRACTION"
    REPORTED_VS_DERIVED = "REPORTED_VS_DERIVED"
    CORROBORATION = "CORROBORATION"
    DIAGNOSTIC = "DIAGNOSTIC"


class EpistemicClass(StrEnum):
    """What kind of claim a reported number is (invariant 8); D1a emits these two."""

    OBSERVED = "OBSERVED"
    COMPUTED = "COMPUTED"
