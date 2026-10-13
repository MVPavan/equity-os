"""Qualification scope: where a demonstrated tier holds, checked per measurement.

Shared by dictionary formulas, mapping entries and construction rules (data spec §2).
Outside its recorded scope a demonstrated tier is ``EQUIVALENCE_UNPROVEN``. Scope is by
schema, surface, basis and period kind plus typed conditions, never by calendar quarter.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from types import MappingProxyType
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, PlainSerializer, model_validator

from fundamentals.contracts.canonical import Basis, PeriodKind
from fundamentals.contracts.evidence_tier import EvidenceTier
from fundamentals.contracts.measurement_key import MeasurementKey

_CONFLICTING_CONDITION = (
    "condition {condition_id!r} is declared more than once with different meanings"
)
_CONDITION_AND_EXCLUSION = "condition {condition_id!r} is both a condition and an exclusion"
_MISFILED_PROOF = "proof keyed {key!r} is for condition {condition_id!r}"


class ConditionPredicate(StrEnum):
    """What a qualification condition asserts about another canonical value."""

    EQUALS_ZERO = "EQUALS_ZERO"
    NOT_EQUALS_ZERO = "NOT_EQUALS_ZERO"


class QualificationCondition(BaseModel):
    """A fact about the same package, period and basis, e.g. discontinued profit is zero."""

    model_config = ConfigDict(frozen=True)

    condition_id: str = Field(min_length=1)
    canonical_id: str = Field(min_length=1)
    predicate: ConditionPredicate


class ProvenCondition(BaseModel):
    """Whether a condition held for one measurement, and the interpretations that showed it."""

    model_config = ConfigDict(frozen=True)

    condition_id: str = Field(min_length=1)
    holds: bool
    evidence_interpretation_ids: tuple[int, ...] = Field(min_length=1)


class QualificationFixture(BaseModel):
    """A hash-pinned measured capture and its company identity for the D3 sample rule."""

    model_config = ConfigDict(frozen=True)

    capture_id: str = Field(min_length=1)
    capture_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    entity_id: int = Field(gt=0)
    discriminating: bool = False


class QualificationScope(BaseModel):
    """The recorded scope inside which a demonstrated tier holds."""

    model_config = ConfigDict(frozen=True)

    scope_id: str = Field(min_length=1)
    schema_identities: frozenset[str]
    surfaces: frozenset[str]
    bases: frozenset[Basis]
    period_kinds: frozenset[PeriodKind]
    conditions: tuple[QualificationCondition, ...] = ()
    exclusions: tuple[QualificationCondition, ...] = ()
    fixture_capture_sha256s: tuple[str, ...] = ()
    fixture_evidence: tuple[QualificationFixture, ...] = ()
    sample_rule: str | None = None

    @model_validator(mode="after")
    def _one_meaning_per_condition(self) -> QualificationScope:
        """Refuse a condition id reused with another meaning, or both required and excluded."""
        meanings: dict[str, QualificationCondition] = {}
        for condition in self.conditions + self.exclusions:
            seen = meanings.setdefault(condition.condition_id, condition)
            if seen != condition:
                raise ValueError(_CONFLICTING_CONDITION.format(condition_id=condition.condition_id))
        required = {condition.condition_id for condition in self.conditions}
        for exclusion in self.exclusions:
            if exclusion.condition_id in required:
                raise ValueError(
                    _CONDITION_AND_EXCLUSION.format(condition_id=exclusion.condition_id)
                )
        return self


def _frozen_proofs(proofs: Mapping[str, ProvenCondition]) -> Mapping[str, ProvenCondition]:
    """Copy the proofs into a read-only mapping."""
    return MappingProxyType(dict(proofs))


# Read-only once validated, so a frozen context cannot have proofs added or swapped later.
ProofMapping = Annotated[
    Mapping[str, ProvenCondition], AfterValidator(_frozen_proofs), PlainSerializer(dict)
]


class QualificationContext(BaseModel):
    """Where one measurement was observed; per measurement, never per capture or package."""

    model_config = ConfigDict(frozen=True)

    schema_identity: str
    surface: str
    basis: Basis
    period_kind: PeriodKind
    proven: ProofMapping

    @model_validator(mode="after")
    def _proofs_filed_under_their_condition(self) -> QualificationContext:
        """Refuse a proof stored under another condition's id."""
        for key, proof in self.proven.items():
            if key != proof.condition_id:
                raise ValueError(_MISFILED_PROOF.format(key=key, condition_id=proof.condition_id))
        return self


class ScopedTier(BaseModel):
    """A tier after its scope was checked, with the scope id and condition evidence that held."""

    model_config = ConfigDict(frozen=True)

    tier: EvidenceTier
    qualification_ref: str | None
    condition_evidence: tuple[ProvenCondition, ...]


def qualification_context(
    key: MeasurementKey,
    *,
    schema_identity: str,
    surface: str,
    fiscal_year_end_month: int,
    proven: Mapping[str, ProvenCondition],
) -> QualificationContext:
    """Build the context for one key: its own basis and its own period's kind."""
    return QualificationContext(
        schema_identity=schema_identity,
        surface=surface,
        basis=key.basis,
        period_kind=key.period.kind(fiscal_year_end_month),
        proven=proven,
    )


def scoped_tier(
    tier: EvidenceTier, scope: QualificationScope | None, context: QualificationContext
) -> ScopedTier:
    """Resolve a declared tier against its scope for one measurement.

    A demonstrated tier stays demonstrated only when schema, surface, basis and
    period kind are in scope, every condition is proven to hold and every
    exclusion is proven not to hold. No scope, out of scope, or a condition or
    exclusion unproven either way gives ``EQUIVALENCE_UNPROVEN`` with no ref.
    A tier below demonstrated is returned unchanged: scope can only withhold
    strength, never add it.
    """
    if tier is not EvidenceTier.EQUIVALENCE_DEMONSTRATED:
        return ScopedTier(tier=tier, qualification_ref=None, condition_evidence=())
    unproven = ScopedTier(
        tier=EvidenceTier.EQUIVALENCE_UNPROVEN, qualification_ref=None, condition_evidence=()
    )
    if scope is None or not _qualification_evidenced(scope) or not _in_scope(scope, context):
        return unproven
    evidence: list[ProvenCondition] = []
    for condition, must_hold in _checks(scope):
        proven = context.proven.get(condition.condition_id)
        if proven is None or proven.holds is not must_hold:
            return unproven
        evidence.append(proven)
    return ScopedTier(
        tier=tier, qualification_ref=scope.scope_id, condition_evidence=tuple(evidence)
    )


def _qualification_evidenced(scope: QualificationScope) -> bool:
    """D3 needs five distinct companies, a discriminating measured case and a sample rule.

    Bare scope declarations or capture hashes cannot establish company diversity. Filing
    alignment proofs are applied separately and do not pass through this global rule.
    """
    fixtures = scope.fixture_evidence
    hashes = {fixture.capture_sha256 for fixture in fixtures}
    captures = {fixture.capture_id for fixture in fixtures}
    return (
        scope.sample_rule is not None
        and bool(scope.sample_rule.strip())
        and len({fixture.entity_id for fixture in fixtures}) >= 5
        and len(hashes) == len(fixtures)
        and len(captures) == len(fixtures)
        and any(fixture.discriminating for fixture in fixtures)
        and (not scope.fixture_capture_sha256s or hashes == set(scope.fixture_capture_sha256s))
    )


def _in_scope(scope: QualificationScope, context: QualificationContext) -> bool:
    """Whether schema, surface, basis and period kind all fall inside the scope."""
    return (
        context.schema_identity in scope.schema_identities
        and context.surface in scope.surfaces
        and context.basis in scope.bases
        and context.period_kind in scope.period_kinds
    )


def _checks(scope: QualificationScope) -> list[tuple[QualificationCondition, bool]]:
    """Pair each condition with ``True`` (must hold) and each exclusion with ``False``."""
    return [(condition, True) for condition in scope.conditions] + [
        (exclusion, False) for exclusion in scope.exclusions
    ]
