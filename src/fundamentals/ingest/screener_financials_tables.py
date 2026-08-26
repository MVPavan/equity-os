"""Reading the Screener company page's financial tables.

Pure and deterministic: HTML in, typed sections out, or a typed refusal. Nothing
here fetches and nothing here follows a link.

The page is read position-led and drift-tolerantly, the way the Tijori families
are: whatever rows exist are parsed, known labels are modeled, unknown ones are
retained verbatim as ``UNMODELED``, known-but-unreadable ones are flagged
``INVALID``, and a row that cannot be aligned to the header at all is
quarantined with its lexemes instead of being dropped. Only two things are
refused outright — a requested section that is absent, and a section holding
more than one ``data-table`` — because both would make "the section's numbers"
depend on document order, and the page carries bare ``data-table`` elements
(the peer comparison) outside every section.

Numbers are read percent-aware, which is where this module deliberately parts
from :func:`fundamentals.ingest.tijori_common.decimal_from_text`: a Screener
``OPM %`` row is data we keep, so ``"23%"`` reads as ``Decimal("23")`` with
:attr:`~fundamentals.ingest.screener_financials_models.Unit.PERCENT`, rather
than as an unreadable lexeme. The lexeme survives beside the reading either way.
"""

from __future__ import annotations

import re
from collections import Counter
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from fundamentals.contracts.provenance import Provenance, SourceAnchorType
from fundamentals.ingest.screener_financials_models import (
    AMOUNT_SECTIONS,
    KNOWN_SECTION_ROWS,
    PERCENT_SUFFIX,
    TTM_DATE_KEY,
    AmbiguousStructureError,
    Cell,
    DuplicateAnchorError,
    GrowthRow,
    GrowthTable,
    Period,
    PeriodKind,
    QuarantinedRow,
    RowLink,
    RowStatus,
    Section,
    SectionOutcome,
    SectionTable,
    SectionUnreadableError,
    TableRow,
    Unit,
)

DATA_TABLE_ID_SUFFIX = "data-table"
RANGES_TABLE_ID_SUFFIX = "ranges-table"

_DATA_TABLE_XPATH = ".//table[contains(concat(' ', normalize-space(@class), ' '), ' data-table ')]"
_RANGES_TABLE_XPATH = (
    ".//table[contains(concat(' ', normalize-space(@class), ' '), ' ranges-table ')]"
)
_SUB_NOTE_XPATH = ".//*[contains(concat(' ', normalize-space(@class), ' '), ' sub ')]"
_SCHEDULE_BUTTON_PREDICATE = "button[contains(@onclick, 'showSchedule')]"
_SCHEDULE_BUTTON_XPATH = f".//{_SCHEDULE_BUTTON_PREDICATE}"
_ALL_SCHEDULE_BUTTONS_XPATH = f"//{_SCHEDULE_BUTTON_PREDICATE}"

# ``Company.showSchedule('<Parent>', '<section>', this)`` — the first argument is
# the exact ``parent=`` value the schedules API expects, which is why it is read
# from the call rather than reconstructed from the row's visible label.
_SHOW_SCHEDULE = re.compile(
    r"showSchedule\(\s*(['\"])(?P<parent>.*?)\1\s*,\s*(['\"])(?P<section>.*?)\3"
)
_PLAIN_DECIMAL = re.compile(r"^[+-]?\d+(\.\d+)?$")
_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_NBSP = "\xa0"
_THOUSANDS_SEPARATOR = ","
_EXPAND_MARKER = "+"
_UNIT_STATEMENT_MARKER = "Figures"
_RS_CRORE_MARKER = "Rs. Crores"
_RUPEES_LABEL_SUFFIX = " in Rs"
_DAYS_LABEL_SUFFIX = " Days"

_NO_SECTION = "screener page carries no {section!r} section"
_AMBIGUOUS_TABLE = (
    "screener {section!r} section holds {count} data tables; exactly one is required so "
    "the section's numbers cannot depend on document order"
)
_CELL_COUNT_MISMATCH = "row has {cells} cells for {periods} header periods"
_DUPLICATE_PERIODS = (
    "screener {section!r} table repeats the column label(s) {labels}; period labels are "
    "how a schedule response is matched to a column, so a repeat would silently bind "
    "sub-rows to whichever column happens to be read last"
)
_DUPLICATE_FAMILY = (
    "screener page offers {count} expanders for {family}; one of them would be requested "
    "and the other silently dropped, and nothing says the two describe the same row"
)


def normalize_text(raw: str) -> str:
    """Collapse the page's non-breaking spaces and runs of whitespace."""
    return " ".join(raw.replace(_NBSP, " ").split())


def read_number(raw: str) -> tuple[Decimal | None, bool]:
    """Read one display string as ``(value, is_percent)``.

    Thousands commas and a single trailing percent sign are the only decorations
    Screener uses; anything else reads as ``None`` and survives as its lexeme.
    """
    candidate = normalize_text(raw)
    is_percent = candidate.endswith(PERCENT_SUFFIX)
    if is_percent:
        candidate = candidate[: -len(PERCENT_SUFFIX)].strip()
    candidate = candidate.replace(_THOUSANDS_SEPARATOR, "")
    if not _PLAIN_DECIMAL.match(candidate):
        return None, is_percent
    try:
        parsed = Decimal(candidate)
    except InvalidOperation:
        return None, is_percent
    return (parsed if parsed.is_finite() else None), is_percent


def html_anchor(
    *,
    source_id: str,
    file_sha256: str,
    retrieved_at: Any,
    table_id: str,
    row_path: str,
    column_index: int,
    column_label: str,
) -> Provenance:
    """Build one HTML_TABLE anchor for a page cell."""
    return Provenance(
        source_id=source_id,
        file_sha256=file_sha256,
        anchor_type=SourceAnchorType.HTML_TABLE,
        table_id=table_id,
        row_path=row_path,
        column_index=column_index,
        column_label=column_label,
        retrieved_at=retrieved_at,
    )


def row_path(position: int, label: str) -> str:
    """Address a row by its position first and its label second.

    Position leads because a renamed row is still the same row; the label rides
    along so a re-ordered table is visible rather than silently re-anchored.
    """
    return f"tr[{position}]:{label}"


# The fields that actually address a value, per anchor kind. Comparing the
# whole model would never collide (the anchors differ in retrieved_at at best);
# comparing less than this would report distinct values as the same one.
_ANCHOR_ADDRESS_FIELDS: dict[SourceAnchorType, tuple[str, ...]] = {
    SourceAnchorType.HTML_TABLE: ("table_id", "row_path", "column_index"),
    SourceAnchorType.API_DOCUMENT: ("document_id", "row_label", "column_label"),
}


def reject_duplicate_anchors(provenances: tuple[Provenance, ...], *, context: str) -> None:
    """Fail loudly when two values in one artifact share a complete anchor.

    An anchor is a retrieval procedure. Two values addressed identically means
    one of them cannot be found again, and a consumer deduplicating on the
    anchor would silently drop it. Page cells and schedule cells are addressed
    by different fields, so each kind is compared on its own address.
    """
    addresses = Counter(
        (
            found.anchor_type,
            tuple(
                str(getattr(found, field))
                for field in _ANCHOR_ADDRESS_FIELDS.get(found.anchor_type, ())
            ),
        )
        for found in provenances
    )
    collisions = sorted(
        f"{anchor_type.value}:{'/'.join(address)}"
        for (anchor_type, address), count in addresses.items()
        if count > 1
    )
    if collisions:
        raise DuplicateAnchorError(
            f"{context} anchors two values identically: {', '.join(collisions)}"
        )


def read_section(
    root: Any,
    section: Section,
    *,
    source_id: str,
    file_sha256: str,
    retrieved_at: Any,
) -> SectionTable:
    """Read one ``data-table`` section, or refuse it as unreadable.

    ``GROWTH`` is not a page section: it is read by
    :func:`read_growth_section` from the ranges tables inside ``#profit-loss``.
    """
    element = _one_section(root, section)
    tables = element.xpath(_DATA_TABLE_XPATH)
    if len(tables) != 1:
        raise SectionUnreadableError(
            _AMBIGUOUS_TABLE.format(section=section.value, count=len(tables))
        )
    table_id = f"{section.value}:{DATA_TABLE_ID_SUFFIX}"
    unit_statement = _unit_statement(element)
    periods = _read_periods(tables[0], section=section)
    rows, quarantined = _read_rows(
        tables[0],
        section=section,
        periods=periods,
        unit_statement=unit_statement,
        table_id=table_id,
        source_id=source_id,
        file_sha256=file_sha256,
        retrieved_at=retrieved_at,
    )
    reject_duplicate_anchors(
        tuple(cell.provenance for row in rows for cell in row.cells),
        context=f"screener section {section.value}",
    )
    return SectionTable(
        section=section,
        table_id=table_id,
        outcome=(
            SectionOutcome.OK_EMPTY
            if not periods and not rows and not quarantined
            else SectionOutcome.OK
        ),
        unit_statement=unit_statement,
        periods=periods,
        rows=rows,
        quarantined=quarantined,
    )


def read_growth_section(
    root: Any, *, source_id: str, file_sha256: str, retrieved_at: Any
) -> SectionTable:
    """Read the four ``ranges-table`` growth blocks rendered inside ``#profit-loss``.

    They share the P&L section element but not its shape: each is a list of
    ``<window>: <pct>`` lines with no period columns at all, so folding them into
    the P&L table would mean inventing columns for them.
    """
    element = _one_section(root, Section.PROFIT_LOSS)
    tables: list[GrowthTable] = []
    anchors: list[Provenance] = []
    for position, table in enumerate(element.xpath(_RANGES_TABLE_XPATH)):
        table_id = f"{Section.PROFIT_LOSS.value}:{RANGES_TABLE_ID_SUFFIX}[{position}]"
        title = normalize_text(" ".join(table.xpath(".//th//text()")))
        rows: list[GrowthRow] = []
        for row_position, row in enumerate(table.xpath(".//tr")):
            cells = row.xpath("./td")
            if len(cells) != 2:
                continue
            window = normalize_text(cells[0].text_content()).rstrip(":").strip()
            raw_text = normalize_text(cells[1].text_content())
            value, is_percent = read_number(raw_text)
            anchor = html_anchor(
                source_id=source_id,
                file_sha256=file_sha256,
                retrieved_at=retrieved_at,
                table_id=table_id,
                row_path=row_path(row_position, window),
                column_index=0,
                column_label=title or RANGES_TABLE_ID_SUFFIX,
            )
            anchors.append(anchor)
            rows.append(
                GrowthRow(
                    position=row_position,
                    window=window,
                    value=value,
                    raw_text=raw_text,
                    unit=Unit.PERCENT if is_percent else Unit.UNKNOWN,
                    provenance=anchor,
                )
            )
        tables.append(GrowthTable(position=position, title=title, rows=tuple(rows)))
    reject_duplicate_anchors(tuple(anchors), context="screener section growth")
    return SectionTable(
        section=Section.GROWTH,
        table_id=f"{Section.PROFIT_LOSS.value}:{RANGES_TABLE_ID_SUFFIX}",
        outcome=SectionOutcome.OK_EMPTY if not tables else SectionOutcome.OK,
        unit_statement=_unit_statement(element),
        growth_tables=tuple(tables),
    )


def schedule_parents(root: Any) -> tuple[tuple[Section, str], ...]:
    """Every ``(section, parent)`` family the page itself offers to expand.

    Read from the ``showSchedule`` calls, which are the page's own statement of
    what the API will answer for. A family list held as a constant would go
    stale silently; this one cannot.
    """
    families: list[tuple[Section, str]] = []
    for button in root.xpath(_ALL_SCHEDULE_BUTTONS_XPATH):
        match = _SHOW_SCHEDULE.search(button.get("onclick") or "")
        if match is None:
            continue
        try:
            section = Section(match.group("section"))
        except ValueError:
            continue
        families.append((section, match.group("parent")))
    repeated = sorted(
        f"{section.value}/{parent}"
        for (section, parent), count in Counter(families).items()
        if count > 1
    )
    if repeated:
        raise AmbiguousStructureError(_DUPLICATE_FAMILY.format(count=2, family=", ".join(repeated)))
    return tuple(families)


def _one_section(root: Any, section: Section) -> Any:
    """Return the page's single element for one section id, or refuse."""
    elements = root.xpath(f"//*[@id={section.value!r}]")
    if len(elements) != 1:
        raise SectionUnreadableError(_NO_SECTION.format(section=section.value))
    return elements[0]


def _unit_statement(element: Any) -> str | None:
    """The section's own note ("Consolidated Figures in Rs. Crores"), verbatim."""
    for note in element.xpath(_SUB_NOTE_XPATH):
        text = normalize_text(note.text_content())
        if _UNIT_STATEMENT_MARKER in text:
            return text
    return None


def _read_periods(table: Any, *, section: Section) -> tuple[Period, ...]:
    """Read the header columns, keeping ``TTM`` typed rather than dated.

    Column labels must be unique. A schedule response addresses its values by
    period *label*, so two columns sharing one would let a sub-row reconcile
    against a column it was never meant to describe.
    """
    headers = table.xpath(".//thead//th")
    periods: list[Period] = []
    for index, header in enumerate(headers[1:]):
        date_key = header.get("data-date-key")
        label = normalize_text(header.text_content())
        periods.append(
            Period(
                index=index,
                label=label,
                kind=_period_kind(date_key),
                date_key=date_key,
                period_end=_period_end(date_key),
            )
        )
    repeated = sorted(
        label for label, count in Counter(period.label for period in periods).items() if count > 1
    )
    if repeated:
        raise AmbiguousStructureError(
            _DUPLICATE_PERIODS.format(section=section.value, labels=", ".join(repeated))
        )
    return tuple(periods)


def _period_kind(date_key: str | None) -> PeriodKind:
    """Classify one column by what its ``data-date-key`` actually says."""
    if date_key == TTM_DATE_KEY:
        return PeriodKind.TTM
    if date_key is not None and _ISO_DATE.match(date_key):
        return PeriodKind.DATE
    return PeriodKind.UNTYPED


def _period_end(date_key: str | None) -> date | None:
    """The column's period end, only when the page published a real date."""
    if date_key is None or not _ISO_DATE.match(date_key):
        return None
    try:
        return date.fromisoformat(date_key)
    except ValueError:
        return None


def _read_rows(
    table: Any,
    *,
    section: Section,
    periods: tuple[Period, ...],
    unit_statement: str | None,
    table_id: str,
    source_id: str,
    file_sha256: str,
    retrieved_at: Any,
) -> tuple[tuple[TableRow, ...], tuple[QuarantinedRow, ...]]:
    """Read every body row, aligning to the header or quarantining the row."""
    known = KNOWN_SECTION_ROWS.get(section, frozenset())
    rows: list[TableRow] = []
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
        parsed, links, any_percent, any_value, any_published = _read_cells(
            values,
            periods=periods,
            table_id=table_id,
            position=position,
            label=label,
            source_id=source_id,
            file_sha256=file_sha256,
            retrieved_at=retrieved_at,
        )
        rows.append(
            TableRow(
                position=position,
                label=label,
                status=_row_status(
                    label, known=known, any_value=any_value, any_published=any_published
                ),
                unit=_row_unit(
                    label,
                    section=section,
                    unit_statement=unit_statement,
                    any_percent=any_percent,
                    any_value=any_value,
                    has_links=bool(links),
                ),
                cells=parsed,
                links=links,
                schedule_parent=_schedule_parent(cells[0]),
            )
        )
    return tuple(rows), tuple(quarantined)


def _read_cells(
    values: list[Any],
    *,
    periods: tuple[Period, ...],
    table_id: str,
    position: int,
    label: str,
    source_id: str,
    file_sha256: str,
    retrieved_at: Any,
) -> tuple[tuple[Cell, ...], tuple[RowLink, ...], bool, bool, bool]:
    """Read one aligned row's cells and the outbound links it carries."""
    parsed: list[Cell] = []
    links: list[RowLink] = []
    any_percent = any_value = any_published = False
    path = row_path(position, label)
    for period, value in zip(periods, values, strict=True):
        raw_text = normalize_text(value.text_content())
        number, is_percent = read_number(raw_text)
        published = bool(raw_text)
        for href in value.xpath(".//a/@href"):
            links.append(RowLink(period_index=period.index, href=href))
            published = True
        any_percent = any_percent or (is_percent and number is not None)
        any_value = any_value or number is not None
        any_published = any_published or published
        parsed.append(
            Cell(
                period_index=period.index,
                value=number,
                raw_text=raw_text,
                published=published,
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
        )
    return tuple(parsed), tuple(links), any_percent, any_value, any_published


def _row_label(cell: Any) -> str:
    """The row's label, with the expander's trailing ``+`` removed."""
    text = normalize_text(cell.text_content())
    if text.endswith(_EXPAND_MARKER):
        text = text[: -len(_EXPAND_MARKER)].strip()
    return text


def _schedule_parent(cell: Any) -> str | None:
    """The exact ``parent=`` value this row's expander would request, if any."""
    for button in cell.xpath(_SCHEDULE_BUTTON_XPATH):
        match = _SHOW_SCHEDULE.search(button.get("onclick") or "")
        if match is not None:
            return match.group("parent")
    return None


def _row_status(
    label: str, *, known: frozenset[str], any_value: bool, any_published: bool
) -> RowStatus:
    """Classify how much of this row the contract understood.

    A known row that published cells but yielded no number is ``INVALID`` — the
    figure we expect is there and unreadable. A known row that published nothing
    is simply a company that did not report it, and stays ``MODELED``.
    """
    if label not in known:
        return RowStatus.UNMODELED
    if any_published and not any_value:
        return RowStatus.INVALID
    return RowStatus.MODELED


def _row_unit(
    label: str,
    *,
    section: Section,
    unit_statement: str | None,
    any_percent: bool,
    any_value: bool,
    has_links: bool,
) -> Unit:
    """Record the row's unit from what the page states, never from the row name alone.

    The section note is applied only where it describes the rows: ``#ratios``
    carries the same "Figures in Rs. Crores" note but holds day counts and
    ratios, so a row there that declares no unit of its own stays ``UNKNOWN``
    rather than being labelled crores.
    """
    if label.endswith(PERCENT_SUFFIX) or any_percent:
        return Unit.PERCENT
    if label.endswith(_DAYS_LABEL_SUFFIX):
        return Unit.DAYS
    if label.endswith(_RUPEES_LABEL_SUFFIX):
        return Unit.RUPEES
    if has_links and not any_value:
        return Unit.DOCUMENT_LINK
    if (
        section in AMOUNT_SECTIONS
        and unit_statement is not None
        and _RS_CRORE_MARKER in unit_statement
    ):
        return Unit.RS_CRORE
    return Unit.UNKNOWN
