"""Thesis-layer data contracts: validated facts in, cross-verified judgment out.

This module is the seam between the deterministic Fundamentals pipeline and the
multi-model thesis layer. The pipeline produces cross-verified, provenance-bound
*facts*; those are projected here into a :class:`ValidatedFactSet` that is the
*only* thing a model ever sees. Everything a model returns is captured as a
:class:`ThesisDraft` of pure judgment, and the deterministic cross-verifier emits
a :class:`CrossVerification` (unsourced-number flags plus a divergence queue).

Every model is treated as a source of *opinion*, never of numbers: a validated
fact is labelled :attr:`EpistemicClass.OBSERVED`; a model's output is
:attr:`EpistemicClass.OPINION`. A number a model emits that is not in the
validated fact set is surfaced as an :class:`UnsourcedClaim`, never trusted.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class EpistemicClass(StrEnum):
    """Epistemic class of a claim (roadmap invariant 8: output labelled by class)."""

    OBSERVED = "observed"
    COMPUTED = "computed"
    INFERRED = "inferred"
    FORECAST = "forecast"
    OPINION = "opinion"


class UnknownReason(StrEnum):
    """Why a material concept is withheld from the models as an ``unknown``."""

    MISSING = "missing"
    CONFLICT = "conflict"


class JudgmentSection(StrEnum):
    """The judgment sections a model is asked to produce (never numbers)."""

    DRIVERS = "drivers"
    THESIS_IMPACT = "thesis_impact"
    OBSERVABLE_FALSIFIERS = "observable_falsifiers"
    KEY_RISKS = "key_risks"
    OPEN_QUESTIONS = "open_questions"
    NEEDED_BUT_MISSING = "needed_but_missing"


class DraftStatus(StrEnum):
    """Outcome of asking one model for a draft."""

    OK = "ok"
    EMPTY = "empty"
    FAILED = "failed"
    TIMED_OUT = "timed_out"


class DiscrepancyKind(StrEnum):
    """The kind of divergence the cross-verifier detected between two drafts."""

    COVERAGE_GAP = "coverage_gap"
    DIVERGENT_POINTS = "divergent_points"
    STANCE_DIVERGENCE = "stance_divergence"
    UNSTRUCTURED_OUTPUT = "unstructured_output"


class ThesisDocumentStatus(StrEnum):
    """Whether the document carries two, one, or zero usable model drafts."""

    OK = "ok"
    PARTIAL = "partial"
    BLOCKED = "blocked"


class FactAnchor(BaseModel):
    """One source's reported value for a fact, with a human-readable anchor.

    ``description`` is a one-line pointer back to the exact source location (a PDF
    page/block/span or an XBRL context) plus a sha256 prefix — enough to re-audit
    the number without shipping any copyrighted source-document text to a model.
    """

    model_config = ConfigDict(frozen=True)

    source_id: str
    source_class: str
    value: str
    description: str


class ValidatedFact(BaseModel):
    """One material fact the pipeline validated: a value the models may cite.

    The value is ground truth; a model supplies judgment about it, never a new
    number. ``single_sourced`` marks a fact confirmed by only one first-party
    source (still admissible, but weaker — surfaced for the human's attention).
    """

    model_config = ConfigDict(frozen=True)

    concept_qname: str
    label: str
    value: str
    unit: str
    status: str
    agreed_sources: tuple[str, ...]
    corroborating_sources: tuple[str, ...]
    first_party_source_count: int
    single_sourced: bool
    period_start: str | None
    period_end: str | None
    scope: str
    currency: str | None
    epistemic_class: EpistemicClass = EpistemicClass.OBSERVED
    anchors: tuple[FactAnchor, ...]


class Unknown(BaseModel):
    """A material concept withheld from the models (conflicting or missing)."""

    model_config = ConfigDict(frozen=True)

    concept_qname: str
    label: str
    reason: UnknownReason
    detail: str


class ValidatedFactSet(BaseModel):
    """The complete, sourced input a model is given for one stock-quarter."""

    model_config = ConfigDict(frozen=True)

    symbol: str
    name: str
    domain: str
    quarter: str
    period_start: str | None
    period_end: str | None
    scope: str
    basis: str
    currency: str | None
    facts: tuple[ValidatedFact, ...]
    unknowns: tuple[Unknown, ...]


class DraftSection(BaseModel):
    """One judgment section of a model draft: a list of concise points."""

    model_config = ConfigDict(frozen=True)

    section: JudgmentSection
    points: tuple[str, ...]


class ThesisDraft(BaseModel):
    """One model's independent judgment draft over the validated fact set."""

    model_config = ConfigDict(frozen=True)

    model_label: str
    client_name: str
    status: DraftStatus
    stance: str
    sections: tuple[DraftSection, ...]
    raw_text: str
    parsed: bool
    duration_seconds: float
    error: str | None = None

    @property
    def is_usable(self) -> bool:
        """A draft with real content the cross-verifier can inspect."""
        return self.status is DraftStatus.OK and bool(self.raw_text.strip())

    def section_points(self, section: JudgmentSection) -> tuple[str, ...]:
        """Return the points a draft carries for one section (empty if absent)."""
        for draft_section in self.sections:
            if draft_section.section is section:
                return draft_section.points
        return ()


class UnsourcedClaim(BaseModel):
    """A number a model emitted that is not in the validated fact set.

    This is a red flag to surface for human attention, never a value to trust:
    the deterministic pipeline is the only authoritative calculator (invariant 6).
    """

    model_config = ConfigDict(frozen=True)

    model_label: str
    number: str
    section: str
    snippet: str


class Discrepancy(BaseModel):
    """One divergence between the two drafts, queued for human adjudication."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    section: str
    kind: DiscrepancyKind
    model_a_label: str
    model_b_label: str
    model_a_points: tuple[str, ...]
    model_b_points: tuple[str, ...]
    detail: str


class CrossVerification(BaseModel):
    """The deterministic cross-check output: unsourced numbers and divergences."""

    model_config = ConfigDict(frozen=True)

    unsourced_claims: tuple[UnsourcedClaim, ...]
    discrepancies: tuple[Discrepancy, ...]

    @property
    def adjudication_required(self) -> bool:
        """Whether anything needs a human glance before the thesis is trusted."""
        return bool(self.unsourced_claims) or bool(self.discrepancies)


class ThesisDocument(BaseModel):
    """The assembled, non-authoritative thesis: facts, drafts, and the queue."""

    model_config = ConfigDict(frozen=True)

    fact_set: ValidatedFactSet
    drafts: tuple[ThesisDraft, ...]
    cross_verification: CrossVerification
    status: ThesisDocumentStatus

    @property
    def usable_draft_count(self) -> int:
        """Number of drafts that carried real judgment content."""
        return sum(1 for draft in self.drafts if draft.is_usable)
