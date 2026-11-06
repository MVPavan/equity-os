"""The vendor-first policy, §6.4's predicates and §6.6's check class (VENDOR-1 spec).

T1 says how the two vendors relate, the filing state how the filing relates to them; each side
is its stored ``[lower, upper]`` interval. The check class digests every component that must
match before evidence is reused; the issuer class comes from onboarding provenance (reading 1).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, LiteralString

import yaml
from psycopg import Connection
from pydantic import BaseModel, ConfigDict

from equity_os.contracts.measurement.canonical import PeriodKind, Representation
from equity_os.contracts.measurement.evidence import (
    Interpretation,
    InterpretationOrigin,
    KnowledgeTimeStatus,
    Occurrence,
    VendorExtractorPin,
)
from equity_os.contracts.measurement.evidence_tier import EvidenceTier
from equity_os.contracts.sourcing.source_catalog import SCREENER_PAGE, TIJORI_PAGE
from equity_os.contracts.verification.comparison import ExtractionStatus, SourceRole, SourceState
from equity_os.contracts.verification.vendor_first import FilingFailure, FilingState, VendorOutcome
from equity_os.normalisation.mapping.mapping import MappingSet
from equity_os.verification.comparison.run_models import ResultRow, SourceValue

_Interval = tuple[Decimal, Decimal]
_Interpretations = Mapping[int | None, Interpretation]
_Occurrences = Mapping[int | None, Occurrence]
NON_FINANCIAL = "NON_FINANCIAL"
# Reading 1: an onboarded (or partially onboarded) entity whose Ind AS framework setting cites
# onboarding's DISCOVERY input, both recorded by the cutoff. Nothing else implies a class.
_ISSUER_CLASS: LiteralString = """
SELECT EXISTS (SELECT 1 FROM eqos.onboarding_records
        WHERE entity_id = %(entity)s AND outcome IN ('ONBOARDED', 'PARTIAL')
            AND recorded_at <= %(cutoff)s)
    AND EXISTS (SELECT 1 FROM eqos.settings_records s
        JOIN eqos.evidence_inputs e ON e.id = s.evidence_input_id
        WHERE s.entity_id = %(entity)s AND s.setting_key = 'REPORTING_FRAMEWORK'
            AND s.value_text = 'IND_AS' AND e.kind = 'DISCOVERY' AND s.recorded_at <= %(cutoff)s)
"""


class VendorFirstPolicy(BaseModel):
    """The policy file, pinned by the SHA-256 of its bytes."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    version: str
    content_sha256: str
    precision_limit: Decimal
    min_clean_key_periods: int


def load_vendor_first_policy(path: Path) -> VendorFirstPolicy:
    """Load a vendor-first policy file and pin it by content."""
    content = path.read_bytes()
    return VendorFirstPolicy.model_validate(
        {**yaml.safe_load(content), "content_sha256": hashlib.sha256(content).hexdigest()}
    )


def vendor_outcome(
    row: ResultRow,
    interpretations: _Interpretations,
    mapping: MappingSet,
    policy: VendorFirstPolicy,
) -> tuple[VendorOutcome, SourceValue | None]:
    """T1, first match wins; on agreement, also the narrower side (Screener on a tie).

    A ``VALUE`` side is already a ``MAPPED`` interpretation (selection); a child trace or a
    constructed interpretation is not DIRECT, so constructed values are unmapped here.
    """
    screener, tijori = (_vendor(row, page) for page in (SCREENER_PAGE, TIJORI_PAGE))
    if screener is None or tijori is None:
        return VendorOutcome.VENDOR_UNMAPPED, None
    if any(_unmapped(side, interpretations, mapping) for side in (screener, tijori)):
        return VendorOutcome.VENDOR_UNMAPPED, None
    s, t = _interval(screener), _interval(tijori)
    if _disjoint(s, t):
        return VendorOutcome.VENDORS_DISAGREE, None
    s_width, t_width = s[1] - s[0], t[1] - t[0]
    largest = max(abs(_value(screener)), abs(_value(tijori)))
    if largest == 0:
        imprecise = s_width > 0 or t_width > 0
    else:
        imprecise = max(s_width, t_width) / 2 > policy.precision_limit * largest
    if imprecise:
        return VendorOutcome.VENDORS_IMPRECISE, None
    return VendorOutcome.VENDORS_AGREE, tijori if t_width < s_width else screener


def filing_admissible(
    row: ResultRow, interpretations: _Interpretations, occurrences: _Occurrences
) -> FilingFailure | tuple[Interpretation, Occurrence]:
    """Today's first-party rule for one cell: its filed interpretation and occurrence (XBRL
    preferred), or why the filing fails. Open review items are row 0a's, not this test's."""
    values = _first_party(row)
    if row.extraction_status is ExtractionStatus.NOT_APPLICABLE:
        if len(values) != 1:
            return FilingFailure.NOT_SINGLE_REPRESENTATION
    elif row.extraction_status is not ExtractionStatus.AGREE:
        return FilingFailure.EXTRACTION_NOT_AGREE
    direct = {
        value.representation: interpretations[value.interpretation_id]
        for value in values
        if interpretations[value.interpretation_id].origin is InterpretationOrigin.DIRECT
    }
    chosen = direct.get(Representation.XBRL) or direct.get(Representation.PDF)
    if chosen is None:
        return FilingFailure.NO_DIRECT_OCCURRENCE
    occurrence = occurrences[chosen.occurrence_id]
    if occurrence.knowledge_time_status is not KnowledgeTimeStatus.KNOWN:
        return FilingFailure.KNOWLEDGE_TIME_UNKNOWN
    return chosen, occurrence


def filing_state(row: ResultRow, admissible: bool) -> FilingState:
    """The first-party side of a cell against both vendor intervals; ``admissible`` is today's
    first-party admission rule. F is the XBRL value, else the PDF one, as admission chooses."""
    first_party = [
        value for value in row.source_values if value.source_role is SourceRole.FIRST_PARTY
    ]
    if all(value.state is SourceState.NO_VALUE for value in first_party):
        return FilingState.FILING_ABSENT
    if not admissible or any(
        value.state in (SourceState.UNAVAILABLE, SourceState.INVALID) for value in first_party
    ):
        return FilingState.FILING_FAILED
    filed = {
        value.representation: value for value in first_party if value.state is SourceState.VALUE
    }
    f = _interval(filed.get(Representation.XBRL) or filed[Representation.PDF])
    vendors = (_vendor(row, page) for page in (SCREENER_PAGE, TIJORI_PAGE))
    if any(_disjoint(f, _interval(side)) for side in vendors if side is not None):
        return FilingState.FILING_DIFFERS
    return FilingState.FILING_AGREES


def check_class(
    row: ResultRow,
    interpretations: _Interpretations,
    *,
    mapping: MappingSet,
    extractor_pins: Sequence[VendorExtractorPin],
    dictionary_version: str,
    policy_version: str,
    issuer_class: str,
    period_kind: PeriodKind,
) -> str:
    """The check class of a cell both vendors map: a digest of every §6.6 component, so any
    version change makes a new class with no evidence."""
    extractors = {(pin.source_id, pin.surface): pin.version for pin in extractor_pins}
    payload = {
        "canonical_id": row.key.canonical_id,
        "period_kind": period_kind.value,
        "basis": row.key.basis.value,
        "framework": row.key.framework.value,
        "issuer_class": issuer_class,
        "mapping_set": mapping.version,
        "dictionary": dictionary_version,
        "policy": policy_version,
    }
    for name, page in (("screener", SCREENER_PAGE), ("tijori", TIJORI_PAGE)):
        side = _vendor(row, page)
        assert side is not None
        payload[f"{name}_entry"] = str(interpretations[side.interpretation_id].mapping_entry_id)
        payload[f"{name}_extractor"] = extractors[page]
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def issuer_class(conn: Connection[Any], entity_id: int, cutoff: datetime) -> str | None:
    """``NON_FINANCIAL`` on positive onboarding provenance known at the cutoff, else ``None``."""
    found = conn.execute(_ISSUER_CLASS, {"entity": entity_id, "cutoff": cutoff}).fetchone()
    return NON_FINANCIAL if found is not None and found[0] else None


def _first_party(row: ResultRow) -> list[SourceValue]:
    """A row's first-party source values that carry a value and its interpretation."""
    return [
        value
        for value in row.source_values
        if value.source_role is SourceRole.FIRST_PARTY
        and value.state is SourceState.VALUE
        and value.interpretation_id is not None
    ]


def _unmapped(side: SourceValue, interpretations: _Interpretations, mapping: MappingSet) -> bool:
    """T1 rule 1 for one ``VALUE`` side: not a DIRECT interpretation, or a related entry."""
    if side.interpretation_id is None:
        return True
    chosen = interpretations[side.interpretation_id]
    if chosen.origin is not InterpretationOrigin.DIRECT or chosen.mapping_entry_id is None:
        return True
    return mapping.entry(chosen.mapping_entry_id).tier is EvidenceTier.RELATED_NOT_EQUIVALENT


def _vendor(row: ResultRow, page: tuple[str, str]) -> SourceValue | None:
    """The row's ``VALUE`` side from one vendor page, if any."""
    for value in row.source_values:
        if (value.source_id, value.surface) == page and value.state is SourceState.VALUE:
            return value
    return None


def _value(side: SourceValue) -> Decimal:
    """A ``VALUE`` side's value."""
    assert side.value is not None
    return side.value


def _interval(side: SourceValue) -> _Interval:
    """A side's stored interval; an exact value is its own zero-width interval."""
    value = _value(side)
    lower = value if side.lower is None else side.lower
    return lower, value if side.upper is None else side.upper


def _disjoint(first: _Interval, other: _Interval) -> bool:
    """Whether two closed intervals share no point."""
    return first[1] < other[0] or other[1] < first[0]
