"""Reading the Shareholding Pattern and the investor drill-downs that expand it.

Pure and deterministic: HTML or a JSON body in, typed artifacts out, or a typed
refusal. Nothing here fetches.

The two halves are one module because neither is trustworthy alone. The page's
Shareholding Pattern tables sit on a response Slice 0 proved — right session,
right company, right basis — and state each bucket's total. A drill-down
response is a bare ``{holder: {period: "pct"}}`` map that names no company, no
basis and no bucket; its URL is its only binding. Holding one to the other is
the entire assertion available here, and it comes in two strengths:

* **Promoters are disclosed in full.** Their holdings sum to the page's bucket
  row — TITAN 52.90 = 52.90 across 410 holders, HFCL and NETWEB within two
  hundredths of a point — so this family is held to equality within rounding and
  earns :attr:`~fundamentals.ingest.screener_company_models.EvidenceClass.SUM_PROVEN`.
* **Every other bucket lists only holders at or above 1 %.** Their sums sit far
  below the page row (TITAN DIIs 8.07 against 15.15; ETERNAL FIIs 2.87 against
  29.09) and occasionally equal it exactly when one holder *is* the bucket
  (ETERNAL others, 4.61). Equality is therefore unprovable and only the upper
  bound is checkable, so passing yields ``BOUNDED`` and never ``SUM_PROVEN``.
  The observed floor of 1.00 per disclosed holding is deliberately *not*
  enforced: it is a disclosure threshold Screener applies, not a rule about this
  company, and enforcing it would fail a legitimate response the day SEBI
  changes it.

An empty ``{}`` body is legitimate here, unlike in Slice 1's schedules: TITAN's
government bucket holds 0.19 % and no single holder crosses the threshold, so
the response is genuinely empty and still satisfies its upper bound.
"""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

from fundamentals.contracts.provenance import Provenance, SourceAnchorType
from fundamentals.ingest.screener_company_artifacts import (
    BucketRow,
    InvestorBucket,
    InvestorHolding,
    PeriodComparison,
    ShareholdingTable,
)
from fundamentals.ingest.screener_company_discovery import (
    SHAREHOLDING_SECTION_ID,
    shareholding_table,
)
from fundamentals.ingest.screener_company_models import (
    FULL_DISCLOSURE_BUCKETS,
    PERSON_URL_ATTRIBUTE,
    RESERVED_HOLDER_KEYS,
    SET_ATTRIBUTES_KEY,
    Binding,
    BucketDisclosure,
    BucketOutcome,
    DocumentUnreadableError,
    HoldingReconciliationError,
    InvestorHook,
    Periodicity,
    SumStrategy,
    Validation,
    ValidationStatus,
    percent_tolerance,
)
from fundamentals.ingest.screener_financials_models import (
    AmbiguousStructureError,
    Cell,
    IdentityStrength,
    Period,
    PeriodKind,
    QuarantinedRow,
    Unit,
)
from fundamentals.ingest.screener_financials_tables import (
    html_anchor,
    normalize_text,
    read_number,
    reject_duplicate_anchors,
    row_path,
)

SHAREHOLDER_COUNT_ROW = "No. of Shareholders"
SUB_ROW_CLASS = "sub"

_SUB_NOTE_XPATH = ".//*[contains(concat(' ', normalize-space(@class), ' '), ' sub ')]"
_SHOW_SHAREHOLDERS_XPATH = ".//button[contains(@onclick, 'showShareholders')]"
_EXPAND_MARKER = "+"

_CELL_COUNT_MISMATCH = "row has {cells} cells for {periods} header periods"
_DUPLICATE_PERIODS = (
    "screener {table} table repeats the column label(s) {labels}; the investors API "
    "addresses its values by period label, so a repeat would bind a holder to whichever "
    "column happens to be read last"
)
_DUPLICATE_HOLDER = (
    "investors body for {bucket} names holder {holder!r} more than once; JSON permits it "
    "and json.loads keeps only the last, so one holding would vanish while the sum still "
    "matched whichever copy survived — which is invisible to the very check meant to "
    "catch a missing holder"
)
_UNREADABLE_VALUE = (
    "holder {holder!r} of {bucket} publishes {raw!r} for {period}, which is not a "
    "percentage. Skipping it would quietly lower the total, which an upper bound reads as "
    "fine and an equality check reads as a shortfall of unknown size"
)
_NOT_AN_OBJECT = "investors body for {bucket} is not a JSON object"
_HOLDER_NOT_AN_OBJECT = "investors holder {holder!r} of {bucket} is not a JSON object"
_RESERVED_TYPE = (
    "reserved key {key!r} on holder {holder!r} of {bucket} carries a {seen}, not a dict; "
    "a reserved key is skipped rather than read, so a changed type would be silently "
    "discarded"
)
_RESERVED_COLLISION = (
    "the page's own column label(s) {labels} collide with a reserved investors key; "
    "reserved keys are skipped as metadata, so a real period would be read as none"
)
_NO_PAGE_ROW = (
    "no shareholding row expands bucket {bucket!r}, so this response was held to nothing. "
    "The investors API names no company, no basis and no bucket — the page row is the "
    "entire assertion available — so a drill-down with no row is a document admitted on "
    "its URL alone while every other bucket of the run was checked; refusing it is the "
    "only way that cannot happen quietly. Check {url}"
)
_SUM_MISMATCH = (
    "{bucket} holdings on the {periodicity} table do not sum to the page row they expand: "
    "{details}. Promoter holdings are disclosed in full, so a gap means the response is "
    "not this company's promoters on this basis; check {url}"
)
_BOUND_EXCEEDED = (
    "{bucket} disclosed holdings exceed the page row they are drawn from: {details}. A "
    "bucket lists a subset of its own holders, so a subset larger than the whole means "
    "the response does not belong to this bucket; check {url}"
)
_PERIOD_DETAIL = "{period} holders sum to {total} against page value {page} (tolerance {tol})"
_SUM_MATCHED = "holdings sum to the page row across {count} period(s), within rounding"
_WITHIN_BOUND = (
    "holdings stay within the page row across {count} period(s); only holders at or above "
    "1% are published, so this bounds the bucket rather than proving it"
)
_NOT_COMPARABLE = (
    "no period carried both a disclosed holding and a readable page value, so nothing was checked"
)
_UNALIGNED = (
    "{bucket} holdings carry period(s) the shareholding table does not: {labels}. The page "
    "header is the only thing binding these percentages to points in time, so a body "
    "carrying other columns is not a weaker version of this document — it is one that "
    "cannot be placed in time at all; check {url}"
)


def read_shareholding_table(
    root: Any,
    periodicity: Periodicity,
    *,
    source_id: str,
    file_sha256: str,
    retrieved_at: Any,
) -> ShareholdingTable | None:
    """Read one Shareholding Pattern table off the proven page, or ``None``.

    ``None`` means the page renders no such tab, which is a fact about the
    company rather than a failure — and is distinct from a tab that rendered
    with no rows.
    """
    table = shareholding_table(root, periodicity)
    if table is None:
        return None
    table_id = f"{SHAREHOLDING_SECTION_ID}:{periodicity.value}"
    periods = _read_periods(table, table_id=table_id)
    rows, quarantined = _read_rows(
        table,
        periods=periods,
        table_id=table_id,
        source_id=source_id,
        file_sha256=file_sha256,
        retrieved_at=retrieved_at,
    )
    reject_duplicate_anchors(
        tuple(cell.provenance for row in rows for cell in row.cells),
        context=f"screener {table_id}",
    )
    return ShareholdingTable(
        periodicity=periodicity,
        table_id=table_id,
        unit_statement=_unit_statement(root),
        periods=periods,
        rows=rows,
        quarantined=quarantined,
    )


def read_investor_bucket(
    raw_body: bytes,
    *,
    hook: InvestorHook,
    table: ShareholdingTable | None,
    url: str,
    document_id: str,
    body_sha256: str,
    source_id: str,
    retrieved_at: Any,
) -> InvestorBucket:
    """Parse one drill-down response and hold it to the page row it expands.

    Raises :class:`HoldingReconciliationError` when a fully-disclosed bucket
    does not sum to its page row, or when any bucket's disclosed subset exceeds
    the row it is drawn from.
    """
    label = f"{hook.bucket}/{hook.periodicity.value}"
    body = _decode(raw_body, bucket=label)
    periods = table.periods if table is not None else ()
    holders = _read_holders(
        body,
        bucket=label,
        periods=periods,
        document_id=document_id,
        table_key=f"investors:{hook.bucket}:{hook.periodicity.value}",
        source_id=source_id,
        file_sha256=body_sha256,
        retrieved_at=retrieved_at,
    )
    reject_duplicate_anchors(
        tuple(cell.provenance for holder in holders for cell in holder.cells),
        context=f"screener investors {label}",
    )
    unmatched = tuple(
        dict.fromkeys(period for holder in holders for period in holder.unmatched_periods)
    )
    disclosure = (
        BucketDisclosure.FULL
        if hook.bucket in FULL_DISCLOSURE_BUCKETS
        else BucketDisclosure.THRESHOLD
    )
    strategy = (
        SumStrategy.FLAT_SUM if disclosure is BucketDisclosure.FULL else SumStrategy.UPPER_BOUND
    )
    if unmatched:
        raise HoldingReconciliationError(
            _UNALIGNED.format(bucket=label, labels=", ".join(unmatched), url=url)
        )
    page_row = _page_row(table, hook.bucket)
    if page_row is None:
        raise HoldingReconciliationError(_NO_PAGE_ROW.format(bucket=hook.bucket, url=url))
    comparisons = _compare(holders, periods=periods, page_row=page_row)
    if not comparisons:
        raise HoldingReconciliationError(_NOT_COMPARABLE.format(bucket=hook.bucket, url=url))
    outcome, note = _classify(comparisons, strategy=strategy)
    _refuse_violations(
        comparisons, strategy=strategy, bucket=label, periodicity=hook.periodicity, url=url
    )
    return InvestorBucket(
        bucket=hook.bucket,
        periodicity=hook.periodicity,
        row_label=hook.row_label,
        url=url,
        document_id=document_id,
        body_sha256=body_sha256,
        identity_strength=IdentityStrength.CONFIGURED_URL_ONLY,
        disclosure=disclosure,
        strategy=strategy,
        outcome=outcome,
        binding=Binding.CONFIGURED_URL_ONLY,
        validation=(
            Validation.EQUALITY if strategy is SumStrategy.FLAT_SUM else Validation.UPPER_BOUND
        ),
        validation_status=ValidationStatus.PASSED,
        note=note,
        holders=holders,
        comparisons=comparisons,
        unmatched_periods=unmatched,
    )


def _unit_statement(root: Any) -> str | None:
    """The Shareholding section's own note ("Numbers in percentages"), verbatim."""
    for section in root.xpath(f"//*[@id={SHAREHOLDING_SECTION_ID!r}]"):
        for note in section.xpath(_SUB_NOTE_XPATH):
            text = normalize_text(note.text_content())
            if text:
                return text
    return None


def _read_periods(table: Any, *, table_id: str) -> tuple[Period, ...]:
    """Read the header columns, which carry a label and deliberately no date.

    Screener stamps no ``data-date-key`` on these headers, so every column is
    :attr:`~fundamentals.ingest.screener_financials_models.PeriodKind.UNTYPED`
    with a null ``period_end``. Parsing "Jun 2026" into a date would publish a
    period end the site never stated — and the quarterly and yearly tables use
    the same label shape for different things.
    """
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
            _DUPLICATE_PERIODS.format(table=table_id, labels=", ".join(repeated))
        )
    return periods


def _read_rows(
    table: Any,
    *,
    periods: tuple[Period, ...],
    table_id: str,
    source_id: str,
    file_sha256: str,
    retrieved_at: Any,
) -> tuple[tuple[BucketRow, ...], tuple[QuarantinedRow, ...]]:
    """Read every bucket row plus the shareholder-count row beneath them."""
    rows: list[BucketRow] = []
    quarantined: list[QuarantinedRow] = []
    for position, row in enumerate(table.xpath(".//tbody/tr")):
        cells = row.xpath("./td")
        if not cells:
            continue
        label = _row_label(cells[0])
        values = cells[1:]
        if len(values) != len(periods):
            quarantined.append(
                QuarantinedRow(
                    position=position,
                    label=label,
                    reason=_CELL_COUNT_MISMATCH.format(cells=len(values), periods=len(periods)),
                    raw_cells=tuple(normalize_text(value.text_content()) for value in values),
                )
            )
            continue
        bucket = _row_bucket(cells[0])
        parsed = tuple(
            Cell(
                period_index=period.index,
                value=read_number(normalize_text(value.text_content()))[0],
                raw_text=normalize_text(value.text_content()),
                published=bool(normalize_text(value.text_content())),
                provenance=html_anchor(
                    source_id=source_id,
                    file_sha256=file_sha256,
                    retrieved_at=retrieved_at,
                    table_id=table_id,
                    row_path=row_path(position, label),
                    column_index=period.index,
                    column_label=period.label,
                ),
            )
            for period, value in zip(periods, values, strict=True)
        )
        rows.append(
            BucketRow(
                position=position,
                label=label,
                bucket=bucket,
                unit=Unit.COUNT if bucket is None and _is_count_row(row) else Unit.PERCENT,
                cells=parsed,
            )
        )
    return tuple(rows), tuple(quarantined)


def _is_count_row(row: Any) -> bool:
    """True for the ``tr.sub`` row of shareholder counts under the buckets.

    Read from the row's own class rather than from its label so a renamed row
    is still recognised as counts rather than silently published as percentages
    under the section's "Numbers in percentages" note.
    """
    return SUB_ROW_CLASS in (row.get("class") or "").split()


def _row_label(cell: Any) -> str:
    """The row's label, with the drill-down button's trailing ``+`` removed."""
    text = normalize_text(cell.text_content())
    if text.endswith(_EXPAND_MARKER):
        text = text[: -len(_EXPAND_MARKER)].strip()
    return text


def _row_bucket(cell: Any) -> str | None:
    """The API bucket key this row's drill-down would request, if it has one."""
    for button in cell.xpath(_SHOW_SHAREHOLDERS_XPATH):
        onclick = button.get("onclick") or ""
        start = onclick.find("(")
        if start < 0:
            continue
        argument = onclick[start + 1 :].lstrip()
        if len(argument) < 2 or argument[0] not in "'\"":
            continue
        end = argument.find(argument[0], 1)
        if end > 0:
            return argument[1:end]
    return None


def _decode(raw_body: bytes, *, bucket: str) -> dict[str, Any]:
    """Decode the response, refusing a body that names one holder twice.

    ``json.loads`` resolves duplicate keys last-one-wins and says nothing, so a
    body carrying a holder twice loses a holding silently. The pairs hook is the
    only place that can see it, because by the time a dict exists the evidence
    is gone.
    """

    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        seen: set[str] = set()
        for key, _ in items:
            if key in seen:
                raise DocumentUnreadableError(_DUPLICATE_HOLDER.format(bucket=bucket, holder=key))
            seen.add(key)
        return dict(items)

    try:
        parsed = json.loads(raw_body.decode("utf-8", errors="replace"), object_pairs_hook=pairs)
    except json.JSONDecodeError as error:
        raise DocumentUnreadableError(
            f"investors body for {bucket} is not JSON: {error}"
        ) from error
    if not isinstance(parsed, dict):
        raise DocumentUnreadableError(_NOT_AN_OBJECT.format(bucket=bucket))
    return parsed


def _read_holders(
    body: dict[str, Any],
    *,
    bucket: str,
    periods: tuple[Period, ...],
    document_id: str,
    table_key: str,
    source_id: str,
    file_sha256: str,
    retrieved_at: Any,
) -> tuple[InvestorHolding, ...]:
    """Read every holder, aligning its periods to the page table's own labels."""
    by_label = {period.label: period for period in periods}
    collisions = sorted(RESERVED_HOLDER_KEYS & set(by_label))
    if collisions:
        raise AmbiguousStructureError(_RESERVED_COLLISION.format(labels=", ".join(collisions)))
    holders: list[InvestorHolding] = []
    for position, (holder, raw_values) in enumerate(body.items()):
        if not isinstance(raw_values, dict):
            raise DocumentUnreadableError(
                _HOLDER_NOT_AN_OBJECT.format(holder=holder, bucket=bucket)
            )
        attributes = raw_values.get(SET_ATTRIBUTES_KEY)
        if attributes is not None and not isinstance(attributes, dict):
            raise DocumentUnreadableError(
                _RESERVED_TYPE.format(
                    key=SET_ATTRIBUTES_KEY,
                    holder=holder,
                    bucket=bucket,
                    seen=type(attributes).__name__,
                )
            )
        cells: list[Cell] = []
        unmatched: list[str] = []
        for period_label, raw_value in raw_values.items():
            if period_label in RESERVED_HOLDER_KEYS:
                continue
            period = by_label.get(period_label)
            if period is None:
                # A period the shareholding table does not carry. Retained by
                # name: it is a real reading with no column to anchor it to, and
                # dropping it would hide a page/API divergence.
                unmatched.append(period_label)
                continue
            raw_text = normalize_text(raw_value) if isinstance(raw_value, str) else ""
            value = read_number(raw_text)[0]
            if value is None:
                raise DocumentUnreadableError(
                    _UNREADABLE_VALUE.format(
                        holder=holder, bucket=bucket, raw=raw_value, period=period_label
                    )
                )
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
                        row_label=holder,
                        column_label=period_label,
                        retrieved_at=retrieved_at,
                    ),
                )
            )
        holders.append(
            InvestorHolding(
                position=position,
                holder=holder,
                person_url=_person_url(attributes),
                cells=tuple(cells),
                unmatched_periods=tuple(unmatched),
            )
        )
    return tuple(holders)


def _person_url(attributes: Any) -> str | None:
    """The holder's own Screener page path, retained and never followed."""
    if not isinstance(attributes, dict):
        return None
    value = attributes.get(PERSON_URL_ATTRIBUTE)
    return value if isinstance(value, str) else None


def _page_row(table: ShareholdingTable | None, bucket: str) -> BucketRow | None:
    """The table row this bucket expands, matched by the button's own key.

    Exactly one row may claim a bucket. Taking the first of several would pick
    the comparison's reference by document order, which is the one thing this
    gate must not leave to chance.
    """
    if table is None:
        return None
    matched = [row for row in table.rows if row.bucket == bucket]
    if len(matched) > 1:
        raise AmbiguousStructureError(
            f"screener {table.table_id} has {len(matched)} rows whose drill-down requests "
            f"{bucket!r}; a comparison would use whichever was read first"
        )
    return matched[0] if matched else None


def _compare(
    holders: tuple[InvestorHolding, ...],
    *,
    periods: tuple[Period, ...],
    page_row: BucketRow | None,
) -> tuple[PeriodComparison, ...]:
    """Total the disclosed holdings per period against the page's bucket row."""
    if page_row is None:
        return ()
    page_values = {
        cell.period_index: cell.value for cell in page_row.cells if cell.value is not None
    }
    comparisons: list[PeriodComparison] = []
    for period in periods:
        addends = [
            cell.value
            for holder in holders
            for cell in holder.cells
            if cell.period_index == period.index and cell.value is not None
        ]
        page_value = page_values.get(period.index)
        if page_value is None:
            continue
        total = sum(addends, Decimal(0))
        tolerance = percent_tolerance(len(addends))
        comparisons.append(
            PeriodComparison(
                period_label=period.label,
                disclosed_total=total,
                page_value=page_value,
                difference=total - page_value,
                tolerance=tolerance,
                within_tolerance=abs(total - page_value) <= tolerance,
            )
        )
    return tuple(comparisons)


def _classify(
    comparisons: tuple[PeriodComparison, ...], *, strategy: SumStrategy
) -> tuple[BucketOutcome, str]:
    """Say which relation held, of the only two that can reach this point.

    Everything else is refused upstream: a violation raises, an unaligned body
    raises, and a bucket with nothing to compare against raises. So by the time
    a bucket is classified its relation has run and held, and the only question
    left is which relation it was.
    """
    if strategy is SumStrategy.FLAT_SUM:
        return BucketOutcome.SUM_MATCHED, _SUM_MATCHED.format(count=len(comparisons))
    return BucketOutcome.WITHIN_BOUND, _WITHIN_BOUND.format(count=len(comparisons))


def _refuse_violations(
    comparisons: tuple[PeriodComparison, ...],
    *,
    strategy: SumStrategy,
    bucket: str,
    periodicity: Periodicity,
    url: str,
) -> None:
    """Raise the typed refusal for whichever relation this bucket must satisfy.

    A fully-disclosed bucket must equal its page row within rounding in both
    directions. A threshold bucket may fall as far below as it likes — that is
    what a 1 % floor does — but may never exceed the row it is a subset of.
    """
    if strategy is SumStrategy.FLAT_SUM:
        failures = tuple(
            comparison for comparison in comparisons if not comparison.within_tolerance
        )
        template = _SUM_MISMATCH
    else:
        failures = tuple(
            comparison for comparison in comparisons if comparison.difference > comparison.tolerance
        )
        template = _BOUND_EXCEEDED
    if not failures:
        return
    details = "; ".join(
        _PERIOD_DETAIL.format(
            period=failure.period_label,
            total=failure.disclosed_total,
            page=failure.page_value,
            tol=failure.tolerance,
        )
        for failure in failures
    )
    raise HoldingReconciliationError(
        template.format(bucket=bucket, periodicity=periodicity.value, details=details, url=url)
    )
