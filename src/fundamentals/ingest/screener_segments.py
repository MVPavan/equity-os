"""Reading one Product Segments fragment and holding its Sales line to the page.

Pure and deterministic: an HTML fragment in, a typed table out, or a typed
refusal. Nothing here fetches.

**Basis is selected by the query VALUE.** The URL is built by
:func:`~fundamentals.ingest.screener_company_models.segments_path`, which emits
``?consolidated=true`` for consolidated and no parameter at all for standalone.
This is the opposite of the schedules API, where the key's *presence* decides
and its value is ignored — so a caller who "turns consolidated off" by sending
``consolidated=false`` gets the standalone body from this endpoint and the
consolidated one from that one. Both bodies parse cleanly, carry the same
period labels, and differ only in their numbers.

That is what the Sales gate is for, and it is a weaker gate than Slice 1's
because the source is weaker. Screener's page Sales row and its segment Sales
rows do not have to agree, and across the live captures they disagree in both
directions for honest reasons:

* TITAN exceeds the page by 105–184 crore every quarter and 70–552 every year —
  the table lists no elimination line at all;
* ETERNAL matches exactly in most periods and falls 17–23 crore short in two,
  where its ``Less: Intersegment`` row deducts revenue the page's Sales row does
  not;
* HFCL matches within a crore recently and falls 261 short in Mar 2016, where it
  published four segment lines against the five it publishes now.

So "sum below page" cannot be a refusal in general: it would refuse real
consolidated data on two of the three companies captured. What it *can* be is a
refusal on the **newest** comparable period, because that is where the honest
cases do not occur and the basis swap does. A standalone body served against
TITAN's consolidated page is below on every period and by 3,114 crore on the
newest quarter, while every legitimate capture is at or above the page there.
Everything else is classified honestly and kept:
:attr:`~fundamentals.ingest.screener_company_models.SegmentOutcome.EXCEEDS_PAGE`
and ``BELOW_PAGE`` are ``BOUNDED``, never ``SUM_PROVEN``.

Only the Sales line is checked. Profit, Capital Employed and every growth or
margin percentage restate or ratio the same figures, so summing them proves
nothing; they are retained unchecked.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from fundamentals.ingest.screener_company_artifacts import (
    PeriodComparison,
    SegmentLine,
    SegmentRow,
    SegmentTable,
)
from fundamentals.ingest.screener_company_models import (
    PAGE_SALES_ROW,
    SEGMENT_SALES_LINE,
    Binding,
    EmptyShellError,
    PeriodAlignmentError,
    SegmentHook,
    SegmentOutcome,
    SegmentReconciliationError,
    Validation,
    ValidationStatus,
    crore_tolerance,
)
from fundamentals.ingest.screener_financials_models import (
    AmbiguousStructureError,
    Cell,
    IdentityStrength,
    Period,
    PeriodKind,
    QuarantinedRow,
    SectionTable,
    TableRow,
)
from fundamentals.ingest.screener_financials_tables import (
    html_anchor,
    normalize_text,
    read_number,
    reject_duplicate_anchors,
    row_path,
)

SEGMENT_LINE_ATTRIBUTE = "data-segment-line"

_DATA_TABLE_XPATH = "//table[contains(concat(' ', normalize-space(@class), ' '), ' data-table ')]"
_COLSPAN_CELL_XPATH = "./td[@colspan]"

_NO_TABLE = (
    "screener segments fragment for {section} holds {count} data tables; exactly one is "
    "required so the table's numbers cannot depend on document order"
)
_EMPTY_SHELL = (
    "screener segments fragment for {section} carries no period columns, but the page "
    "renders a Product Segments button for it. A periodless shell is what a wrong company "
    "id or a basis parameter this endpoint does not accept returns, so it is refused "
    "rather than recorded as an empty table; check {url}"
)
_NOT_A_WINDOW = (
    "screener segments periods {fragment} are not a contiguous run of the {section} "
    "section's own columns {page}; the page header is the only thing binding these "
    "columns to real periods"
)
_DUPLICATE_PERIODS = "screener segments fragment for {section} repeats the column label(s) {labels}"
_BELOW_PAGE = (
    "segment Sales for {section} fall below the page Sales row in the newest comparable "
    "period: {details}. The segments API selects basis by the query VALUE "
    "'consolidated=true', so a standalone body answering a consolidated request looks "
    "exactly like this; check {url}"
)
_PERIOD_DETAIL = "{period} segments sum to {total} against page value {page} (tolerance {tol})"
_RECONCILED = "segment Sales sum to the page row across {count} period(s), within rounding"
_EXCEEDS = (
    "segment Sales exceed the page row in {count} period(s) (largest {largest}); consistent "
    "with inter-segment revenue this table does not disclose, and not proof of either figure"
)
_BELOW = (
    "segment Sales fall short of the page row in {count} historical period(s) (largest "
    "{largest}); consistent with an unreported segment or an elimination the page does not "
    "deduct, and not proof of either figure"
)
_MIXED = (
    "segment Sales vary in both directions: {above} period(s) above the page row (largest "
    "{above_largest}) and {below} period(s) below it (largest {below_largest}). Reporting "
    "only the overshoot would hide the periods that are missing a segment, which are the "
    "ones worth looking at"
)
_NOT_COMPARABLE = (
    "segment Sales for {section} could not be compared against the page at all: {reason}. "
    "The page rendered a Product Segments button for this section, so a fragment with "
    "nothing to compare is drift rather than an exemption — and the comparison is the only "
    "thing standing between a standalone body and a consolidated artifact; check {url}"
)
_NO_SALES_LINE = "the fragment carries no {line!r} line"
_NO_OVERLAP = "no period carried both a segment Sales figure and a readable page Sales value"
_NO_PAGE_SECTION = "the page carries no readable {section!r} section to compare against"
_QUARANTINED_SALES = (
    "the Sales line has {count} row(s) that could not be aligned to the header ({labels}), "
    "so its total is missing whatever they hold"
)


def read_segments(
    raw_body: bytes,
    *,
    hook: SegmentHook,
    page_section: SectionTable | None,
    url: str,
    document_id: str,
    body_sha256: str,
    source_id: str,
    retrieved_at: Any,
    parse: Any,
) -> SegmentTable:
    """Parse one segments fragment and hold its Sales line to the page section.

    ``parse`` is the shared HTML parser
    (:func:`~fundamentals.ingest.screener_session_page.parse_document`), injected
    so this module stays free of a parser import and testable on a bare string.
    """
    root = parse(raw_body.decode("utf-8", errors="replace"))
    tables = root.xpath(_DATA_TABLE_XPATH)
    if len(tables) != 1:
        raise AmbiguousStructureError(_NO_TABLE.format(section=hook.section, count=len(tables)))
    periods = _read_periods(tables[0], section=hook.section)
    if not periods:
        raise EmptyShellError(_EMPTY_SHELL.format(section=hook.section, url=url))
    _assert_window(periods, page_section=page_section, section=hook.section)

    lines = _read_lines(
        tables[0],
        periods=periods,
        section=hook.section,
        source_id=source_id,
        file_sha256=body_sha256,
        retrieved_at=retrieved_at,
    )
    reject_duplicate_anchors(
        tuple(cell.provenance for line in lines for row in line.rows for cell in row.cells),
        context=f"screener segments {hook.section}",
    )
    _refuse_incomparable(lines, page_section=page_section, section=hook.section, url=url)
    comparisons = _compare(lines, periods=periods, page_row=_page_sales_row(page_section))
    if not comparisons:
        raise SegmentReconciliationError(
            _NOT_COMPARABLE.format(section=hook.section, reason=_NO_OVERLAP, url=url)
        )
    _refuse_newest_shortfall(comparisons, section=hook.section, url=url)
    outcome, note = _classify(comparisons)
    return SegmentTable(
        section=hook.section,
        segment_type=hook.segment_type,
        url=url,
        document_id=document_id,
        body_sha256=body_sha256,
        identity_strength=IdentityStrength.CONFIGURED_URL_ONLY,
        outcome=outcome,
        binding=Binding.CONFIGURED_URL_ONLY,
        validation=Validation.LOWER_BOUND_NEWEST,
        validation_status=ValidationStatus.PASSED,
        note=note,
        periods=periods,
        lines=lines,
        comparisons=comparisons,
    )


def _read_periods(table: Any, *, section: str) -> tuple[Period, ...]:
    """Read the fragment's header columns, which carry labels and no dates."""
    headers = table.xpath(".//thead//th")
    periods = tuple(
        Period(index=index, label=normalize_text(header.text_content()), kind=PeriodKind.UNTYPED)
        for index, header in enumerate(headers[1:])
    )
    seen: dict[str, int] = {}
    for period in periods:
        seen[period.label] = seen.get(period.label, 0) + 1
    repeated = sorted(label for label, count in seen.items() if count > 1)
    if repeated:
        raise AmbiguousStructureError(
            _DUPLICATE_PERIODS.format(section=section, labels=", ".join(repeated))
        )
    return periods


def _assert_window(
    periods: tuple[Period, ...], *, page_section: SectionTable | None, section: str
) -> None:
    """Require the fragment's columns to be a contiguous run of the page's own.

    A *window*, not a prefix and not a suffix: which end is trimmed depends on
    the section. The quarters table shows one more quarter than the fragment, so
    the fragment is the last twelve of thirteen; the P&L table's final column is
    ``TTM``, which the fragment does not carry, so there the fragment is the
    first twelve of thirteen. ETERNAL's P&L fragment is six columns inside the
    page's ten. Requiring either end alone would refuse half the live captures.
    """
    if page_section is None:
        return
    page_labels = [period.label for period in page_section.periods]
    fragment_labels = [period.label for period in periods]
    span = len(fragment_labels)
    if any(
        page_labels[start : start + span] == fragment_labels
        for start in range(len(page_labels) - span + 1)
    ):
        return
    raise PeriodAlignmentError(
        _NOT_A_WINDOW.format(
            fragment=", ".join(fragment_labels),
            section=section,
            page=", ".join(page_labels),
        )
    )


def _read_lines(
    table: Any,
    *,
    periods: tuple[Period, ...],
    section: str,
    source_id: str,
    file_sha256: str,
    retrieved_at: Any,
) -> tuple[SegmentLine, ...]:
    """Read every ``tbody[data-segment-line]`` block, title row and all.

    Each block opens with a title row and closes with a spacer, both of which
    Screener marks by a ``td[colspan]`` rather than by position — the toggle
    buttons live in the title row's spanning cell. Structural rows are therefore
    identified by that attribute: the first is the block's title, any later one
    is the spacer. A body row whose cell count does not match the header is
    quarantined rather than dropped (ETERNAL renders label-only rows for lines
    it has no figures for).
    """
    lines: list[SegmentLine] = []
    for position, body in enumerate(table.xpath(".//tbody")):
        line = body.get(SEGMENT_LINE_ATTRIBUTE)
        if line is None:
            continue
        table_id = f"segments:{section}:{line}"
        title = ""
        rows: list[SegmentRow] = []
        quarantined: list[QuarantinedRow] = []
        for row_position, row in enumerate(body.xpath("./tr")):
            cells = row.xpath("./td")
            if not cells:
                continue
            label = normalize_text(cells[0].text_content())
            if row.xpath(_COLSPAN_CELL_XPATH):
                if not title:
                    title = label
                continue
            values = cells[1:]
            if len(values) != len(periods):
                quarantined.append(
                    QuarantinedRow(
                        position=row_position,
                        label=label,
                        reason=(f"row has {len(values)} cells for {len(periods)} header periods"),
                        raw_cells=tuple(normalize_text(value.text_content()) for value in values),
                    )
                )
                continue
            rows.append(
                SegmentRow(
                    position=row_position,
                    label=label,
                    cells=tuple(
                        _cell(
                            value,
                            period=period,
                            table_id=table_id,
                            path=row_path(row_position, label),
                            source_id=source_id,
                            file_sha256=file_sha256,
                            retrieved_at=retrieved_at,
                        )
                        for period, value in zip(periods, values, strict=True)
                    ),
                )
            )
        lines.append(
            SegmentLine(
                position=position,
                line=line,
                title=title,
                table_id=table_id,
                rows=tuple(rows),
                quarantined=tuple(quarantined),
            )
        )
    return tuple(lines)


def _cell(
    value: Any,
    *,
    period: Period,
    table_id: str,
    path: str,
    source_id: str,
    file_sha256: str,
    retrieved_at: Any,
) -> Cell:
    """Read one displayed segment figure, keeping its lexeme beside the number.

    A growth cell with nothing to compare against renders as a bare ``"%"``,
    which reads as no number and is published — a real rendering, distinct from
    the empty string Screener uses for a period a segment did not report.
    """
    raw_text = normalize_text(value.text_content())
    return Cell(
        period_index=period.index,
        value=read_number(raw_text)[0],
        raw_text=raw_text,
        published=bool(raw_text),
        provenance=html_anchor(
            source_id=source_id,
            file_sha256=file_sha256,
            retrieved_at=retrieved_at,
            table_id=table_id,
            row_path=path,
            column_index=period.index,
            column_label=period.label,
        ),
    )


def _refuse_incomparable(
    lines: tuple[SegmentLine, ...],
    *,
    page_section: SectionTable | None,
    section: str,
    url: str,
) -> None:
    """Refuse a fragment that offers nothing the page's Sales row can be held to.

    Three ways in, and each used to be an exemption: no Sales line at all, a
    Sales line whose rows could not be aligned to the header, and a page section
    that would not parse. Every one of them would have let a wrong-basis body
    reach the artifact untested, because this comparison is the only check a
    segments fragment ever gets.
    """
    sales = next((line for line in lines if line.line == SEGMENT_SALES_LINE), None)
    if sales is None:
        reason = _NO_SALES_LINE.format(line=SEGMENT_SALES_LINE)
    elif sales.quarantined:
        reason = _QUARANTINED_SALES.format(
            count=len(sales.quarantined),
            labels=", ".join(row.label for row in sales.quarantined),
        )
    elif page_section is None:
        reason = _NO_PAGE_SECTION.format(section=section)
    elif _page_sales_row(page_section) is None:
        reason = f"the page {section!r} section carries no {PAGE_SALES_ROW!r} row"
    else:
        return
    raise SegmentReconciliationError(
        _NOT_COMPARABLE.format(section=section, reason=reason, url=url)
    )


def _page_sales_row(page_section: SectionTable | None) -> TableRow | None:
    """The page section's Sales row, matched by label exactly once."""
    if page_section is None:
        return None
    matched = [row for row in page_section.rows if row.label == PAGE_SALES_ROW]
    if len(matched) > 1:
        raise AmbiguousStructureError(
            f"screener {page_section.section.value} section has {len(matched)} rows labelled "
            f"{PAGE_SALES_ROW!r}; a comparison would use whichever was read first"
        )
    return matched[0] if matched else None


def _compare(
    lines: tuple[SegmentLine, ...],
    *,
    periods: tuple[Period, ...],
    page_row: TableRow | None,
) -> tuple[PeriodComparison, ...]:
    """Total the Sales line per period against the page's Sales row.

    Periods where no segment published a figure are skipped rather than summed
    to zero: ETERNAL's P&L fragment carries a Mar 2021 column with every segment
    blank against a page value of 1,994, and calling that a shortfall would
    manufacture a failure out of an absence.
    """
    sales = next((line for line in lines if line.line == SEGMENT_SALES_LINE), None)
    if sales is None or page_row is None:
        return ()
    page_values = {
        cell.period_index: cell.value for cell in page_row.cells if cell.value is not None
    }
    by_label = {period.index: period.label for period in periods}
    comparisons: list[PeriodComparison] = []
    for period in periods:
        addends = [
            cell.value
            for row in sales.rows
            for cell in row.cells
            if cell.period_index == period.index and cell.value is not None
        ]
        page_value = _aligned_page_value(
            page_values, page_row=page_row, label=by_label[period.index]
        )
        if not addends or page_value is None:
            continue
        total = sum(addends, Decimal(0))
        tolerance = crore_tolerance(len(addends))
        comparisons.append(
            PeriodComparison(
                period_label=by_label[period.index],
                disclosed_total=total,
                page_value=page_value,
                difference=total - page_value,
                tolerance=tolerance,
                within_tolerance=abs(total - page_value) <= tolerance,
            )
        )
    return tuple(comparisons)


def _aligned_page_value(
    page_values: dict[int, Decimal], *, page_row: TableRow, label: str
) -> Decimal | None:
    """The page Sales value for one *label*, since the two indices differ.

    The fragment's column 0 is not the page's column 0 — the window alignment
    already established that the fragment's labels sit somewhere inside the
    page's. Comparing by index would silently offset every figure by one
    quarter, which is exactly the kind of near-miss this gate is meant to catch.
    """
    for cell in page_row.cells:
        if cell.provenance.column_label == label:
            return page_values.get(cell.period_index)
    return None


def _refuse_newest_shortfall(
    comparisons: tuple[PeriodComparison, ...], *, section: str, url: str
) -> None:
    """Refuse a fragment whose newest comparable period undershoots the page.

    Only the newest, and only downward. Segment revenue *above* reported revenue
    is what an undisclosed elimination looks like and is common in correct data;
    revenue below it in an old period is what an unreported segment looks like
    and is also common. Below it in the newest period is neither: no live
    capture does it, and the wrong-basis body does it every time.
    """
    if not comparisons:
        return
    newest = comparisons[-1]
    if newest.difference >= -newest.tolerance:
        return
    raise SegmentReconciliationError(
        _BELOW_PAGE.format(
            section=section,
            details=_PERIOD_DETAIL.format(
                period=newest.period_label,
                total=newest.disclosed_total,
                page=newest.page_value,
                tol=newest.tolerance,
            ),
            url=url,
        )
    )


def _classify(comparisons: tuple[PeriodComparison, ...]) -> tuple[SegmentOutcome, str]:
    """Say what the Sales comparison actually showed, in both directions.

    A table can be above the page row in some periods and below it in others —
    TITAN's and HFCL's yearly tables both are. Letting the overshoot win hid the
    shortfall periods entirely, and a period that is short is the one that might
    mean a segment stopped being reported.
    """
    above = [
        comparison for comparison in comparisons if comparison.difference > comparison.tolerance
    ]
    below = [
        comparison for comparison in comparisons if comparison.difference < -comparison.tolerance
    ]
    if not above and not below:
        return SegmentOutcome.RECONCILED, _RECONCILED.format(count=len(comparisons))
    largest_above = max(above, key=lambda comparison: comparison.difference, default=None)
    largest_below = min(below, key=lambda comparison: comparison.difference, default=None)
    if above and below:
        assert largest_above is not None and largest_below is not None  # noqa: S101
        return SegmentOutcome.MIXED_VARIANCE, _MIXED.format(
            above=len(above),
            above_largest=f"{largest_above.period_label} +{largest_above.difference}",
            below=len(below),
            below_largest=f"{largest_below.period_label} {largest_below.difference}",
        )
    if above:
        assert largest_above is not None  # noqa: S101
        return SegmentOutcome.EXCEEDS_PAGE, _EXCEEDS.format(
            count=len(above),
            largest=f"{largest_above.period_label} +{largest_above.difference}",
        )
    assert largest_below is not None  # noqa: S101
    return SegmentOutcome.BELOW_PAGE, _BELOW.format(
        count=len(below), largest=f"{largest_below.period_label} {largest_below.difference}"
    )
