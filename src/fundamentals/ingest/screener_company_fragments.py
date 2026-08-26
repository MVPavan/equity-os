"""Reading the four company-page fragments that are not held to a page row.

Pure and deterministic: an HTML fragment in, a typed artifact out, or a typed
refusal. Nothing here fetches.

Three of the four are ``URL_ONLY``, and that is the honest answer rather than a
gap to be closed later. The Related Party and Corporate actions modals carry no
navigation, no ``#company-info``, no company name and no basis marker — there is
literally nothing on them to assert against, so the request URL is their entire
binding to this company. The quick-ratios list is worse than unassertable: it is
the *signed-in owner's* Manage-quick_ratios selection, so which ratios appear is
a fact about the account and not about the issuer, which is why
:attr:`~fundamentals.ingest.screener_company_models.QuickRatioList.configured_by_account`
is recorded beside it.

The peers fragment is the exception and is checked hard. Every row carries
``data-row-company-id`` and links to a company page, so the response states
whose peer list it is *and* on which basis: exactly one row must be this
company, and its link must end in ``/consolidated/`` on a consolidated run and
must not on a standalone one. The self row is not the first row (TITAN and
ETERNAL are row 1; HFCL and NETWEB are row 3), so it is found by id and never by
position.

Structure verified 2026-08-26 against captured fragments for TITAN, NETWEB,
ETERNAL and HFCL on both bases (private captures, not committed).
"""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal
from typing import Any

from fundamentals.ingest.screener_company_artifacts import (
    CorporateAction,
    CorporateActionsTable,
    CorporateActionTab,
    PeerColumn,
    PeerRow,
    PeersTable,
    QuickRatio,
    QuickRatioList,
    RelatedParty,
    RelatedPartyLine,
    RelatedPartyTable,
)
from fundamentals.ingest.screener_company_models import (
    CRORE_SUFFIX,
    MONTH_ABBREVIATIONS,
    PERCENT_SUFFIX,
    RUPEE_SIGN,
    Binding,
    CorporateActionDateError,
    EmptyShellError,
    PeerIdentityError,
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
from fundamentals.ingest.screener_session_models import Basis

RELATED_PARTY_TABLE_ID = "related-party"
CORPORATE_ACTIONS_TAB_PREFIX = "corporate-actions-"
PEERS_TABLE_ID = "peers"
QUICK_RATIOS_TABLE_ID = "quick-ratios"

PARTY_HEADER_CLASS = "strong"
PARTY_TAG_XPATH = ".//small"
CONSOLIDATED_HREF_SUFFIX = "/consolidated/"
ROW_COMPANY_ID_ATTRIBUTE = "data-row-company-id"
TOOLTIP_ATTRIBUTE = "data-tooltip"
DATA_SOURCE_ATTRIBUTE = "data-source"
API_RATIO_SOURCE = "quick-ratio"

_DATA_TABLE_XPATH = "//table[contains(concat(' ', normalize-space(@class), ' '), ' data-table ')]"
_CALLOUT_XPATH = "//p[contains(concat(' ', normalize-space(@class), ' '), ' callout ')]"
_STRONG_XPATH = ".//*[contains(concat(' ', normalize-space(@class), ' '), ' font-weight-500 ')]"
_SUB_XPATH = ".//*[contains(concat(' ', normalize-space(@class), ' '), ' sub ')]"
_NAME_XPATH = ".//*[contains(concat(' ', normalize-space(@class), ' '), ' name ')]"
_VALUE_XPATH = ".//*[contains(concat(' ', normalize-space(@class), ' '), ' value ')]"
_NUMBER_XPATH = ".//*[contains(concat(' ', normalize-space(@class), ' '), ' number ')]"

_DAY_PATTERN = re.compile(r"^(?P<month>[A-Za-z]{3})\s+(?P<day>\d{1,2})$")
_YEAR_PATTERN = re.compile(r"^\d{4}$")
_RUPEE_AMOUNT = re.compile(rf"^{RUPEE_SIGN}\s*(?P<amount>[\d,]+(?:\.\d+)?)$")

_NO_TABLE = (
    "screener {kind} fragment holds {count} data tables; exactly one is required so the "
    "fragment's numbers cannot depend on document order"
)
_EMPTY_RELATED_PARTY = (
    "screener related-party fragment carries no parties, but the page renders a Related "
    "Party button. An empty table is what the consolidated URL of a standalone-only "
    "company returns, and the page never links it; check {url}"
)
_SELF_ROW_MISSING = (
    "screener peers fragment carries {count} rows for company id {company_id}; exactly one "
    "is required, because the requesting company's own row is what proves whose peer list "
    "this is (it is not always the first row); check {url}"
)
_SELF_ROW_BASIS = (
    "screener peers fragment names company {company_id} through {href!r}, which does not "
    "match the {basis} basis that was requested; the peers API is scoped by the "
    "basis-specific warehouse id, so a mismatch means the wrong id was called; check {url}"
)
_BAD_DATE = (
    "screener corporate action on tab {tab!r} carries the date {year!r} {day!r}, which is "
    "not a four-digit year and an abbreviated 'Mon DD'; guessing would publish a confident "
    "wrong date"
)
_DUPLICATE_TAB = "screener corporate-actions fragment carries {count} panes for tab {tab!r}"


def read_related_party(
    raw_body: bytes,
    *,
    url: str,
    document_id: str,
    body_sha256: str,
    source_id: str,
    retrieved_at: Any,
    parse: Any,
) -> RelatedPartyTable:
    """Parse the Related Party modal, keeping every row addressed by position.

    Line labels repeat across parties and within one party with case variants
    ("Inter-corporate deposit placed" beside "Inter-corporate Deposit placed"),
    so parties and lines are addressed as ``party[i]/line[j]`` and never keyed by
    text. A header-only table is refused: the page's own button is proof the
    company has related-party disclosures, so an empty one means the URL is not
    the one the page pointed at.
    """
    root = parse(raw_body.decode("utf-8", errors="replace"))
    table = _one_data_table(root, kind="related-party")
    periods = _fragment_periods(table)
    parties, anchors = _read_parties(
        table,
        periods=periods,
        source_id=source_id,
        file_sha256=body_sha256,
        retrieved_at=retrieved_at,
    )
    if not parties:
        raise EmptyShellError(_EMPTY_RELATED_PARTY.format(url=url))
    reject_duplicate_anchors(anchors, context="screener related-party")
    return RelatedPartyTable(
        url=url,
        document_id=document_id,
        body_sha256=body_sha256,
        source_note=_callout(root),
        periods=periods,
        parties=parties,
    )


def read_corporate_actions(
    raw_body: bytes,
    *,
    url: str,
    document_id: str,
    body_sha256: str,
    source_id: str,
    retrieved_at: Any,
    parse: Any,
) -> CorporateActionsTable:
    """Parse the Corporate actions modal, whatever tabs this company renders.

    The tab set varies (equityhistory, dividend, bonus, split, esops, prefissue)
    and is read from the fragment's own buttons, so an unfamiliar tab is
    retained under its own key rather than dropped. Dates are parsed through a
    closed month map: an unrecognised month raises rather than guesses.
    """
    root = parse(raw_body.decode("utf-8", errors="replace"))
    tabs: list[CorporateActionTab] = []
    seen: set[str] = set()
    for position, button in enumerate(root.xpath("//button[@data-tab-id]")):
        tab_id = button.get("data-tab-id") or ""
        if not tab_id.startswith(CORPORATE_ACTIONS_TAB_PREFIX):
            continue
        tab = tab_id[len(CORPORATE_ACTIONS_TAB_PREFIX) :]
        if tab in seen:
            raise AmbiguousStructureError(_DUPLICATE_TAB.format(count=2, tab=tab))
        seen.add(tab)
        panes = root.xpath(f"//*[@id={tab_id!r}]")
        if len(panes) > 1:
            raise AmbiguousStructureError(_DUPLICATE_TAB.format(count=len(panes), tab=tab))
        tabs.append(
            CorporateActionTab(
                position=position,
                tab=tab,
                label=normalize_text(button.text_content()),
                table_id=f"corporate-actions:{tab}",
                actions=(
                    ()
                    if not panes
                    else _read_actions(
                        panes[0],
                        tab=tab,
                        source_id=source_id,
                        file_sha256=body_sha256,
                        retrieved_at=retrieved_at,
                    )
                ),
            )
        )
    reject_duplicate_anchors(
        tuple(action.provenance for tab in tabs for action in tab.actions),
        context="screener corporate-actions",
    )
    return CorporateActionsTable(
        url=url, document_id=document_id, body_sha256=body_sha256, tabs=tuple(tabs)
    )


def read_peers(
    raw_body: bytes,
    *,
    company_id: int,
    basis: Basis,
    url: str,
    document_id: str,
    body_sha256: str,
    source_id: str,
    retrieved_at: Any,
    parse: Any,
) -> PeersTable:
    """Parse the peers fragment and assert it is this company's, on this basis.

    Raises :class:`PeerIdentityError` when the fragment names this company zero
    or several times, or when the self row's link contradicts the requested
    basis. Everything else on the fragment is other companies' numbers, which
    nothing here can check — hence
    :attr:`~fundamentals.ingest.screener_company_models.PeersTable.peer_values_evidence`.
    """
    root = parse(raw_body.decode("utf-8", errors="replace"))
    table = _one_data_table(root, kind="peers")
    columns, header_row = _peer_columns(table)
    rows, quarantined = _peer_rows(
        table,
        columns=columns,
        header_row=header_row,
        company_id=company_id,
        source_id=source_id,
        file_sha256=body_sha256,
        retrieved_at=retrieved_at,
    )
    self_rows = [row for row in rows if row.is_self]
    if len(self_rows) != 1:
        raise PeerIdentityError(
            _SELF_ROW_MISSING.format(count=len(self_rows), company_id=company_id, url=url)
        )
    self_row = self_rows[0]
    href = self_row.href or ""
    if href.endswith(CONSOLIDATED_HREF_SUFFIX) is not (basis is Basis.CONSOLIDATED):
        raise PeerIdentityError(
            _SELF_ROW_BASIS.format(company_id=company_id, href=href, basis=basis.value, url=url)
        )
    reject_duplicate_anchors(
        tuple(cell.provenance for row in rows for cell in row.cells), context="screener peers"
    )
    return PeersTable(
        url=url,
        document_id=document_id,
        body_sha256=body_sha256,
        self_row_position=self_row.position,
        columns=columns,
        rows=rows,
        median_label=_median_label(table),
        quarantined=quarantined,
    )


def read_quick_ratios(
    raw_body: bytes | None,
    *,
    element: Any,
    url: str | None,
    document_id: str,
    body_sha256: str,
    source_id: str,
    retrieved_at: Any,
    parse: Any,
    configured_by_account: bool,
    identity_strength: IdentityStrength,
    binding: Binding,
) -> QuickRatioList:
    """Read one header-ratio list, from the API fragment or from the page block.

    Both use identical markup and differ only in ``data-source`` and in who
    chose the rows, so one reader serves both; the caller supplies either
    ``raw_body`` (the API fragment) or an already-parsed page ``element``.
    """
    root = parse(raw_body.decode("utf-8", errors="replace")) if raw_body is not None else element
    ratios: list[QuickRatio] = []
    for position, item in enumerate(root.xpath(f".//li[@{DATA_SOURCE_ATTRIBUTE}]")):
        names = item.xpath(_NAME_XPATH)
        values = item.xpath(_VALUE_XPATH)
        if not names or not values:
            continue
        name = normalize_text(names[0].text_content())
        raw_text = normalize_text(values[0].text_content())
        numbers = [normalize_text(node.text_content()) for node in values[0].xpath(_NUMBER_XPATH)]
        ratios.append(
            QuickRatio(
                position=position,
                name=name,
                values=tuple(read_number(number)[0] for number in numbers),
                raw_text=raw_text,
                unit=_ratio_unit(raw_text),
                source=item.get(DATA_SOURCE_ATTRIBUTE) or "",
                provenances=tuple(
                    html_anchor(
                        source_id=source_id,
                        file_sha256=body_sha256,
                        retrieved_at=retrieved_at,
                        table_id=QUICK_RATIOS_TABLE_ID,
                        row_path=row_path(position, name),
                        column_index=index,
                        column_label=f"value[{index}]",
                    )
                    for index in range(len(numbers))
                ),
            )
        )
    reject_duplicate_anchors(
        tuple(anchor for ratio in ratios for anchor in ratio.provenances),
        context="screener quick-ratios",
    )
    return QuickRatioList(
        url=url,
        document_id=document_id,
        body_sha256=body_sha256,
        identity_strength=identity_strength,
        binding=binding,
        configured_by_account=configured_by_account,
        table_id=QUICK_RATIOS_TABLE_ID,
        ratios=tuple(ratios),
    )


def _ratio_unit(raw_text: str) -> Unit:
    """The unit one header ratio states, from its own decorations only.

    ``MIXED`` covers the one shape that carries two notations at once, which is
    what a "High / Low" pair looks like when only one side keeps the rupee sign.
    """
    rupees = raw_text.startswith(RUPEE_SIGN)
    crores = raw_text.endswith(CRORE_SUFFIX)
    percent = raw_text.endswith(PERCENT_SUFFIX)
    if percent and rupees:
        return Unit.MIXED
    if crores:
        return Unit.RS_CRORE
    if percent:
        return Unit.PERCENT
    if rupees:
        return Unit.RUPEES
    return Unit.RATIO


def _one_data_table(root: Any, *, kind: str) -> Any:
    """Return the fragment's single ``data-table``, refusing zero or several."""
    tables = root.xpath(_DATA_TABLE_XPATH)
    if len(tables) != 1:
        raise AmbiguousStructureError(_NO_TABLE.format(kind=kind, count=len(tables)))
    return tables[0]


def _callout(root: Any) -> str | None:
    """The fragment's own disclaimer callout, verbatim."""
    for callout in root.xpath(_CALLOUT_XPATH):
        text = normalize_text(callout.text_content())
        if text:
            return text
    return None


def _fragment_periods(table: Any) -> tuple[Period, ...]:
    """Read a fragment's year columns, which carry labels and no dates."""
    headers = table.xpath(".//thead//th")
    return tuple(
        Period(index=index, label=normalize_text(header.text_content()), kind=PeriodKind.UNTYPED)
        for index, header in enumerate(headers[1:])
    )


def _read_parties(
    table: Any,
    *,
    periods: tuple[Period, ...],
    source_id: str,
    file_sha256: str,
    retrieved_at: Any,
) -> tuple[tuple[RelatedParty, ...], tuple[Any, ...]]:
    """Split the flat row list into party blocks, keeping positions as addresses."""
    parties: list[RelatedParty] = []
    anchors: list[Any] = []
    name = tag = None
    lines: list[RelatedPartyLine] = []
    quarantined: list[QuarantinedRow] = []

    def flush() -> None:
        if name is None:
            return
        parties.append(
            RelatedParty(
                position=len(parties),
                name=name,
                tag=tag,
                lines=tuple(lines),
                quarantined=tuple(quarantined),
            )
        )

    for row in table.xpath(".//tbody/tr"):
        cells = row.xpath("./td")
        if not cells:
            continue
        if PARTY_HEADER_CLASS in (row.get("class") or "").split():
            flush()
            lines, quarantined = [], []
            tag = _party_tag(cells[0])
            name = _party_name(cells[0], tag)
            continue
        if name is None:
            continue
        label = normalize_text(cells[0].text_content())
        values = cells[1:]
        position = len(lines) + len(quarantined)
        if len(values) != len(periods):
            quarantined.append(
                QuarantinedRow(
                    position=position,
                    label=label,
                    reason=f"row has {len(values)} cells for {len(periods)} header periods",
                    raw_cells=tuple(normalize_text(value.text_content()) for value in values),
                )
            )
            continue
        path = f"party[{len(parties)}]/line[{position}]:{label}"
        cells_parsed: list[Cell] = []
        for period, value in zip(periods, values, strict=True):
            raw_text = normalize_text(value.text_content())
            anchor = html_anchor(
                source_id=source_id,
                file_sha256=file_sha256,
                retrieved_at=retrieved_at,
                table_id=RELATED_PARTY_TABLE_ID,
                row_path=path,
                column_index=period.index,
                column_label=period.label,
            )
            anchors.append(anchor)
            cells_parsed.append(
                Cell(
                    period_index=period.index,
                    value=read_number(raw_text)[0],
                    raw_text=raw_text,
                    published=bool(raw_text),
                    provenance=anchor,
                )
            )
        lines.append(RelatedPartyLine(position=position, label=label, cells=tuple(cells_parsed)))
    flush()
    return tuple(parties), tuple(anchors)


def _party_tag(cell: Any) -> str | None:
    """The party's relationship tag (Parent Co., Subsidiary, Key Person, …)."""
    for small in cell.xpath(PARTY_TAG_XPATH):
        text = normalize_text(small.text_content())
        if text:
            return text
    return None


def _party_name(cell: Any, tag: str | None) -> str:
    """The party's name with its relationship tag removed from the end.

    The tag renders inside the same cell, so the cell's text is "Sanjay Lodha
    Key Person"; keeping the tag in the name would make the name unmatchable
    against any other source.
    """
    text = normalize_text(cell.text_content())
    if tag is not None and text.endswith(tag):
        return text[: -len(tag)].strip()
    return text


def _read_actions(
    pane: Any, *, tab: str, source_id: str, file_sha256: str, retrieved_at: Any
) -> tuple[CorporateAction, ...]:
    """Read one tab's events, one ``<tbody>`` per event."""
    actions: list[CorporateAction] = []
    for position, body in enumerate(pane.xpath(".//tbody")):
        for row in body.xpath("./tr"):
            cells = row.xpath("./td")
            if len(cells) < 2:
                continue
            year_text = _first_text(cells[0], _STRONG_XPATH)
            day_text = _first_text(cells[0], _SUB_XPATH)
            title = _first_text(cells[1], _STRONG_XPATH)
            detail = _first_text(cells[1], _SUB_XPATH)
            actions.append(
                CorporateAction(
                    position=position,
                    event_date=_action_date(year_text, day_text, tab=tab),
                    year_text=year_text,
                    day_text=day_text,
                    title=title,
                    detail=detail,
                    amount=_rupee_amount(title),
                    provenance=html_anchor(
                        source_id=source_id,
                        file_sha256=file_sha256,
                        retrieved_at=retrieved_at,
                        table_id=f"corporate-actions:{tab}",
                        row_path=f"tbody[{position}]:{year_text} {day_text}",
                        column_index=0,
                        column_label="event",
                    ),
                )
            )
    return tuple(actions)


def _first_text(cell: Any, xpath: str) -> str:
    """The first matching child's text, or the empty string."""
    for node in cell.xpath(xpath):
        return normalize_text(node.text_content())
    return ""


def _action_date(year_text: str, day_text: str, *, tab: str) -> date:
    """Parse "2026" plus "Jul 09" into an ISO date, refusing anything else."""
    day_match = _DAY_PATTERN.match(day_text)
    month = MONTH_ABBREVIATIONS.get(day_match.group("month")) if day_match else None
    if not _YEAR_PATTERN.match(year_text) or day_match is None or month is None:
        raise CorporateActionDateError(_BAD_DATE.format(tab=tab, year=year_text, day=day_text))
    try:
        return date(int(year_text), month, int(day_match.group("day")))
    except ValueError as error:
        raise CorporateActionDateError(
            _BAD_DATE.format(tab=tab, year=year_text, day=day_text)
        ) from error


def _rupee_amount(title: str) -> Decimal | None:
    """The dividend amount, only when the title is a bare rupee figure.

    ``"₹ 15"`` reads as 15; ``"EQUITY SHARES @ ₹4790"`` and ``"New face value:
    1.00"`` do not, because a number pulled out of prose is a guess about what
    the number means.
    """
    match = _RUPEE_AMOUNT.match(title)
    return None if match is None else read_number(match.group("amount"))[0]


def _peer_columns(table: Any) -> tuple[tuple[PeerColumn, ...], Any]:
    """Read the header row, which Screener renders as ``<th>`` inside ``<tbody>``.

    Not in a ``<thead>``: the peers fragment puts its header row in the body, so
    a ``thead`` lookup finds nothing and every row would then be off by one.
    Column ids are the full field names from ``data-tooltip`` ("Return on
    capital employed"), which is what the screening query language uses; the
    rendered abbreviation ("ROCE %") is kept beside it.
    """
    for row in table.xpath(".//tbody/tr"):
        headers = row.xpath("./th")
        if not headers:
            continue
        return (
            tuple(
                PeerColumn(
                    index=index,
                    field=header.get(TOOLTIP_ATTRIBUTE) or normalize_text(header.text_content()),
                    label=normalize_text(header.text_content()),
                )
                for index, header in enumerate(headers)
            ),
            row,
        )
    return (), None


def _peer_rows(
    table: Any,
    *,
    columns: tuple[PeerColumn, ...],
    header_row: Any,
    company_id: int,
    source_id: str,
    file_sha256: str,
    retrieved_at: Any,
) -> tuple[tuple[PeerRow, ...], tuple[QuarantinedRow, ...]]:
    """Read every peer row, marking the one that names this company."""
    rows: list[PeerRow] = []
    quarantined: list[QuarantinedRow] = []
    for position, row in enumerate(table.xpath(".//tbody/tr")):
        if row is header_row:
            continue
        cells = row.xpath("./td")
        if not cells:
            continue
        raw_id = row.get(ROW_COMPANY_ID_ATTRIBUTE)
        row_company_id = int(raw_id) if raw_id is not None and raw_id.strip().isdigit() else None
        hrefs = row.xpath(".//a/@href")
        name = normalize_text(cells[1].text_content()) if len(cells) > 1 else ""
        if len(cells) != len(columns):
            quarantined.append(
                QuarantinedRow(
                    position=position,
                    label=name,
                    reason=f"row has {len(cells)} cells for {len(columns)} header columns",
                    raw_cells=tuple(normalize_text(cell.text_content()) for cell in cells),
                )
            )
            continue
        path = row_path(position, name)
        rows.append(
            PeerRow(
                position=position,
                company_id=row_company_id,
                name=name,
                href=hrefs[0] if hrefs else None,
                is_self=row_company_id == company_id,
                identity_strength=(
                    IdentityStrength.PAGE_ASSERTED
                    if row_company_id == company_id
                    else IdentityStrength.CONFIGURED_URL_ONLY
                ),
                cells=tuple(
                    Cell(
                        period_index=column.index,
                        value=read_number(normalize_text(cell.text_content()))[0],
                        raw_text=normalize_text(cell.text_content()),
                        published=bool(normalize_text(cell.text_content())),
                        provenance=html_anchor(
                            source_id=source_id,
                            file_sha256=file_sha256,
                            retrieved_at=retrieved_at,
                            table_id=PEERS_TABLE_ID,
                            row_path=path,
                            column_index=column.index,
                            column_label=column.field,
                        ),
                    )
                    for column, cell in zip(columns, cells, strict=True)
                ),
            )
        )
    return tuple(rows), tuple(quarantined)


def _median_label(table: Any) -> str | None:
    """The footer's "Median: N Co." label, which states the peer-set size."""
    for cell in table.xpath(".//tfoot//td"):
        text = normalize_text(cell.text_content())
        if text:
            return text
    return None
