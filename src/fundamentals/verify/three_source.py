"""Putting XBRL, Screener and Tijori on one row per concept, offline.

The comparator is pure: it takes the sides
:mod:`fundamentals.verify.three_source_inputs` read out of retained evidence and
returns a report. It reaches no store, no reconciler and no command layer, which
is what makes a report re-derivable from the same bytes months later.

Two rules carry the weight. Agreement is the sum of both sides' half-ULPs and
nothing else — a residual at that boundary is exactly what the two declared
precisions allow, and one unit beyond it is not. What a difference may be
*called* is the mapping's business, not the number's: only a demonstrated
equivalence may say ``MISMATCH``, because elsewhere the thing that differs may be
the mapping rather than either vendor's arithmetic.

The registry is read at call time from
:data:`fundamentals.verify.three_source_map.REGISTRY`, so each pair reports the
tier of the entry that produced its value — two candidate concepts carrying the
identical number still keep their own verdicts.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Final

import structlog
from pydantic import BaseModel, ConfigDict, Field

from fundamentals.ingest.screener_crosscheck import EvidenceTier
from fundamentals.verify import three_source_map
from fundamentals.verify.laneb_sensitivity_model import MutationClass
from fundamentals.verify.laneb_triage import relative_difference
from fundamentals.verify.three_source_inputs import GoldSpine, Side, SideValue
from fundamentals.verify.three_source_map import SourceLineMapping

_LOGGER = structlog.get_logger(__name__)

DEFAULT_MAGNITUDE_THRESHOLD: Final = Decimal("0.20")

_MISSING_SIDE = "no value on the {side} side"
_UNIT_MISMATCH = "unit {left!r} is not comparable with {right!r}"
_PERIOD_MISMATCH = "period end {left} is not comparable with {right}"
_TIER_THREE_REASON = (
    "tier 3 cannot claim a mismatch: the mapping is unproven, so the difference "
    "may be the mapping rather than either value"
)
_SIGN_REASON = "{name}: the two sides are exact negatives of each other"
_SCALE_REASON = "{name}: one side is exactly {ratio}x the other"

_UNMAPPED_SIDE = "three_source_side_unmapped"

# The exact ratios a decimal-place or thousands-separator defect produces. An
# exact power of ten between two figures is a unit fault, not a disagreement
# about the business, so it is reported by name instead of by magnitude.
_SCALE_RATIOS: Final[tuple[tuple[Decimal, MutationClass], ...]] = (
    (Decimal(10), MutationClass.SCALE_10),
    (Decimal(100), MutationClass.SCALE_100),
    (Decimal(1000), MutationClass.THOUSANDS_TRUNCATED),
)

# Weakest last: a pair between two vendors may conclude only what the weaker of
# the two mappings entitles it to.
_TIER_STRENGTH: Final[dict[EvidenceTier, int]] = {
    EvidenceTier.EQUIVALENCE_DEMONSTRATED: 0,
    EvidenceTier.RELATED_NOT_EQUIVALENT: 1,
    EvidenceTier.EQUIVALENCE_UNPROVEN: 2,
}


class PairOutcome(StrEnum):
    """What one comparison of two sides established."""

    AGREE = "AGREE"
    MISMATCH = "MISMATCH"
    ANOMALY = "ANOMALY"
    NOT_COMPARABLE = "NOT_COMPARABLE"
    MISSING_LEFT = "MISSING_LEFT"
    MISSING_RIGHT = "MISSING_RIGHT"
    MISSING_BOTH = "MISSING_BOTH"


class PairTriage(StrEnum):
    """Why one non-agreeing pair is, or is not, worth a reviewer's attention."""

    STRUCTURAL = "STRUCTURAL"
    MAGNITUDE = "MAGNITUDE"
    NOISE = "NOISE"
    NONE = "NONE"


class PairResult(BaseModel):
    """One comparison of two sides, with the evidence behind its verdict."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    left: SideValue | None
    right: SideValue | None
    left_side: Side
    right_side: Side
    mapping_id: str | None
    tier: EvidenceTier
    outcome: PairOutcome
    difference: Decimal | None
    tolerance: Decimal | None
    relative_difference: Decimal | None
    triage: PairTriage
    reasons: tuple[str, ...] = ()


class TripleRow(BaseModel):
    """One concept as all three sources state it, and the three comparisons of it."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    concept_qname: str = Field(min_length=1)
    period_end: date
    xbrl: SideValue | None
    screener: SideValue | None
    tijori: SideValue | None
    pairs: tuple[PairResult, ...]
    mapping_ids: tuple[str, ...] = ()


class TripleReport(BaseModel):
    """Every compared concept for one stock-quarter, with what the run should heed."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    symbol: str = Field(min_length=1)
    period_end: date
    map_version: str = Field(min_length=1)
    gold_sha256: str = Field(min_length=1)
    capture_ids: tuple[str, ...] = ()
    rows: tuple[TripleRow, ...] = ()
    counts: dict[PairOutcome, int] = Field(default_factory=dict)
    warn: bool = False


def _missing_outcome(left: SideValue | None, right: SideValue | None) -> PairOutcome:
    """Name which of the two sides failed to produce a value."""
    if left is None and right is None:
        return PairOutcome.MISSING_BOTH
    if left is None:
        return PairOutcome.MISSING_LEFT
    return PairOutcome.MISSING_RIGHT


def _structural_reason(left: Decimal, right: Decimal) -> str | None:
    """Name a sign flip or an exact power-of-ten ratio, if the two figures are one."""
    if left != 0 and left == -right:
        return _SIGN_REASON.format(name=MutationClass.SIGN_FLIP.value)
    if left == 0 or right == 0:
        return None
    larger, smaller = max(abs(left), abs(right)), min(abs(left), abs(right))
    ratio = larger / smaller
    for candidate, name in _SCALE_RATIOS:
        if ratio == candidate:
            return _SCALE_REASON.format(name=name.value, ratio=candidate)
    return None


def _pair(
    *,
    left: SideValue | None,
    right: SideValue | None,
    left_side: Side,
    right_side: Side,
    mapping_id: str | None,
    tier: EvidenceTier,
    outcome: PairOutcome,
    triage: PairTriage,
    reasons: tuple[str, ...],
    difference: Decimal | None = None,
    tolerance: Decimal | None = None,
    relative: Decimal | None = None,
) -> PairResult:
    """Assemble one pair result, so every branch of the comparison states all of it."""
    return PairResult(
        left=left,
        right=right,
        left_side=left_side,
        right_side=right_side,
        mapping_id=mapping_id,
        tier=tier,
        outcome=outcome,
        difference=difference,
        tolerance=tolerance,
        relative_difference=relative,
        triage=triage,
        reasons=reasons,
    )


def compare_pair(
    left: SideValue | None,
    right: SideValue | None,
    *,
    tier: EvidenceTier,
    mapping_id: str | None,
    left_side: Side,
    right_side: Side,
    magnitude_threshold: Decimal = DEFAULT_MAGNITUDE_THRESHOLD,
) -> PairResult:
    """Compare two sides under the tolerance both of them declared.

    A missing side is a hole in the evidence and is named as such; sides in
    different units or periods are not comparable at all; and past the summed
    half-ULP the verdict is whatever the tier entitles this line to conclude.
    """
    if left is None or right is None:
        reasons = tuple(
            _MISSING_SIDE.format(side=side.value)
            for side, value in ((left_side, left), (right_side, right))
            if value is None
        )
        return _pair(
            left=left,
            right=right,
            left_side=left_side,
            right_side=right_side,
            mapping_id=mapping_id,
            tier=tier,
            outcome=_missing_outcome(left, right),
            triage=PairTriage.STRUCTURAL,
            reasons=reasons,
        )

    if left.unit != right.unit or left.period_end != right.period_end:
        reasons = ()
        if left.unit != right.unit:
            reasons = (*reasons, _UNIT_MISMATCH.format(left=left.unit, right=right.unit))
        if left.period_end != right.period_end:
            reasons = (
                *reasons,
                _PERIOD_MISMATCH.format(left=left.period_end, right=right.period_end),
            )
        return _pair(
            left=left,
            right=right,
            left_side=left_side,
            right_side=right_side,
            mapping_id=mapping_id,
            tier=tier,
            outcome=PairOutcome.NOT_COMPARABLE,
            triage=PairTriage.STRUCTURAL,
            reasons=reasons,
        )

    difference = abs(left.amount - right.amount)
    tolerance = left.half_ulp + right.half_ulp
    relative = relative_difference(left.amount, right.amount)
    if difference <= tolerance:
        return _pair(
            left=left,
            right=right,
            left_side=left_side,
            right_side=right_side,
            mapping_id=mapping_id,
            tier=tier,
            outcome=PairOutcome.AGREE,
            triage=PairTriage.NONE,
            reasons=(),
            difference=difference,
            tolerance=tolerance,
            relative=relative,
        )

    reasons = ()
    outcome = PairOutcome.ANOMALY
    if tier is EvidenceTier.EQUIVALENCE_DEMONSTRATED:
        outcome = PairOutcome.MISMATCH
    elif tier is EvidenceTier.EQUIVALENCE_UNPROVEN:
        reasons = (*reasons, _TIER_THREE_REASON)

    structural = _structural_reason(left.amount, right.amount)
    if structural is not None:
        triage = PairTriage.STRUCTURAL
        reasons = (*reasons, structural)
    elif relative is not None and relative >= magnitude_threshold:
        triage = PairTriage.MAGNITUDE
    else:
        triage = PairTriage.NOISE

    return _pair(
        left=left,
        right=right,
        left_side=left_side,
        right_side=right_side,
        mapping_id=mapping_id,
        tier=tier,
        outcome=outcome,
        triage=triage,
        reasons=reasons,
        difference=difference,
        tolerance=tolerance,
        relative=relative,
    )


def _mapping_index() -> dict[str, SourceLineMapping]:
    """Index the live registry by mapping id, read at call time."""
    return {entry.mapping_id: entry for entry in three_source_map.REGISTRY}


def _by_concept(
    values: Sequence[SideValue], entries: dict[str, SourceLineMapping]
) -> dict[str, SideValue]:
    """Place each vendor value under every candidate concept its entry lists.

    Two candidates make two rows, never one merged row: which concept the vendor
    means is undecided, and collapsing them would decide it by arithmetic.
    """
    placed: dict[str, SideValue] = {}
    for value in values:
        entry = entries.get(value.mapping_id) if value.mapping_id is not None else None
        if entry is None:
            _LOGGER.debug(_UNMAPPED_SIDE, side=value.side.value, mapping_id=value.mapping_id)
            continue
        for concept in entry.concept_qnames:
            placed.setdefault(concept, value)
    return placed


def _tier_of(value: SideValue | None, entries: dict[str, SourceLineMapping]) -> EvidenceTier:
    """The tier the entry behind this value declares, defaulting to unproven."""
    if value is None or value.mapping_id is None:
        return EvidenceTier.EQUIVALENCE_UNPROVEN
    entry = entries.get(value.mapping_id)
    return entry.tier if entry is not None else EvidenceTier.EQUIVALENCE_UNPROVEN


def _weaker(left: EvidenceTier, right: EvidenceTier) -> EvidenceTier:
    """The weaker of two tiers: a vendor-to-vendor pair is bounded by both mappings."""
    return left if _TIER_STRENGTH[left] >= _TIER_STRENGTH[right] else right


def _vendor_mapping_id(screener: SideValue | None, tijori: SideValue | None) -> str | None:
    """The mapping a vendor-to-vendor pair is reported under: Screener's, else Tijori's."""
    for value in (screener, tijori):
        if value is not None and value.mapping_id is not None:
            return value.mapping_id
    return None


def _mapping_ids(*values: SideValue | None) -> tuple[str, ...]:
    """The distinct mapping ids behind one row, in side order."""
    ids = [value.mapping_id for value in values if value is not None and value.mapping_id]
    return tuple(dict.fromkeys(identifier for identifier in ids if identifier is not None))


def compare_triple(
    spine: GoldSpine,
    screener: Sequence[SideValue],
    tijori: Sequence[SideValue],
    *,
    symbol: str,
    period_end: date,
    capture_ids: Sequence[str] = (),
) -> TripleReport:
    """Compare all three sources for one stock-quarter, one row per concept."""
    entries = _mapping_index()
    screener_by_concept = _by_concept(screener, entries)
    tijori_by_concept = _by_concept(tijori, entries)
    concepts = sorted(set(spine.values) | set(screener_by_concept) | set(tijori_by_concept))

    counts: dict[PairOutcome, int] = {outcome: 0 for outcome in PairOutcome}
    rows: list[TripleRow] = []
    warn = False
    for concept in concepts:
        xbrl = spine.values.get(concept)
        screener_value = screener_by_concept.get(concept)
        tijori_value = tijori_by_concept.get(concept)
        screener_tier = _tier_of(screener_value, entries)
        tijori_tier = _tier_of(tijori_value, entries)
        pairs = (
            compare_pair(
                xbrl,
                screener_value,
                tier=screener_tier,
                mapping_id=screener_value.mapping_id if screener_value else None,
                left_side=Side.XBRL,
                right_side=Side.SCREENER,
            ),
            compare_pair(
                xbrl,
                tijori_value,
                tier=tijori_tier,
                mapping_id=tijori_value.mapping_id if tijori_value else None,
                left_side=Side.XBRL,
                right_side=Side.TIJORI,
            ),
            compare_pair(
                screener_value,
                tijori_value,
                tier=_weaker(screener_tier, tijori_tier),
                mapping_id=_vendor_mapping_id(screener_value, tijori_value),
                left_side=Side.SCREENER,
                right_side=Side.TIJORI,
            ),
        )
        for pair in pairs:
            counts[pair.outcome] += 1
            warn = warn or _warns(pair)
        rows.append(
            TripleRow(
                concept_qname=concept,
                period_end=period_end,
                xbrl=xbrl,
                screener=screener_value,
                tijori=tijori_value,
                pairs=pairs,
                mapping_ids=_mapping_ids(screener_value, tijori_value),
            )
        )

    return TripleReport(
        symbol=symbol,
        period_end=period_end,
        map_version=three_source_map.MAP_VERSION,
        gold_sha256=spine.gold_sha256,
        capture_ids=tuple(capture_ids),
        rows=tuple(rows),
        counts=counts,
        warn=warn,
    )


def _warns(pair: PairResult) -> bool:
    """Whether one pair earns the report's warn flag.

    A demonstrated mismatch always does. An anomaly does only when its triage
    says something structural or material: a warn flag raised by every unproven
    rounding difference is ignored within a week.
    """
    if pair.outcome is PairOutcome.MISMATCH:
        return True
    return pair.outcome is PairOutcome.ANOMALY and pair.triage in (
        PairTriage.MAGNITUDE,
        PairTriage.STRUCTURAL,
    )
