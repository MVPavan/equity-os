"""Per-fact cross-source agreement classification.

Given every :class:`Observation` a set of sources reported for one comparison
column (same concept, period, scope, accounting basis, currency, unit, scale,
and dimensions), this module classifies how well those sources agree on the
value. It reuses the frozen comparison logic in :mod:`fundamentals.verify`
(``ComparisonKey`` for column identity, ``cross_check`` for the decimals-derived
numeric tolerance) rather than re-implementing any of it.

The classification honours two product invariants:

* **Two independent first-party sources are required to confirm a value.** NSE
  Ind AS XBRL, BSE XBRL, and an issuer results PDF are first-party; Screener and
  Tijori are *derived* aggregators. Derived sources may corroborate an agreed
  value but never count toward the required two — a fact confirmed only by
  derived sources (or by a single first-party source) is flagged
  ``SINGLE_FIRST_PARTY`` for human review.
* **Only compatible columns are compared.** Observations whose comparison key
  does not match the primary column (e.g. a standalone value mixed in with
  consolidated ones) are excluded from the numeric comparison and surfaced as
  incompatible, never silently footed together.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from decimal import Decimal
from enum import StrEnum

import structlog
from pydantic import BaseModel, ConfigDict

from fundamentals.contracts.observation import Observation
from fundamentals.contracts.provenance import Provenance
from fundamentals.verify.comparison_key import ComparisonKey
from fundamentals.verify.cross_check import cross_check
from fundamentals.verify.crossfoot import observation_half_ulp

_LOGGER = structlog.get_logger("fundamentals.reconcile.agreement")

# Source-id substrings that mark an aggregator (derived) source. Derived sources
# corroborate but never satisfy the required-two first-party count.
DERIVED_SOURCE_MARKERS: tuple[str, ...] = ("screener", "tijori")

# Default number of independent first-party sources required to confirm a value.
DEFAULT_REQUIRED_FIRST_PARTY = 2

# Default relative band for MINOR_DIFF: values within this fraction of the larger
# magnitude (but outside the tight decimals-derived tolerance) are a minor diff
# rather than a conflict.
DEFAULT_MINOR_DIFF_REL_TOLERANCE = Decimal("0.005")


class SourceClass(StrEnum):
    """Whether a source is an authoritative first-party filing or a derived aggregator."""

    FIRST_PARTY = "first_party"
    DERIVED = "derived"


class AgreementStatus(StrEnum):
    """Per-fact cross-source agreement outcome."""

    AGREE = "agree"
    MINOR_DIFF = "minor_diff"
    CONFLICT = "conflict"
    SINGLE_FIRST_PARTY = "single_first_party"


def classify_source(source_id: str) -> SourceClass:
    """Classify a ``source_id`` as first-party or derived (aggregator)."""
    lowered = source_id.lower()
    if any(marker in lowered for marker in DERIVED_SOURCE_MARKERS):
        return SourceClass.DERIVED
    return SourceClass.FIRST_PARTY


class AgreementPolicy(BaseModel):
    """Tunable thresholds for the agreement classifier."""

    model_config = ConfigDict(frozen=True)

    required_first_party: int = DEFAULT_REQUIRED_FIRST_PARTY
    minor_diff_rel_tolerance: Decimal = DEFAULT_MINOR_DIFF_REL_TOLERANCE


DEFAULT_POLICY = AgreementPolicy()


class SourceValue(BaseModel):
    """One source's reported value for a fact, with its provenance binding."""

    model_config = ConfigDict(frozen=True)

    source_id: str
    source_class: SourceClass
    normalized_value: Decimal
    normalized_unit: str
    provenance: Provenance


class AgreementResult(BaseModel):
    """Per-fact cross-source agreement outcome over one comparison column.

    ``agreed_value`` is the retained cross-source value: the value the winning
    first-party cluster concurs on (``AGREE``/``MINOR_DIFF``), the lone
    first-party value when only one exists (``SINGLE_FIRST_PARTY``), or ``None``
    when there is no first-party agreement to retain (``CONFLICT`` or a
    derived-only fact).
    """

    model_config = ConfigDict(frozen=True)

    comparison_key: ComparisonKey
    status: AgreementStatus
    agreed_value: Decimal | None
    normalized_unit: str
    source_values: tuple[SourceValue, ...]
    agreed_sources: tuple[str, ...]
    corroborating_sources: tuple[str, ...]
    incompatible_sources: tuple[str, ...]
    first_party_source_count: int

    @property
    def needs_human_review(self) -> bool:
        """A conflict or a fact lacking two first-party sources needs adjudication."""
        return self.status in (AgreementStatus.CONFLICT, AgreementStatus.SINGLE_FIRST_PARTY)


def _is_first_party(obs: Observation) -> bool:
    """Whether an observation comes from a first-party (non-derived) source."""
    return classify_source(obs.provenance.source_id) is SourceClass.FIRST_PARTY


def _primary_group(
    observations: Sequence[Observation],
) -> tuple[tuple[Observation, ...], tuple[str, ...]]:
    """Split observations into the majority comparison column and the incompatible rest.

    Groups by full comparison key preserving first-appearance order, then takes
    the largest group as the primary column. Sources outside it are returned as
    incompatible (excluded from numeric comparison).
    """
    groups: dict[ComparisonKey, list[Observation]] = {}
    for obs in observations:
        groups.setdefault(ComparisonKey.from_observation(obs), []).append(obs)
    primary_key = max(groups, key=lambda key: len(groups[key]))
    primary = tuple(groups[primary_key])
    primary_ids = {obs.provenance.source_id for obs in primary}
    incompatible = tuple(
        sorted(
            {
                obs.provenance.source_id
                for obs in observations
                if obs.provenance.source_id not in primary_ids
            }
        )
    )
    return primary, incompatible


def _cluster(
    observations: Sequence[Observation],
    matches: Callable[[Observation, Observation], bool],
) -> list[list[Observation]]:
    """Greedily group observations that agree, by single-linkage on each cluster head."""
    clusters: list[list[Observation]] = []
    for obs in observations:
        for cluster in clusters:
            if matches(cluster[0], obs):
                cluster.append(obs)
                break
        else:
            clusters.append([obs])
    return clusters


def _tight_match(left: Observation, right: Observation) -> bool:
    """Two observations agree within the decimals-derived tolerance (reuses cross_check)."""
    return cross_check(left, right).matched


def _minor_match_factory(rel_tolerance: Decimal) -> Callable[[Observation, Observation], bool]:
    """Build a looser-band matcher: within a relative band or the tight tolerance."""

    def _minor_match(left: Observation, right: Observation) -> bool:
        tight = observation_half_ulp(left) + observation_half_ulp(right)
        magnitude = max(abs(left.normalized_value), abs(right.normalized_value))
        band = rel_tolerance * magnitude
        residual = abs(left.normalized_value - right.normalized_value)
        return residual <= max(tight, band)

    return _minor_match


def _distinct_first_party(cluster: Sequence[Observation]) -> set[str]:
    """Distinct first-party source ids present in a cluster."""
    return {obs.provenance.source_id for obs in cluster if _is_first_party(obs)}


def _best_cluster(clusters: Sequence[list[Observation]]) -> list[Observation]:
    """The cluster confirmed by the most distinct first-party sources (empty if none)."""
    if not clusters:
        return []
    return max(clusters, key=lambda cluster: len(_distinct_first_party(cluster)))


def _representative(cluster: Sequence[Observation]) -> Observation | None:
    """A deterministic first-party representative of a cluster (lowest source id)."""
    first_party = sorted(
        (obs for obs in cluster if _is_first_party(obs)),
        key=lambda obs: obs.provenance.source_id,
    )
    return first_party[0] if first_party else None


def _source_values(observations: Sequence[Observation]) -> tuple[SourceValue, ...]:
    """Project each observation to its per-source value, ordered by source id."""
    values = [
        SourceValue(
            source_id=obs.provenance.source_id,
            source_class=classify_source(obs.provenance.source_id),
            normalized_value=obs.normalized_value,
            normalized_unit=obs.normalized_unit,
            provenance=obs.provenance,
        )
        for obs in observations
    ]
    return tuple(sorted(values, key=lambda value: value.source_id))


def _corroborating(
    representative: Observation | None,
    derived: Sequence[Observation],
    matches: Callable[[Observation, Observation], bool],
) -> tuple[str, ...]:
    """Distinct derived sources whose value corroborates the retained representative."""
    if representative is None:
        return ()
    return tuple(
        sorted({obs.provenance.source_id for obs in derived if matches(representative, obs)})
    )


def classify_agreement(
    observations: Sequence[Observation],
    policy: AgreementPolicy = DEFAULT_POLICY,
) -> AgreementResult:
    """Classify per-fact cross-source agreement for one comparison column.

    Fails closed on an empty observation set. Only observations sharing the
    primary comparison key are compared; derived sources corroborate but never
    satisfy the required first-party count.
    """
    if not observations:
        raise ValueError("classify_agreement requires at least one observation")

    primary, incompatible = _primary_group(observations)
    first_party = [obs for obs in primary if _is_first_party(obs)]
    derived = [obs for obs in primary if not _is_first_party(obs)]
    first_party_count = len(_distinct_first_party(primary))

    comparison_key = ComparisonKey.from_observation(primary[0])
    normalized_unit = primary[0].normalized_unit
    minor_match = _minor_match_factory(policy.minor_diff_rel_tolerance)

    tight_clusters = _cluster(first_party, _tight_match)
    best_tight = _best_cluster(tight_clusters)
    best_tight_count = len(_distinct_first_party(best_tight))

    loose_clusters = _cluster(first_party, minor_match)
    best_loose = _best_cluster(loose_clusters)
    best_loose_count = len(_distinct_first_party(best_loose))

    winning: list[Observation]
    if first_party_count < policy.required_first_party:
        status = AgreementStatus.SINGLE_FIRST_PARTY
        winning = first_party  # 0 or 1 observations
    elif best_tight_count >= policy.required_first_party:
        status = AgreementStatus.AGREE
        winning = best_tight
    elif best_loose_count >= policy.required_first_party:
        status = AgreementStatus.MINOR_DIFF
        winning = best_loose
    else:
        status = AgreementStatus.CONFLICT
        winning = []

    representative = _representative(winning)
    agreed_value = representative.normalized_value if representative is not None else None
    agreed_sources = tuple(sorted(_distinct_first_party(winning)))
    corroborating = _corroborating(representative, derived, minor_match)

    _LOGGER.debug(
        "classified_agreement",
        concept=comparison_key.concept_qname,
        status=str(status),
        first_party_source_count=first_party_count,
        agreed_sources=list(agreed_sources),
        corroborating_sources=list(corroborating),
        incompatible_sources=list(incompatible),
    )

    return AgreementResult(
        comparison_key=comparison_key,
        status=status,
        agreed_value=agreed_value,
        normalized_unit=normalized_unit,
        source_values=_source_values(primary),
        agreed_sources=agreed_sources,
        corroborating_sources=corroborating,
        incompatible_sources=incompatible,
        first_party_source_count=first_party_count,
    )
