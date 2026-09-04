"""Lane B: compare Upstox statement values against Screener's, and claim only what is shown.

**This module never adjudicates truth and nothing it produces is a fact.** The
independence probe found these Upstox endpoints share upstream lineage with
Screener — ``operating_profit`` reproduces Screener's profit before tax 12/12
across three companies and both bases, and Upstox reproduces Screener's
divergence from the BSE filing on TITAN Jun-2026 net profit. Shared lineage
disqualifies them from corroborating Screener and is precisely what makes them
useful for detecting *extraction drift*.

A disagreement means only that two representations differ. It could be refresh
or restatement timing, a different aggregation or formula, precision, an
Upstox-side defect, misalignment in this comparator, or Screener faithfully
rendering a vendor error that our parser read correctly. Lane B gives a triage
**direction**, never a diagnosis.

**The name map is the whole point.** Upstox's ``operating_profit`` is not
operating profit; it is *profit before tax*. A comparator built on matching
names would report a false mismatch on every company and every quarter, and it
would read as a catastrophic parser defect that does not exist. The map is a
frozen declaration and every entry states what the vendor's label actually
means.

**Tiers constrain the claim, not the arithmetic.** All three tiers derive their
tolerance the same way — the sum of each participating value's half-ULP, which
is how rounding error propagates through addition. What differs is what a
breach is allowed to be *called*:

* tier 1, equivalence demonstrated — a breach is a ``MISMATCH``;
* tier 2, related but not equivalent — a breach is an ``ANOMALY``, because the
  mapping is a reconstruction rather than a shown identity;
* tier 3, equivalence unproven — ``NOT_COMPARABLE`` whatever the numbers say.

No threshold is guessed anywhere. The tolerance comes from
:func:`fundamentals.verify.crossfoot.half_ulp`, the same derivation the
cross-footing checks use.

**Deviation from decision C, recorded.** C names
``verify.crossfoot.observation_half_ulp`` and ``verify.comparison_key``. Both
take an :class:`~fundamentals.contracts.observation.Observation`, and Lane B is
barred from constructing one — a leaked Upstox value classified ``first_party``
is the exact hazard the bar exists for. So the *arithmetic* was extracted into
``half_ulp`` and is shared, while alignment uses this module's own small key.
C's intent, no invented tolerance, is preserved; its literal wording is not.
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from fundamentals.verify.crossfoot import half_ulp

# Values on both sides are already stated in crore, so no rescaling is needed
# and ``decimals`` alone carries the precision.
CRORE_SCALE = 1


class EvidenceTier(StrEnum):
    """How much a comparison on this line is entitled to conclude.

    **A tier is not self-sufficient — read the mapping's ``means`` with it.**
    ``EQUIVALENCE_DEMONSTRATED`` may carry a stated exclusion there, because an
    identity can hold across most of a population and fail on a named part of
    it. Both tier-1 lines currently do: the 2026-09-04 sweep held on 73 of 80
    live lines and failed on companies with material exceptional items or
    associates. Grading those lines down would have emptied tier 1 and made
    ``MISMATCH`` unreachable, hiding a real Upstox-side defect among 62 tier-2
    anomalies, so the owner kept the tier and required the exclusion to travel
    in ``means`` — which reaches every report row, as the enum member does not.
    """

    EQUIVALENCE_DEMONSTRATED = "EQUIVALENCE_DEMONSTRATED"
    RELATED_NOT_EQUIVALENT = "RELATED_NOT_EQUIVALENT"
    EQUIVALENCE_UNPROVEN = "EQUIVALENCE_UNPROVEN"


class CrosscheckOutcome(StrEnum):
    """What one compared line established. None of these blocks anything."""

    AGREE = "AGREE"
    MISMATCH = "MISMATCH"
    ANOMALY = "ANOMALY"
    NOT_COMPARABLE = "NOT_COMPARABLE"
    MISSING_UPSTOX = "MISSING_UPSTOX"
    MISSING_SCREENER = "MISSING_SCREENER"


class TriageClass(StrEnum):
    """Why one compared line is, or is not, worth a reviewer's attention.

    Declared beside :class:`CrosscheckOutcome` rather than in the triage module
    that assigns it, because :class:`CrosscheckRow` carries the value and the
    comparison must not depend on the verification package that reads it. The
    member order is the reporting order: the classes are listed strongest first,
    and ``warnings.tsv`` sorts on that order.
    """

    # The sensitivity harness caught a dropped or stale Screener row on every
    # seeded cell, and the live sweep produced none, so it is the one class that
    # never consults a threshold.
    STRUCTURAL = "STRUCTURAL"
    MAGNITUDE = "MAGNITUDE"
    WHOLE_TABLE = "WHOLE_TABLE"
    # The two classes that place the fault somewhere other than this repo's
    # Screener parse: listed for the review queue, never counted as a warning.
    UPSTOX_SIDE = "UPSTOX_SIDE"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    NOISE = "NOISE"
    NONE = "NONE"


# What a run warns on, and what it merely lists. Separate sets because an
# acknowledged or Upstox-side line belongs in the reviewer's queue but must
# never inflate the warn figure a future block decision would be argued from.
WARN_CLASSES: frozenset[TriageClass] = frozenset(
    {TriageClass.STRUCTURAL, TriageClass.MAGNITUDE, TriageClass.WHOLE_TABLE}
)
LISTED_CLASSES: frozenset[TriageClass] = WARN_CLASSES | {
    TriageClass.UPSTOX_SIDE,
    TriageClass.ACKNOWLEDGED,
}


class UnmappedCategoryError(LookupError):
    """Raised for a vendor category with no declared meaning.

    Refused rather than guessed: a category nobody has mapped has no comparison
    anyone could defend, and inventing one is how a false mismatch is born.
    """


class StatedValue(BaseModel):
    """One number as a source stated it, with the precision it stated it to.

    ``raw_label`` is the vendor's own label and travels all the way into the
    report, so mapping drift stays visible instead of being absorbed by the
    mapped name.
    """

    model_config = ConfigDict(frozen=True)

    amount: Decimal
    # Digits of accuracy in the value as stated: 0 for Screener's integer crore,
    # 2 for the two decimal places Upstox returns.
    decimals: int
    raw_label: str = Field(min_length=1)

    @property
    def half_ulp(self) -> Decimal:
        """Half a unit in this value's last reported place."""
        return half_ulp(self.decimals, CRORE_SCALE)


class LineMapping(BaseModel):
    """One Upstox category, what it actually means, and the Screener rows for it.

    ``screener_rows`` holds more than one row only where the Upstox value is a
    reconstruction — which is exactly the case that cannot be tier 1.
    """

    model_config = ConfigDict(frozen=True)

    upstox_category: str = Field(min_length=1)
    means: str = Field(min_length=1)
    screener_rows: tuple[str, ...] = Field(min_length=1)
    tier: EvidenceTier


# The three quarterly summary lines Upstox publishes, plus the tier-3 surfaces
# fetched under decision B. Every ``means`` below is what the probe observed,
# not what the vendor's label says.
#
# Corrected 2026-09-04 against the live Lane B contract. The five balance-sheet
# and cash-flow keys were written from the vendor's documentation and none of
# them existed: the balance-sheet summary carries ``total_asset`` and
# ``total_liability``, singular and as fields of a flat history row rather than
# as categories, and the cash-flow categories are the bare words ``operating``,
# ``investing`` and ``financing``. Every one of those five lookups would have
# raised :class:`UnmappedCategoryError` on the first real payload.
INCOME_STATEMENT_MAP: tuple[LineMapping, ...] = (
    LineMapping(
        upstox_category="revenue",
        means="Total Revenue — sales plus other income, not revenue from operations",
        screener_rows=("Sales", "Other Income"),
        # A reconstruction: the probe recorded gaps of 152 and 51 crore against
        # this sum, far outside any rounding interval. Related, not equivalent.
        tier=EvidenceTier.RELATED_NOT_EQUIVALENT,
    ),
    LineMapping(
        upstox_category="operating_profit",
        means=(
            "Profit Before Tax — despite the label, this is NOT operating profit. "
            "EXCLUSION: the identity failed on CGPOWER, 3 of 4 periods, by up to "
            "556.62 crore, where exceptional items are material and each vendor's "
            "own pre-tax-to-post-tax chain is internally consistent at a different "
            "figure. Held on 73 of 80 lines in the 2026-09-04 sweep."
        ),
        screener_rows=("Profit before tax",),
        tier=EvidenceTier.EQUIVALENCE_DEMONSTRATED,
    ),
    LineMapping(
        upstox_category="net_profit",
        means=(
            "Profit After Tax. EXCLUSION: the identity failed on LAURUSLABS in 3 of "
            "4 periods while profit before tax agreed to the crore in all four, and "
            "the differences ran in both directions across years — the signature of "
            "associates or minority interest placed differently, not of a parse "
            "error. Held on 73 of 80 lines in the 2026-09-04 sweep."
        ),
        screener_rows=("Net Profit",),
        tier=EvidenceTier.EQUIVALENCE_DEMONSTRATED,
    ),
    LineMapping(
        upstox_category="total_asset",
        means="Balance-sheet total assets, stated as total_asset; totals only",
        screener_rows=("Total Assets",),
        # Balance-sheet evidence is weak: the independence probe covered the
        # income statement, not this.
        tier=EvidenceTier.RELATED_NOT_EQUIVALENT,
    ),
    LineMapping(
        upstox_category="total_liability",
        means="Liabilities excluding equity — NOT Screener's 'Total Liabilities' row",
        # Screener's ``Total Liabilities`` is the balancing total and equals its
        # ``Total Assets`` on every period of every company checked. Mapping to
        # it produced a five-figure false ANOMALY on all four TITAN periods.
        # Upstox's ``total_liability`` is borrowings plus other liabilities:
        # exact on Mar-2026, and off by the same 2-3 crore as ``total_asset`` on
        # Mar-2025 and Mar-2024, which is a shared restatement offset rather
        # than a mapping error. Verified on TITAN consolidated and NETWEB
        # standalone, 2026-09-04.
        screener_rows=("Borrowings", "Other Liabilities"),
        tier=EvidenceTier.RELATED_NOT_EQUIVALENT,
    ),
    LineMapping(
        upstox_category="operating",
        means="Net cash from operating activities",
        screener_rows=("Cash from Operating Activity",),
        # Cash-flow lineage was never tested at all.
        tier=EvidenceTier.EQUIVALENCE_UNPROVEN,
    ),
    LineMapping(
        upstox_category="investing",
        means="Net cash from investing activities",
        screener_rows=("Cash from Investing Activity",),
        tier=EvidenceTier.EQUIVALENCE_UNPROVEN,
    ),
    LineMapping(
        upstox_category="financing",
        means="Net cash from financing activities",
        screener_rows=("Cash from Financing Activity",),
        tier=EvidenceTier.EQUIVALENCE_UNPROVEN,
    ),
)

_MAP_INDEX: dict[str, LineMapping] = {
    entry.upstox_category: entry for entry in INCOME_STATEMENT_MAP
}


def mapping_for(upstox_category: str) -> LineMapping:
    """Resolve one declared mapping, refusing a category nobody has mapped."""
    mapping = _MAP_INDEX.get(upstox_category)
    if mapping is None:
        raise UnmappedCategoryError(
            f"upstox category {upstox_category!r} has no declared Screener mapping; "
            f"refusing to guess one"
        )
    return mapping


class CrosscheckRow(BaseModel):
    """One compared line: both sides as stated, the derived tolerance, the claim.

    Carries no fact, observation or provenance type. It is a report row, and a
    report row is all it may ever become.
    """

    model_config = ConfigDict(frozen=True)

    upstox_category: str
    means: str
    tier: EvidenceTier
    outcome: CrosscheckOutcome
    upstox_raw_label: str | None = None
    screener_raw_labels: tuple[str, ...] = ()
    upstox_amount: Decimal | None = None
    screener_amount: Decimal | None = None
    difference: Decimal | None = None
    tolerance: Decimal | None = None
    values_equal: bool | None = None
    # Set by the triage pass, never by the comparison: the scale-free measure
    # both Lane B thresholds were derived in, and the class it decided. Defaults
    # keep an untriaged report readable and make the pass an annotation.
    relative_difference: Decimal | None = None
    triage: TriageClass = TriageClass.NONE


class CrosscheckReport(BaseModel):
    """Every compared line for one issuer, basis and period. Always log-only."""

    model_config = ConfigDict(frozen=True)

    isin: str = Field(min_length=1)
    basis: str = Field(min_length=1)
    period: str = Field(min_length=1)
    rows: tuple[CrosscheckRow, ...] = ()

    @property
    def mismatch_count(self) -> int:
        """How many tier-1 lines breached their derived tolerance."""
        return sum(1 for row in self.rows if row.outcome is CrosscheckOutcome.MISMATCH)

    @property
    def anomaly_count(self) -> int:
        """How many tier-2 lines breached their derived interval."""
        return sum(1 for row in self.rows if row.outcome is CrosscheckOutcome.ANOMALY)

    @property
    def exit_code(self) -> int:
        """Always zero. Decision A is log-only, and this is where that is enforced.

        The base disagreement rate is unmeasured. A check that blocks on an
        unknown rate either halts the pipeline or is switched off within a day;
        promote to warn or block once the first report supplies the number.
        """
        return 0


def compare_line(
    mapping: LineMapping,
    *,
    upstox: StatedValue | None,
    screener: Sequence[StatedValue],
) -> CrosscheckRow:
    """Compare one mapped line and return what the evidence entitles us to say.

    A missing side is recorded as missing rather than scored. Summing a partial
    set of addends would manufacture a total mismatch out of a coverage gap,
    which is why an incomplete Screener side is ``MISSING_SCREENER`` and not a
    difference.
    """
    if upstox is None:
        return _incomplete(mapping, CrosscheckOutcome.MISSING_UPSTOX, screener=screener)
    if len(screener) != len(mapping.screener_rows):
        return _incomplete(
            mapping, CrosscheckOutcome.MISSING_SCREENER, upstox=upstox, screener=screener
        )

    screener_total = sum((value.amount for value in screener), Decimal(0))
    difference = abs(upstox.amount - screener_total)
    # Each rounded value contributes its own half-ULP, on both sides. That is
    # how rounding error propagates through addition, and it is why two integer
    # addends widen the interval rather than leaving it at a single half-ULP.
    tolerance = upstox.half_ulp + sum((value.half_ulp for value in screener), Decimal(0))
    within = difference <= tolerance

    return CrosscheckRow(
        upstox_category=mapping.upstox_category,
        means=mapping.means,
        tier=mapping.tier,
        outcome=_outcome(mapping.tier, within=within),
        upstox_raw_label=upstox.raw_label,
        screener_raw_labels=tuple(value.raw_label for value in screener),
        upstox_amount=upstox.amount,
        screener_amount=screener_total,
        difference=difference,
        tolerance=tolerance,
        values_equal=upstox.amount == screener_total,
    )


def _outcome(tier: EvidenceTier, *, within: bool) -> CrosscheckOutcome:
    """Name the result at the strength this line's evidence actually supports.

    Tier 3 returns ``NOT_COMPARABLE`` even when the values match. Equivalence is
    unproven there, so counting an agreement as evidence of correctness is the
    same error as counting a difference as evidence of a defect — and a reader
    tallying tier-3 agreements would be doing exactly that.
    """
    if tier is EvidenceTier.EQUIVALENCE_UNPROVEN:
        return CrosscheckOutcome.NOT_COMPARABLE
    if within:
        return CrosscheckOutcome.AGREE
    if tier is EvidenceTier.EQUIVALENCE_DEMONSTRATED:
        return CrosscheckOutcome.MISMATCH
    return CrosscheckOutcome.ANOMALY


def _incomplete(
    mapping: LineMapping,
    outcome: CrosscheckOutcome,
    *,
    upstox: StatedValue | None = None,
    screener: Sequence[StatedValue] = (),
) -> CrosscheckRow:
    """Record a line one side did not cover, keeping whatever the other side said."""
    return CrosscheckRow(
        upstox_category=mapping.upstox_category,
        means=mapping.means,
        tier=mapping.tier,
        outcome=outcome,
        upstox_raw_label=None if upstox is None else upstox.raw_label,
        screener_raw_labels=tuple(value.raw_label for value in screener),
        upstox_amount=None if upstox is None else upstox.amount,
    )
