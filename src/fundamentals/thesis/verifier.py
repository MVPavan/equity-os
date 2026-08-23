"""Deterministic cross-verification of two independent model drafts.

Two guarantees, both produced by *code* (a model is used only to draft, never to
police numbers — roadmap invariant 6):

* **Unsourced-number detection.** Every number a draft emits is parsed and checked
  against the validated fact set. Any number not backed by a validated fact — a
  rounded figure, a computed ratio, a peer or historical number, a price target —
  is surfaced as an :class:`UnsourcedClaim`. It is a red flag, never a value to
  trust.
* **Divergence detection.** The two drafts' judgment sections are compared
  point-by-point (token-overlap) and by stance; material divergences become the
  :class:`Discrepancy` adjudication queue the human reviews.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from decimal import Decimal, InvalidOperation

from pydantic import BaseModel, ConfigDict

from fundamentals.thesis.contracts import (
    CrossVerification,
    Discrepancy,
    DiscrepancyKind,
    JudgmentSection,
    ThesisDraft,
    UnsourcedClaim,
    ValidatedFactSet,
)

# A number token: optional currency prefix, digits with optional grouping/decimal,
# optional percent suffix. Grouping and currency are stripped before parsing.
_NUMBER_RE = re.compile(
    r"(?:₹|\$|rs\.?|inr|usd)?\s*(?P<num>\d[\d,]*(?:\.\d+)?)(?P<pct>\s*%)?",
    re.IGNORECASE,
)
_WORD_RE = re.compile(r"[a-z0-9]+")

# Points whose token-overlap (Jaccard) is below this are treated as materially
# different judgments; identical/near-identical points sit well above it.
_JACCARD_THRESHOLD = 0.18
_MIN_TOKEN_LEN = 3
_SNIPPET_MAX_CHARS = 220
_STANCE_LABEL = "stance"
_UNSTRUCTURED_LABEL = "unstructured"
_WHOLE_DRAFT_LABEL = "(whole draft)"

_STOPWORDS: frozenset[str] = frozenset(
    {
        "the",
        "and",
        "for",
        "with",
        "that",
        "this",
        "from",
        "into",
        "are",
        "was",
        "were",
        "will",
        "would",
        "could",
        "should",
        "have",
        "has",
        "had",
        "its",
        "their",
        "than",
        "then",
        "but",
        "not",
        "any",
        "all",
        "may",
        "can",
        "per",
        "over",
        "under",
        "more",
        "less",
    }
)


class NumberHit(BaseModel):
    """One numeric token found in free text, with its parsed value."""

    model_config = ConfigDict(frozen=True)

    raw: str
    value: Decimal
    is_percent: bool


def _to_decimal(raw: str) -> Decimal | None:
    """Parse a possibly grouped numeric string to a Decimal, or ``None``."""
    cleaned = raw.replace(",", "").strip()
    if not cleaned:
        return None
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None


def extract_numbers(text: str) -> list[NumberHit]:
    """Extract every numeric token from free text (currency/grouping tolerated)."""
    hits: list[NumberHit] = []
    for match in _NUMBER_RE.finditer(text):
        value = _to_decimal(match.group("num"))
        if value is None:
            continue
        hits.append(
            NumberHit(
                raw=match.group("num"),
                value=value,
                is_percent=match.group("pct") is not None,
            )
        )
    return hits


def _period_year(period: str | None) -> int | None:
    """Return the four-digit year prefix of an ISO date string, if present."""
    if period is None or len(period) < 4 or not period[:4].isdigit():
        return None
    return int(period[:4])


def known_numbers(fact_set: ValidatedFactSet) -> frozenset[Decimal]:
    """Every number a draft may legitimately echo, derived from the fact set.

    This is the validated fact values (retained and per-source), the reporting
    period's date components and nearby fiscal years, the quarter label's digits,
    and each fact's first-party source count. A draft number outside this set is
    an unsourced claim.
    """
    known: set[Decimal] = set()
    for fact in fact_set.facts:
        for candidate in (fact.value, *(anchor.value for anchor in fact.anchors)):
            parsed = _to_decimal(candidate)
            if parsed is not None:
                known.add(parsed)
        known.add(Decimal(fact.first_party_source_count))
    for period in (fact_set.period_start, fact_set.period_end):
        if period is None:
            continue
        for part in re.findall(r"\d+", period):
            known.add(Decimal(part))
        year = _period_year(period)
        if year is not None:
            known.update({Decimal(year - 1), Decimal(year), Decimal(year + 1)})
    for part in re.findall(r"\d+", fact_set.quarter):
        known.add(Decimal(part))
    return frozenset(known)


def _snippet(text: str) -> str:
    """Collapse whitespace and truncate text for a compact flag snippet."""
    collapsed = " ".join(text.split())
    if len(collapsed) <= _SNIPPET_MAX_CHARS:
        return collapsed
    return collapsed[:_SNIPPET_MAX_CHARS].rstrip() + "…"


def _scan_targets(draft: ThesisDraft) -> list[tuple[str, str]]:
    """List the (section-label, text) fragments of a draft to scan for numbers."""
    if not draft.parsed:
        return [(_UNSTRUCTURED_LABEL, draft.raw_text)]
    targets: list[tuple[str, str]] = []
    if draft.stance.strip():
        targets.append((_STANCE_LABEL, draft.stance))
    for section in draft.sections:
        targets.extend((section.section.value, point) for point in section.points)
    return targets


def _unsourced_claims(draft: ThesisDraft, known: frozenset[Decimal]) -> list[UnsourcedClaim]:
    """Flag every number in one draft that is not a validated fact."""
    claims: list[UnsourcedClaim] = []
    for section_label, text in _scan_targets(draft):
        for hit in extract_numbers(text):
            if hit.value in known:
                continue
            claims.append(
                UnsourcedClaim(
                    model_label=draft.model_label,
                    number=hit.raw + ("%" if hit.is_percent else ""),
                    section=section_label,
                    snippet=_snippet(text),
                )
            )
    return claims


def _tokenize(text: str) -> frozenset[str]:
    """Lowercase content-token set of a point (drops stopwords and short tokens)."""
    return frozenset(
        token
        for token in _WORD_RE.findall(text.lower())
        if len(token) >= _MIN_TOKEN_LEN and token not in _STOPWORDS
    )


def _jaccard(left: frozenset[str], right: frozenset[str]) -> float:
    """Token-set Jaccard similarity (empty vs empty is identical)."""
    if not left and not right:
        return 1.0
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def _unmatched(
    points_a: Sequence[str], points_b: Sequence[str]
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Return the points on each side with no similar counterpart on the other."""
    tokens_a = [_tokenize(point) for point in points_a]
    tokens_b = [_tokenize(point) for point in points_b]
    unmatched_a = tuple(
        point
        for point, token in zip(points_a, tokens_a, strict=True)
        if max((_jaccard(token, other) for other in tokens_b), default=0.0) < _JACCARD_THRESHOLD
    )
    unmatched_b = tuple(
        point
        for point, token in zip(points_b, tokens_b, strict=True)
        if max((_jaccard(token, other) for other in tokens_a), default=0.0) < _JACCARD_THRESHOLD
    )
    return unmatched_a, unmatched_b


def _discrepancy(
    section: str,
    kind: DiscrepancyKind,
    draft_a: ThesisDraft,
    draft_b: ThesisDraft,
    points_a: tuple[str, ...],
    points_b: tuple[str, ...],
    detail: str,
) -> Discrepancy:
    """Build a discrepancy record for the adjudication queue."""
    return Discrepancy(
        section=section,
        kind=kind,
        model_a_label=draft_a.model_label,
        model_b_label=draft_b.model_label,
        model_a_points=points_a,
        model_b_points=points_b,
        detail=detail,
    )


def _unstructured_discrepancies(draft_a: ThesisDraft, draft_b: ThesisDraft) -> list[Discrepancy]:
    """Flag each unparsed draft: its judgment cannot be auto-diffed."""
    discrepancies: list[Discrepancy] = []
    for draft in (draft_a, draft_b):
        if not draft.parsed:
            discrepancies.append(
                _discrepancy(
                    _WHOLE_DRAFT_LABEL,
                    DiscrepancyKind.UNSTRUCTURED_OUTPUT,
                    draft_a,
                    draft_b,
                    (),
                    (),
                    f"{draft.model_label} did not return structured JSON; "
                    "auto-diff not possible — human review required",
                )
            )
    return discrepancies


def _divergences(draft_a: ThesisDraft, draft_b: ThesisDraft) -> list[Discrepancy]:
    """Compare two parsed drafts section-by-section and by stance."""
    if not draft_a.parsed or not draft_b.parsed:
        return _unstructured_discrepancies(draft_a, draft_b)

    discrepancies: list[Discrepancy] = []
    stance_a = " ".join(draft_a.stance.split())
    stance_b = " ".join(draft_b.stance.split())
    if stance_a and stance_b and stance_a.casefold() != stance_b.casefold():
        discrepancies.append(
            _discrepancy(
                _STANCE_LABEL,
                DiscrepancyKind.STANCE_DIVERGENCE,
                draft_a,
                draft_b,
                (stance_a,),
                (stance_b,),
                f"overall stance differs: {draft_a.model_label}={stance_a!r} vs "
                f"{draft_b.model_label}={stance_b!r}",
            )
        )

    for section in JudgmentSection:
        points_a = draft_a.section_points(section)
        points_b = draft_b.section_points(section)
        if not points_a and not points_b:
            continue
        if bool(points_a) != bool(points_b):
            discrepancies.append(
                _discrepancy(
                    section.value,
                    DiscrepancyKind.COVERAGE_GAP,
                    draft_a,
                    draft_b,
                    points_a,
                    points_b,
                    f"only one model addressed {section.value}",
                )
            )
            continue
        unmatched_a, unmatched_b = _unmatched(points_a, points_b)
        if unmatched_a or unmatched_b:
            discrepancies.append(
                _discrepancy(
                    section.value,
                    DiscrepancyKind.DIVERGENT_POINTS,
                    draft_a,
                    draft_b,
                    unmatched_a,
                    unmatched_b,
                    f"{len(unmatched_a)} point(s) unique to {draft_a.model_label}, "
                    f"{len(unmatched_b)} unique to {draft_b.model_label}",
                )
            )
    return discrepancies


def cross_verify(fact_set: ValidatedFactSet, drafts: Sequence[ThesisDraft]) -> CrossVerification:
    """Run number-checking on each usable draft and divergence-check the first two."""
    known = known_numbers(fact_set)
    usable = [draft for draft in drafts if draft.is_usable]

    unsourced: list[UnsourcedClaim] = []
    for draft in usable:
        unsourced.extend(_unsourced_claims(draft, known))

    discrepancies: list[Discrepancy] = []
    if len(usable) >= 2:
        discrepancies = _divergences(usable[0], usable[1])

    return CrossVerification(unsourced_claims=tuple(unsourced), discrepancies=tuple(discrepancies))
