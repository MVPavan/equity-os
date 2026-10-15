"""The claim check: one claim against what its citation resolved to (ledger spec §1).

Deterministic and pure: the first matching row of the spec table wins. Resolution, authority
and times are :mod:`fundamentals.ledger.citations`' job; this module only compares.
"""

from __future__ import annotations

import re
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from fundamentals.contracts.evidence import RunMode
from fundamentals.contracts.ledger import (
    CitationKind,
    ClaimState,
    GuidanceContract,
    InputTime,
    NumericClaim,
    ResolvedCitation,
)
from fundamentals.ledger.display import rounded
from fundamentals.verify.quote_anchor import guidance_quote_holds

IST_OFFSET = timedelta(hours=5, minutes=30)
AS_KNOWN_ONLY = frozenset({InputTime.RECORDED, InputTime.SELECTED, InputTime.POLICY})
VALUED = frozenset(
    {CitationKind.FIGURE, CitationKind.CALCULATION, CitationKind.POLICY, CitationKind.COMPARISON}
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

    A self-cited ``POLICY`` claim resolves only on an import, from its own version's record.
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
    if _differs(
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
        if not _quote_means_claim(claim, resolved.quote_text, resolved.guidance):
            return ClaimState.QUOTE_MEANING_MISMATCH
    if resolved.trusted is False:
        return ClaimState.MATCH_UNTRUSTED
    return ClaimState.MATCH


def _differs(claimed: tuple[object, ...], cited: tuple[object, ...]) -> bool:
    """Whether any field the cited record carries (non-``None``) differs from the claim's."""
    return any(
        other is not None and mine != other for mine, other in zip(claimed, cited, strict=True)
    )


def _quote_means_claim(claim: NumericClaim, quote: str, contract: GuidanceContract | None) -> bool:
    """Row 7: the guidance gate holds for the bounds, the quote states exactly the claim's
    qualifiers, and the guidance contract agrees field by field."""
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
    return contract is None or asserted == contract
