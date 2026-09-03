"""Slice 4 reading and cross-check contract: one watchlist page beside its export.

Every fixture is synthetic, built from the structure the live surface was
verified to have and nothing copied from it. The facts that were expensive to
learn are the ones the fixtures encode: the page states no total, so the only
completeness oracle is the agreement of two server renderings; the header row
repeats inside one ``tbody`` and its ``S.No.`` spans the notebook column; the
value headers name their CSV counterpart in ``data-tooltip``; the company link
has four shapes; the CSV is alphabetical while the page is in watchlist order;
and one CSV field is quoted because it contains a comma.

Each test states the requirement id it pins and why the behaviour matters. The
transport seam, the builders and the acquisition helpers live in
:mod:`screener_watchlist_fixtures`; the comparison between the two renderings
lives in :mod:`test_screener_watchlist_crosscheck`, and the transport and
page-binding rules of the acquisition in :mod:`test_screener_watchlist_acquire`.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

import pytest
import screener_watchlist_fixtures as fx
from pydantic import ValidationError

from fundamentals.ingest.screener_session_models import ScreenerSessionError

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
# The frozen models, enum and errors every other test reads through
# --------------------------------------------------------------------------


def test_the_outcome_enum_has_no_empty_member(monkeypatch: pytest.MonkeyPatch) -> None:
    """SL4-14 / A9: an outcome that cannot be told apart from a failure is not published.

    Nothing in the evidence distinguishes a genuinely empty watchlist from an
    anonymous shell or a degraded page rendering no rows. An ``EMPTY`` outcome
    would let that shell be published as a successful answer, so the enum is
    ``RESULTS`` and ``INCOMPLETE`` only.
    """
    outcomes = fx.models.WatchlistOutcome
    assert issubclass(outcomes, StrEnum)
    assert {member.name for member in outcomes} == {"RESULTS", "INCOMPLETE"}


def test_an_incomplete_artifact_with_neither_failure_nor_evidence_cannot_be_built(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SL4-14: ``INCOMPLETE`` must carry what it proved or what refused it.

    A consumer branching on the outcome reads the failure or the cross-check
    record next. An incomplete artifact carrying neither is unauditable: it says
    something stopped the run and records nothing anyone could act on.
    """
    run, _ = fx.acquire_roster(monkeypatch, _ROSTER)

    with pytest.raises(ValidationError):
        fx.rebuilt(
            run.artifact,
            outcome=fx.models.WatchlistOutcome.INCOMPLETE,
            incomplete_reason="stopped",
            failure=None,
            cross_check=None,
        )


def test_a_results_artifact_cannot_carry_an_incomplete_reason(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SL4-14: the outcome and the fields beside it are one fact, not two.

    A ``results`` artifact that also names a reason it stopped is readable by
    every consumer and wrong for all of them; the validator, not convention, is
    what keeps the two from disagreeing.
    """
    run, _ = fx.acquire_roster(monkeypatch, _ROSTER)

    with pytest.raises(ValidationError):
        fx.rebuilt(run.artifact, incomplete_reason="stopped")


def test_every_watchlist_refusal_is_a_session_error() -> None:
    """The CLI dispatcher catches ``ScreenerSessionError`` and exits by code.

    A refusal outside that hierarchy reaches the operator as a traceback with
    exit 1, indistinguishable from a bug, and skips the retained-evidence path.
    """
    base = fx.models.ScreenerWatchlistError
    assert issubclass(base, ScreenerSessionError)
    for name in (
        "WatchlistStructureError",
        "WatchlistPageError",
        "WatchlistExportError",
        "WatchlistCrossCheckError",
    ):
        assert issubclass(getattr(fx.models, name), base)


@pytest.mark.parametrize(
    ("watchlist_id", "expected"),
    [
        (None, fx.WATCHLIST_PAGE_URL),
        (fx.WATCHLIST_ID, f"{fx.WATCHLIST_PAGE_URL}{fx.WATCHLIST_ID}/"),
    ],
)
def test_the_page_url_is_the_default_list_or_one_named_list(
    watchlist_id: int | None, expected: str
) -> None:
    """The two page shapes are the only two URLs this seam GETs.

    Both were exercised live and render the same list; the id form is what a
    second watchlist would need. A URL built any other way is a request the
    capture never made.
    """
    assert fx.models.watchlist_url(watchlist_id) == expected


@pytest.mark.parametrize("watchlist_id", [0, -1])
def test_a_non_positive_watchlist_id_never_becomes_a_url(watchlist_id: int) -> None:
    """A watchlist id below one is a caller defect, and must not spend a request."""
    with pytest.raises(ScreenerSessionError):
        fx.models.watchlist_url(watchlist_id)


def test_no_export_url_is_ever_constructed() -> None:
    """SL4-17 / A18: the export is posted to the form the page gives, never to a built URL.

    The two page shapes carry two different form actions, and the dropdown
    exposes no id to build one from. A builder here would invent a URL the
    fetched page never offered — which is exactly how the earlier probes
    returned zero bytes.
    """
    assert not hasattr(fx.models, "watchlist_export_url")


def test_the_published_guarantee_is_cross_render_consistency_and_never_completeness() -> None:
    """A8 / A24: two renderings agreeing does not prove the list contains nothing else.

    Both are served by one backend and could share one capped or stale snapshot.
    The artifact's own documentation must say what it proves in those words, so
    a consumer never reads agreement as completeness.
    """
    for documented in (fx.models.WatchlistArtifact, fx.watchlist.acquire_watchlist):
        assert "cross-render consistency" in (documented.__doc__ or "")
    field_names = set(fx.models.WatchlistArtifact.model_fields)
    assert not {name for name in field_names if "complete" in name} - {"incomplete_reason"}


# --------------------------------------------------------------------------
# The HTML table, read on its own
# --------------------------------------------------------------------------


def test_the_repeated_header_rows_are_never_admitted_as_members() -> None:
    """SL4-03: the header repeats inside one ``tbody`` and every repeat is a header.

    Verified live: one ``tbody``, a header row every sixteen data rows, no
    ``thead``. A reader taking the first row as the only header admits five
    header rows as companies; one refusing later ``th`` refuses the whole page.
    """
    roster = fx.members(fx.LIVE_MEMBER_COUNT)
    body = fx.watchlist_page(roster)
    headers, data, total = fx.row_shapes(body)
    assert data == len(roster)
    assert headers > 1
    assert headers + data == total

    table = fx.read_table(body)

    assert len(table.rows) == len(roster)
    assert tuple(row.serial_number for row in table.rows) == tuple(range(1, len(roster) + 1))


@pytest.mark.parametrize(
    "stray",
    [
        '<tr><td colspan="7">Sector: Widgets</td></tr>',
        '<tr data-row-company-id="8800099"><th>99.</th><th>x</th></tr>',
        "<tr><th>1.</th><td>x</td></tr>",
        "<tr></tr>",
    ],
    ids=["grouping-row", "id-carrying-header", "mixed-cells", "empty-row"],
)
def test_a_row_that_is_neither_a_header_nor_a_member_refuses_the_table(stray: str) -> None:
    """SL4-03 / SL4-04: a row the reader cannot classify is under-reporting.

    Silently skipping it is how a dropped company looks exactly like a smaller
    watchlist. Refusing is a drift policy, and it costs availability if the
    source adds a benign grouping row — that cost is accepted on purpose.
    """
    rows = "".join(fx.data_row(member) for member in _ROSTER[:2])
    body = fx.page(fx.table_of(fx.header_row(fx.DEFAULT_COLUMNS) + rows + stray))

    with pytest.raises(fx.models.WatchlistStructureError):
        fx.read_table(body)


def test_a_member_row_outside_the_tbody_is_not_silently_dropped() -> None:
    """SL4-04: every ``tr`` of the table must be accounted for, wherever it sits.

    A reader walking ``./tbody/tr`` cannot see a row in ``tfoot`` or loose under
    ``table``; the serials still run 1..N over what it did see, so nothing else
    catches the omission.
    """
    rows = "".join(fx.data_row(member) for member in _ROSTER[:2])
    displaced = fx.data_row(_ROSTER[2])
    table = (
        f'<table class="{fx.TABLE_CLASS}"><tbody>{fx.header_row(fx.DEFAULT_COLUMNS)}{rows}'
        f"</tbody><tfoot>{displaced}</tfoot></table>"
    )

    with pytest.raises(fx.models.WatchlistStructureError):
        fx.read_table(fx.page(table))


@pytest.mark.parametrize(
    ("header", "row"),
    [
        (fx.header_row(fx.DEFAULT_COLUMNS, serial_colspan=None), fx.data_row(_ROSTER[0])),
        (fx.header_row(fx.DEFAULT_COLUMNS, serial_colspan=3), fx.data_row(_ROSTER[0])),
        (fx.header_row(fx.DEFAULT_COLUMNS), fx.data_row(_ROSTER[0], extra_cell=True)),
    ],
    ids=["no-colspan", "colspan-too-wide", "extra-data-cell"],
)
def test_the_header_colspan_sum_must_equal_the_member_row_cell_count(header: str, row: str) -> None:
    """SL4-05 / A1: ``S.No.`` spans the notebook column, so the sums must agree.

    The rule is the relation, never the two numbers: a header summing to one
    less than the row means a value cell has no label, and one summing to more
    means a label has no value. Either publishes numbers under the wrong name.
    """
    with pytest.raises(fx.models.WatchlistStructureError):
        fx.read_table(fx.page(fx.table_of(header + row)))


def test_a_repeated_header_that_differs_from_the_first_refuses_the_table() -> None:
    """SL4-05: every header repeat must declare the identical label sequence.

    A repeat with one renamed tooltip means the rows below it belong to a
    different column mapping than the rows above, and concatenating them
    publishes values under the wrong metric.
    """
    renamed = fx.renamed_columns(fx.DEFAULT_COLUMNS, 2, "Gamma renamed")
    rows = [fx.data_row(member) for member in _ROSTER[:4]]
    markup = fx.table_of(
        fx.header_row(fx.DEFAULT_COLUMNS)
        + "".join(rows[:2])
        + fx.header_row(renamed)
        + "".join(rows[2:])
    )

    with pytest.raises(fx.models.WatchlistStructureError):
        fx.read_table(fx.page(markup))


@pytest.mark.parametrize(
    "serials",
    [("1.", "2.", "4."), ("1.", "2.", "2."), ("2.", "3.", "4.")],
    ids=["gap", "repeat", "starts-at-two"],
)
def test_serials_must_run_contiguously_from_one(serials: tuple[str, ...]) -> None:
    """SL4-06: the serial is the cheapest proof that no row was dropped or doubled.

    A gap is a member the page rendered and the reader lost; a repeat is one
    admitted twice; a start above one is a page that is not the first. Each
    would otherwise pass as a smaller or larger list.
    """
    rows = "".join(
        fx.data_row(member, serial_cell=serial)
        for member, serial in zip(_ROSTER[:3], serials, strict=True)
    )

    with pytest.raises(fx.models.WatchlistStructureError):
        fx.read_table(fx.page(fx.table_of(fx.header_row(fx.DEFAULT_COLUMNS) + rows)))


@pytest.mark.parametrize(
    ("href", "expected"),
    [
        ("/company/SYNTH001/", ("SYNTH001", False)),
        ("/company/SYNTH001/consolidated/", ("SYNTH001", True)),
        ("/company/550001/consolidated/", ("550001", True)),
        ("/company/id/8800001/", (None, False)),
        ("/company/id/8800001/consolidated/", (None, True)),
        ("/company/id/8800002/consolidated/", None),
        ("/company/id/8800002/", None),
        ("/company/id/", None),
        ("/company/id/consolidated/", None),
        ("/company/SYNTH001/standalone/", None),
        ("https://www.screener.in/company/SYNTH001/", None),
        ("/screen/raw/SYNTH001/", None),
    ],
)
def test_a_company_link_has_four_shapes_and_the_id_route_must_agree_with_the_row(
    href: str, expected: tuple[str | None, bool] | None
) -> None:
    """SL4-23 / A29: the id-routed link carries a basis suffix Slice 3 never rendered.

    Slice 3's reader admits ``/company/id/<n>/`` only as exactly two segments, so
    the watchlist's ``/company/id/<n>/consolidated/`` — a delisted member on the
    owner's own list — would refuse the whole page on the first run. Reading the
    first segment as a slug would instead record a company called ``id``. The
    suffix is a basis signal, never a malformed link, and the id must agree
    with the row's own identity or two identifiers describe two companies.
    """
    body = fx.page(
        fx.table_of(fx.header_row(fx.DEFAULT_COLUMNS) + fx.data_row(_ROSTER[0], href=href))
    )

    if expected is None:
        with pytest.raises(fx.models.WatchlistStructureError):
            fx.read_table(body)
        return

    table = fx.read_table(body)
    row = table.rows[0]
    assert (row.slug, row.consolidated) == expected
    assert row.data_row_company_id == _ROSTER[0].company_id


def test_the_value_headers_declare_their_csv_names_in_data_tooltip_in_order() -> None:
    """SL4-01d: the page states the column correspondence; the reader must read it.

    The visible text is an abbreviation (``Alpha Rs.``); the tooltip is the full
    metric name the CSV header uses. Reading the abbreviation instead leaves the
    HTML and CSV columns with no stated mapping, and the cross-check would rest
    on value coincidence alone.
    """
    table = fx.read_table(fx.watchlist_page(_ROSTER))

    assert tuple(table.value_labels) == _TOOLTIPS
    assert tuple(table.visible_labels) == tuple(column.html_label for column in fx.DEFAULT_COLUMNS)


@pytest.mark.parametrize(
    "header",
    [
        fx.header_row(fx.DEFAULT_COLUMNS, untooltipped=2),
        fx.header_row(fx.DEFAULT_COLUMNS, name_tooltip=True),
    ],
    ids=["value-header-without-tooltip", "name-header-with-tooltip"],
)
def test_a_tooltip_missing_from_a_value_header_or_present_on_name_refuses(header: str) -> None:
    """SL4-01d / A34: a value column with no stated name cannot be matched to the CSV.

    The value positions are defined structurally — the expanded columns after
    the first two — so a tooltip on ``Name`` cannot shift the mapping; it can
    only mean the header is not the one this reader knows, and must refuse
    rather than be read around.
    """
    body = fx.page(fx.table_of(header + fx.data_row(_ROSTER[0])))

    with pytest.raises(fx.models.WatchlistStructureError):
        fx.read_table(body)


def test_a_repeated_data_row_company_id_refuses_the_table() -> None:
    """SL4-21: the row id is the HTML side's identity, and it must be unique.

    Two rows sharing an id are one company admitted twice — or a page that is
    not what this reader thinks — and both are caught only here, since the
    serials still run contiguously.
    """
    rows = fx.data_row(_ROSTER[0]) + fx.data_row(_ROSTER[1], row_id=str(_ROSTER[0].company_id))

    with pytest.raises(fx.models.WatchlistStructureError):
        fx.read_table(fx.page(fx.table_of(fx.header_row(fx.DEFAULT_COLUMNS) + rows)))


def test_display_names_are_kept_verbatim_after_entity_decoding() -> None:
    """SL4-08 / SL4-01a: the name is a join key, truncated at the source and never repaired.

    ``Synth Member 09.`` is a stored 16-character display name, not a rendering
    artifact; an apostrophe arrives as ``&#x27;`` and must be decoded once. A
    reader that trims the dot, expands the name or leaves the entity in place
    cannot join the row to its CSV record.
    """
    table = fx.read_table(fx.watchlist_page(_ROSTER))

    assert [row.display_name for row in table.rows] == [member.name for member in _ROSTER]


# --------------------------------------------------------------------------
# The CSV export, read on its own
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("http_status", "content_type", "content_disposition", "accepted"),
    [
        (200, "text/csv", fx.EXPORT_DISPOSITION, True),
        (200, "text/csv; charset=utf-8", fx.EXPORT_DISPOSITION, True),
        (200, "text/csv", 'attachment; filename="fixture core list.csv"', True),
        (200, "text/html; charset=utf-8", fx.EXPORT_DISPOSITION, False),
        (200, None, fx.EXPORT_DISPOSITION, False),
        (200, "text/csv", None, False),
        (200, "text/csv", "inline", False),
        (302, "text/csv", fx.EXPORT_DISPOSITION, False),
    ],
)
def test_the_export_must_prove_it_is_the_export_by_media_type_and_filename(
    http_status: int, content_type: str | None, content_disposition: str | None, accepted: bool
) -> None:
    """SL4-12 / A12: a 200 login page parses as a one-column CSV and must not.

    The media type is parsed, so a charset parameter is tolerated rather than
    refused; the disposition must name a file, quoted or not. Comparing raw
    header strings would refuse the live response the moment the server adds a
    parameter, and accepting anything would parse an HTML shell as data.
    """
    body = fx.export_csv(_ROSTER)

    if accepted:
        header, records = fx.read_export(
            body,
            http_status=http_status,
            content_type=content_type,
            content_disposition=content_disposition,
        )
        assert header == fx.csv_header(fx.DEFAULT_COLUMNS)
        assert len(records) == len(_ROSTER)
        return

    with pytest.raises(fx.models.WatchlistExportError):
        fx.read_export(
            body,
            http_status=http_status,
            content_type=content_type,
            content_disposition=content_disposition,
        )


def test_a_byte_order_mark_never_becomes_part_of_the_first_header() -> None:
    """SL4-12: decoded with ``utf-8-sig``, so the ``Name`` label stays ``Name``.

    A BOM absorbed into the label makes the identity column unfindable by name,
    and A27 locates every identity field by label.
    """
    header, _ = fx.read_export(b"\xef\xbb\xbf" + fx.export_csv(_ROSTER).encode("utf-8"))

    assert header[0] == "Name"


def test_a_ragged_record_refuses_the_export() -> None:
    """SL4-12: every record must be as wide as the header.

    A short record shifts every later field under the wrong label; a long one
    has a value no label names. Both are silent misattribution downstream.
    """
    records = fx.csv_records(_ROSTER)
    ragged = (*records[:1], records[1][:-1], *records[2:])

    with pytest.raises(fx.models.WatchlistExportError):
        fx.read_export(fx.export_csv(_ROSTER, records=ragged))


def test_a_quoted_field_containing_a_comma_is_one_field() -> None:
    """A4: one live industry name is quoted because it contains a comma.

    Splitting on ``,`` turns that record into one field wider than the header
    and every value after it lands under the wrong label. A real CSV reader is
    the only correct answer, and a hand-built fixture without such a field
    would never show the difference.
    """
    with_comma = next(member for member in _ROSTER if "," in member.industry)

    header, records = fx.read_export(fx.export_csv(_ROSTER))

    record = next(record for record in records if record[header.index("Name")] == with_comma.name)
    assert len(record) == len(header)
    assert record[header.index("Industry")] == with_comma.industry
