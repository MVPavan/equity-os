"""Fixture-only coverage for the Tijori site-level and timeline event surfaces.

Every fixture is a synthetic replica of a live page's STRUCTURE — the same
islands, the same container ids, the same loader decoys — carrying invented
content. No test opens a socket.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from fundamentals.contracts.provenance import Provenance, SourceAnchorType
from fundamentals.ingest.tijori_events import build_tijori_events
from fundamentals.ingest.tijori_events_common import reject_duplicate_anchors
from fundamentals.ingest.tijori_events_html import collect_upcoming, parse_tree
from fundamentals.ingest.tijori_events_models import (
    CAPABILITY_DECLARATIONS,
    CAPTURE_DATE,
    MAX_ELEMENT_DEPTH,
    MAX_EVENT_TYPE_DEPTH,
    TijoriCompanyTimeline,
    TijoriEventsAuthError,
    TijoriEventsCapability,
    TijoriEventsCapabilityState,
    TijoriEventsIdentityError,
    TijoriEventsIdentityStrength,
    TijoriEventsOutcome,
    TijoriEventsSchemaError,
    TijoriEventsScope,
    TijoriEventsSurface,
    TijoriEventsSurfaceError,
    TijoriQuarterlyResults,
    TijoriSiteTimeline,
    TijoriUpcomingEvents,
    capabilities_of,
)
from fundamentals.ingest.tijori_page import JsonScriptCollector
from fundamentals.ingest.tijori_tables import TijoriParseError

_FIXTURES = Path(__file__).parent / "fixtures"
_UPCOMING = _FIXTURES / "synthetic_tijori_upcoming.html"
_QUARTERLY = _FIXTURES / "synthetic_tijori_quarterly_results.html"
_TIMELINE = _FIXTURES / "synthetic_tijori_timeline_site.html"
_COMPANY_TIMELINE = _FIXTURES / "synthetic_tijori_timeline_company.html"
_CONCALL = _FIXTURES / "synthetic_tijori_concall.html"

_SLUG = "titan-company-limited"
_SYMBOL = "TITAN"
_COMPANY_ID = 81
_SOURCE_URL = "https://www.tijorifinance.com/results/upcoming-events/"
_WATCHLIST = {_SLUG: _SYMBOL}
_TBODY = re.compile(r"<tbody>.*?</tbody>", re.DOTALL)


def _build(
    surface: TijoriEventsSurface,
    raw: bytes,
    **extra: object,
) -> object:
    """Build one artifact from raw bytes, as the adapter's entry point does."""
    return build_tijori_events(
        raw,
        surface=surface,
        source_url=_SOURCE_URL,
        content_sha256=hashlib.sha256(raw).hexdigest(),
        retrieved_at=datetime(2026, 8, 25, tzinfo=UTC),
        watchlist_slugs=_WATCHLIST,
        **extra,  # type: ignore[arg-type]
    )


def _upcoming() -> TijoriUpcomingEvents:
    """The upcoming-events artifact built from its synthetic replica."""
    built = _build(TijoriEventsSurface.UPCOMING, _UPCOMING.read_bytes())
    assert isinstance(built, TijoriUpcomingEvents)
    return built


def _quarterly() -> TijoriQuarterlyResults:
    """The quarterly-results artifact built from its synthetic replica."""
    built = _build(TijoriEventsSurface.QUARTERLY_RESULTS, _QUARTERLY.read_bytes())
    assert isinstance(built, TijoriQuarterlyResults)
    return built


def _timeline() -> TijoriSiteTimeline:
    """The site-timeline artifact built from its synthetic replica."""
    built = _build(TijoriEventsSurface.TIMELINE, _TIMELINE.read_bytes())
    assert isinstance(built, TijoriSiteTimeline)
    return built


def _company_timeline(raw: bytes | None = None) -> TijoriCompanyTimeline:
    """The company-timeline artifact built from its synthetic fragment."""
    built = _build(
        TijoriEventsSurface.COMPANY_TIMELINE,
        _COMPANY_TIMELINE.read_bytes() if raw is None else raw,
        slug=_SLUG,
        symbol=_SYMBOL,
        company_id=_COMPANY_ID,
    )
    assert isinstance(built, TijoriCompanyTimeline)
    return built


def test_the_upcoming_listing_is_selected_by_its_container_not_by_shape() -> None:
    """The loader shells share the listing's shape, so shape alone would be ambiguous."""
    listing = collect_upcoming(_UPCOMING.read_text(encoding="utf-8"))

    assert listing.column_labels == ("Company", "Date")
    assert len(listing.rows) == 3
    assert listing.lazy_tables == (
        "upcoming_results_loader table_loader",
        "upcoming_concalls_loader table_loader",
    )


def test_upcoming_rows_record_the_watchlist_match_and_the_miss() -> None:
    """A listed company this repo does not track is market data, never a failure."""
    built = _upcoming()

    tracked, first_other = built.rows[0], built.rows[1]
    assert tracked.company.slug == _SLUG
    assert tracked.company.on_watchlist is True
    assert tracked.company.watchlist_symbol == _SYMBOL
    assert first_other.company.on_watchlist is False
    assert first_other.company.watchlist_symbol is None
    assert built.outcome is TijoriEventsOutcome.OK


def test_an_upcoming_row_keeps_its_secondary_renderings_instead_of_dropping_them() -> None:
    """The symbol badge and the mobile date are alternate renderings of the row."""
    row = _upcoming().rows[0]

    assert tuple(cell.raw_text for cell in row.cells) == ("Titan Company", "Sep 12, 2026")
    assert row.alternate_texts == ("TITAN", "Sep 12, 26")


def test_upcoming_cells_carry_position_led_html_table_anchors() -> None:
    """An HTML cell is re-found by table, row, and rendered column — never by island."""
    cell = _upcoming().rows[1].cells[1]

    assert cell.provenance.anchor_type is SourceAnchorType.HTML_TABLE
    assert cell.provenance.table_id == "html:upcoming-events/results"
    assert cell.provenance.row_path == "1/synthetic-alpha-industries-ltd"
    assert cell.provenance.column_index == 1
    assert cell.provenance.column_label == "Date"
    assert cell.provenance.island_id is None
    assert cell.provenance.document_id is None


def test_a_row_without_its_machine_readable_slug_is_quarantined_not_dropped() -> None:
    """Dropping an unaddressable row would silently shorten the listing."""
    built = _upcoming()

    assert built.element_count == 3
    assert len(built.malformed_rows) == 1
    assert "missing data-slug" in built.malformed_rows[0]


def test_the_listing_records_the_counts_the_page_declared() -> None:
    """A page showing 3 of 7 has more rows than it rendered; that is worth recording."""
    built = _upcoming()

    assert built.declared_shown == 3
    assert built.declared_total == 7


def test_an_empty_listing_is_a_typed_empty_outcome_not_a_failure() -> None:
    """A day with no upcoming events is a fact about the market, not a broken read."""
    emptied = _TBODY.sub("<tbody></tbody>", _UPCOMING.read_text(encoding="utf-8"), count=1)

    built = _build(TijoriEventsSurface.UPCOMING, emptied.encode("utf-8"))

    assert isinstance(built, TijoriUpcomingEvents)
    assert built.element_count == 0
    assert built.outcome is TijoriEventsOutcome.OK_EMPTY
    assert built.note is not None


def test_quarterly_results_read_each_item_with_its_header_and_its_table() -> None:
    """One announced result is a company, a date, its headline metrics, and its lines."""
    item = _quarterly().items[0]

    assert item.company.slug == _SLUG
    assert item.announced.raw_text == "22 Aug 2026"
    assert tuple(metric.label for metric in item.headline_metrics) == ("M Cap:", "PE:")
    assert item.headline_metrics[1].cell.value == Decimal("42.5")
    assert item.column_labels[0] == "(In Cr.)"
    assert item.rows[0].label == "Sales"
    assert item.rows[0].cells[2].value == Decimal("21356")
    assert item.rows[0].cells[2].provenance.column_label == "Jun 2026"
    assert item.detail_link is not None


def test_a_percent_lexeme_reads_as_null_while_its_source_text_survives() -> None:
    """The shared cell rule never invents a number out of a decorated lexeme."""
    growth = _quarterly().items[0].rows[0].cells[0]

    assert growth.raw_text == "29.25%"
    assert growth.value is None


def test_a_result_row_whose_cardinality_disagrees_keeps_its_lexemes_unaligned() -> None:
    """Which end of a short row is missing is not determinable, so it is never guessed."""
    row = _quarterly().items[1].rows[1]

    assert row.label == "Operating Profit"
    assert row.cells == ()
    assert row.unaligned_raw_values == ("57.17%", "49.10", "-23.28")


def test_two_result_items_sharing_a_row_label_do_not_share_an_anchor() -> None:
    """'Sales' appears in every item, so the item must lead the address."""
    built = _quarterly()

    first = built.items[0].rows[0].cells[0].provenance
    second = built.items[1].rows[0].cells[0].provenance
    assert first.row_path == second.row_path == "0/Sales"
    assert first.table_id != second.table_id
    assert first.table_id.endswith(f"0/{_SLUG}")


def test_the_timeline_taxonomy_is_read_as_types_not_as_a_feed_of_events() -> None:
    """FACT: eventsList is the filter catalogue; the feed is not in this document."""
    built = _timeline()

    top = tuple(node.name for node in built.event_types)
    assert top == ("Exchange Filings", "Fundamentals")
    assert built.event_types[0].event_id is None
    assert "not the event feed" in built.feed_status


def test_a_taxonomy_leaf_is_anchored_to_the_island_by_its_position_led_path() -> None:
    """A display name repeats across groups, so position leads every node address."""
    leaf = _timeline().event_types[0].children[0].children[0]

    assert leaf.name == "Acquisition"
    assert leaf.event_id is not None
    assert leaf.event_id.value == Decimal(28)
    assert leaf.event_id.provenance.anchor_type is SourceAnchorType.JSON_ISLAND
    assert leaf.event_id.provenance.island_id == "eventsList"
    assert leaf.event_id.provenance.row_label == "0/Exchange Filings/0/Company Update/0/Acquisition"
    assert leaf.event_id.provenance.table_id is None


def test_a_group_that_also_carries_a_leaf_sibling_keeps_both() -> None:
    """The live taxonomy mixes subgroups and leaves inside one group's events list."""
    fundamentals = _timeline().event_types[1]

    assert tuple(child.name for child in fundamentals.children) == ("Metrics", "Company Debt")
    assert fundamentals.children[1].event_id is not None
    assert fundamentals.leaf_count == 2


def test_an_unmodeled_reference_key_is_retained_rather_than_dropped() -> None:
    """``is_empty`` is published on portfolios and this contract does not model it."""
    portfolio = _timeline().portfolios[0]

    assert portfolio.unmodeled_fields_json == '{"is_empty": true}'
    assert portfolio.entity_id is not None
    assert portfolio.entity_id.provenance.island_id == "portfoliosList"


def test_the_timeline_scalar_islands_are_read_with_their_lexemes() -> None:
    """An empty ``timestamp`` island is a published value, not a missing one."""
    scalars = {scalar.island_id: scalar.cell for scalar in _timeline().scalars}

    assert scalars["startDate"].raw_text == "10/21/2002"
    assert scalars["startDate"].value is None
    assert scalars["userId"].value == Decimal(2414340)
    assert scalars["timestamp"].raw_text == ""


def test_a_market_page_records_the_islands_that_proved_its_session() -> None:
    """The auth basis is only evidence if the markers it rests on are named."""
    timeline = _timeline()
    upcoming = _upcoming()

    assert timeline.metadata.auth_marker_islands == (
        "is_landing_page",
        "plan_details",
        "is_auth",
    )
    assert upcoming.metadata.auth_marker_islands == ("is_landing_page", "plan_details")
    assert timeline.metadata.access is not None
    assert timeline.metadata.access.plan_tier == "premium"


def test_a_market_artifact_claims_no_company_identity() -> None:
    """Every company on these pages is data on a row, not the document's issuer."""
    metadata = _upcoming().metadata

    assert metadata.scope is TijoriEventsScope.MARKET_WIDE
    assert metadata.identity_strength is TijoriEventsIdentityStrength.NO_COMPANY_IDENTITY
    assert metadata.company_id is None
    assert "market-wide listing" in metadata.identity_basis


def test_a_landing_page_response_is_refused_before_any_row_is_read() -> None:
    """An anonymous visitor gets the same template with is_landing_page set."""
    landing = _UPCOMING.read_text(encoding="utf-8").replace(
        '<script id="is_landing_page" type="application/json">""</script>',
        '<script id="is_landing_page" type="application/json">true</script>',
    )

    with pytest.raises(TijoriEventsAuthError, match="anonymous landing page"):
        _build(TijoriEventsSurface.UPCOMING, landing.encode("utf-8"))


def test_a_page_without_a_plan_island_cannot_prove_a_subscribed_session() -> None:
    """The plan object is the marker that a paying session rendered this page."""
    unplanned = _UPCOMING.read_text(encoding="utf-8").replace(
        '<script id="plan_details" type="application/json">'
        '{"id": 1, "name": "premium", "plan_tier": "premium"}</script>',
        '<script id="plan_details" type="application/json">{}</script>',
    )

    with pytest.raises(TijoriEventsAuthError, match="no usable plan_details"):
        _build(TijoriEventsSurface.UPCOMING, unplanned.encode("utf-8"))


def test_a_missing_auth_marker_island_is_a_refusal_not_a_default() -> None:
    """A gate that silently passes when its marker is absent is not a gate."""
    stripped = _UPCOMING.read_text(encoding="utf-8").replace(
        '<script id="is_landing_page" type="application/json">""</script>', ""
    )

    with pytest.raises(TijoriParseError, match="is_landing_page.*missing"):
        _build(TijoriEventsSurface.UPCOMING, stripped.encode("utf-8"))


def test_the_timeline_requires_is_auth_rather_than_checking_it_when_present() -> None:
    """A marker checked only when present is a gate that opens when it disappears."""
    dropped = _TIMELINE.read_text(encoding="utf-8").replace(
        '<script id="is_auth" type="application/json">true</script>', ""
    )

    with pytest.raises(TijoriParseError, match="is_auth.*missing"):
        _build(TijoriEventsSurface.TIMELINE, dropped.encode("utf-8"))


def test_a_surface_that_does_not_publish_is_auth_is_not_failed_by_its_absence() -> None:
    """The required-marker table is per surface: upcoming never publishes is_auth."""
    built = _upcoming()

    assert "is_auth" not in built.metadata.auth_marker_islands
    assert built.outcome is TijoriEventsOutcome.OK


@pytest.mark.parametrize(
    "plan_body",
    ['{"unrelated": true}', '{"id": 1}', '{"plan_tier": ""}', '"premium"'],
    ids=["unrelated-keys", "id-without-name", "blank-tier", "not-an-object"],
)
def test_a_plan_island_that_is_not_a_plan_object_fails_the_gate(plan_body: str) -> None:
    """Any non-empty dict passing as proof of a subscription is a fail-open gate."""
    swapped = _UPCOMING.read_text(encoding="utf-8").replace(
        '{"id": 1, "name": "premium", "plan_tier": "premium"}', plan_body
    )

    with pytest.raises(TijoriEventsAuthError, match="no usable plan_details"):
        _build(TijoriEventsSurface.UPCOMING, swapped.encode("utf-8"))


def test_the_timeline_refuses_a_response_whose_is_auth_island_is_false() -> None:
    """The timeline page publishes is_auth, so an unauthenticated one is detectable."""
    logged_out = _TIMELINE.read_text(encoding="utf-8").replace(
        '<script id="is_auth" type="application/json">true</script>',
        '<script id="is_auth" type="application/json">false</script>',
    )

    with pytest.raises(TijoriEventsAuthError, match="not authenticated"):
        _build(TijoriEventsSurface.TIMELINE, logged_out.encode("utf-8"))


def test_the_company_fragment_reads_every_rendered_event_in_order() -> None:
    """Grouped children are events in their own right and keep their group id."""
    built = _company_timeline()

    assert built.element_count == 4
    assert tuple(event.event_name for event in built.events) == (
        "Company Op Metrics",
        "Marketshare Update",
        "Business Update",
        "Other Important",
    )
    child = built.events[1]
    assert child.is_grouped_child is True
    assert child.group_id == "4673934"
    assert child.announced is None


def test_a_fragment_row_missing_its_event_cell_is_quarantined_not_dropped() -> None:
    """An unaddressable row must be visible, not silently absent from the timeline."""
    built = _company_timeline()

    assert len(built.malformed_rows) == 1
    assert "sbadrow" in built.malformed_rows[0]


def test_a_dict_table_keeps_every_rendered_cell_because_it_has_no_label_column() -> None:
    """Its title spans two rows, so the value row has no title to align against."""
    table = _company_timeline().events[0].detail_tables[0]

    assert table.table_class == "dict-table"
    assert tuple(cell.raw_text for cell in table.rows[0].cells) == (
        "Number of Stores",
        "Jun 2026",
        "Mar 2026",
    )
    assert table.rows[1].cells[0].value == Decimal(3680)
    assert table.rows[1].cells[0].provenance.anchor_type is SourceAnchorType.HTML_TABLE
    assert table.rows[1].cells[0].provenance.table_id.endswith("s3yj2/table:0")
    assert table.rows[1].cells[0].provenance.column_label == "col0"


def test_an_embedded_event_island_is_retained_byte_for_byte() -> None:
    """A retained source that was decoded and re-serialized is not the source.

    Round-tripping would rewrite ``1.250`` as ``1.25``, reorder keys, and leave
    an unparseable body with nothing to keep. The retained text must equal the
    rendered script body exactly.
    """
    rendered = _COMPANY_TIMELINE.read_text(encoding="utf-8")
    opening = '<script id="1234567890123456789" type="application/json">'
    start = rendered.index(opening) + len(opening)
    exact_body = rendered[start : rendered.index("</script>", start)]

    island = _company_timeline().events[2].islands[0]

    assert island.payload_json == exact_body
    assert '"engagement_score": 1.250' in island.payload_json
    assert island.decode_error is None
    assert island.island_id == "1234567890123456789"
    assert island.provenance.anchor_type is SourceAnchorType.JSON_ISLAND
    assert island.provenance.island_id == "1234567890123456789"
    assert island.provenance.table_key == "event:s2qsg"


def test_an_unparseable_event_island_keeps_its_bytes_and_records_why() -> None:
    """The retention is the point; the parse is only a check on it."""
    broken = _COMPANY_TIMELINE.read_text(encoding="utf-8").replace(
        '{"data": {"id": "1234567890123456789"', '{"data": {"id": NOT_JSON'
    )

    island = _company_timeline(broken.encode("utf-8")).events[2].islands[0]

    assert "NOT_JSON" in island.payload_json
    assert island.decode_error is not None


def test_every_primary_fact_of_a_timeline_event_carries_its_own_anchor() -> None:
    """A company, a date, an event name, and a link are source claims like any cell."""
    event = _company_timeline().events[2]

    assert event.company_cell.raw_text == "Titan Company"
    assert event.event_cell.raw_text == "Business Update"
    assert event.announced is not None
    assert event.announced.raw_text == "07-Aug-2026"
    assert tuple(cell.raw_text for cell in event.link_cells) == (
        "https://example.invalid/status/1234567890123456789",
    )
    for cell, label in (
        (event.company_cell, "company"),
        (event.event_cell, "event"),
        (event.announced, "date"),
        (event.content_cell, "content"),
        (event.link_cells[0], "link"),
    ):
        assert cell.provenance.anchor_type is SourceAnchorType.HTML_TABLE
        assert cell.provenance.table_id == "html:company-timeline/s2qsg"
        assert cell.provenance.row_path == "event"
        assert cell.provenance.column_label == label


def test_every_primary_fact_of_a_result_item_carries_its_own_anchor() -> None:
    """The header of a result item is as much a source claim as its numbers."""
    item = _quarterly().items[0]

    assert item.company_cell.raw_text == "Titan Company"
    assert item.detail_link is not None
    for cell, label, index in (
        (item.company_cell, "company", 0),
        (item.announced, "date", 1),
        (item.detail_link, "link", 2),
    ):
        assert cell.provenance.anchor_type is SourceAnchorType.HTML_TABLE
        assert cell.provenance.row_path == "header"
        assert cell.provenance.column_label == label
        assert cell.provenance.column_index == index
    assert item.company_cell.provenance.table_id.endswith(f"0/{_SLUG}")


def test_an_event_text_excludes_the_island_and_stylesheet_it_renders() -> None:
    """A stylesheet is not rendered text and a payload is already retained once."""
    event = _company_timeline().events[3]

    assert "elem_wrappers" not in event.content_cell.raw_text
    assert "Synthetic filing summary" in event.content_cell.raw_text


def test_the_company_fragment_binds_identity_to_the_configured_url_only() -> None:
    """The fragment asserts no identity, exactly like the analysis APIs."""
    metadata = _company_timeline().metadata

    assert metadata.scope is TijoriEventsScope.COMPANY
    assert metadata.identity_strength is TijoriEventsIdentityStrength.CONFIGURED_URL_ONLY
    assert metadata.company_id == _COMPANY_ID
    assert metadata.symbol == _SYMBOL
    assert "no identity island" in metadata.identity_basis
    assert "login redirect" in metadata.auth_basis


def test_a_whole_page_answered_where_a_fragment_was_asked_for_is_refused() -> None:
    """A login page rendered at HTTP 200 must not read as a timeline with no events."""
    with pytest.raises(TijoriEventsAuthError, match="whole HTML document"):
        _company_timeline(_CONCALL.read_bytes())


def test_an_embedded_document_inside_an_event_is_not_mistaken_for_a_page_shell() -> None:
    """Tijori embeds a full <html> document inside some event content cells."""
    built = _company_timeline()

    assert built.events[3].event_name == "Other Important"


def test_a_fragment_with_no_event_rows_is_refused_rather_than_reported_empty() -> None:
    """FACT: the fragment renders no empty-state markup, so zero rows proves nothing.

    An empty rendering has never been observed for this endpoint. A response with
    no ``tr[data-id]`` is therefore indistinguishable from a login page, a
    template change, or a wrong-endpoint answer, and reporting it as a verified
    empty timeline would publish a broken read as a fact about the company.
    """
    with pytest.raises(TijoriEventsSchemaError, match="no tr\\[data-id\\] event row"):
        _company_timeline(b"\n    \n")


def test_a_login_page_body_cannot_pass_the_fragment_gate() -> None:
    """Positive evidence is required: absence of a page shell is not enough."""
    login = b'<div class="login"><form><input type="password" name="p" /></form></div>'

    with pytest.raises(TijoriEventsSchemaError, match="no tr\\[data-id\\] event row"):
        _company_timeline(login)


def test_a_zero_count_explained_by_quarantined_rows_is_drift_not_emptiness() -> None:
    """Rows this adapter could not address must never be reported as no rows at all."""
    only_bad = _TBODY.sub(
        '<tbody><tr><td class="company"><div>'
        '<a href="/company/x-ltd/" class="name">X</a></div></td>'
        '<td class="date"><div class="desktop">Sep 1, 2026</div></td></tr></tbody>',
        _UPCOMING.read_text(encoding="utf-8"),
        count=1,
    )

    with pytest.raises(TijoriEventsSchemaError, match="addressed none of the 1 row"):
        _build(TijoriEventsSurface.UPCOMING, only_bad.encode("utf-8"))


def test_a_row_naming_another_company_is_quarantined_not_counted() -> None:
    """The fragment is addressed by company id, so a foreign row is drift."""
    text = _COMPANY_TIMELINE.read_text(encoding="utf-8")
    mutated = text.replace(
        'company-id="81">\n                            <div class="tweet-embed">',
        'company-id="99">\n                            <div class="tweet-embed">',
    )
    assert mutated != text

    built = _company_timeline(mutated.encode("utf-8"))

    assert built.element_count == 3
    assert "s2qsg" not in {event.row_id for event in built.events}
    assert len(built.identity_mismatch_rows) == 1
    assert "company-id '99'" in built.identity_mismatch_rows[0]


def test_a_fragment_whose_every_row_names_another_company_is_refused() -> None:
    """A wrong-company page must fail, not quietly return that company's events."""
    wrong = _COMPANY_TIMELINE.read_text(encoding="utf-8").replace(
        "/company/titan-company-limited", "/company/other-company-ltd"
    )

    with pytest.raises(TijoriEventsIdentityError, match="carries no row matching"):
        _company_timeline(wrong.encode("utf-8"))


def test_a_row_publishing_no_identity_marker_still_passes_through() -> None:
    """Tijori renders some rows without a company link; those are recorded, not judged."""
    built = _company_timeline()

    assert built.identity_mismatch_rows == ()
    assert all(event.company.slug == _SLUG for event in built.events)


def test_the_company_fragment_cannot_be_built_without_a_configured_company() -> None:
    """The company id in the URL IS the identity, so it is required, not optional."""
    with pytest.raises(TijoriEventsSurfaceError, match="needs --stock"):
        build_tijori_events(
            _COMPANY_TIMELINE.read_bytes(),
            surface=TijoriEventsSurface.COMPANY_TIMELINE,
            source_url=_SOURCE_URL,
            content_sha256="0" * 64,
            retrieved_at=datetime(2026, 8, 25, tzinfo=UTC),
        )


def test_the_concall_monitor_document_carries_nothing_to_acquire() -> None:
    """The verdict's evidence: no tables, no data islands, only a promotional panel.

    The live page (owner capture, 2026-08-25) renders exactly this shape: a
    redirection panel pointing at a separate product. Its only islands are plan
    markers, so there is no listing to parse and no XHR to chase in this slice.
    """
    document = _CONCALL.read_text(encoding="utf-8")
    collector = JsonScriptCollector(("eventsList", "date_range", "is_auth"))
    collector.feed(document)
    collector.close()

    assert "<table" not in document
    assert collector.islands == {}
    assert "con-summary" in document


def test_the_concall_monitor_is_refused_as_a_surface_rather_than_returning_empty() -> None:
    """Returning an empty artifact would report 'no concalls' for a page with none."""
    with pytest.raises(TijoriEventsSurfaceError, match="not acquirable"):
        _build(TijoriEventsSurface.CONCALL_MONITOR, _CONCALL.read_bytes())


def test_a_non_utf8_response_is_refused_by_the_shared_page_decoder() -> None:
    """A body that is not UTF-8 HTML is drift, never a document to guess at."""
    with pytest.raises(TijoriParseError, match="not UTF-8"):
        _build(TijoriEventsSurface.UPCOMING, b"\xff\xfe not html")


def test_the_duplicate_anchor_backstop_compares_the_whole_address() -> None:
    """A future addressing change that collapses two elements must be fatal, not silent."""
    built = _upcoming()
    collided = built.model_copy(
        update={
            "rows": (
                built.rows[0],
                built.rows[1].model_copy(update={"cells": built.rows[0].cells}),
            )
        }
    )

    with pytest.raises(TijoriEventsSchemaError, match="anchors two elements identically"):
        reject_duplicate_anchors(collided)


def test_the_backstop_accepts_two_anchors_that_differ_only_by_column_index() -> None:
    """Column position is part of the address, so two labels-alike cells stay distinct."""
    assert reject_duplicate_anchors(_quarterly()) is None


def test_a_timeline_artifact_reports_its_withheld_feed_beside_its_taxonomy() -> None:
    """'timeline: 15' must not be readable as fifteen market events."""
    states = {outcome.capability: outcome for outcome in _timeline().capabilities}

    assert set(states) == {
        TijoriEventsCapability.TIMELINE_TAXONOMY,
        TijoriEventsCapability.TIMELINE_FEED,
    }
    taxonomy = states[TijoriEventsCapability.TIMELINE_TAXONOMY]
    feed = states[TijoriEventsCapability.TIMELINE_FEED]
    assert taxonomy.state is TijoriEventsCapabilityState.ACQUIRED
    assert taxonomy.element_count == 15
    assert feed.state is TijoriEventsCapabilityState.XHR_NOT_ACQUIRED
    assert feed.element_count is None


def test_the_upcoming_page_reports_its_concall_tab_as_unacquired() -> None:
    """The results tab is served statically; the concall tab is an empty shell."""
    states = {outcome.capability: outcome for outcome in _upcoming().capabilities}

    assert states[TijoriEventsCapability.UPCOMING_RESULTS].element_count == 3
    concalls = states[TijoriEventsCapability.UPCOMING_CONCALLS_FEED]
    assert concalls.state is TijoriEventsCapabilityState.XHR_NOT_ACQUIRED
    assert concalls.element_count is None


def test_every_capability_verdict_is_dated_to_the_capture_that_established_it() -> None:
    """An undated verdict reads as a permanent claim about Tijori."""
    assert all(CAPTURE_DATE in declaration.note for declaration in CAPABILITY_DECLARATIONS)


def test_the_concall_capability_is_declared_as_an_external_product() -> None:
    """It is not 'lazy-loaded' — the feature moved to a separate product."""
    (declaration,) = capabilities_of(TijoriEventsSurface.CONCALL_MONITOR)

    assert declaration.state is TijoriEventsCapabilityState.EXTERNAL_PRODUCT_AT_CAPTURE
    assert "separate product" in declaration.note


def test_every_declared_capability_belongs_to_exactly_one_surface() -> None:
    """A capability with no surface could never be reported by a run."""
    declared = [declaration.capability for declaration in CAPABILITY_DECLARATIONS]

    assert sorted(declared, key=str) == sorted(TijoriEventsCapability, key=str)
    assert len(declared) == len(set(declared))
    for surface in TijoriEventsSurface:
        assert capabilities_of(surface), f"{surface.value} declares no capability"


def test_a_document_nested_past_the_bound_is_refused_not_recursed() -> None:
    """Every reader walks this tree recursively; an unbounded document is a refusal."""
    too_deep = "<div>" * (MAX_ELEMENT_DEPTH + 2)

    with pytest.raises(TijoriEventsSchemaError, match="nests elements more than"):
        parse_tree(too_deep)


def test_a_taxonomy_nested_past_the_bound_is_refused_not_recursed() -> None:
    """The island is untrusted JSON and the live taxonomy is three levels deep."""
    nested: dict[str, object] = {"group": "leaf", "id": 1}
    for index in range(MAX_EVENT_TYPE_DEPTH + 2):
        nested = {"group": f"g{index}", "events": [nested]}
    island = json.dumps([nested])
    document = _TIMELINE.read_text(encoding="utf-8")
    start = document.index('<script id="eventsList" type="application/json">')
    end = document.index("</script>", start)
    swapped = (
        document[: start + len('<script id="eventsList" type="application/json">')]
        + island
        + document[end:]
    )

    with pytest.raises(TijoriEventsSchemaError, match="nests event types more than"):
        _build(TijoriEventsSurface.TIMELINE, swapped.encode("utf-8"))


def test_the_tree_parser_drops_svg_decoration_but_keeps_the_markup_around_it() -> None:
    """SVG is the bulk of these documents and carries nothing addressable."""
    root = parse_tree('<div id="x"><svg><path d="M0 0"/></svg><span>kept</span></div>')

    from fundamentals.ingest.tijori_events_html import find_all, text_of

    assert not find_all(root, "path")
    assert text_of(root) == "kept"


def _anchor(**overrides: object) -> Provenance:
    """One HTML_TABLE anchor, for the foreign-field assertions below."""
    fields: dict[str, object] = {
        "source_id": "tijori",
        "file_sha256": "0" * 64,
        "anchor_type": SourceAnchorType.HTML_TABLE,
        "table_id": "html:upcoming-events/results",
        "row_path": "0/x",
        "column_index": 0,
        "column_label": "Company",
        "retrieved_at": datetime(2026, 8, 25, tzinfo=UTC),
    }
    fields.update(overrides)
    return Provenance(**fields)  # type: ignore[arg-type]


def test_an_html_table_anchor_may_not_borrow_an_api_documents_fields() -> None:
    """The anchor type IS the retrieval procedure; a mixed anchor is ambiguous."""
    with pytest.raises(ValueError, match="belong to a different anchor kind"):
        _anchor(document_id="api:something")
