"""Deterministic display of claims and the narrative they fill (ledger spec §1 Display; P2).

A placeholder ``{{c:<claim key>|<style>}}`` renders from the claim's typed value alone, shaped
by a closed-enum style (plan D5). Location and class markers are not placeholders and stay as
written. The narrative is the sections in ordinal order, placeholders filled, joined with no
separator, so an imported earnings update's narrative is its source bytes (D7).
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable
from decimal import Decimal

from fundamentals.contracts.ledger import (
    CitationKind,
    DisplayStyle,
    Grouping,
    NumericClaim,
    RangeForm,
    ReportSection,
)

PLACEHOLDER = re.compile(r"\{\{c:([^|}]+)\|([^}]*)\}\}")
PERCENT = "%"
DASH = "–"
COMMA = ", "
_FLAGS = {"plus": "plus", "unit": "unit", "qual": "qualifier", "trim": "trim", "quote": "quote"}
_PREFIX_QUALIFIERS = {"about": "about "}
_SUFFIX_QUALIFIERS = {"plus": "-plus"}
# A comparator figure or filed tax cited to its filed interpretation, not an admitted fact
# (invariant 7): always shown with its label, whatever the slot's style.
FILED = "filed"
FILED_SUFFIX = " (filed value, single source, not cross-checked)"
_BAD_TOKEN = "style token {token!r} is unknown, repeated or conflicting in {style!r}"
_NO_QUOTE = "claim {key!r} is not a SOURCE_QUOTE, so it has no quote to show"
_NO_CLAIM = "placeholder names no claim of this version: {key!r}"
_NO_VALUE = "claim {key!r} has neither a value nor bounds"


class DisplayError(ValueError):
    """A placeholder cannot render: unknown claim, or an invalid style for it."""


def parse_style(text: str) -> DisplayStyle:
    """The style named by comma-separated tokens; empty text is the default style."""
    fields: dict[str, object] = {}
    for token in filter(None, text.split(",")):
        field, value = _field(token)
        if field is None or field in fields:
            raise DisplayError(_BAD_TOKEN.format(token=token, style=text))
        fields[field] = value
    return DisplayStyle.model_validate(fields)


def rounded(value: Decimal, claim: NumericClaim) -> Decimal:
    """``value`` at the claim's display precision and rounding mode."""
    return value.quantize(Decimal(1).scaleb(-claim.precision), rounding=claim.rounding.value)


def render_claim(claim: NumericClaim, style: DisplayStyle) -> str:
    """The claim's display text under ``style``."""
    if style.quote:
        if claim.citation.kind is not CitationKind.SOURCE_QUOTE or claim.citation.quote is None:
            raise DisplayError(_NO_QUOTE.format(key=claim.claim_key))
        return claim.citation.quote
    unit = claim.unit if style.unit and claim.unit else None
    if claim.value is not None:
        text = _with_unit(_number(claim.value, claim, style), unit)
    elif claim.lower_bound is not None and claim.upper_bound is not None:
        text = _range(claim.lower_bound, claim.upper_bound, claim, style, unit)
    else:
        raise DisplayError(_NO_VALUE.format(key=claim.claim_key))
    if style.qualifier:
        for qualifier in claim.qualifiers:
            prefix, suffix = (
                _PREFIX_QUALIFIERS.get(qualifier, ""),
                _SUFFIX_QUALIFIERS.get(qualifier, ""),
            )
            text = f"{prefix}{text}{suffix}"
    return text + FILED_SUFFIX if FILED in claim.qualifiers else text


def render_section(text: str, claims: Iterable[NumericClaim]) -> str:
    """The section text with every claim placeholder filled."""
    by_key = {claim.claim_key: claim for claim in claims}

    def fill(match: re.Match[str]) -> str:
        claim = by_key.get(match.group(1))
        if claim is None:
            raise DisplayError(_NO_CLAIM.format(key=match.group(1)))
        return render_claim(claim, parse_style(match.group(2)))

    return PLACEHOLDER.sub(fill, text)


def narrative(sections: Iterable[ReportSection], claims: Iterable[NumericClaim]) -> bytes:
    """The deterministic narrative: rendered sections in ordinal order, UTF-8 (P2)."""
    stored = tuple(claims)
    ordered = sorted(sections, key=lambda section: section.ordinal)
    return "".join(render_section(section.body, stored) for section in ordered).encode()


def content_hash(sections: Iterable[ReportSection], claims: Iterable[NumericClaim]) -> str:
    """SHA-256 of the narrative: the version's content hash (P2)."""
    return hashlib.sha256(narrative(sections, claims)).hexdigest()


def _field(token: str) -> tuple[str | None, object]:
    """The style field one token sets, and its value."""
    if token in _FLAGS:
        return _FLAGS[token], True
    for enum, field in ((Grouping, "grouping"), (RangeForm, "range_form")):
        if token in enum._value2member_map_:
            return field, token
    return None, None


def _number(value: Decimal, claim: NumericClaim, style: DisplayStyle) -> str:
    """One rounded value: sign, grouping and trim per ``style``."""
    shown = rounded(value, claim)
    digits = f"{abs(shown):f}"
    if style.trim and "." in digits:
        digits = digits.rstrip("0").rstrip(".")
    whole, dot, fraction = digits.partition(".")
    text = _group(whole, style.grouping) + dot + fraction
    if shown < 0:
        return "-" + text
    return "+" + text if style.plus and shown > 0 else text


def _group(whole: str, grouping: Grouping) -> str:
    """Integer digits grouped 3-3-3 (international) or 2-2-3 (Indian)."""
    if grouping is Grouping.NONE or len(whole) <= 3:
        return whole
    if grouping is Grouping.INTERNATIONAL:
        return f"{int(whole):,}"
    head, tail = whole[:-3], whole[-3:]
    pairs = [head[max(0, end - 2) : end] for end in range(len(head), 0, -2)]
    return ",".join(reversed(pairs)) + "," + tail


def _with_unit(text: str, unit: str | None) -> str:
    """``%`` attaches without a space; any other unit takes one."""
    if unit is None:
        return text
    return text + unit if unit == PERCENT else f"{text} {unit}"


def _range(
    lower: Decimal, upper: Decimal, claim: NumericClaim, style: DisplayStyle, unit: str | None
) -> str:
    """Bounds as one value when equal, ``a–b<unit>`` or ``a<unit>, b<unit>``."""
    low, high = _number(lower, claim, style), _number(upper, claim, style)
    if lower == upper:
        return _with_unit(low, unit)
    if style.range_form is RangeForm.COMMA:
        return _with_unit(low, unit) + COMMA + _with_unit(high, unit)
    return _with_unit(low + DASH + high, unit)
