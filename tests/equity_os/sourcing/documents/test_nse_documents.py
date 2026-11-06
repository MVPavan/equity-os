"""Retained NSE listings pin classifications, revisions and first-party fetch routes."""

import hashlib
import json
from collections import Counter
from datetime import date
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

PROBE = Path(__file__).resolve().parents[4] / "data/raw/watchlist/aparinds/docs-probe-2026-10-27"
PINS = {
    "nse_announcements.json": "356a548d67d9938305b3b592d3d0c45f79a386c46f0d9c23d2256dc7c9f77328",
    "nse_board_meetings.json": "c39e71c66fdb19149d9d0bf5c8450b6cc5ce73ec1bda983d1a3859c45f36c966",
    "nse_annual_reports.json": "3f0cc030b8f0512e08e49a5a83c9ba05db8d1baef7eb1a0a047e99c6b3cf16ed",
    "company_APARINDS_consolidated.html": (
        "9b82e3226e66a3ff1bdc368fe5b0c0bc65a2d40b8f96ad28b7e4c827f75d2abd"
    ),
}


def read_probe(name: str) -> bytes:
    """Read a retained original only if it matches its probe pin."""
    body = (PROBE / name).read_bytes()
    assert hashlib.sha256(body).hexdigest() == PINS[name], f"altered probe: {name}"
    return body


@pytest.mark.retained
def test_nse_listings_preserve_occurrences_and_classify_only_filed_documents() -> None:
    """Schedules/recordings stay observations; volatile clocks cannot create revisions."""
    from equity_os.sourcing.documents.first_party_documents import (
        classify_announcement,
        listing_rows,
        meeting_date,
        observed_link,
        stable_row,
    )

    announcements = read_probe("nse_announcements.json")
    rows = listing_rows("ANNOUNCEMENTS_LISTING", announcements)
    assert len(rows) == len({key for key, _ in rows}) == 41
    counts = Counter(str(classify_announcement(row)) for _, row in rows)
    expected = dict(
        TRANSCRIPT=1,
        CONCALL_SCHEDULE=2,
        CONCALL_RECORDING=1,
        PRESENTATION=2,
        CREDIT_RATING=1,
        RESULTS=1,
        CONCALL_UNRESOLVED=0,
    )
    assert {kind: counts[kind] for kind in expected} == expected
    for kind, filed in (("TRANSCRIPT", date(2026, 7, 31)), ("RESULTS", date(2026, 7, 24))):
        link = next(
            observed_link("ANNOUNCEMENTS_LISTING", row)
            for _, row in rows
            if classify_announcement(row) == kind
        )
        assert link is not None and link.filed_at is not None and link.filed_at.date() == filed
    assert all(
        link.host == "nsearchives.nseindia.com"
        for _, row in rows
        if (link := observed_link("ANNOUNCEMENTS_LISTING", row))
    )
    board = read_probe("nse_board_meetings.json")
    meetings = listing_rows("BOARD_MEETINGS_LISTING", board)
    assert len(meetings) == 6 and listing_rows("BOARD_MEETINGS_LISTING", board) == meetings
    assert [
        meeting_date(row)
        for _, row in meetings
        if row["bm_purpose"] == "Financial Results" and meeting_date(row) == date(2026, 10, 29)
    ] == [date(2026, 10, 29)]
    key, payload = meetings[0]
    assert (
        stable_row(payload | {"difference": "changed", "diff": "changed", "sysTime": "changed"})
        == payload
    )
    reports = [
        link
        for _, row in listing_rows("ANNUAL_REPORTS_LISTING", read_probe("nse_annual_reports.json"))
        if (link := observed_link("ANNUAL_REPORTS_LISTING", row))
    ]
    assert len(reports) == 17
    assert Counter(Path(urlsplit(link.url).path).suffix.lower() for link in reports) == {
        ".pdf": 3,
        ".zip": 14,
    }
    assert sorted((link.period for link in reports), reverse=True)[:5] == [
        "2026",
        "2025",
        "2024",
        "2023",
        "2022",
    ]


def test_unresolved_missing_sequence_and_non_exchange_links_fail_closed() -> None:
    """A familiar word outside the exact category cannot turn a notice into a transcript."""
    from equity_os.contracts.sourcing.source_catalog import DocumentKind
    from equity_os.sourcing.documents.first_party_documents import (
        DocumentLink,
        classify_announcement,
        document_request,
        listing_rows,
        nse_listing_url,
        observed_link,
    )

    row = dict(
        desc="Analysts/Institutional Investor Meet/Con. Call Updates",
        attchmntText="Issuer has informed the Exchange about Concall Transcript Submission",
    )
    assert classify_announcement(row) == "CONCALL_UNRESOLVED"
    assert observed_link("ANNOUNCEMENTS_LISTING", row) is None
    assert classify_announcement(row | {"desc": "Other"}) == "OTHER"
    with pytest.raises(ValueError):
        listing_rows("ANNOUNCEMENTS_LISTING", json.dumps([row]).encode())
    for host in ("www.careratings.com", "apar.com", "files.tijorifinance.com", "www.bseindia.com"):
        link = DocumentLink(
            kind=DocumentKind.TRANSCRIPT,
            period="Jul 2026",
            host=host,
            url=f"https://{host}/stockinfo/AnnPdfOpen.aspx?Pname=synthetic.pdf",
            found_on="screener",
        )
        request = document_request(link)
        if host == "www.bseindia.com":
            assert (
                request is not None
                and request.url
                == "https://www.bseindia.com/xml-data/corpfiling/AttachHis/synthetic.pdf"
            )
        else:
            assert request is None
    url = nse_listing_url("ANNOUNCEMENTS_LISTING", "SYNTH", date(2026, 1, 2), date(2026, 2, 1))
    assert parse_qs(urlsplit(url).query) == {
        "index": ["equities"],
        "symbol": ["SYNTH"],
        "from_date": ["02-01-2026"],
        "to_date": ["01-02-2026"],
    }


def test_results_are_recognised_under_both_nse_categories() -> None:
    """Apar's 2023-07..2025-01 results sit under 'Financial Result Updates'; missing them hid
    seven of thirteen quarters, while a board-meeting notice without results stays OTHER."""
    from equity_os.sourcing.documents.first_party_documents import classify_announcement

    text = "Issuer has submitted to the Exchange, the financial results for the period ended"
    for desc in ("Financial Result Updates", "Outcome of Board Meeting"):
        assert classify_announcement(dict(desc=desc, attchmntText=text)) == "RESULTS"
    notice = dict(desc="Outcome of Board Meeting", attchmntText="regarding Board meeting held")
    assert classify_announcement(notice) == "OTHER"
    assert classify_announcement(dict(desc="Press Release", attchmntText=text)) == "OTHER"


def test_presentations_are_recognised_by_attachment_text() -> None:
    """Apar files presentations under four categories (eqos-3ndm); a results filing that
    mentions one stays RESULTS, so its PDF still reaches results extraction."""
    from equity_os.sourcing.documents.first_party_documents import classify_announcement

    for desc, text in (
        ("Updates", "regarding 'Corporate Presentation - July, 2026'."),
        ("General Updates", "about Corporate Presentation May, 2025"),
        (
            "Analysts/Institutional Investor Meet/Con. Call Updates",
            "about Presentation and Link of Recording",
        ),
    ):
        assert classify_announcement(dict(desc=desc, attchmntText=text)) == "PRESENTATION"
    both = "the financial results and investor presentation for the period ended"
    row = dict(desc="Outcome of Board Meeting", attchmntText=both)
    assert classify_announcement(row) == "RESULTS"
