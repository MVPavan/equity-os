"""The vendor-first policy and §6.4's predicates: T1 (how the two vendors relate) and the filing
state of a cell (VENDOR-1 spec §6.4). Each side is its stored ``[lower, upper]`` interval."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from decimal import Decimal
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict

from equity_os.contracts.measurement.canonical import Representation
from equity_os.contracts.measurement.evidence import Interpretation, InterpretationOrigin
from equity_os.contracts.measurement.evidence_tier import EvidenceTier
from equity_os.contracts.sourcing.source_catalog import SCREENER_PAGE, TIJORI_PAGE
from equity_os.contracts.verification.comparison import SourceRole, SourceState
from equity_os.contracts.verification.vendor_first import FilingState, VendorOutcome
from equity_os.normalisation.mapping.mapping import MappingSet
from equity_os.verification.comparison.run_models import ResultRow, SourceValue

_Interval = tuple[Decimal, Decimal]


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
    interpretations: Mapping[int, Interpretation],
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


def _unmapped(
    side: SourceValue, interpretations: Mapping[int, Interpretation], mapping: MappingSet
) -> bool:
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
