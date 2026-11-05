"""The claim check: one claim against what its citation resolved to (ledger spec §1).

Deterministic and pure: the first matching row of the spec table wins. Resolution, authority
and times are :mod:`equity_os.publication.checking.citations`' job; this module only compares.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from equity_os.contracts.measurement.canonical import ValueKind
from equity_os.contracts.measurement.evidence import RunMode
from equity_os.contracts.publication.ledger import (
    CitationKind,
    ClaimState,
    GuidanceContract,
    InputTime,
    NumericClaim,
    ResolvedCitation,
)
from equity_os.publication.checking.quote_anchor import guidance_quote_holds
from equity_os.publication.drafting.display import rounded

IST_OFFSET = timedelta(hours=5, minutes=30)
AS_KNOWN_ONLY = frozenset({InputTime.RECORDED, InputTime.SELECTED, InputTime.POLICY})
VALUED = frozenset(
    {
        CitationKind.FIGURE,
        CitationKind.CALCULATION,
        CitationKind.POLICY,
        CitationKind.COMPARISON,
        CitationKind.THESIS_CLAIM,
    }
)
CRORE, PER_SHARE, PERCENT = "INR crore", "INR per share", "%"
# The closed unit table of keyed claims: each unit's value kind, currency and scale. A run-store
# value is in base units and converts by the claim's scale, so row 3 holds all three to its key.
UNITS: Mapping[str, tuple[ValueKind, str | None, int | None]] = {
    CRORE: (ValueKind.CURRENCY_AMOUNT, "INR", 10_000_000),
    PER_SHARE: (ValueKind.PER_SHARE_AMOUNT, "INR", 1),
    PERCENT: (ValueKind.PERCENTAGE, None, None),
}
# The dictionary's other value kinds carry no unit: a keyed claim of one states none, nor a
# currency or scale.
UNITLESS = frozenset({ValueKind.COUNT, ValueKind.RATIO, ValueKind.DAYS})
NO_CONTRACT = GuidanceContract(
    metric=None, scope=None, horizon=None, unit=None, constant_currency=None
)
# The closed qualifier lexicon: each qualifier and the whole word that states it.
QUALIFIER_WORDS = {"plus": re.compile(r"\bplus\b"), "about": re.compile(r"\babout\b")}


class _QuotedBounds(BaseModel):
    """A quote claim in the shape the existing guidance gate reads."""

    model_config = ConfigDict(frozen=True)

    source_quote: str | None
    lower_bound: Decimal
    upper_bound: Decimal


def cutoff_instant(day: date) -> datetime:
    """A date-only cutoff's end: 24:00 IST that day."""
    return datetime.combine(day + timedelta(days=1), time(), tzinfo=UTC) - IST_OFFSET


def quote_qualifiers(quote: str) -> frozenset[str]:
    """The qualifiers a quote states, from the closed lexicon, as whole words."""
    return frozenset(name for name, word in QUALIFIER_WORDS.items() if word.search(quote))


def check_claim(
    claim: NumericClaim,
    resolved: ResolvedCitation | None,
    *,
    mode: RunMode,
    cutoff: datetime,
    imported: bool,
) -> ClaimState:
    """The claim's state: the first spec row (1-9) whose condition holds.

    A self-cited ``POLICY`` claim resolves only on an import, from its own version's record. A
    drafted quote claim no sealed import binds a unique contract to fails row 7 (plan D4, M9).
    """
    citation = claim.citation
    self_cited = citation.kind is CitationKind.POLICY and citation.policy_decision_id is None
    if resolved is None or (self_cited and not imported):
        return ClaimState.UNRESOLVED
    if any(
        at is None or at > cutoff
        for name, at in resolved.times
        if mode is RunMode.AS_KNOWN or name not in AS_KNOWN_ONLY
    ):
        return ClaimState.POST_CUTOFF
    if not _typed(claim) or _differs(
        (claim.value_kind, claim.unit, claim.currency, claim.scale),
        (resolved.value_kind, resolved.unit, resolved.currency, resolved.scale),
    ):
        return ClaimState.UNIT_MISMATCH
    if claim.measurement_key is not None and _differs(
        (claim.measurement_key.digest(),), (resolved.key_digest,)
    ):
        return ClaimState.KEY_MISMATCH
    if citation.kind in VALUED and (
        claim.value is None
        or resolved.value is None
        or rounded(claim.value, claim) != rounded(resolved.value, claim)
    ):
        return ClaimState.VALUE_MISMATCH
    if citation.kind is CitationKind.SOURCE_QUOTE:
        if resolved.quote_text is None or resolved.quote_text != citation.quote:
            return ClaimState.QUOTE_NOT_FOUND
        unbound = resolved.guidance is None and not imported
        if unbound or not _quote_means_claim(claim, resolved.quote_text, resolved.guidance):
            return ClaimState.QUOTE_MEANING_MISMATCH
    if resolved.trusted is False:
        return ClaimState.MATCH_UNTRUSTED
    return ClaimState.MATCH


def _differs(claimed: tuple[object, ...], cited: tuple[object, ...]) -> bool:
    """Whether any field the cited record carries (non-``None``) differs from the claim's."""
    return any(
        other is not None and mine != other for mine, other in zip(claimed, cited, strict=True)
    )


def _typed(claim: NumericClaim) -> bool:
    """Whether a keyed claim's unit, by the unit table (or none, for a unitless kind), is its
    value kind, currency and scale, and its value kind and currency are its measurement key's
    (row 3, before any comparison)."""
    key = claim.measurement_key
    typed = (claim.value_kind, claim.currency, claim.scale)
    unitless = claim.unit is None and claim.value_kind in UNITLESS
    expected = (claim.value_kind, None, None) if unitless else UNITS.get(claim.unit or "")
    return key is None or (expected == typed and typed[:2] == (key.value_kind, key.currency))


def _quote_means_claim(claim: NumericClaim, quote: str, contract: GuidanceContract | None) -> bool:
    """Row 7: the guidance gate holds for the bounds, the quote states exactly the claim's
    qualifiers, and the bound guidance contract agrees field by field. A claim asserting any
    contract field fails closed when no contract is bound."""
    lower = claim.lower_bound if claim.value is None else claim.value
    upper = claim.upper_bound if claim.value is None else claim.value
    if lower is None or upper is None:
        return False
    quoted = _QuotedBounds(source_quote=claim.citation.quote, lower_bound=lower, upper_bound=upper)
    if not guidance_quote_holds(quoted, quote):
        return False
    if frozenset(claim.qualifiers) != quote_qualifiers(quote):
        return False
    asserted = GuidanceContract(
        metric=claim.metric,
        scope=claim.scope,
        horizon=claim.horizon,
        unit=claim.unit,
        constant_currency=claim.constant_currency,
    )
    return asserted == (contract or NO_CONTRACT)
