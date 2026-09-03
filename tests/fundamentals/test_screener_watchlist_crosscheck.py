"""Slice 4 cross-render contract: what the page and the export must agree on.

Companion to :mod:`test_screener_watchlist`, which pins how each rendering is
read on its own. This file pins the comparison between them — membership,
column correspondence, identity and every value — and what a published row and
the audit record beside it carry. The page states no total, so this agreement
is the only oracle the slice has; it is re-proved on every run and recorded so
a consumer can audit it without reparsing bytes.

The transport seam, the builders and the acquisition helpers live in
:mod:`screener_watchlist_fixtures`.
"""

from __future__ import annotations

import hashlib
from decimal import Decimal
from typing import Any

import pytest
import screener_watchlist_fixtures as fx

from fundamentals.contracts.provenance import SourceAnchorType

_ROSTER = fx.members()
_TOOLTIPS = tuple(column.tooltip for column in fx.DEFAULT_COLUMNS)


def _incomplete(run: Any, refusal: str | None = None) -> Any:
    """Assert a run refused, optionally by the named typed error, and return its artifact."""
    artifact = run.artifact
    assert artifact.outcome is fx.models.WatchlistOutcome.INCOMPLETE
    assert artifact.failure is not None
    assert artifact.incomplete_reason
    if refusal is not None:
        assert artifact.failure.refusal == refusal
    return artifact


# --------------------------------------------------------------------------
# The cross-render check: membership, columns, identity, values
# --------------------------------------------------------------------------


@pytest.mark.parametrize("columns", [fx.DEFAULT_COLUMNS, fx.WIDE_COLUMNS])
def test_a_consistent_pair_publishes_results_for_whatever_columns_are_configured(
    monkeypatch: pytest.MonkeyPatch, columns: tuple[fx.Column, ...]
) -> None:
    """SL4-10 / A30: the column set is the user's configuration, never pinned.

    The same rules must hold for a narrower or wider configuration. A reader
    holding a registry of columns, or a count, publishes the wider result under
    the wrong labels or refuses it outright.
    """
    roster = fx.members(columns=columns)
    run, _ = fx.acquire_roster(monkeypatch, roster, columns=columns)

    assert run.artifact.outcome is fx.models.WatchlistOutcome.RESULTS
    assert tuple(column.label for column in run.artifact.columns) == tuple(
        column.tooltip for column in columns
    )
    assert len(run.artifact.rows) == len(roster)


def test_rows_are_joined_on_the_decoded_name_and_never_on_position(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SL4-02: the page is in watchlist order and the CSV is alphabetical.

    A positional join is silently wrong on every live pair: it would hand each
    company the exchange codes and industry of some other member. The fixture
    names run backwards so no two positions coincide.
    """
    run, _ = fx.acquire_roster(monkeypatch, _ROSTER)

    assert run.artifact.outcome is fx.models.WatchlistOutcome.RESULTS
    by_name = {member.name: member for member in _ROSTER}
    for row in run.artifact.rows:
        expected = by_name[row.company.display_name]
        assert row.company.isin_code == expected.isin_code
        assert row.company.data_row_company_id == expected.company_id


def test_a_published_company_is_the_union_of_both_renderings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SL4-07: neither artifact is a superset, so the row carries both identities.

    The HTML alone has the row id and slug; the CSV alone has the exchange
    codes, ISIN and industry. Publishing either side's identity without the
    other drops the fields the other slices join on.
    """
    run, _ = fx.acquire_roster(monkeypatch, _ROSTER)

    member = _ROSTER[0]
    company = next(row.company for row in run.artifact.rows if row.serial_number == 1)
    assert company.data_row_company_id == member.company_id
    assert company.slug == member.nse_code
    assert company.consolidated is True
    assert company.nse_code == member.nse_code
    assert company.bse_code == member.bse_code
    assert company.isin_code == member.isin_code
    assert company.industry_group == member.industry_group
    assert company.industry == member.industry


def test_a_member_on_only_one_side_refuses_and_is_named_in_the_record(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SL4-01a / A13: the name sets must be exactly equal, and the difference is the diagnosis.

    A cap, a truncation or a dropped row on either side breaks the equality;
    that is the whole safety argument of the slice. Recording which names were
    on which side is what lets an operator tell a membership churn from a
    parser fault without refetching.
    """
    run, _ = fx.acquire(
        monkeypatch,
        page=fx.watchlist_page(_ROSTER),
        export=fx.export_csv(_ROSTER, records=fx.csv_records(_ROSTER[1:])),
    )
    artifact = _incomplete(run, "WatchlistCrossCheckError")
    assert artifact.rows == ()
    assert artifact.cross_check is not None
    assert tuple(artifact.cross_check.only_in_html) == (_ROSTER[0].name,)
    assert tuple(artifact.cross_check.only_in_csv) == ()

    extra = fx.rebuilt(_ROSTER[0], name="Synth Member 999", isin_code="SYN000000999")
    run, _ = fx.acquire(
        monkeypatch,
        page=fx.watchlist_page(_ROSTER),
        export=fx.export_csv(_ROSTER, records=(*fx.csv_records(_ROSTER), fx.csv_record(extra))),
    )
    artifact = _incomplete(run, "WatchlistCrossCheckError")
    assert artifact.rows == ()
    assert tuple(artifact.cross_check.only_in_csv) == (extra.name,)
    assert tuple(artifact.cross_check.only_in_html) == ()


def test_a_duplicated_display_name_on_either_side_refuses_and_is_recorded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SL4-01a / A13: the name is the join key, so a repeat makes the join ambiguous.

    Two rows with one name would merge one company's Screener id onto the
    other's ISIN. The set equality alone cannot see it — a duplicate on both
    sides still compares equal as sets.
    """
    doubled = fx.with_member(_ROSTER, 2, name=_ROSTER[0].name)

    run, _ = fx.acquire(monkeypatch, page=fx.watchlist_page(doubled), export=fx.export_csv(_ROSTER))
    artifact = _incomplete(run, "WatchlistCrossCheckError")
    assert tuple(artifact.cross_check.duplicate_names_html) == (_ROSTER[0].name,)

    run, _ = fx.acquire(monkeypatch, page=fx.watchlist_page(_ROSTER), export=fx.export_csv(doubled))
    artifact = _incomplete(run, "WatchlistCrossCheckError")
    assert tuple(artifact.cross_check.duplicate_names_csv) == (_ROSTER[0].name,)


def test_an_entity_in_the_page_is_decoded_exactly_once_before_joining(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SL4-01a / A34: ``&#x27;`` must join to ``'``, and ``&amp;amp;`` must join to ``&amp;``.

    lxml already decodes entities when reading text. Decoding a second time
    turns a literal ``&amp;`` in a stored name into ``&`` and the join fails;
    not decoding at all leaves the apostrophe member unjoinable.
    """
    roster = fx.with_member(_ROSTER, 1, name="Synth &amp; Co 1")
    apostrophe = next(member for member in roster if "'" in member.name)

    run, _ = fx.acquire_roster(monkeypatch, roster)

    assert run.artifact.outcome is fx.models.WatchlistOutcome.RESULTS
    names = {row.company.display_name for row in run.artifact.rows}
    assert "Synth &amp; Co 1" in names
    assert apostrophe.name in names


def test_a_csv_with_more_value_fields_than_the_page_has_value_columns_refuses(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SL4-01b / A30: the value-column count, the value-field count and the tooltip count agree.

    No number is asserted; only the relation. A CSV one field wider than the
    page means the export is answering a different column configuration, and
    aligning the two by position publishes every later value under the wrong
    name.
    """
    wider = tuple((*record, "1.00", "2.00") for record in fx.csv_records(_ROSTER))

    run, _ = fx.acquire(
        monkeypatch,
        page=fx.watchlist_page(_ROSTER),
        export=fx.export_csv(_ROSTER, columns=fx.WIDE_COLUMNS, records=wider),
    )

    artifact = _incomplete(run, "WatchlistCrossCheckError")
    assert artifact.rows == ()


def test_the_csv_identity_fields_are_found_by_label_and_not_by_position(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A27: the six-field identity prefix is observed, not contractual.

    A future column edit that moves ``ISIN Code`` must not silently swap it
    with ``BSE Code``. Locating the identity fields by their labels, and the
    value block as the tail matching the tooltips, is what makes that safe.
    """
    identity = ("ISIN Code", "Name", "Industry", "BSE Code", "NSE Code", "Industry Group")

    run, _ = fx.acquire(
        monkeypatch,
        page=fx.watchlist_page(_ROSTER),
        export=fx.export_csv(_ROSTER, identity=identity),
    )

    assert run.artifact.outcome is fx.models.WatchlistOutcome.RESULTS
    member = _ROSTER[0]
    company = next(row.company for row in run.artifact.rows if row.serial_number == 1)
    assert (company.isin_code, company.bse_code, company.industry) == (
        member.isin_code,
        member.bse_code,
        member.industry,
    )


def test_an_export_that_publishes_no_nse_code_column_still_binds_and_publishes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A27 / SL4-01e: the identity columns are optional except ``Name`` and ``ISIN Code``.

    Only those two are required — the name to join on and the ISIN to key on.
    Everything else is whatever the export happens to publish, so a column set
    without ``NSE Code`` must bind each slug by the code that *is* published
    rather than refusing the list, and the uniqueness rules must skip the column
    that is not there instead of reading some other field under its label.
    """
    identity = ("Name", "BSE Code", "ISIN Code", "Industry Group", "Industry")
    roster = tuple(
        member
        if "/id/" in member.href
        else fx.rebuilt(member, href=f"/company/{member.bse_code}/consolidated/")
        for member in _ROSTER
    )

    run, _ = fx.acquire(
        monkeypatch,
        page=fx.watchlist_page(roster),
        export=fx.export_csv(roster, identity=identity),
    )

    assert run.artifact.outcome is fx.models.WatchlistOutcome.RESULTS
    assert {row.company.nse_code for row in run.artifact.rows} == {None}
    published = next(row.company for row in run.artifact.rows if row.serial_number == 1)
    assert published.slug == published.bse_code == _ROSTER[0].bse_code


def test_a_tooltip_sequence_disagreeing_with_the_csv_headers_by_one_refuses(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SL4-01d / A13: the stated column mapping is re-proved on every run.

    Both sides are driven by one column configuration today; that must be
    checked, not assumed. One renamed header is a column whose values would be
    published under a name the page never gave it. Both sequences are recorded
    so the disagreement is visible without reparsing bytes.
    """
    renamed = fx.renamed_columns(fx.DEFAULT_COLUMNS, 2, "Gamma renamed")

    run, _ = fx.acquire(
        monkeypatch,
        page=fx.watchlist_page(_ROSTER),
        export=fx.export_csv(_ROSTER, columns=renamed),
    )

    artifact = _incomplete(run, "WatchlistCrossCheckError")
    assert artifact.rows == ()
    assert tuple(artifact.cross_check.html_value_labels) == _TOOLTIPS
    assert tuple(artifact.cross_check.csv_value_labels) == tuple(
        column.tooltip for column in renamed
    )


def test_one_cell_differing_between_the_renderings_refuses_and_names_the_cell(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SL4-01c / A13 / A25: every value must agree, and the disagreement is diagnosable.

    A single differing cell is either a price tick between the two requests or
    a column shift; the two read nothing alike once the company, the column and
    both raw strings are recorded. Without that record the operator can only
    refetch, which spends the request budget to learn what was already known.
    """
    member = _ROSTER[1]
    changed = fx.with_member(_ROSTER, member.serial, values=("999.99", *member.values[1:]))

    run, _ = fx.acquire(monkeypatch, page=fx.watchlist_page(_ROSTER), export=fx.export_csv(changed))

    artifact = _incomplete(run, "WatchlistCrossCheckError")
    assert artifact.rows == ()
    mismatches = tuple(artifact.cross_check.value_mismatches)
    assert len(mismatches) == 1
    assert mismatches[0].display_name == member.name
    assert mismatches[0].column_label == fx.DEFAULT_COLUMNS[0].tooltip
    assert (mismatches[0].html_text, mismatches[0].csv_text) == (member.values[0], "999.99")


def test_a_thousands_separator_on_one_side_only_is_a_disagreement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SL4-01c / A3: the texts compare exactly; nothing is normalised away.

    No comma appears on either side of the live surface, so stripping them
    removes nothing today and would hide the first day the two renderings start
    formatting differently — which is schema drift that must be seen.
    """
    member = _ROSTER[0]
    html_side = fx.with_member(_ROSTER, member.serial, values=("1,234.50", *member.values[1:]))
    csv_side = fx.with_member(_ROSTER, member.serial, values=("1234.50", *member.values[1:]))

    run, _ = fx.acquire(
        monkeypatch, page=fx.watchlist_page(html_side), export=fx.export_csv(csv_side)
    )

    _incomplete(run, "WatchlistCrossCheckError")


def test_whitespace_and_non_breaking_spaces_around_a_page_value_are_not_a_disagreement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SL4-01c / A21: the HTML text is normalised for comparison — and only for comparison.

    The template pads every cell with newlines and indentation, and a
    non-breaking space is what the site uses where a plain one would wrap.
    Comparing the raw text refuses every live page; the published number is
    still parsed from the CSV, never from this text.
    """
    member = _ROSTER[0]
    padded = fx.data_row(member).replace(
        f"\n      {member.values[0]}\n", f"&nbsp;{member.values[0]}&nbsp;\n"
    )
    assert padded != fx.data_row(member)
    rows = padded + "".join(fx.data_row(other) for other in _ROSTER[1:])

    run, _ = fx.acquire(
        monkeypatch,
        page=fx.page(fx.table_of(fx.header_row(fx.DEFAULT_COLUMNS) + rows)),
        export=fx.export_csv(_ROSTER),
    )

    assert run.artifact.outcome is fx.models.WatchlistOutcome.RESULTS


@pytest.mark.parametrize(
    ("serial", "overrides"),
    [
        (1, {"nse_code": "SYNTHXXX"}),
        (3, {"bse_code": "559999"}),
        (1, {"nse_code": "", "bse_code": ""}),
    ],
    ids=["slug-differs-from-nse", "slug-differs-from-bse-without-nse", "no-code-published"],
)
def test_a_slug_that_disagrees_with_the_csv_exchange_code_refuses(
    monkeypatch: pytest.MonkeyPatch, serial: int, overrides: dict[str, str]
) -> None:
    """SL4-01e / A6: the slug is the exchange code, and it binds the two rows.

    This is the one identity check independent of the display name. Two
    companies sharing a truncated name with coincidentally equal values would
    otherwise merge one Screener id onto the other's ISIN in silence.
    """
    member = _ROSTER[serial - 1]
    assert member.href.startswith(f"/company/{member.nse_code or member.bse_code}/")
    csv_side = fx.with_member(_ROSTER, serial, **overrides)

    run, _ = fx.acquire(
        monkeypatch, page=fx.watchlist_page(_ROSTER), export=fx.export_csv(csv_side)
    )

    _incomplete(run, "WatchlistCrossCheckError")


def test_an_id_routed_member_with_no_exchange_code_is_exempt_without_refusing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SL4-01e / A7: the delisted shape publishes no code on either side.

    There is no slug to compare, so the check has nothing to say about this
    row; refusing it would refuse the owner's own list for one delisted member.
    It stays identified by its row id and its ISIN.
    """
    delisted = next(member for member in _ROSTER if "/id/" in member.href)

    run, _ = fx.acquire_roster(monkeypatch, _ROSTER)

    assert run.artifact.outcome is fx.models.WatchlistOutcome.RESULTS
    company = next(row.company for row in run.artifact.rows if row.serial_number == delisted.serial)
    assert company.slug is None
    assert (company.nse_code, company.bse_code) == (None, None)
    assert company.isin_code == delisted.isin_code


@pytest.mark.parametrize(
    "overrides",
    [{"isin_code": ""}, {"isin_code": "SYN000000001"}],
    ids=["empty-isin", "duplicate-isin"],
)
def test_an_isin_that_is_empty_or_repeated_refuses(
    monkeypatch: pytest.MonkeyPatch, overrides: dict[str, str]
) -> None:
    """SL4-21 / A32: ISIN is present and unique on every live CSV row, delisted included.

    It is the CSV side's identity, as the row id is the HTML side's. A repeat is
    one company exported twice; an absence is a row nothing downstream can key
    on. The exchange codes are not required — fifteen live rows have no NSE
    code and one has neither.
    """
    csv_side = fx.with_member(_ROSTER, 2, **overrides)

    run, _ = fx.acquire(
        monkeypatch, page=fx.watchlist_page(_ROSTER), export=fx.export_csv(csv_side)
    )

    _incomplete(run, "WatchlistCrossCheckError")


@pytest.mark.parametrize(
    ("overrides", "identifier", "value"),
    [
        (
            {"nse_code": _ROSTER[0].nse_code, "href": "/company/id/8800002/"},
            "NSE Code",
            _ROSTER[0].nse_code,
        ),
        (
            {"bse_code": _ROSTER[0].bse_code, "href": "/company/id/8800002/"},
            "BSE Code",
            _ROSTER[0].bse_code,
        ),
        (
            {"nse_code": "", "bse_code": _ROSTER[0].nse_code, "href": _ROSTER[0].href},
            "slug",
            _ROSTER[0].nse_code,
        ),
    ],
    ids=["duplicate-nse-code", "duplicate-bse-code", "duplicate-slug"],
)
def test_a_repeated_exchange_code_or_company_slug_refuses(
    monkeypatch: pytest.MonkeyPatch, overrides: dict[str, str], identifier: str, value: str
) -> None:
    """SL4-21 / A22 / A41: uniqueness is required of every published identifier, not just the ISIN.

    Two rows carrying one exchange code, or two links routing to one company
    page, are one company admitted twice — and each of them satisfies the
    slug/code check on its own, so nothing else in the slice sees it. The ISIN
    rules do not: two rows may hold distinct ISINs and still be the same issuer
    under two names.

    Each case here trips exactly one of the three: the duplicated-code rows are
    id-routed, so the slug check has nothing to compare, and the duplicated-slug
    row is bound by its BSE code where the row it collides with is bound by its
    NSE code, leaving both code columns unique.
    """
    collided = fx.with_member(_ROSTER, 2, **overrides)

    run, _ = fx.acquire_roster(monkeypatch, collided)

    artifact = _incomplete(run, "WatchlistCrossCheckError")
    assert artifact.rows == ()
    assert identifier in artifact.incomplete_reason
    assert value in artifact.incomplete_reason


@pytest.mark.parametrize(
    "drifted",
    ["1,234.50", "12.5%", "NA", "NaN"],
    ids=["thousands-separator", "percent-suffix", "not-available", "not-a-number"],
)
def test_a_non_empty_value_that_is_not_a_finite_number_refuses(
    monkeypatch: pytest.MonkeyPatch, drifted: str
) -> None:
    """SL4-26 / A37: an unreadable figure is drift to be seen, never an absent one.

    SL4-01c compares the two renderings as *text*, so a lexeme both sides render
    identically passes every oracle here — and publishing it as ``value: None``
    beside a non-empty ``csv_text`` makes a company whose ROCE is ``12.5%``
    indistinguishable from one with no ROCE at all, which is precisely what
    SL4-09 says ``None`` means. Thousands commas are a decoration this source
    already uses on the sibling screen table, so the day it uses them here every
    figure at or above a thousand would publish as absent under a ``results``
    outcome. ``NaN`` parses as a ``Decimal`` and is not a figure either.
    """
    member = _ROSTER[0]
    roster = fx.with_member(_ROSTER, member.serial, values=(drifted, *member.values[1:]))

    run, _ = fx.acquire_roster(monkeypatch, roster)

    artifact = _incomplete(run, "WatchlistCrossCheckError")
    assert artifact.rows == ()
    assert drifted in artifact.incomplete_reason
    assert member.name in artifact.incomplete_reason
    assert fx.DEFAULT_COLUMNS[0].tooltip in artifact.incomplete_reason


def test_empty_exchange_codes_may_repeat_across_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    """SL4-21 / A32: uniqueness applies to published codes, never to their absence.

    Several BSE-only members share an empty NSE code, and the delisted member
    has neither. Treating the empty string as a duplicate would refuse every
    live list.
    """
    assert sum(1 for member in _ROSTER if not member.nse_code) > 1

    run, _ = fx.acquire_roster(monkeypatch, _ROSTER)

    assert run.artifact.outcome is fx.models.WatchlistOutcome.RESULTS


# --------------------------------------------------------------------------
# What a published row carries
# --------------------------------------------------------------------------


def test_an_empty_cell_on_both_sides_is_none_and_never_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SL4-09: an empty cell is "no such figure", and a zero is a figure.

    A company publishing no return on capital must not be published with a
    return of zero; downstream that is a screen filter matching a company it
    should not. Both raw texts stay on the cell so the emptiness is auditable.
    """
    member, position = next(
        (member, position)
        for member in _ROSTER
        for position, text in enumerate(member.values)
        if text == ""
    )

    run, _ = fx.acquire_roster(monkeypatch, _ROSTER)

    row = next(row for row in run.artifact.rows if row.serial_number == member.serial)
    cell = row.cells[position]
    assert cell.value is None
    assert (cell.csv_text, cell.html_text) == ("", "")


def test_a_value_is_parsed_from_the_csv_and_anchored_by_csv_field_position(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SL4-20 / A21: the CSV is authoritative; the page text is comparison-only.

    The CSV has no entities, no padding and no suffixes, so it needs no cleanup
    that could turn a real value into ``None``. The anchor indexes the CSV field
    and names the CSV header, because the notebook column makes the page's
    ``td`` index a different number — reusing Slice 3's convention would point
    every provenance at the wrong column.

    SL4-27 / A38: an anchor names one file and addresses a position *in that
    file*. The anchor names the export, so its row is the export's record
    position and its type is the CSV's. The page's row 1 is the CSV's last
    record here — the two orders differ on every row, which is why SL4-02
    forbids the positional join in the first place — so an anchor carrying the
    page's serial would send an auditor to another company's figure.
    """
    member = _ROSTER[0]
    position = next(index for index, text in enumerate(member.values) if text)
    header = fx.csv_header(fx.DEFAULT_COLUMNS)
    csv_position = 1 + next(
        index
        for index, record in enumerate(fx.csv_records(_ROSTER))
        if record[header.index("Name")] == member.name
    )
    assert csv_position != member.serial

    run, _ = fx.acquire_roster(monkeypatch, _ROSTER)

    row = next(row for row in run.artifact.rows if row.serial_number == 1)
    cell = row.cells[position]
    column = run.artifact.columns[position]
    assert cell.value == Decimal(member.values[position])
    assert cell.csv_text == member.values[position]
    assert cell.csv_field_index == header.index(fx.DEFAULT_COLUMNS[position].tooltip)
    assert column.csv_field_index == cell.csv_field_index
    assert column.html_label == fx.DEFAULT_COLUMNS[position].html_label
    assert cell.provenance.column_index == cell.csv_field_index
    assert cell.provenance.column_label == fx.DEFAULT_COLUMNS[position].tooltip
    assert cell.provenance.file_sha256 == run.documents[1].content_sha256
    assert cell.provenance.source_id == fx.SOURCE_ID
    assert cell.provenance.anchor_type is SourceAnchorType.CSV_RECORD
    assert cell.provenance.row_path == f"record[{csv_position}]"
    assert cell.provenance.row_path != f"record[{member.serial}]"


def test_the_cross_check_record_binds_both_retained_documents(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SL4-16: the oracle is auditable without reparsing bytes.

    Both URLs, statuses, digests and byte counts on the artifact are what tie a
    published row back to the two responses on disk; without them a consumer
    cannot tell which retained bytes a run was judged on.
    """
    page = fx.watchlist_page(_ROSTER)
    export = fx.export_csv(_ROSTER)

    run, _ = fx.acquire(monkeypatch, page=page, export=export)

    record = run.artifact.cross_check
    assert record is not None
    assert (record.html_source_url, record.export_source_url) == (
        fx.WATCHLIST_PAGE_URL,
        fx.export_url(),
    )
    assert (record.html_http_status, record.export_http_status) == (200, 200)
    assert record.html_sha256 == hashlib.sha256(page.encode("utf-8")).hexdigest()
    assert record.export_sha256 == hashlib.sha256(export.encode("utf-8")).hexdigest()
    assert (record.html_byte_count, record.export_byte_count) == (
        len(page.encode("utf-8")),
        len(export.encode("utf-8")),
    )
    assert [document.content_sha256 for document in run.documents] == [
        record.html_sha256,
        record.export_sha256,
    ]


def test_the_cross_check_record_states_what_was_compared_and_that_nothing_disagreed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SL4-16 / A13: a compared-cell count alone does not prove the right cells were compared.

    The record carries both header sequences, both row counts and the empty
    disagreement lists, so a successful run can be audited for having checked
    every row against every column rather than some of each.
    """
    run, _ = fx.acquire_roster(monkeypatch, _ROSTER)

    record = run.artifact.cross_check
    assert (record.html_row_count, record.csv_row_count) == (len(_ROSTER), len(_ROSTER))
    assert record.compared_cell_count == len(_ROSTER) * len(fx.DEFAULT_COLUMNS)
    assert tuple(record.html_value_labels) == _TOOLTIPS == tuple(record.csv_value_labels)
    assert tuple(record.only_in_html) == tuple(record.only_in_csv) == ()
    assert tuple(record.duplicate_names_html) == tuple(record.duplicate_names_csv) == ()
    assert tuple(record.value_mismatches) == ()


def test_the_cross_check_record_keeps_the_export_content_headers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A28 / SL4-19: the two content headers are the only response headers retained.

    They are what proved the export was the export, so they belong on the
    record; every other response header is never retained and never logged.
    """
    run, _ = fx.acquire_roster(monkeypatch, _ROSTER)

    record = run.artifact.cross_check
    assert record.export_content_type == fx.EXPORT_CONTENT_TYPE
    assert record.export_content_disposition == fx.EXPORT_DISPOSITION
