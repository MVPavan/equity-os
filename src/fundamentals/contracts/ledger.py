"""Report-ledger contracts: versions, claims, validations and decisions (ledger spec §1).

Rows are append-only in ``migrations/0012_report_ledger.sql``; the database sets every digest,
decider and recorded time, so those fields appear here only on records read back.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from fundamentals.contracts.canonical import ValueKind
from fundamentals.contracts.evidence import RunMode
from fundamentals.contracts.guidance_claim import EpistemicClass
from fundamentals.contracts.measurement_key import MeasurementKey


class ReportKind(StrEnum):
    BOOTSTRAP_THESIS = "BOOTSTRAP_THESIS"
    EARNINGS_UPDATE = "EARNINGS_UPDATE"


class SubjectKind(StrEnum):
    REPORT_VERSION = "REPORT_VERSION"
    REPORT = "REPORT"
    DISPOSITION_PROPOSAL = "DISPOSITION_PROPOSAL"
    INTERPRETATION = "INTERPRETATION"


class DecisionKind(StrEnum):
    SUBMIT = "SUBMIT"
    IMPORT_SEAL = "IMPORT_SEAL"
    IMPORTED_APPROVAL = "IMPORTED_APPROVAL"
    APPROVE = "APPROVE"
    REQUEST_CHANGES = "REQUEST_CHANGES"
    REJECT = "REJECT"
    WITHDRAW = "WITHDRAW"
    ACCEPT = "ACCEPT"
    SET_POLICY = "SET_POLICY"


class DeciderRole(StrEnum):
    RUNTIME = "RUNTIME"
    PANEL = "PANEL"
    OWNER = "OWNER"


class CitationKind(StrEnum):
    FIGURE = "FIGURE"
    CALCULATION = "CALCULATION"
    SOURCE_QUOTE = "SOURCE_QUOTE"
    COMPARISON = "COMPARISON"
    POLICY = "POLICY"


class Rounding(StrEnum):
    """A claim's display rounding; values are the ``decimal`` module's mode names."""

    ROUND_HALF_UP = "ROUND_HALF_UP"
    ROUND_HALF_EVEN = "ROUND_HALF_EVEN"


class ClaimState(StrEnum):
    """Claim-check outcome; the first matching row of the spec table wins."""

    UNRESOLVED = "UNRESOLVED"
    POST_CUTOFF = "POST_CUTOFF"
    UNIT_MISMATCH = "UNIT_MISMATCH"
    KEY_MISMATCH = "KEY_MISMATCH"
    VALUE_MISMATCH = "VALUE_MISMATCH"
    QUOTE_NOT_FOUND = "QUOTE_NOT_FOUND"
    QUOTE_MEANING_MISMATCH = "QUOTE_MEANING_MISMATCH"
    MATCH_UNTRUSTED = "MATCH_UNTRUSTED"
    MATCH = "MATCH"


class VersionState(StrEnum):
    """Version-level check findings, each blocking submission."""

    UNREGISTERED_NUMBER = "UNREGISTERED_NUMBER"
    UNLABELLED_PROSE = "UNLABELLED_PROSE"
    UNCITED_PROSE = "UNCITED_PROSE"


class VersionStatus(StrEnum):
    """A version's status, derived from the decision log and never stored (P1)."""

    DRAFT = "DRAFT"
    IN_REVIEW = "IN_REVIEW"
    APPROVED = "APPROVED"
    CHANGES_REQUESTED = "CHANGES_REQUESTED"
    REJECTED = "REJECTED"
    HISTORICAL = "HISTORICAL"
    SUPERSEDED = "SUPERSEDED"
    WITHDRAWN = "WITHDRAWN"


class Grouping(StrEnum):
    NONE = "group-none"
    INDIAN = "group-indian"
    INTERNATIONAL = "group-intl"


class RangeForm(StrEnum):
    DASH = "range-dash"
    COMMA = "range-comma"


class InputTime(StrEnum):
    """An input time the claim check holds against the cutoff (spec row 2); the last three
    count in ``AS_KNOWN`` only."""

    KNOWLEDGE = "KNOWLEDGE"
    FIRST_SEEN = "FIRST_SEEN"
    RUN = "RUN"
    RECORDED = "RECORDED"
    SELECTED = "SELECTED"
    POLICY = "POLICY"


class Verdict(StrEnum):
    APPROVE = "APPROVE"
    REQUEST_CHANGES = "REQUEST_CHANGES"
    REJECT = "REJECT"


class Citation(BaseModel):
    """The one record a claim cites; the columns each kind sets are fixed by the schema.

    A ``POLICY`` citation with no decision is a self-citation (imports only).
    """

    model_config = ConfigDict(frozen=True)

    kind: CitationKind
    source_sha256: str | None = None
    fact_origin: str | None = None
    fact_origin_id: int | None = None
    interpretation_id: int | None = None
    run_id: int | None = None
    calculation_trace_id: int | None = None
    capture_ref_id: int | None = None
    anchor: str | None = None
    quote: str | None = None
    pair_outcome_id: int | None = None
    policy_decision_id: int | None = None


class NumericClaim(BaseModel):
    """A typed number in a section: a value, or bounds and horizon for guidance. No display text.

    ``metric`` to ``constant_currency`` are a ``SOURCE_QUOTE``'s guidance contract.
    ``unresolved`` marks an imported claim with no cited record.
    """

    model_config = ConfigDict(frozen=True)

    claim_key: str
    section_key: str
    citation: Citation
    measurement_key: MeasurementKey | None = None
    value_kind: ValueKind
    unit: str | None = None
    currency: str | None = None
    scale: int | None = None
    value: Decimal | None = None
    lower_bound: Decimal | None = None
    upper_bound: Decimal | None = None
    horizon: str | None = None
    qualifiers: tuple[str, ...] = ()
    precision: int
    rounding: Rounding
    epistemic_class: EpistemicClass
    metric: str | None = None
    metric_label: str | None = None
    scope: str | None = None
    constant_currency: bool | None = None
    unresolved: bool = False


class ReportSection(BaseModel):
    """One section's Markdown text with placeholders and markers."""

    model_config = ConfigDict(frozen=True)

    ordinal: int
    section_key: str
    body: str


class VersionDraft(BaseModel):
    """Everything a version's content holds; ``import_sources`` are (path, bytes) pairs."""

    model_config = ConfigDict(frozen=True)

    report_id: int
    predecessor_id: int | None = None
    author: str
    knowledge_cutoff: datetime
    pinned_run_ids: tuple[int, ...] = ()
    content_hash: str
    sections: tuple[ReportSection, ...]
    claims: tuple[NumericClaim, ...] = ()
    import_sources: tuple[tuple[str, bytes], ...] = ()


class Validation(BaseModel):
    """One claim check of a version: a state per claim key and any version-level states."""

    model_config = ConfigDict(frozen=True)

    version_id: int
    checker_version: str
    mode: RunMode
    overlay_position: datetime
    pinned_input_sha256: str
    sealed_digest: str
    claim_states: tuple[tuple[str, ClaimState], ...]
    version_states: tuple[VersionState, ...] = ()
    id: int | None = None
    recorded_at: datetime | None = None


class PolicyValue(BaseModel):
    """An owner-set policy value held by a ``SET_POLICY`` decision (D12)."""

    model_config = ConfigDict(frozen=True)

    key: str
    value: Decimal
    unit: str


class DecisionRecord(BaseModel):
    """A stored decision as read back, with its trigger-set fields."""

    model_config = ConfigDict(frozen=True)

    id: int
    subject_kind: SubjectKind
    subject_id: int
    kind: DecisionKind
    sequence: int
    predecessor_id: int | None
    sealed_digest: str | None
    validation_id: int | None
    panel_review_id: int | None
    original_approval_sha256: str | None
    ruling: str | None
    decided_on: date | None
    policy: PolicyValue | None
    decider: DeciderRole
    recorded_at: datetime
    decision_sha256: str


class DisplayStyle(BaseModel):
    """A placeholder's closed-enum display style (plan D5); the defaults are the empty style."""

    model_config = ConfigDict(frozen=True)

    grouping: Grouping = Grouping.NONE
    plus: bool = False
    unit: bool = False
    qualifier: bool = False
    range_form: RangeForm = RangeForm.DASH
    trim: bool = False
    quote: bool = False


class GuidanceContract(BaseModel):
    """The guidance fields a quote claim is compared with field by field (spec row 7)."""

    model_config = ConfigDict(frozen=True)

    metric: str | None
    scope: str | None
    horizon: str | None
    unit: str | None
    constant_currency: bool | None


class ResolvedCitation(BaseModel):
    """What a claim's cited record says, read at the validation's overlay position.

    A ``None`` field is one the cited record does not carry, so the check skips it. ``times``
    are the inputs row 2 holds against the cutoff (``None``: missing); ``trusted`` is the
    cited run cell's trust view, ``None`` when no run cell is cited.
    """

    model_config = ConfigDict(frozen=True)

    value: Decimal | None = None
    key_digest: str | None = None
    value_kind: ValueKind | None = None
    unit: str | None = None
    currency: str | None = None
    scale: int | None = None
    times: tuple[tuple[InputTime, datetime | None], ...] = ()
    quote_text: str | None = None
    guidance: GuidanceContract | None = None
    trusted: bool | None = None
