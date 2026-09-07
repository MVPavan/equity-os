"""Collect run-time comparatives from declared, hash-pinned XBRL instances."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from decimal import DecimalException
from pathlib import Path

from pydantic import ValidationError

from fundamentals.api.comparatives import (
    REASON_INCOMPATIBLE,
    REASON_SELECTION_FAILED,
    _calculate,
    _unavailable,
)
from fundamentals.api.config import ComparatorInstanceConfig, FundamentalsConfig
from fundamentals.api.pipeline import _normalize_entity
from fundamentals.contracts.comparative import (
    TAXONOMY_DRIFT_PREFIX,
    ComparativeChange,
    ComparatorKind,
    ConceptComparative,
)
from fundamentals.contracts.observation import Observation, PeriodType, Scope
from fundamentals.contracts.provenance import Provenance
from fundamentals.extract.xbrl_parser import (
    FactSelectionError,
    XbrlParseError,
    parse_instance,
    select_observation,
)
from fundamentals.extract.xbrl_taxonomies import _ALL_TAXONOMIES
from fundamentals.verify.comparison_key import ComparisonKey


class RunComparativesError(RuntimeError):
    """Raised when a declared prior XBRL instance cannot be proven usable."""


def _instance(config: FundamentalsConfig, kind: ComparatorKind) -> ComparatorInstanceConfig | None:
    """Return the declared instance for one comparator kind, if any."""
    if config.comparators is None:
        return None
    return config.comparators.qoq if kind is ComparatorKind.QOQ else config.comparators.yoy


def _load_instance(
    config: FundamentalsConfig,
    config_path: Path,
    kind: ComparatorKind,
    instance: ComparatorInstanceConfig,
) -> tuple[Observation, ...]:
    """Hash-verify, parse, and entity-normalise one declared prior instance."""
    path = config.comparator_path(config_path, kind)
    if path is None:
        raise RunComparativesError(f"no {kind.value} comparator path declared")
    try:
        xml_bytes = path.read_bytes()
    except OSError as error:
        raise RunComparativesError(
            f"cannot read {kind.value} comparator {path}: {error}"
        ) from error
    actual_sha256 = hashlib.sha256(xml_bytes).hexdigest()
    if actual_sha256 != instance.sha256:
        raise RunComparativesError(
            f"{kind.value} comparator sha256 mismatch: expected {instance.sha256}, "
            f"got {actual_sha256}"
        )
    try:
        parsed = parse_instance(
            xml_bytes,
            source_id=config.xbrl.source_id,
            file_sha256=actual_sha256,
            retrieved_at=config.quarter.knowledge_cutoff,
            taxonomies=_ALL_TAXONOMIES,
        )
    except (DecimalException, ValidationError, ValueError, XbrlParseError) as error:
        raise RunComparativesError(
            f"cannot parse {kind.value} comparator {path}: {error}"
        ) from error
    return tuple(
        _normalize_entity(
            observation,
            config.xbrl.entity_scheme_aliases,
            config.xbrl.entity_id_aliases,
            config.issuer.entity_scheme,
        )
        for observation in parsed.observations
    )


def _select_prior(
    observations: tuple[Observation, ...],
    current_concept: str,
    instance: ComparatorInstanceConfig,
) -> Observation:
    """Select the sole consolidated, dimension-free prior by configured local name."""
    local_name = current_concept.split(":", 1)[-1]
    candidates = tuple(
        observation
        for observation in observations
        if observation.concept_qname.split(":", 1)[-1] == local_name
    )
    qnames = {observation.concept_qname for observation in candidates}
    if len(qnames) != 1:
        raise FactSelectionError(
            f"local-name comparator selector for {local_name!r} matched {len(qnames)} concepts"
        )
    return select_observation(
        candidates,
        concept_qname=qnames.pop(),
        scope=Scope.CONSOLIDATED,
        period_type=PeriodType.DURATION,
        period_start=instance.period_start,
        period_end=instance.period_end,
    )


def _taxonomy_drift(current: Observation, prior: Observation) -> str | None:
    """Describe semantic taxonomy drift that requires an analyst opt-in."""
    current_prefix = current.concept_qname.split(":", 1)[0]
    prior_prefix = prior.concept_qname.split(":", 1)[0]
    current_identity = (current.taxonomy_namespace, current.registry_version)
    prior_identity = (prior.taxonomy_namespace, prior.registry_version)
    reasons: list[str] = []
    if current_prefix != prior_prefix:
        reasons.append(f"concept prefix {current_prefix!r} != {prior_prefix!r}")
    if current_identity != prior_identity:
        reasons.append(f"taxonomy identity {current_identity!r} != {prior_identity!r}")
    return f"{TAXONOMY_DRIFT_PREFIX}{'; '.join(reasons)}" if reasons else None


def _change(
    *,
    kind: ComparatorKind,
    current: Observation,
    observations: tuple[Observation, ...] | None,
    instance: ComparatorInstanceConfig | None,
) -> ComparativeChange:
    """Select, key-check, and calculate one run-time prior comparison."""
    if instance is None:
        assert current.period_start is not None
        assert current.period_end is not None
        return _unavailable(
            kind,
            current.period_start,
            current.period_end,
            f"no {kind.value} comparator declared",
        )
    if observations is None:
        raise RunComparativesError(f"declared {kind.value} comparator was not loaded")
    try:
        prior = _select_prior(observations, current.concept_qname, instance)
    except FactSelectionError as error:
        return _unavailable(
            kind,
            instance.period_start,
            instance.period_end,
            REASON_SELECTION_FAILED.format(error=error),
        )

    drift = _taxonomy_drift(current, prior)
    if drift is not None and not instance.accept_taxonomy_drift:
        return _unavailable(kind, instance.period_start, instance.period_end, drift)
    comparable_prior = prior
    if drift is not None:
        comparable_prior = prior.model_copy(
            update={
                "concept_qname": current.concept_qname,
                "taxonomy_namespace": current.taxonomy_namespace,
                "registry_version": current.registry_version,
            }
        )
    compatibility = ComparisonKey.from_observation(current).comparative_compatibility(
        ComparisonKey.from_observation(comparable_prior)
    )
    if not compatibility.comparable:
        return _unavailable(
            kind,
            instance.period_start,
            instance.period_end,
            REASON_INCOMPATIBLE.format(reasons="; ".join(compatibility.reasons)),
        )
    return _calculate(
        kind=kind,
        period_start=instance.period_start,
        period_end=instance.period_end,
        current_value=current.normalized_value,
        prior=prior,
    ).model_copy(update={"taxonomy_drift": drift})


def collect_run_comparatives(
    config: FundamentalsConfig,
    *,
    config_path: Path,
    current: Mapping[str, Observation],
    current_sources: Mapping[str, tuple[Provenance, ...]],
) -> tuple[ConceptComparative, ...]:
    """Build QoQ and YoY changes for configured role concepts in their declared order."""
    observations: dict[ComparatorKind, tuple[Observation, ...] | None] = {}
    instances = {kind: _instance(config, kind) for kind in ComparatorKind}
    for kind, instance in instances.items():
        observations[kind] = (
            _load_instance(config, config_path, kind, instance) if instance is not None else None
        )

    comparatives: list[ConceptComparative] = []
    for role_concept in config.concepts.roles:
        concept = role_concept.concept_qname
        current_observation = current.get(concept)
        if current_observation is None:
            comparatives.append(
                ConceptComparative(
                    concept_qname=concept,
                    current_unavailable_reason="no selected current XBRL observation",
                    qoq=_unavailable(
                        ComparatorKind.QOQ,
                        config.quarter.period_start,
                        config.quarter.period_end,
                        "no selected current XBRL observation",
                    ),
                    yoy=_unavailable(
                        ComparatorKind.YOY,
                        config.quarter.period_start,
                        config.quarter.period_end,
                        "no selected current XBRL observation",
                    ),
                )
            )
            continue
        changes = {
            kind: _change(
                kind=kind,
                current=current_observation,
                observations=observations[kind],
                instance=instances[kind],
            )
            for kind in ComparatorKind
        }
        comparatives.append(
            ConceptComparative(
                concept_qname=concept,
                current_value=current_observation.normalized_value,
                unit=current_observation.normalized_unit,
                current_sources=current_sources[concept],
                qoq=changes[ComparatorKind.QOQ],
                yoy=changes[ComparatorKind.YOY],
            )
        )
    return tuple(comparatives)
