"""Compare the watchlist page against its own CSV export, and record the comparison.

The page states no total, so the only completeness oracle Slice 4 has is the
agreement of two independent server renderings of one list. Rules SL4-01a
through SL4-01e live here: the export must publish the identity columns the join
needs, the two value-label sequences must be equal, membership must agree, the
join must be on the decoded display name rather than on position, and every
value cell must match. So do the rules that keep a published cell honest once
the join succeeds: no identifier repeats on either side (SL4-21), a non-empty
value that is not a finite number refuses rather than publishing as absent
(SL4-26), and each cell is anchored to the export record it was read from
(SL4-27). What comes back is one
:class:`~fundamentals.ingest.screener_watchlist_models.WatchlistCrossCheck`
audit record — written whether or not the comparison passed — beside the reason
it failed, or the columns and rows it is safe to publish.

Separate from :mod:`fundamentals.ingest.screener_watchlist` only so that neither
file exceeds this repo's per-file ceiling. The dependency runs one way: the
readers and ``acquire_watchlist`` import from here, and nothing here imports
back.
"""

from __future__ import annotations

from collections import Counter
from decimal import Decimal, InvalidOperation

from fundamentals.contracts.provenance import Provenance, SourceAnchorType
from fundamentals.ingest.screener_session_models import SOURCE_ID, ScreenerDocumentFetch
from fundamentals.ingest.screener_watchlist_models import (
    CSV_BSE_CODE,
    CSV_IDENTITY_LABELS,
    CSV_INDUSTRY,
    CSV_INDUSTRY_GROUP,
    CSV_ISIN_CODE,
    CSV_NAME,
    CSV_NSE_CODE,
    WATCHLIST_TABLE_ID,
    WatchlistCell,
    WatchlistColumn,
    WatchlistCompany,
    WatchlistCrossCheck,
    WatchlistRow,
    WatchlistTable,
    WatchlistTableRow,
    WatchlistValueMismatch,
)

_MISSING_CSV_IDENTITY = "watchlist export publishes no {name!r} or no {isin!r} column"
_COLUMNS_DISAGREE = "the page declares value columns {html} and the export publishes {csv}"
_MEMBERSHIP_DISAGREES = (
    "the page and the export list different members: only in page {only_html}, only in "
    "export {only_csv}, repeated in page {dup_html}, repeated in export {dup_csv}"
)
_ISIN_ABSENT = "the export publishes a member with no ISIN code"
_ISIN_REPEATED = "the export publishes the same ISIN code on more than one member"
_CODE_REPEATED = "the export publishes the same {label} on more than one member: {codes}"
_SLUG_REPEATED = "the page routes more than one row to the same company slug: {slugs}"
_NO_EXCHANGE_CODE = "the page routes {name!r} by slug {slug!r} and the export publishes no code"
_SLUG_DISAGREES = "the page routes {name!r} by slug {slug!r} but the export publishes {code!r}"
_VALUES_DISAGREE = "the page and the export disagree on {count} value cell(s)"
_UNPARSABLE_VALUE = (
    "the export publishes {text!r} for {name!r} under {label!r}, which is not a finite number; "
    "publishing it as an absent figure would be indistinguishable from a company that has none"
)
_CSV_ROW_PATH = "record[{position}]"


def cross_check(
    table: WatchlistTable,
    *,
    header: tuple[str, ...],
    records: tuple[tuple[str, ...], ...],
    page_fetch: ScreenerDocumentFetch,
    export_fetch: ScreenerDocumentFetch,
    content_type: str | None,
    content_disposition: str | None,
) -> tuple[WatchlistCrossCheck, str | None, tuple[WatchlistColumn, ...], tuple[WatchlistRow, ...]]:
    """Compare the two renderings and record exactly what was compared.

    Identity fields are located by label, never by counting past a prefix, and the
    value block is whatever the header carries beside them; the two label
    sequences must then be equal, because the page states that correspondence.
    """
    identity = {label: header.index(label) for label in CSV_IDENTITY_LABELS if label in header}
    value_indexes = tuple(
        index for index, label in enumerate(header) if label not in CSV_IDENTITY_LABELS
    )
    csv_value_labels = tuple(header[index] for index in value_indexes)
    html_names = tuple(row.display_name for row in table.rows)
    csv_names = (
        () if CSV_NAME not in identity else tuple(record[identity[CSV_NAME]] for record in records)
    )
    only_in_html = tuple(sorted(set(html_names) - set(csv_names)))
    only_in_csv = tuple(sorted(set(csv_names) - set(html_names)))
    duplicate_html = _duplicates(html_names)
    duplicate_csv = _duplicates(csv_names)

    columns: tuple[WatchlistColumn, ...] = ()
    rows: tuple[WatchlistRow, ...] = ()
    mismatches: tuple[WatchlistValueMismatch, ...] = ()
    compared = 0
    if CSV_NAME not in identity or CSV_ISIN_CODE not in identity:
        reason: str | None = _MISSING_CSV_IDENTITY.format(name=CSV_NAME, isin=CSV_ISIN_CODE)
    elif csv_value_labels != table.value_labels:
        reason = _COLUMNS_DISAGREE.format(html=table.value_labels, csv=csv_value_labels)
    elif only_in_html or only_in_csv or duplicate_html or duplicate_csv:
        reason = _MEMBERSHIP_DISAGREES.format(
            only_html=only_in_html,
            only_csv=only_in_csv,
            dup_html=duplicate_html,
            dup_csv=duplicate_csv,
        )
    else:
        columns = tuple(
            WatchlistColumn(
                csv_field_index=index,
                label=header[index],
                html_label=table.visible_labels[position],
            )
            for position, index in enumerate(value_indexes)
        )
        reason, rows, mismatches, compared = _join(
            table,
            header=header,
            records=records,
            identity=identity,
            value_indexes=value_indexes,
            export_fetch=export_fetch,
        )
    record = WatchlistCrossCheck(
        html_source_url=page_fetch.source_url,
        export_source_url=export_fetch.source_url,
        html_http_status=page_fetch.http_status,
        export_http_status=export_fetch.http_status,
        html_sha256=page_fetch.content_sha256,
        export_sha256=export_fetch.content_sha256,
        html_byte_count=page_fetch.byte_count,
        export_byte_count=export_fetch.byte_count,
        export_content_type=content_type,
        export_content_disposition=content_disposition,
        html_row_count=len(table.rows),
        csv_row_count=len(records),
        compared_cell_count=compared,
        html_value_labels=table.value_labels,
        csv_value_labels=csv_value_labels,
        only_in_html=only_in_html,
        only_in_csv=only_in_csv,
        duplicate_names_html=duplicate_html,
        duplicate_names_csv=duplicate_csv,
        value_mismatches=mismatches,
    )
    return record, reason, columns, rows


def _join(
    table: WatchlistTable,
    *,
    header: tuple[str, ...],
    records: tuple[tuple[str, ...], ...],
    identity: dict[str, int],
    value_indexes: tuple[int, ...],
    export_fetch: ScreenerDocumentFetch,
) -> tuple[str | None, tuple[WatchlistRow, ...], tuple[WatchlistValueMismatch, ...], int]:
    """Join the two renderings on the decoded display name and compare every cell.

    Never on position: the page is in watchlist order and the export is
    alphabetical, so a positional join hands each company another's codes. The
    same asymmetry is why each cell's anchor addresses the *export's* record
    position: the anchor names the export file, and a page position inside it
    would resolve to another company's figure on almost every row.
    """
    isins = [record[identity[CSV_ISIN_CODE]] for record in records]
    if not all(isins):
        return _ISIN_ABSENT, (), (), 0
    if len(set(isins)) != len(isins):
        return _ISIN_REPEATED, (), (), 0
    repeated = _repeated_identifiers(table, records=records, identity=identity)
    if repeated is not None:
        return repeated, (), (), 0
    by_name = {
        record[identity[CSV_NAME]]: (position, record)
        for position, record in enumerate(records, start=1)
    }
    rows: list[WatchlistRow] = []
    mismatches: list[WatchlistValueMismatch] = []
    compared = 0
    for row in table.rows:
        csv_position, record = by_name[row.display_name]
        bse_code = _identity_field(record, identity, CSV_BSE_CODE)
        nse_code = _identity_field(record, identity, CSV_NSE_CODE)
        unbound = _slug_disagreement(row, nse_code or bse_code)
        if unbound is not None:
            return unbound, (), (), compared
        cells: list[WatchlistCell] = []
        for position, index in enumerate(value_indexes):
            csv_text = record[index]
            html_text = row.values[position]
            compared += 1
            if csv_text != html_text:
                mismatches.append(
                    WatchlistValueMismatch(
                        display_name=row.display_name,
                        column_label=header[index],
                        html_text=html_text,
                        csv_text=csv_text,
                    )
                )
            value = _decimal(csv_text)
            if value is None and csv_text:
                return (
                    _UNPARSABLE_VALUE.format(
                        text=csv_text, name=row.display_name, label=header[index]
                    ),
                    (),
                    (),
                    compared,
                )
            cells.append(
                WatchlistCell(
                    csv_field_index=index,
                    value=value,
                    csv_text=csv_text,
                    html_text=html_text,
                    provenance=Provenance(
                        source_id=SOURCE_ID,
                        file_sha256=export_fetch.content_sha256,
                        anchor_type=SourceAnchorType.CSV_RECORD,
                        table_id=WATCHLIST_TABLE_ID,
                        row_path=_CSV_ROW_PATH.format(position=csv_position),
                        column_index=index,
                        column_label=header[index],
                        retrieved_at=export_fetch.fetched_at,
                    ),
                )
            )
        rows.append(
            WatchlistRow(
                serial_number=row.serial_number,
                company=WatchlistCompany(
                    data_row_company_id=row.data_row_company_id,
                    slug=row.slug,
                    display_name=row.display_name,
                    consolidated=row.consolidated,
                    bse_code=bse_code,
                    nse_code=nse_code,
                    isin_code=record[identity[CSV_ISIN_CODE]],
                    industry_group=_identity_field(record, identity, CSV_INDUSTRY_GROUP),
                    industry=_identity_field(record, identity, CSV_INDUSTRY),
                ),
                cells=tuple(cells),
            )
        )
    if mismatches:
        return _VALUES_DISAGREE.format(count=len(mismatches)), (), tuple(mismatches), compared
    return None, tuple(rows), (), compared


def _repeated_identifiers(
    table: WatchlistTable,
    *,
    records: tuple[tuple[str, ...], ...],
    identity: dict[str, int],
) -> str | None:
    """Refuse a published identifier either rendering carries on two members.

    The ISIN is checked separately because it is required; these three are
    optional, so only their published values are compared. Two rows sharing an
    exchange code, or two links routing to one company page, are one company
    admitted twice however well the names and values agree — and each of them
    passes the slug/code check independently, so nothing else sees it.
    """
    for label in (CSV_NSE_CODE, CSV_BSE_CODE):
        if label not in identity:
            continue
        codes = _duplicates(
            tuple(record[identity[label]] for record in records if record[identity[label]])
        )
        if codes:
            return _CODE_REPEATED.format(label=label, codes=codes)
    slugs = _duplicates(tuple(row.slug for row in table.rows if row.slug))
    if slugs:
        return _SLUG_REPEATED.format(slugs=slugs)
    return None


def _slug_disagreement(row: WatchlistTableRow, code: str | None) -> str | None:
    """Refuse a slug-routed row the export cannot bind by exchange code.

    The slug *is* the exchange code, which is the one identity check independent
    of the truncated display name. An id-routed row publishes no code on either
    side and is exempt rather than refused.
    """
    if row.slug is None:
        return None
    if code is None:
        return _NO_EXCHANGE_CODE.format(name=row.display_name, slug=row.slug)
    if row.slug != code:
        return _SLUG_DISAGREES.format(name=row.display_name, slug=row.slug, code=code)
    return None


def _identity_field(record: tuple[str, ...], identity: dict[str, int], label: str) -> str | None:
    """One optional identity field, with an unpublished value read as ``None``."""
    if label not in identity:
        return None
    return record[identity[label]] or None


def _decimal(text: str) -> Decimal | None:
    """Read one export value, distinguishing "no figure" from "not a figure".

    ``None`` means one of two things and the caller must tell them apart: an
    empty cell, which SL4-09 publishes as an absent figure, or text this reader
    cannot turn into a finite number — which the caller refuses, because both
    renderings can carry the same unrecognised lexeme (``1,234.50``, ``12.5%``)
    and agree perfectly while the published value is silently absent.
    """
    if not text:
        return None
    try:
        parsed = Decimal(text)
    except InvalidOperation:
        return None
    return parsed if parsed.is_finite() else None


def _duplicates(names: tuple[str, ...]) -> tuple[str, ...]:
    """Every name a rendering published more than once, in sorted order."""
    return tuple(sorted(name for name, count in Counter(names).items() if count > 1))
