"""Shared canonical fact view for reconciliation and report sections."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from typing import Protocol

from fundamentals.contracts.observation import (
    AccountingFramework,
    Observation,
    PeriodType,
    Scope,
)
from fundamentals.contracts.provenance import Provenance
from fundamentals.contracts.role import FactRole
from fundamentals.extract.xbrl_parser import FactSelectionError, select_observation
from fundamentals.reconcile.agreement import AgreementResult, classify_agreement
from fundamentals.reconcile.report import (
    FIRST_PARTY_SOURCE_KINDS,
    XBRL_SOURCE_KINDS,
    CollectedSource,
    SourceStatus,
)

CANONICAL_ENTITY_SCHEME = "nse-symbol"

_DERIVED_ROLE_ALIASES: dict[FactRole, tuple[str, ...]] = {
    FactRole.REVENUE: ("screener:Sales", "tijori:sales"),
    FactRole.PROFIT_BEFORE_TAX: ("tijori:pbt",),
    FactRole.PROFIT_FOR_PERIOD: ("screener:NetProfit", "tijori:net_profit"),
    FactRole.BASIC_EPS: ("screener:EPS", "tijori:eps"),
}


class RoleConceptView(Protocol):
    """Read-only role/concept shape accepted from configuration models."""

    @property
    def role(self) -> FactRole:
        """Return the configured report role."""
        ...

    @property
    def concept_qname(self) -> str:
        """Return the configured concept QName."""
        ...


def material_concepts(
    roles: Sequence[RoleConceptView], cross_check: Sequence[str]
) -> tuple[str, ...]:
    """Return role concepts followed by any additional cross-check concepts."""
    ordered = dict.fromkeys(role.concept_qname for role in roles)
    for concept in cross_check:
        ordered.setdefault(concept, None)
    return tuple(ordered)


def derived_concept_map(roles: Sequence[RoleConceptView]) -> dict[str, str]:
    """Build the derived-concept to canonical-concept map from configured roles."""
    role_map = {role.role: role.concept_qname for role in roles}
    return {
        alias: canonical
        for role, aliases in _DERIVED_ROLE_ALIASES.items()
        if (canonical := role_map.get(role)) is not None
        for alias in aliases
    }


def canonicalise(
    observation: Observation,
    symbol: str,
    *,
    canonical_concept: str | None = None,
) -> Observation:
    """Project an observation onto the canonical cross-host comparison column."""
    updates: dict[str, object] = {
        "entity_scheme": CANONICAL_ENTITY_SCHEME,
        "entity_id": symbol,
        "taxonomy_namespace": None,
        "registry_version": None,
    }
    if canonical_concept is not None:
        updates.update(
            concept_qname=canonical_concept,
            scope=Scope.CONSOLIDATED,
            accounting_basis=AccountingFramework.IND_AS,
        )
    return observation.model_copy(update=updates)


def select_first_party(
    observations: Sequence[Observation],
    concept: str,
    *,
    period_start: date,
    period_end: date,
) -> Observation | None:
    """Select one segment-free consolidated-quarter observation, or return none."""
    try:
        return select_observation(
            tuple(observations),
            concept_qname=concept,
            scope=Scope.CONSOLIDATED,
            period_type=PeriodType.DURATION,
            period_start=period_start,
            period_end=period_end,
        )
    except FactSelectionError:
        return None


def _derived_for_concept(
    concept: str,
    source: CollectedSource,
    *,
    symbol: str,
    period_end: date,
    derived_map: dict[str, str],
) -> list[Observation]:
    """Re-express derived target-quarter observations onto one canonical concept."""
    return [
        canonicalise(observation, symbol, canonical_concept=concept)
        for observation in source.observations
        if derived_map.get(observation.concept_qname) == concept
        and observation.period_type is PeriodType.DURATION
        and observation.period_end == period_end
    ]


def gather_fact_observations(
    concept: str,
    sources: Sequence[CollectedSource],
    *,
    symbol: str,
    period_start: date,
    period_end: date,
    derived_map: dict[str, str],
) -> list[Observation]:
    """Collect and canonicalise every source observation for one concept."""
    gathered: list[Observation] = []
    for source in sources:
        if source.status is not SourceStatus.OK:
            continue
        if source.kind in XBRL_SOURCE_KINDS:
            picked = select_first_party(
                source.observations,
                concept,
                period_start=period_start,
                period_end=period_end,
            )
            if picked is not None:
                gathered.append(canonicalise(picked, symbol))
        elif source.kind in FIRST_PARTY_SOURCE_KINDS:
            gathered.extend(
                canonicalise(observation, symbol)
                for observation in source.observations
                if observation.concept_qname == concept
            )
        else:
            gathered.extend(
                _derived_for_concept(
                    concept,
                    source,
                    symbol=symbol,
                    period_end=period_end,
                    derived_map=derived_map,
                )
            )
    return gathered


def role_agreement(
    concept: str,
    sources: Sequence[CollectedSource],
    *,
    symbol: str,
    period_start: date,
    period_end: date,
    derived_map: dict[str, str],
) -> AgreementResult | None:
    """Classify one concept through the canonical shared fact view."""
    gathered = gather_fact_observations(
        concept,
        sources,
        symbol=symbol,
        period_start=period_start,
        period_end=period_end,
        derived_map=derived_map,
    )
    return classify_agreement(gathered) if gathered else None


def winning_anchors(result: AgreementResult) -> tuple[Provenance, ...]:
    """Return provenance for every retained first-party source value."""
    return tuple(
        value.provenance
        for value in result.source_values
        if value.source_id in result.agreed_sources
    )
