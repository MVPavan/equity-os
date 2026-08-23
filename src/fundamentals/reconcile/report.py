"""Frozen report contracts shared by orchestration and downstream views."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from fundamentals.contracts.comparative import ConceptComparative
from fundamentals.contracts.observation import Observation
from fundamentals.reconcile.agreement import AgreementStatus, SourceClass


class SourceKind(StrEnum):
    """The sources the runner can cross-check per stock."""

    NSE = "nse"
    BSE = "bse"
    SCREENER = "screener"
    TIJORI = "tijori"
    PDF = "pdf"
    SEC = "sec"


ALL_SOURCE_KINDS: frozenset[SourceKind] = frozenset(SourceKind)
FIRST_PARTY_SOURCE_KINDS: frozenset[SourceKind] = frozenset(
    {SourceKind.NSE, SourceKind.BSE, SourceKind.PDF}
)
XBRL_SOURCE_KINDS: frozenset[SourceKind] = frozenset({SourceKind.NSE, SourceKind.BSE})


class SourceStatus(StrEnum):
    """Outcome of pulling one source for one stock."""

    OK = "ok"
    SKIPPED = "skipped"
    BLOCKED = "blocked"


class StockOutcome(StrEnum):
    """The per-stock verdict against the goal's Definition of Done."""

    DONE = "done"
    NEEDS_ADJUDICATION = "needs_adjudication"
    BLOCKED = "blocked"


class CollectedSource(BaseModel):
    """One source's pulled observations plus its status and any note."""

    model_config = ConfigDict(frozen=True)

    kind: SourceKind
    source_id: str
    status: SourceStatus
    observations: tuple[Observation, ...] = ()
    note: str = ""


class SourceReading(BaseModel):
    """One source's reported value for a reconciled fact."""

    model_config = ConfigDict(frozen=True)

    source_id: str
    source_class: SourceClass
    value: str
    normalized_unit: str


class FactOutcome(BaseModel):
    """The cross-source reconciliation of one material fact."""

    model_config = ConfigDict(frozen=True)

    concept_qname: str
    status: AgreementStatus
    agreed_value: str | None
    agreed_sources: tuple[str, ...]
    corroborating_sources: tuple[str, ...]
    incompatible_sources: tuple[str, ...]
    first_party_source_count: int
    needs_human_review: bool
    readings: tuple[SourceReading, ...]


class CrossFootOutcome(BaseModel):
    """One evaluated accounting identity's result, projected for the report."""

    model_config = ConfigDict(frozen=True)

    identity: str
    passed: bool
    residual: str
    tolerance: str
    flagged_for_review: bool


class DodEvaluation(BaseModel):
    """The goal's Definition of Done, evaluated per stock."""

    model_config = ConfigDict(frozen=True)

    material_facts_agreed: bool
    cross_foot_holds: bool
    gold_file_written: bool
    no_unsourced_number: bool
    no_missing_material_concepts: bool

    @property
    def met(self) -> bool:
        """Whether every Definition-of-Done clause holds for this stock."""
        return (
            self.material_facts_agreed
            and self.cross_foot_holds
            and self.gold_file_written
            and self.no_unsourced_number
            and self.no_missing_material_concepts
        )


class StockReport(BaseModel):
    """Per-stock validation report: coverage, facts, discrepancies, and verdict."""

    model_config = ConfigDict(frozen=True)

    symbol: str
    name: str
    domain: str
    quarter: str
    outcome: StockOutcome
    sources: tuple[CollectedSource, ...]
    facts: tuple[FactOutcome, ...]
    discrepancies: tuple[FactOutcome, ...]
    missing_material_concepts: tuple[str, ...]
    cross_foot: tuple[CrossFootOutcome, ...]
    gold_file_path: str | None
    dod: DodEvaluation
    blockers: tuple[str, ...]
    identifiers_to_verify: tuple[str, ...]
    comparatives: tuple[ConceptComparative, ...] = ()

    @property
    def available_sources(self) -> tuple[str, ...]:
        """Source ids that returned observations for this stock."""
        return tuple(src.source_id for src in self.sources if src.status is SourceStatus.OK)
