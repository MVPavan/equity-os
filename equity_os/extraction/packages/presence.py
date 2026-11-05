"""Structural statement presence and package reporting kind (D1a Task 5).

Presence is structural: a family is present when a statement anchor's native field is
filed with the anchor's period shape at the package period end (nil and unmapped facts
count; mapping success and values are never consulted), or when the PDF locator found
that family's block. Applicability, not presence, decides what is expected.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence
from datetime import date

from equity_os.contracts.measurement.canonical import PeriodKind, Representation, StatementFamily
from equity_os.contracts.measurement.evidence import Occurrence
from equity_os.contracts.measurement.measurement_key import PeriodInterval
from equity_os.normalisation.mapping.mapping import (
    CONTEXT_LOCAL_NAME,
    CONTEXT_SCHEMA_IDENTITY,
    CONTEXT_STATEMENT_FAMILY,
    AnchorPeriodShape,
    StatementAnchor,
    in_namespace,
)

_DURATION_KINDS = frozenset(
    {PeriodKind.QUARTER, PeriodKind.HALF_YEAR, PeriodKind.NINE_MONTH, PeriodKind.YEAR}
)
_MONTHS_OF_KIND: Mapping[PeriodKind, int] = {
    PeriodKind.QUARTER: 3,
    PeriodKind.HALF_YEAR: 6,
    PeriodKind.NINE_MONTH: 9,
    PeriodKind.YEAR: 12,
}
_KIND_OF_FISCAL_MONTHS: Mapping[int, PeriodKind] = {
    months: kind for kind, months in _MONTHS_OF_KIND.items()
}
_NO_PERIOD = "no duration ends at {period_end} and it is not a fiscal quarter end"


def statements_present(
    occurrences: Sequence[Occurrence],
    *,
    period_end: date,
    anchors: Sequence[StatementAnchor],
    pdf_located: Collection[StatementFamily],
) -> Mapping[StatementFamily, tuple[Occurrence, ...]]:
    """Each present family with the occurrences that show it (``package_statement_evidence``).

    ``pdf_located`` names the families whose PDF block the locator found (a reused
    generation records them as its PDF occurrences and located-but-unparsed families).
    """
    evidence: dict[StatementFamily, list[Occurrence]] = {}
    for occurrence in occurrences:
        if occurrence.representation is not Representation.XBRL:
            continue
        for anchor in anchors:
            if _anchors(occurrence, anchor, period_end):
                evidence.setdefault(anchor.statement_family, []).append(occurrence)
    for family in pdf_located:
        evidence.setdefault(family, []).extend(
            occurrence
            for occurrence in occurrences
            if occurrence.representation is Representation.PDF
            and occurrence.native_context.get(CONTEXT_STATEMENT_FAMILY) == family.value
        )
    return {family: tuple(found) for family, found in evidence.items()}


def reporting_kind(
    occurrences: Sequence[Occurrence], *, period_end: date, fiscal_year_end_month: int
) -> PeriodKind:
    """The kind of the longest duration ending at the period end, else the fiscal position."""
    longest: PeriodInterval | None = None
    for occurrence in occurrences:
        period = occurrence.period
        if period is None or period.start is None or period.end != period_end:
            continue
        if period.kind(fiscal_year_end_month) not in _DURATION_KINDS:
            continue
        if longest is None or (longest.start is not None and period.start < longest.start):
            longest = period
    if longest is not None:
        return longest.kind(fiscal_year_end_month)
    months = (period_end.month - fiscal_year_end_month) % 12 or 12
    kind = _KIND_OF_FISCAL_MONTHS.get(months)
    if kind is None:
        raise ValueError(_NO_PERIOD.format(period_end=period_end))
    return kind


def _anchors(occurrence: Occurrence, anchor: StatementAnchor, period_end: date) -> bool:
    """Whether an XBRL occurrence is one of the anchor's fields at the anchor's period shape."""
    context = occurrence.native_context
    period = occurrence.period
    if period is None or context.get(CONTEXT_SCHEMA_IDENTITY) != anchor.schema_identity:
        return False
    if context.get(CONTEXT_LOCAL_NAME) not in anchor.native_fields or not in_namespace(
        context, anchor.schema_identity
    ):
        return False
    if anchor.period_shape is AnchorPeriodShape.INSTANT_AT_PERIOD_END:
        return period.instant == period_end
    return period.start is not None and period.end == period_end
