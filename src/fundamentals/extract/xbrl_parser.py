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

CURRENCY_INR = "INR"
CRORE_SCALE = 10_000_000
PER_SHARE_SCALE = 1
UNIT_CRORE = "INR crore"
UNIT_PER_SHARE = "INR per share"

SHARES_MEASURE_MARKER = "shares"
# XBRL allows decimals="INF"; represent it with a large finite precision marker.
INF_DECIMALS = 15


class XbrlParseError(Exception):
    """Raised when an instance cannot be parsed into trustworthy observations."""


class FactSelectionError(Exception):
    """Raised when a comparison key does not match exactly one observation."""


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
        segment = entity.find(f"{_XBRLI}segment")
        if segment is not None:
            for member in segment.findall(f"{_XBRLDI}explicitMember"):
                axis = member.get("dimension")
                value = (member.text or "").strip()
                if axis is not None:
                    dimensions.append((axis, value))

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


def _file_scope(root: Any) -> Scope:
    """Read the file-level consolidation scope, failing closed if absent.

    Scope is a property of the whole filing, not of a context id — the
    standalone and consolidated files reuse the same ``OneD`` id, so context_ref
    alone cannot discriminate them.
    """
    element = root.find(f"{{{FIN_NAMESPACE}}}{SCOPE_CONCEPT}")
    if element is None:
        raise XbrlParseError(
            f"instance declares no {FIN_PREFIX}:{SCOPE_CONCEPT}; scope is unprovable"
        )
    text = (element.text or "").strip()
    if text == SCOPE_CONSOLIDATED_TEXT:
        return Scope.CONSOLIDATED
    if text == SCOPE_STANDALONE_TEXT:
        return Scope.STANDALONE
    raise XbrlParseError(f"unrecognised report nature {text!r}")


def _measure_to_unit(measure: str) -> tuple[str, str, int]:
    """Map an XBRL unit measure to ``(currency, normalized_unit, scale)``.

    Monetary INR amounts are reported in full rupees and normalized to crore;
    per-share amounts are left at scale 1.
    """
    if SHARES_MEASURE_MARKER in measure:
        return CURRENCY_INR, UNIT_PER_SHARE, PER_SHARE_SCALE
    if measure.startswith("iso4217:"):
        currency = measure.split(":", 1)[1].split("/", 1)[0]
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
) -> tuple[Observation, ...]:
    """Parse an Ind AS XBRL instance into context-bound observations.

    Only numeric facts (those carrying a ``unitRef`` and a decimal value) become
    observations; text facts such as the scope declaration are read for context
    but not emitted. Every observation carries a non-null XBRL-anchored
    ``Provenance`` and the full comparison key needed to reject a distractor.
    """
    try:
        root = etree.fromstring(xml_bytes)
    except etree.XMLSyntaxError as exc:
        raise XbrlParseError(f"instance is not well-formed XML: {exc}") from exc

    contexts = _parse_contexts(root)
    units = _parse_units(root)
    scope = _file_scope(root)

    observations: list[Observation] = []
    fin_tag_prefix = f"{{{FIN_NAMESPACE}}}"
    for element in root.iter():
        tag = element.tag
        if not isinstance(tag, str) or not tag.startswith(fin_tag_prefix):
            continue
        unit_ref = element.get("unitRef")
        if unit_ref is None:
            continue
        context_ref = element.get("contextRef")
        if context_ref is None or context_ref not in contexts:
            continue
        measure = units.get(unit_ref)
        if measure is None:
            raise XbrlParseError(f"fact references unknown unit {unit_ref!r}")

        raw_value = (element.text or "").strip()
        try:
            raw_decimal = Decimal(raw_value)
        except InvalidOperation:
            continue

        local_name = tag[len(fin_tag_prefix) :]
        currency, normalized_unit, scale = _measure_to_unit(measure)
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
                concept_qname=f"{FIN_PREFIX}:{local_name}",
                taxonomy_namespace=FIN_NAMESPACE,
                registry_version=REGISTRY_VERSION,
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
    return tuple(observations)


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
