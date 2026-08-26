"""Reading one Screener schedule response and holding it to the page it expands.

A schedule body is a bare ``{sub_row_label: {period_label: "display string"}}``
map. It names no company, no basis, and no units; the request URL is its entire
binding, which is why every value read out of it is anchored ``API_DOCUMENT``
with ``identity_strength=CONFIGURED_URL_ONLY``.

That is what makes the reconciliation gate load-bearing. The schedules API
selects basis by the *presence* of the ``consolidated`` query key, so a URL
built with the key when it should have been omitted returns a body of the wrong
basis that parses perfectly, aligns to the page's period labels perfectly, and
is wrong by tens of percent. Only comparing the sub-row sum against the page row
it expands catches that.

Which families may be summed is therefore decided by a **registry of shapes
observed live**, not inferred from the body. An inferred rule — "any percent or
subtotal row means analysis, so skip the gate" — is an escape hatch: a
wrong-basis amount breakdown that happens to carry one informational percent row
would be waved through and exit zero. Under the registry, a family is summed
when every sub-row is an amount, exempted when it is entirely percentages or
when it matches one of the four registered mixed shapes, and otherwise refused
as ``UNVERIFIED``. Novelty fails closed.

Two further things block a ``RECONCILED`` claim, because each is a way for the
gate to appear to run while comparing the wrong things: a published sub-row
period that matches no column on the page, and an empty ``{}`` response.
"""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

from fundamentals.contracts.provenance import Provenance, SourceAnchorType
from fundamentals.ingest.screener_financials_models import (
    CLASS_ATTRIBUTE,
    EMPHASIS_CLASS,
    IS_EXPANDABLE_KEY,
    RESERVED_SUB_ROW_KEYS,
    ROUNDING_HALF_UNIT,
    SET_ATTRIBUTES_KEY,
    AmbiguousStructureError,
    Cell,
    IdentityStrength,
    Period,
    PeriodReconciliation,
    ReconciliationStatus,
    ScheduleBodyError,
    ScheduleFamily,
    ScheduleReconciliationError,
    ScheduleStrategy,
    ScheduleSubRow,
    Section,
    SubRowKind,
    TableRow,
)
from fundamentals.ingest.screener_financials_shapes import (
    MIXED_FAMILY_SHAPES,
    HierarchyRule,
    MixedFamilyShape,
)
from fundamentals.ingest.screener_financials_tables import (
    normalize_text,
    read_number,
    reject_duplicate_anchors,
)
from fundamentals.ingest.screener_session_models import Basis

_NOT_AN_OBJECT = "schedule body for {family} is not a JSON object"
_SUB_ROW_NOT_AN_OBJECT = "schedule sub-row {label!r} of {family} is not a JSON object"
_RESERVED_COLLISION = (
    "the page's own column label(s) {labels} collide with reserved schedule key(s) for "
    "{family}; those keys are skipped as metadata, so a real period would be read as none"
)
_RESERVED_TYPE = (
    "reserved key {key!r} on sub-row {label!r} of {family} carries a {seen}, not a "
    "{expected}; a reserved key is skipped rather than read, so a changed type would be "
    "silently discarded"
)
_MISMATCH = (
    "schedule {family} on the {basis} basis does not reconcile with the page row it "
    "expands: {details}. The schedules API selects basis by the presence of the "
    "'consolidated' key, so check the request URL {url} before trusting either number"
)
_PERIOD_DETAIL = "{period} sub-rows sum to {total} against page value {page} (tolerance {tol})"

_ALL_PERCENT_NOTE = "every sub-row is a percentage ({labels}); there is nothing to add"
_KNOWN_MIXED_NOTE = (
    "registered mixed shape for this family: its sub-rows restate or sub-total the parent "
    "row rather than decomposing it, so a sum would double-count"
)
_UNVERIFIED_SHAPE = (
    "sub-row shape is not one this contract has verified for {family}: {detail}. The "
    "reconciliation gate cannot run on an unrecognised shape, so it is refused rather "
    "than exempted"
)
_UNREGISTERED_MIXED = (
    "the family mixes kinds ({detail}) but has no registered signature; only the four "
    "families in MIXED_FAMILY_SIGNATURES are known not to be summable"
)
_OUTSIDE_SIGNATURE = "sub-rows outside the registered signature: {labels}"
_MISSING_REQUIRED = (
    "the rows that identify this family are absent: {labels}. Belonging to the allowed "
    "set only says a row is familiar; without the required rows the body is not the "
    "registered shape and must not inherit its exemption"
)
_HIERARCHY_NOTE = (
    "page row verified as {minuend} minus {subtrahend} across {count} period(s), within rounding"
)
_HIERARCHY_MISSING = (
    "registered hierarchy needs {labels}, which the response did not publish for any "
    "period the page carries"
)
_HIERARCHY_DETAIL = (
    "{period} {minuend} minus {subtrahend} is {derived} against page value {page} (tolerance {tol})"
)
_NO_SUB_ROWS = (
    "the response was empty; an empty HTTP 200 carries no session, issuer or basis "
    "marker, so it cannot be told apart from an expired cookie or a soft block"
)
_NO_OVERLAP = (
    "no period carried both a sub-row amount and a readable page-row value, so the sum "
    "was never checked"
)
_UNALIGNED = (
    "sub-row periods that match no column on the page: {labels}; a partial alignment "
    "cannot prove the response describes the same periods as the page"
)
_RECONCILED = "sub-rows sum to the page row across {count} period(s), within rounding"


def read_schedule(
    raw_body: bytes,
    *,
    section: Section,
    parent: str,
    basis: Basis,
    url: str,
    document_id: str,
    body_sha256: str,
    periods: tuple[Period, ...],
    page_row: TableRow | None,
    source_id: str,
    retrieved_at: Any,
) -> ScheduleFamily:
    """Parse one schedule response, classify it, and hold it to its page row.

    Raises :class:`ScheduleReconciliationError` when a summable family's
    sub-rows do not add up to the row it expands; every other shape surprise is
    retained rather than fatal.
    """
    family = f"{section.value}/{parent}"
    body = _decode(raw_body, family=family)
    sub_rows = _read_sub_rows(
        body,
        family=family,
        periods=periods,
        document_id=document_id,
        table_key=family,
        source_id=source_id,
        file_sha256=body_sha256,
        retrieved_at=retrieved_at,
    )
    reject_duplicate_anchors(
        tuple(cell.provenance for sub_row in sub_rows for cell in sub_row.cells),
        context=f"screener schedule {family}",
    )
    strategy, strategy_note = _resolve_strategy(sub_rows, section=section, parent=parent)
    unaligned = tuple(
        dict.fromkeys(period for sub_row in sub_rows for period in sub_row.unmatched_periods)
    )
    comparisons, status, note = _reconcile(
        sub_rows,
        strategy=strategy,
        strategy_note=strategy_note,
        hierarchy=_hierarchy_rule(section, parent),
        unaligned=unaligned,
        periods=periods,
        page_row=page_row,
    )
    failures = tuple(comparison for comparison in comparisons if not comparison.within_tolerance)
    if failures:
        details = "; ".join(
            _PERIOD_DETAIL.format(
                period=failure.period_label,
                total=failure.sub_row_total,
                page=failure.page_row_value,
                tol=failure.tolerance,
            )
            for failure in failures
        )
        raise ScheduleReconciliationError(
            _MISMATCH.format(family=family, basis=basis.value, details=details, url=url)
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
        periods=periods,
        sub_rows=sub_rows,
        comparisons=comparisons,
        unaligned_periods=unaligned,
    )


def _decode(raw_body: bytes, *, family: str) -> dict[str, Any]:
    """Decode the response as the object shape this API is documented to return."""
    try:
        parsed = json.loads(raw_body.decode("utf-8", errors="replace"))
    except json.JSONDecodeError as error:
        raise ScheduleBodyError(f"schedule body for {family} is not JSON: {error}") from error
    if not isinstance(parsed, dict):
        raise ScheduleBodyError(_NOT_AN_OBJECT.format(family=family))
    return parsed


def _read_sub_rows(
    body: dict[str, Any],
    *,
    family: str,
    periods: tuple[Period, ...],
    document_id: str,
    table_key: str,
    source_id: str,
    file_sha256: str,
    retrieved_at: Any,
) -> tuple[ScheduleSubRow, ...]:
    """Read every sub-row, aligning its periods to the page's header labels."""
    by_label = {period.label: period for period in periods}
    _refuse_reserved_key_collision(by_label, family=family)
    sub_rows: list[ScheduleSubRow] = []
    for position, (label, raw_values) in enumerate(body.items()):
        if not isinstance(raw_values, dict):
            raise ScheduleBodyError(_SUB_ROW_NOT_AN_OBJECT.format(label=label, family=family))
        _check_reserved_types(raw_values, label=label, family=family)
        emphasis = _is_emphasised(raw_values.get(SET_ATTRIBUTES_KEY))
        nested = raw_values.get(IS_EXPANDABLE_KEY)
        cells: list[Cell] = []
        unmatched: list[str] = []
        percent = False
        for period_label, raw_value in raw_values.items():
            if period_label in RESERVED_SUB_ROW_KEYS:
                continue
            raw_text = normalize_text(raw_value) if isinstance(raw_value, str) else ""
            value, is_percent = read_number(raw_text)
            percent = percent or is_percent
            period = by_label.get(period_label)
            if period is None:
                # A period the page's header does not carry. Retained by name:
                # it is a real reading we cannot anchor to a column, and
                # dropping it would hide a header/API divergence.
                unmatched.append(period_label)
                continue
            cells.append(
                Cell(
                    period_index=period.index,
                    value=value,
                    raw_text=raw_text,
                    published=bool(raw_text),
                    provenance=Provenance(
                        source_id=source_id,
                        file_sha256=file_sha256,
                        anchor_type=SourceAnchorType.API_DOCUMENT,
                        document_id=document_id,
                        context_ref=period_label,
                        table_key=table_key,
                        row_label=label,
                        column_label=period_label,
                        retrieved_at=retrieved_at,
                    ),
                )
            )
        sub_rows.append(
            ScheduleSubRow(
                position=position,
                label=label,
                kind=_sub_row_kind(percent=percent, emphasis=emphasis),
                percent=percent,
                emphasis=emphasis,
                cells=tuple(cells),
                unmatched_periods=tuple(unmatched),
                nested_schedule_call=nested if isinstance(nested, str) else None,
            )
        )
    return tuple(sub_rows)


def _refuse_reserved_key_collision(by_label: dict[str, Period], *, family: str) -> None:
    """Refuse a page whose own column label collides with a reserved key name.

    Reserved keys are skipped before period matching, so a column genuinely
    labelled ``setAttributes`` or ``isExpandable`` would have its values
    silently discarded as metadata — and the family could then reconcile on the
    remaining columns while a real period went unread.
    """
    collisions = sorted(RESERVED_SUB_ROW_KEYS & set(by_label))
    if collisions:
        raise AmbiguousStructureError(
            _RESERVED_COLLISION.format(family=family, labels=", ".join(collisions))
        )


def _check_reserved_types(raw_values: dict[str, Any], *, label: str, family: str) -> None:
    """Refuse a reserved key whose value is not the type that key is defined to carry.

    A reserved key is skipped rather than read, so a wrongly-typed one is a
    change in what the key means — and skipping it anyway would hide whatever it
    became. ``setAttributes`` carries an attribute map; ``isExpandable`` carries
    the nested ``showSchedule`` call as a string.
    """
    for key, expected in ((SET_ATTRIBUTES_KEY, dict), (IS_EXPANDABLE_KEY, str)):
        if key in raw_values and not isinstance(raw_values[key], expected):
            raise ScheduleBodyError(
                _RESERVED_TYPE.format(
                    key=key,
                    label=label,
                    family=family,
                    expected=expected.__name__,
                    seen=type(raw_values[key]).__name__,
                )
            )


def _is_emphasised(attributes: Any) -> bool:
    """True when Screener marks this sub-row as its own subtotal."""
    if not isinstance(attributes, dict):
        return False
    classes = attributes.get(CLASS_ATTRIBUTE)
    return isinstance(classes, str) and EMPHASIS_CLASS in classes.split()


def _hierarchy_rule(section: Section, parent: str) -> HierarchyRule | None:
    """The registered arithmetic relation for this family, when it has one."""
    shape = MIXED_FAMILY_SHAPES.get((section, parent))
    return None if shape is None else shape.hierarchy


def _sub_row_kind(*, percent: bool, emphasis: bool) -> SubRowKind:
    """Classify one sub-row by what the response says it is.

    A subtotal marking wins over a percent reading: a row Screener marks
    ``strong`` totals the rows above it whatever its lexemes look like, and that
    is the fact that disqualifies a flat sum.
    """
    if emphasis:
        return SubRowKind.SUBTOTAL
    return SubRowKind.PERCENT if percent else SubRowKind.AMOUNT


def _resolve_strategy(
    sub_rows: tuple[ScheduleSubRow, ...], *, section: Section, parent: str
) -> tuple[ScheduleStrategy, str]:
    """Decide how this family relates to its page row, refusing anything novel.

    Registry first, shape second. A family registered as mixed is checked
    against its shape even when a particular company's body happens to be all
    amounts, because the rows are still restatements of the parent — reading
    NETWEB's four-row ``Net Profit`` as a flat sum would produce a confident
    wrong total rather than an honest exemption.

    Qualifying takes two independent checks. Every row must be *within* the
    allowed set, and every *required* row must be present. The allowed check
    alone is an escape hatch: a body of one familiar row — ``{"Land": 999}``
    against a page showing 600 — is a subset of Fixed Assets' allowed set, and
    would inherit the exemption while carrying a number that is not the page's.
    """
    kinds = {sub_row.kind for sub_row in sub_rows}
    shape = MIXED_FAMILY_SHAPES.get((section, parent))
    if shape is not None:
        return _resolve_registered(sub_rows, shape=shape, section=section, parent=parent)
    if not sub_rows:
        return ScheduleStrategy.FLAT_SUM, _NO_SUB_ROWS
    if kinds == {SubRowKind.AMOUNT}:
        return ScheduleStrategy.FLAT_SUM, ""
    if kinds == {SubRowKind.PERCENT}:
        return ScheduleStrategy.ALL_PERCENT, _ALL_PERCENT_NOTE.format(
            labels=", ".join(sub_row.label for sub_row in sub_rows)
        )
    detail = ", ".join(
        f"{sub_row.label} ({sub_row.kind.value})"
        for sub_row in sub_rows
        if sub_row.kind is not SubRowKind.AMOUNT
    )
    return ScheduleStrategy.UNVERIFIED, _UNVERIFIED_SHAPE.format(
        family=f"{section.value}/{parent}",
        detail=_UNREGISTERED_MIXED.format(detail=detail),
    )


def _resolve_registered(
    sub_rows: tuple[ScheduleSubRow, ...],
    *,
    shape: MixedFamilyShape,
    section: Section,
    parent: str,
) -> tuple[ScheduleStrategy, str]:
    """Admit a registered family only when the body is that family's whole shape."""
    family = f"{section.value}/{parent}"
    observed = {(sub_row.label, sub_row.kind) for sub_row in sub_rows}
    outside = sorted(f"{label} ({kind.value})" for label, kind in observed - shape.allowed)
    if outside:
        return ScheduleStrategy.UNVERIFIED, _UNVERIFIED_SHAPE.format(
            family=family, detail=_OUTSIDE_SIGNATURE.format(labels=", ".join(outside))
        )
    missing = sorted(f"{label} ({kind.value})" for label, kind in shape.required - observed)
    if missing:
        return ScheduleStrategy.UNVERIFIED, _UNVERIFIED_SHAPE.format(
            family=family, detail=_MISSING_REQUIRED.format(labels=", ".join(missing))
        )
    if shape.hierarchy is not None:
        return ScheduleStrategy.HIERARCHICAL, ""
    return ScheduleStrategy.KNOWN_MIXED, _KNOWN_MIXED_NOTE


def _reconcile_hierarchy(
    sub_rows: tuple[ScheduleSubRow, ...],
    *,
    rule: HierarchyRule,
    periods: tuple[Period, ...],
    page_row: TableRow | None,
) -> tuple[tuple[PeriodReconciliation, ...], ReconciliationStatus, str]:
    """Check a page row that is one sub-row minus another, period by period.

    Verified against all three live captures before being enforced: ``Gross
    Block`` less ``Accumulated Depreciation`` matches the ``Fixed Assets`` page
    row to within 1 crore on TITAN and HFCL and 0.41 on NETWEB, inside the
    two-addend rounding band. So this family is *proven* against its page row
    rather than merely exempted from proof.
    """
    minuend = _sub_row_values(sub_rows, rule.minuend)
    subtrahend = _sub_row_values(sub_rows, rule.subtrahend)
    page_values = _page_values(page_row)
    comparisons: list[PeriodReconciliation] = []
    for period in periods:
        left = minuend.get(period.index)
        right = subtrahend.get(period.index)
        page_value = page_values.get(period.index)
        if left is None or right is None or page_value is None:
            continue
        derived = left[0] - right[0]
        tolerance = reconciliation_tolerance((left[1], right[1]))
        comparisons.append(
            PeriodReconciliation(
                period_label=period.label,
                sub_row_total=derived,
                page_row_value=page_value,
                difference=derived - page_value,
                tolerance=tolerance,
                within_tolerance=abs(derived - page_value) <= tolerance,
            )
        )
    if not comparisons:
        return (
            (),
            ReconciliationStatus.NOT_COMPARABLE,
            _HIERARCHY_MISSING.format(labels=f"{rule.minuend}, {rule.subtrahend}"),
        )
    return (
        tuple(comparisons),
        ReconciliationStatus.RECONCILED,
        _HIERARCHY_NOTE.format(
            minuend=rule.minuend, subtrahend=rule.subtrahend, count=len(comparisons)
        ),
    )


def _sub_row_values(
    sub_rows: tuple[ScheduleSubRow, ...], label: str
) -> dict[int, tuple[Decimal, str]]:
    """One named sub-row's readable values and lexemes, by period index."""
    for sub_row in sub_rows:
        if sub_row.label != label:
            continue
        return {
            cell.period_index: (cell.value, cell.raw_text)
            for cell in sub_row.cells
            if cell.value is not None
        }
    return {}


def reconciliation_tolerance(addend_texts: tuple[str, ...]) -> Decimal:
    """The rounding band a correct sum of these addends may fall in.

    The page row is displayed rounded to whole crores, and so is each sub-row
    that the API publishes without a fractional part, so ``n`` addends and one
    total carry a worst-case rounding error of ``(n + 1) / 2``.

    A single addend is a different case, because the sub-row and the parent are
    then the *same underlying number*. Two roundings of one number are equal, so
    when that single addend is itself displayed as a whole crore the two must
    agree exactly — the general band of 1 would otherwise admit a sub-row of 101
    against a parent of 100, which is the size of disagreement this gate exists
    to catch on a small company. When the single addend is published at full
    precision (``0.42`` against a page showing ``0``, live on NETWEB and HFCL
    quarterly Other Income) only the page value is rounded, so the band is the
    page's own half-unit.
    """
    if len(addend_texts) == 1:
        return ROUNDING_HALF_UNIT if _has_fraction(addend_texts[0]) else Decimal(0)
    return ROUNDING_HALF_UNIT * (len(addend_texts) + 1)


def _has_fraction(text: str) -> bool:
    """True when a displayed figure carries digits after a decimal point."""
    _, separator, fraction = text.partition(".")
    return bool(separator) and any(digit != "0" for digit in fraction)


def _reconcile(
    sub_rows: tuple[ScheduleSubRow, ...],
    *,
    strategy: ScheduleStrategy,
    strategy_note: str,
    hierarchy: HierarchyRule | None,
    unaligned: tuple[str, ...],
    periods: tuple[Period, ...],
    page_row: TableRow | None,
) -> tuple[tuple[PeriodReconciliation, ...], ReconciliationStatus, str]:
    """Sum a summable family per period and compare it against the page row.

    ``RECONCILED`` is a positive claim and is reached only from the one path
    that earns it: a registered flat-sum shape, every published sub-row period
    aligned to a page column, and at least one comparison that held.
    """
    if strategy is ScheduleStrategy.UNVERIFIED:
        return (), ReconciliationStatus.UNVERIFIED, strategy_note
    if not sub_rows:
        return (), ReconciliationStatus.UNVERIFIED_EMPTY, _NO_SUB_ROWS
    if unaligned:
        return (
            (),
            ReconciliationStatus.UNVERIFIED,
            _UNALIGNED.format(labels=", ".join(unaligned)),
        )
    if strategy is ScheduleStrategy.HIERARCHICAL:
        rule = hierarchy
        assert rule is not None  # noqa: S101 - HIERARCHICAL is set only with a rule
        return _reconcile_hierarchy(sub_rows, rule=rule, periods=periods, page_row=page_row)
    if strategy is not ScheduleStrategy.FLAT_SUM:
        return (), ReconciliationStatus.NOT_APPLICABLE, strategy_note
    page_values = _page_values(page_row)
    comparisons: list[PeriodReconciliation] = []
    for period in periods:
        addends = [
            cell
            for sub_row in sub_rows
            for cell in sub_row.cells
            if cell.period_index == period.index and cell.value is not None
        ]
        page_value = page_values.get(period.index)
        if not addends or page_value is None:
            continue
        values = [cell.value for cell in addends if cell.value is not None]
        total = sum(values, Decimal(0))
        tolerance = reconciliation_tolerance(tuple(cell.raw_text for cell in addends))
        comparisons.append(
            PeriodReconciliation(
                period_label=period.label,
                sub_row_total=total,
                page_row_value=page_value,
                difference=total - page_value,
                tolerance=tolerance,
                within_tolerance=abs(total - page_value) <= tolerance,
            )
        )
    if not comparisons:
        return (), ReconciliationStatus.NOT_COMPARABLE, _NO_OVERLAP
    return (
        tuple(comparisons),
        ReconciliationStatus.RECONCILED,
        _RECONCILED.format(count=len(comparisons)),
    )


def _page_values(page_row: TableRow | None) -> dict[int, Decimal]:
    """The page row's readable numbers by period index, for comparison."""
    if page_row is None:
        return {}
    return {cell.period_index: cell.value for cell in page_row.cells if cell.value is not None}
