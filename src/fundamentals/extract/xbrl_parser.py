"""Context-aware parser for NSE Ind AS (in-bse-fin) XBRL instances.

Fact-identity collapse is the dominant failure mode this module guards against:
the same concept element appears under several ``xbrli:context`` refs (reporting
quarter, year-to-date, prior-year, segment) and, across the standalone/
consolidated files, under the *same* context id. A plausible label and value are
never sufficient — an :class:`~fundamentals.contracts.observation.Observation`
is only trusted once its full comparison key (concept QName, scope, period,
unit, dimensions, accounting basis) is bound to the context it was measured in.

Two responsibilities live here:

* :func:`parse_observations` — read every numeric fact into a context-bound
  ``Observation`` with a non-null XBRL ``Provenance``. File-level scope is taken
  from ``NatureOfReportStandaloneConsolidated`` (fail-closed if absent), never
  guessed from a context id.
* :func:`select_observation` — pick the single observation matching an explicit
  comparison key, raising when zero or many match so a distractor can never be
  silently substituted for the intended fact.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from lxml import etree  # type: ignore[import-untyped]
from pydantic import BaseModel, ConfigDict

from fundamentals.contracts.observation import (
    AccountingFramework,
    Observation,
    PeriodType,
    Scope,
)
from fundamentals.contracts.provenance import Provenance, SourceAnchorType

# --- XBRL namespaces (fixed for the in-bse-fin 2020-03-31 taxonomy) -----------

NS_XBRLI = "http://www.xbrl.org/2003/instance"
NS_XBRLDI = "http://xbrl.org/2006/xbrldi"
FIN_NAMESPACE = "http://www.bseindia.com/xbrl/fin/2020-03-31/in-bse-fin"
FIN_PREFIX = "in-bse-fin"
REGISTRY_VERSION = "in-bse-fin/2020-03-31"

_XBRLI = f"{{{NS_XBRLI}}}"
_XBRLDI = f"{{{NS_XBRLDI}}}"

# --- Domain constants ---------------------------------------------------------

SCOPE_CONCEPT = "NatureOfReportStandaloneConsolidated"
SCOPE_CONSOLIDATED_TEXT = "Consolidated"
SCOPE_STANDALONE_TEXT = "Standalone"


class TaxonomySpec(BaseModel):
    """A supported taxonomy: its namespace, prefix, registry version, and scope tag.

    Concept resolution dispatches through a registry of these specs rather than a
    single hard-coded namespace, so a filing under another taxonomy (e.g. a newer
    ``in-bse-fin`` revision, or ``in-capmkt``) can be mapped by adding a spec. An
    instance that matches no registered taxonomy fails closed rather than silently
    yielding zero facts.
    """

    model_config = ConfigDict(frozen=True)

    namespace: str
    prefix: str
    registry_version: str
    scope_concept: str = SCOPE_CONCEPT
    consolidated_text: str = SCOPE_CONSOLIDATED_TEXT
    standalone_text: str = SCOPE_STANDALONE_TEXT


DEFAULT_TAXONOMIES: tuple[TaxonomySpec, ...] = (
    TaxonomySpec(
        namespace=FIN_NAMESPACE,
        prefix=FIN_PREFIX,
        registry_version=REGISTRY_VERSION,
    ),
)

CRORE_SCALE = 10_000_000
PER_SHARE_SCALE = 1
DIMENSIONLESS_SCALE = 1
UNIT_CRORE = "INR crore"
UNIT_PER_SHARE = "INR per share"
UNIT_PURE = "pure"
UNIT_SHARES = "shares"

ISO4217_PREFIX = "iso4217:"
SHARES_MEASURE_MARKER = "shares"
PURE_MEASURE = "xbrli:pure"
SHARES_MEASURE = "xbrli:shares"
DIVIDE_SEPARATOR = "/"
# XBRL allows decimals="INF"; represent it with a large finite precision marker.
INF_DECIMALS = 15


class XbrlParseError(Exception):
    """Raised when an instance cannot be parsed into trustworthy observations."""


class FactSelectionError(Exception):
    """Raised when a comparison key does not match exactly one observation."""


class FactRejection(BaseModel):
    """A structured diagnostic for a numeric fact the parser could not trust.

    Rejections make silent data loss visible: a fact with an absent/unknown
    context, an invalid numeric value, or a concept outside the filing taxonomy
    is recorded here (unless it is a *required* concept, which fails closed).
    """

    model_config = ConfigDict(frozen=True)

    concept_qname: str
    context_ref: str | None
    reason: str


class ParseResult(BaseModel):
    """Parsed observations plus the structured rejections encountered."""

    model_config = ConfigDict(frozen=True)

    observations: tuple[Observation, ...]
    rejections: tuple[FactRejection, ...]


class _XbrlContext(BaseModel):
    """Resolved ``xbrli:context``: entity, period and explicit dimensions."""

    model_config = ConfigDict(frozen=True)

    context_id: str
    entity_scheme: str
    entity_id: str
    period_type: PeriodType
    period_start: date | None = None
    period_end: date | None = None
    period_instant: date | None = None
    dimensions: tuple[tuple[str, str], ...] = ()


def _collect_dimensions(container: Any) -> list[tuple[str, str]]:
    """Read explicit and typed dimension members from a segment/scenario container."""
    dimensions: list[tuple[str, str]] = []
    if container is None:
        return dimensions
    for member in container.findall(f"{_XBRLDI}explicitMember"):
        axis = member.get("dimension")
        if axis is not None:
            dimensions.append((axis, (member.text or "").strip()))
    for member in container.findall(f"{_XBRLDI}typedMember"):
        axis = member.get("dimension")
        if axis is not None:
            inner = "".join(part.strip() for part in member.itertext() if part.strip())
            dimensions.append((axis, f"typed:{inner}"))
    return dimensions


def _parse_contexts(root: Any) -> dict[str, _XbrlContext]:
    """Resolve every ``xbrli:context`` into a typed record keyed by id."""
    contexts: dict[str, _XbrlContext] = {}
    for element in root.findall(f"{_XBRLI}context"):
        context_id = element.get("id")
        if context_id is None:
            continue
        entity = element.find(f"{_XBRLI}entity")
        identifier = entity.find(f"{_XBRLI}identifier")
        period = element.find(f"{_XBRLI}period")

        start = period.find(f"{_XBRLI}startDate")
        end = period.find(f"{_XBRLI}endDate")
        instant = period.find(f"{_XBRLI}instant")
        if instant is not None:
            period_type = PeriodType.INSTANT
            period_instant: date | None = date.fromisoformat(instant.text.strip())
            period_start: date | None = None
            period_end: date | None = None
        elif start is not None and end is not None:
            period_type = PeriodType.DURATION
            period_start = date.fromisoformat(start.text.strip())
            period_end = date.fromisoformat(end.text.strip())
            period_instant = None
        else:
            raise XbrlParseError(f"context {context_id!r} has no resolvable period")

        dimensions: list[tuple[str, str]] = []
        # Dimensions can live under entity/segment OR context/scenario; a segment
        # fact hidden under scenario must NOT appear dimension-free (and thus
        # eligible as the consolidated total). Typed members are captured too, so
        # an unsupported dimensional construct is never treated as undimensioned.
        dimensions.extend(_collect_dimensions(entity.find(f"{_XBRLI}segment")))
        dimensions.extend(_collect_dimensions(element.find(f"{_XBRLI}scenario")))

        contexts[context_id] = _XbrlContext(
            context_id=context_id,
            entity_scheme=identifier.get("scheme"),
            entity_id=(identifier.text or "").strip(),
            period_type=period_type,
            period_start=period_start,
            period_end=period_end,
            period_instant=period_instant,
            dimensions=tuple(dimensions),
        )
    return contexts


def _parse_units(root: Any) -> dict[str, str]:
    """Map each ``xbrli:unit`` id to a normalized measure string.

    A simple monetary unit resolves to e.g. ``"iso4217:INR"``; a per-share unit
    resolves to ``"iso4217:INR/xbrli:shares"``.
    """
    units: dict[str, str] = {}
    for element in root.findall(f"{_XBRLI}unit"):
        unit_id = element.get("id")
        if unit_id is None:
            continue
        measure = element.find(f"{_XBRLI}measure")
        if measure is not None:
            units[unit_id] = (measure.text or "").strip()
            continue
        divide = element.find(f"{_XBRLI}divide")
        if divide is not None:
            numerator = divide.find(f"{_XBRLI}unitNumerator/{_XBRLI}measure")
            denominator = divide.find(f"{_XBRLI}unitDenominator/{_XBRLI}measure")
            num_text = (numerator.text or "").strip() if numerator is not None else ""
            den_text = (denominator.text or "").strip() if denominator is not None else ""
            units[unit_id] = f"{num_text}/{den_text}"
    return units


def _detect_taxonomy(root: Any, taxonomies: tuple[TaxonomySpec, ...]) -> TaxonomySpec:
    """Dispatch to the registered taxonomy whose scope tag the instance declares.

    Fails closed when no registered taxonomy matches (rather than returning an
    empty result), and when more than one matches (ambiguous filing).
    """
    matched = [
        spec
        for spec in taxonomies
        if root.find(f"{{{spec.namespace}}}{spec.scope_concept}") is not None
    ]
    if not matched:
        supported = ", ".join(spec.registry_version for spec in taxonomies)
        raise XbrlParseError(
            "instance matches no supported taxonomy "
            f"(scope concept absent for all of: {supported}); refusing to yield an empty result"
        )
    if len(matched) > 1:
        raise XbrlParseError(
            "instance declares scope under multiple supported taxonomies: "
            + ", ".join(spec.registry_version for spec in matched)
        )
    return matched[0]


def _file_scope(root: Any, spec: TaxonomySpec) -> Scope:
    """Read the file-level consolidation scope, failing closed if absent.

    Scope is a property of the whole filing, not of a context id — the
    standalone and consolidated files reuse the same ``OneD`` id, so context_ref
    alone cannot discriminate them.
    """
    element = root.find(f"{{{spec.namespace}}}{spec.scope_concept}")
    if element is None:
        raise XbrlParseError(
            f"instance declares no {spec.prefix}:{spec.scope_concept}; scope is unprovable"
        )
    text = (element.text or "").strip()
    if text == spec.consolidated_text:
        return Scope.CONSOLIDATED
    if text == spec.standalone_text:
        return Scope.STANDALONE
    raise XbrlParseError(f"unrecognised report nature {text!r}")


def _measure_to_unit(measure: str) -> tuple[str | None, str, int]:
    """Map an XBRL unit measure to ``(currency, normalized_unit, scale)``.

    Monetary INR amounts are reported in full rupees and normalized to crore;
    a monetary-per-share divide unit (e.g. ``iso4217:INR/xbrli:shares``, EPS in
    currency terms) is left at scale 1 with the numerator currency. ``xbrli:pure``
    (dimensionless ratios, per-share EPS reported as a plain ratio, percentages)
    and a bare ``xbrli:shares`` (share counts) carry no currency and stay at scale
    1. An unrecognised measure raises so the caller can degrade that single fact to
    a rejection rather than aborting the whole instance.
    """
    if DIVIDE_SEPARATOR in measure:
        numerator, denominator = measure.split(DIVIDE_SEPARATOR, 1)
        if numerator.startswith(ISO4217_PREFIX) and SHARES_MEASURE_MARKER in denominator:
            currency = numerator.split(":", 1)[1]
            return currency, UNIT_PER_SHARE, PER_SHARE_SCALE
        raise XbrlParseError(f"unsupported unit measure {measure!r}")
    if measure == PURE_MEASURE:
        return None, UNIT_PURE, DIMENSIONLESS_SCALE
    if measure == SHARES_MEASURE:
        return None, UNIT_SHARES, DIMENSIONLESS_SCALE
    if measure.startswith(ISO4217_PREFIX):
        currency = measure.split(":", 1)[1]
        return currency, UNIT_CRORE, CRORE_SCALE
    raise XbrlParseError(f"unsupported unit measure {measure!r}")


def _decimals(raw: str | None) -> int:
    """Read the XBRL ``decimals`` attribute, mapping ``INF`` to a finite marker."""
    if raw is None:
        raise XbrlParseError("numeric fact is missing a decimals attribute")
    if raw.strip().upper() == "INF":
        return INF_DECIMALS
    return int(raw)


def parse_observations(
    xml_bytes: bytes,
    *,
    source_id: str,
    file_sha256: str,
    retrieved_at: datetime,
    taxonomies: tuple[TaxonomySpec, ...] = DEFAULT_TAXONOMIES,
    required_concepts: frozenset[str] = frozenset(),
) -> tuple[Observation, ...]:
    """Parse an Ind AS XBRL instance into context-bound observations.

    Thin wrapper over :func:`parse_instance` returning only the observations, so
    existing callers are unchanged; use :func:`parse_instance` to also inspect the
    structured rejection diagnostics.
    """
    return parse_instance(
        xml_bytes,
        source_id=source_id,
        file_sha256=file_sha256,
        retrieved_at=retrieved_at,
        taxonomies=taxonomies,
        required_concepts=required_concepts,
    ).observations


def parse_instance(
    xml_bytes: bytes,
    *,
    source_id: str,
    file_sha256: str,
    retrieved_at: datetime,
    taxonomies: tuple[TaxonomySpec, ...] = DEFAULT_TAXONOMIES,
    required_concepts: frozenset[str] = frozenset(),
) -> ParseResult:
    """Parse an XBRL instance into context-bound observations plus diagnostics.

    Concept resolution dispatches through ``taxonomies`` (fail closed if the
    instance matches none). Only numeric facts (carrying a ``unitRef`` and a
    decimal value) become observations. A fact with an absent/unknown context, an
    invalid numeric value, or a concept outside the filing taxonomy is recorded as
    a structured :class:`FactRejection` — never silently dropped — and aborts the
    parse when its concept is in ``required_concepts``. Every required concept
    must yield at least one observation, or the parse fails closed.
    """
    try:
        root = etree.fromstring(xml_bytes)
    except etree.XMLSyntaxError as exc:
        raise XbrlParseError(f"instance is not well-formed XML: {exc}") from exc

    spec = _detect_taxonomy(root, taxonomies)
    contexts = _parse_contexts(root)
    units = _parse_units(root)
    scope = _file_scope(root, spec)

    observations: list[Observation] = []
    rejections: list[FactRejection] = []
    fin_tag_prefix = f"{{{spec.namespace}}}"
    for element in root.iter():
        tag = element.tag
        if not isinstance(tag, str):
            continue
        unit_ref = element.get("unitRef")
        if unit_ref is None:
            continue  # not a numeric fact
        if not tag.startswith(fin_tag_prefix):
            # A numeric fact outside the filing taxonomy is surfaced, not dropped.
            rejections.append(
                FactRejection(
                    concept_qname=_bare_qname(tag),
                    context_ref=element.get("contextRef"),
                    reason=f"numeric fact outside filing taxonomy {spec.registry_version}",
                )
            )
            continue

        local_name = tag[len(fin_tag_prefix) :]
        concept_qname = f"{spec.prefix}:{local_name}"
        context_ref = element.get("contextRef")
        if context_ref is None or context_ref not in contexts:
            _reject_or_abort(
                concept_qname,
                context_ref,
                "absent or unknown context",
                required_concepts,
                rejections,
            )
            continue

        measure = units.get(unit_ref)
        if measure is None:
            # An undefined unit id is a per-fact defect: degrade it (fail closed
            # only for a required concept) so one bad unitRef never blocks the
            # whole instance.
            _reject_or_abort(
                concept_qname,
                context_ref,
                f"references undefined unit {unit_ref!r}",
                required_concepts,
                rejections,
            )
            continue

        raw_value = (element.text or "").strip()
        try:
            raw_decimal = Decimal(raw_value)
        except InvalidOperation:
            _reject_or_abort(
                concept_qname,
                context_ref,
                f"invalid numeric value {raw_value!r}",
                required_concepts,
                rejections,
            )
            continue

        try:
            currency, normalized_unit, scale = _measure_to_unit(measure)
        except XbrlParseError as exc:
            # An unrecognised unit degrades that single fact to a rejection
            # (a required concept still fails closed), so one odd unit — e.g. a
            # never-before-seen measure on a minor line item — cannot abort the
            # entire instance and drop every other fact with it.
            _reject_or_abort(
                concept_qname,
                context_ref,
                str(exc),
                required_concepts,
                rejections,
            )
            continue
        normalized_value = raw_decimal / Decimal(scale)
        context = contexts[context_ref]

        provenance = Provenance(
            source_id=source_id,
            file_sha256=file_sha256,
            anchor_type=SourceAnchorType.XBRL_CONTEXT,
            context_ref=context_ref,
            retrieved_at=retrieved_at,
        )
        observations.append(
            Observation(
                concept_qname=concept_qname,
                taxonomy_namespace=spec.namespace,
                registry_version=spec.registry_version,
                raw_value=raw_value,
                normalized_value=normalized_value,
                normalized_unit=normalized_unit,
                context_ref=context_ref,
                entity_scheme=context.entity_scheme,
                entity_id=context.entity_id,
                scope=scope,
                accounting_basis=AccountingFramework.IND_AS,
                period_type=context.period_type,
                period_start=context.period_start,
                period_end=context.period_end,
                period_instant=context.period_instant,
                unit_ref=unit_ref,
                currency=currency,
                scale=scale,
                decimals=_decimals(element.get("decimals")),
                dimensions=context.dimensions,
                provenance=provenance,
            )
        )

    _require_completeness(required_concepts, observations)
    return ParseResult(observations=tuple(observations), rejections=tuple(rejections))


def _bare_qname(tag: str) -> str:
    """Return a readable ``{ns}local`` tag as ``local`` for diagnostics."""
    return tag.rsplit("}", 1)[-1]


def _reject_or_abort(
    concept_qname: str,
    context_ref: str | None,
    reason: str,
    required_concepts: frozenset[str],
    rejections: list[FactRejection],
) -> None:
    """Abort on a malformed required concept; otherwise record a rejection."""
    if concept_qname in required_concepts:
        raise XbrlParseError(
            f"required concept {concept_qname!r} has a malformed occurrence: {reason}"
        )
    rejections.append(
        FactRejection(concept_qname=concept_qname, context_ref=context_ref, reason=reason)
    )


def _require_completeness(
    required_concepts: frozenset[str], observations: list[Observation]
) -> None:
    """Fail closed when a required concept produced no observation at all."""
    present = {obs.concept_qname for obs in observations}
    missing = sorted(required_concepts - present)
    if missing:
        raise XbrlParseError(f"required concepts absent from instance: {missing}")


def select_observation(
    observations: tuple[Observation, ...],
    *,
    concept_qname: str,
    scope: Scope,
    period_type: PeriodType,
    period_start: date | None = None,
    period_end: date | None = None,
    period_instant: date | None = None,
    dimensions: tuple[tuple[str, str], ...] = (),
) -> Observation:
    """Return the single observation matching an explicit comparison key.

    The period and dimensions are part of the key, so a year-to-date, prior-year,
    standalone, segment-dimensioned or different-QName occurrence can never be
    substituted for the intended fact. Zero or multiple matches raise
    :class:`FactSelectionError` rather than guessing.
    """
    matches = [
        obs
        for obs in observations
        if obs.concept_qname == concept_qname
        and obs.scope is scope
        and obs.period_type is period_type
        and obs.period_start == period_start
        and obs.period_end == period_end
        and obs.period_instant == period_instant
        and obs.dimensions == dimensions
    ]
    if len(matches) == 1:
        return matches[0]
    raise FactSelectionError(
        f"comparison key for {concept_qname} ({scope.value}, "
        f"{period_start}..{period_end or period_instant}, dims={dimensions}) "
        f"matched {len(matches)} observations, expected exactly 1"
    )
