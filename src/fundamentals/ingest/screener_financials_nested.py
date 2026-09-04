"""The nested schedules a level-2 sub-row advertises, and the two shapes proven.

Level 3 is *earned*, not assumed. A level-2 schedule body may carry an
``isExpandable`` string on one of its sub-rows, and that string —
``Company.showSchedule("<label>", "<section>", this)`` — is the site's own
statement that the sub-row expands further. It is also the entire address of
that schedule, which is why it is parsed here rather than pattern-matched at the
call site: a call naming another label or another section describes something
else, and following it would attach the level-2 sub-row's cells to a body about
a different row.

Like :mod:`fundamentals.ingest.screener_financials_shapes`, this module is
*evidence* rather than design. Only two nested families were observed across ten
companies on both bases (2026-09-04):

* ``balance-sheet / Other Assets / Trade receivables`` — three signed crore rows
  that add up to the level-2 sub-row they hang off;
* ``profit-loss / Expenses / Material Cost %`` — crore rows under a *percent*
  parent, so the relation is a ratio of the page's ``Sales`` row, not a sum.

A third advertised family is drift to capture: it is fetched and retained, but
no registry entry says what its rows mean, so its reconciliation cannot run and
the family must not be claimed as proven. Novelty fails closed, exactly as it
does for the mixed level-2 shapes.
"""

from __future__ import annotations

import re
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict

from fundamentals.ingest.screener_financials_models import (
    ROUNDING_HALF_UNIT,
    IdentityStrength,
    Period,
    PeriodReconciliation,
    ReconciliationStatus,
    ScheduleFamily,
    ScheduleStrategy,
    ScheduleSubRow,
    Section,
    SubRowKind,
    TableRow,
    family_key,
)
from fundamentals.ingest.screener_financials_schedules import (
    NO_OVERLAP,
    OUTSIDE_SIGNATURE,
    PERIOD_DETAIL,
    UNVERIFIED_SHAPE,
    blocked_reconciliation,
    cell_values,
    page_readings,
    parse_sub_rows,
    reconcile_flat_sum,
    refuse_mismatch,
    unaligned_periods,
)
from fundamentals.ingest.screener_session_models import Basis
from fundamentals.verify.crossfoot import half_ulp

# The page row a percent-of-sales identity divides by. Named by its schedule
# parent rather than its label, so the row must be one the page itself offers to
# expand; banks and NBFCs publish ``Revenue`` and have no such row at all.
SALES_SCHEDULE_PARENT = "Sales"

# The API writes the nested call with double quotes inside the JSON string,
# unlike the single quotes the page HTML uses for its own ``showSchedule``
# buttons. Anchored at both ends: a call this pattern does not match whole is a
# call this contract cannot claim to have understood.
NESTED_CALL_PATTERN = re.compile(
    r'^Company\.showSchedule\(\s*"(?P<label>[^"]*)"\s*,\s*"(?P<section>[^"]*)"\s*,\s*this\s*\)$'
)

UNPARSED_CALL = (
    "sub-row {label!r} advertises a nested schedule this contract cannot read: {call!r}. "
    "The call is the whole address of the nested body, so a call that does not parse "
    "cannot be turned into a request"
)
WRONG_SUBJECT_CALL = (
    "sub-row {label!r} of the {section} section advertises {call!r}, which names another "
    "row or another section. Following it would compare this sub-row's cells against a "
    "body describing something else, so it is recorded as drift and not requested"
)
UNREGISTERED_NESTED = (
    "no nested signature is registered for it; only the two families in "
    "NESTED_SCHEDULE_SIGNATURES were ever observed, so nothing says what these rows mean"
)
_NESTED_SUM_NOTE = (
    "sub-rows sum to the parent sub-row they expand across {count} period(s), within rounding"
)
_PERCENT_NOTE = (
    "100 x the sub-row amounts divided by the section's Sales row matches the parent "
    "percent across {count} period(s), within the rounding of both sides propagated "
    "through the division"
)
_NO_SALES_ROW = (
    "the section publishes no expandable Sales row, so the percent-of-Sales identity has "
    "no denominator and was never checked; banks and NBFCs publish Revenue instead"
)
_PERCENT_DETAIL = (
    "{period} 100 x sub-row amounts over Sales is {total} against parent percent {page} "
    "(tolerance {tol})"
)

# The identity is stated in percentage points, so the sub-row sum is scaled by
# 100 before it is compared with the parent's percent cell.
_PERCENT_SCALE = Decimal(100)
# Screener displays these figures already in the unit the identity works in, so
# a displayed half-ULP needs no rescaling.
_DISPLAY_SCALE = 1


class NestedSignature(BaseModel):
    """The verified shape of one nested family, and how it relates to its parent.

    ``allowed`` is every ``(label, kind)`` pair the live captures carried; an
    observed body must be a SUBSET of it, because companies genuinely publish
    different rows. A row outside the set means the family may have changed what
    it decomposes into, and inheriting the registered treatment would hide that
    even when the numbers still add up.
    """

    model_config = ConfigDict(frozen=True)

    strategy: ScheduleStrategy
    allowed: frozenset[tuple[str, SubRowKind]]


NESTED_SCHEDULE_SIGNATURES: dict[tuple[Section, str, str], NestedSignature] = {
    (Section.BALANCE_SHEET, "Other Assets", "Trade receivables"): NestedSignature(
        strategy=ScheduleStrategy.FLAT_SUM,
        allowed=frozenset(
            {
                ("Receivables over 6m", SubRowKind.AMOUNT),
                ("Receivables under 6m", SubRowKind.AMOUNT),
                ("Prov for Doubtful", SubRowKind.AMOUNT),
            }
        ),
    ),
    (Section.PROFIT_LOSS, "Expenses", "Material Cost %"): NestedSignature(
        strategy=ScheduleStrategy.PERCENT_OF_SALES,
        allowed=frozenset(
            {
                ("Raw material cost", SubRowKind.AMOUNT),
                ("Change in inventory", SubRowKind.AMOUNT),
            }
        ),
    ),
}


def nested_call_defect(call: str, *, label: str, section: Section) -> str | None:
    """Why this advertised call may not be followed, or ``None`` when it may.

    A nested schedule is this sub-row's own schedule or it is nothing: the call
    must name this sub-row's label and this family's section.
    """
    match = NESTED_CALL_PATTERN.match(call.strip())
    if match is None:
        return UNPARSED_CALL.format(label=label, call=call)
    if match.group("label") != label or match.group("section") != section.value:
        return WRONG_SUBJECT_CALL.format(label=label, section=section.value, call=call)
    return None


def nested_signature(section: Section, expands: str, parent: str) -> NestedSignature | None:
    """The registered shape of one nested family, when it has one."""
    return NESTED_SCHEDULE_SIGNATURES.get((section, expands, parent))


def deeper_than_acquired(sub_rows: tuple[ScheduleSubRow, ...]) -> tuple[str, ...]:
    """Sub-row labels advertising a schedule below the depth this contract acquires.

    Every family this module reads sits at the ``MAX_SCHEDULE_DEPTH`` bound
    declared beside the vocabulary, so none of
    these rows is ever followed. They are named rather than dropped: the call is
    the only evidence the site goes deeper than this contract does.
    """
    return tuple(sub_row.label for sub_row in sub_rows if sub_row.nested_schedule_call is not None)


def read_nested_schedule(
    raw_body: bytes,
    *,
    section: Section,
    parent: str,
    expands: str,
    basis: Basis,
    url: str,
    document_id: str,
    body_sha256: str,
    periods: tuple[Period, ...],
    reference_row: ScheduleSubRow,
    sales_row: TableRow | None,
    source_id: str,
    retrieved_at: Any,
) -> ScheduleFamily:
    """Parse one level-3 response and hold it to the level-2 sub-row it expands.

    ``reference_row`` is that sub-row, and it — never the page row two levels up
    — is what a nested family decomposes. The fixture case is the live one: an
    ``Other Assets`` page row of 900 above a ``Trade receivables`` sub-row of
    500 would make a gate pointed at the page refuse correct data.

    Strategy is registry-only here, with no shape inference at all: only the two
    families in :data:`NESTED_SCHEDULE_SIGNATURES` were ever observed, so a
    third is retained as evidence of drift rather than read by analogy.
    """
    family = family_key(section, parent, expands)
    sub_rows = parse_sub_rows(
        raw_body,
        family=family,
        periods=periods,
        document_id=document_id,
        body_sha256=body_sha256,
        source_id=source_id,
        retrieved_at=retrieved_at,
    )
    strategy, strategy_note = _resolve_nested_strategy(
        sub_rows, family=family, signature=nested_signature(section, expands, parent)
    )
    unaligned = unaligned_periods(sub_rows)
    reference = cell_values(reference_row.cells)
    blocked = blocked_reconciliation(
        sub_rows, strategy=strategy, strategy_note=strategy_note, unaligned=unaligned
    )
    if blocked is not None:
        comparisons, status, note = blocked
    elif strategy is ScheduleStrategy.PERCENT_OF_SALES:
        comparisons, status, note = _reconcile_percent(
            sub_rows, sales=page_readings(sales_row), periods=periods, reference=reference
        )
    else:
        comparisons, status, note = reconcile_flat_sum(
            sub_rows, periods=periods, reference=reference, reconciled_note=_NESTED_SUM_NOTE
        )
    refuse_mismatch(
        comparisons,
        family=family,
        basis=basis,
        url=url,
        detail=_PERCENT_DETAIL if strategy is ScheduleStrategy.PERCENT_OF_SALES else PERIOD_DETAIL,
    )
    return ScheduleFamily(
        section=section,
        parent=parent,
        basis=basis,
        url=url,
        document_id=document_id,
        body_sha256=body_sha256,
        identity_strength=IdentityStrength.CONFIGURED_URL_ONLY,
        strategy=strategy,
        reconciliation=status,
        reconciliation_note=note,
        expands=expands,
        periods=periods,
        sub_rows=sub_rows,
        comparisons=comparisons,
        unaligned_periods=unaligned,
        deeper_not_acquired=deeper_than_acquired(sub_rows),
    )


def _resolve_nested_strategy(
    sub_rows: tuple[ScheduleSubRow, ...],
    *,
    family: str,
    signature: NestedSignature | None,
) -> tuple[ScheduleStrategy, str]:
    """Admit a nested family only on a registered signature its body stays inside."""
    if signature is None:
        return ScheduleStrategy.UNVERIFIED, UNVERIFIED_SHAPE.format(
            family=family, detail=UNREGISTERED_NESTED
        )
    observed = {(sub_row.label, sub_row.kind) for sub_row in sub_rows}
    outside = sorted(f"{label} ({kind.value})" for label, kind in observed - signature.allowed)
    if outside:
        return ScheduleStrategy.UNVERIFIED, UNVERIFIED_SHAPE.format(
            family=family, detail=OUTSIDE_SIGNATURE.format(labels=", ".join(outside))
        )
    return signature.strategy, ""


def _reconcile_percent(
    sub_rows: tuple[ScheduleSubRow, ...],
    *,
    sales: dict[int, tuple[Decimal, str]] | None,
    periods: tuple[Period, ...],
    reference: dict[int, Decimal],
) -> tuple[tuple[PeriodReconciliation, ...], ReconciliationStatus, str]:
    """Check a percent parent against the ratio its crore sub-rows make of Sales.

    ``Material Cost %`` is a percentage of the section's ``Sales`` row while its
    breakdown is in crores, so a sum against the parent would compare 127 crore
    with 82 percent. The identity that holds is ``100 x sum / Sales``.

    The band is the rounding of both sides propagated through the division: the
    page's own half point for a whole-number percent, plus each addend's
    half-ULP scaled to percent, plus the sensitivity of the ratio to the rounded
    denominator. A flat half point would refuse a correct 81.41 against a
    displayed 82, which is the live NETWEB case.

    A period whose ``Sales`` is unpublished (or zero) is skipped and the rest
    still checked, exactly as the flat-sum gate skips a period with no readable
    page value: a company that reported nothing for one year is not evidence
    about the years it did report. Only when *no* period could be checked does
    the family fall to ``NOT_COMPARABLE``.
    """
    if sales is None:
        return (), ReconciliationStatus.NOT_COMPARABLE, _NO_SALES_ROW
    comparisons: list[PeriodReconciliation] = []
    for period in periods:
        addends = [
            cell
            for sub_row in sub_rows
            for cell in sub_row.cells
            if cell.period_index == period.index and cell.value is not None
        ]
        sales_reading = sales.get(period.index)
        percent = reference.get(period.index)
        if not addends or sales_reading is None or percent is None or not sales_reading[0]:
            continue
        sales_value, sales_text = sales_reading
        total = sum((cell.value for cell in addends if cell.value is not None), Decimal(0))
        ratio = _PERCENT_SCALE * total / sales_value
        tolerance = ROUNDING_HALF_UNIT + (
            _PERCENT_SCALE * sum(_displayed_half_ulp(cell.raw_text) for cell in addends)
            + abs(ratio) * _displayed_half_ulp(sales_text)
        ) / abs(sales_value)
        comparisons.append(
            PeriodReconciliation(
                period_label=period.label,
                sub_row_total=ratio,
                page_row_value=percent,
                difference=ratio - percent,
                tolerance=tolerance,
                within_tolerance=abs(ratio - percent) <= tolerance,
            )
        )
    if not comparisons:
        return (), ReconciliationStatus.NOT_COMPARABLE, NO_OVERLAP
    return (
        tuple(comparisons),
        ReconciliationStatus.RECONCILED,
        _PERCENT_NOTE.format(count=len(comparisons)),
    )


def _displayed_half_ulp(text: str) -> Decimal:
    """Half a unit in the last place the site actually displayed.

    The percent band propagates each figure's *displayed* precision: a whole
    crore carries half a crore, ``120.0`` carries 0.05. That is deliberately not
    the flat-sum band, which reads a displayed fraction as a signal that the
    figure was not rounded at all and admits nothing for it — a rule that works
    where both sides are the same unit and would understate the error once the
    figures are divided.
    """
    _, separator, fraction = text.partition(".")
    return half_ulp(len(fraction) if separator else 0, _DISPLAY_SCALE)
