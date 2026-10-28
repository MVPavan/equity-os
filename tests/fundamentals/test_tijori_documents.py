"""A1 retained listing, citation precedence and ZIP identity."""

import hashlib
from collections import Counter
from datetime import date
from io import BytesIO
from pathlib import Path
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from fundamentals.ingest.first_party_documents import document_request
from fundamentals.ingest.tijori_overview_models import TijoriOverviewIdentityError

PAGE = Path(
    "data/raw/watchlist/aparinds/docs-probe-2026-10-28/tijori_company_apar-industries-limited.html"
)
PIN = "f74e03710fcaa9ecce34ab23a4a7a47e3c83559692602d22295005377d786969"
DAY = date(2026, 7, 1)


def page() -> bytes:
    body = PAGE.read_bytes()
    assert hashlib.sha256(body).hexdigest() == PIN
    return body


@pytest.mark.retained
def test_reader() -> None:
    from lxml import html  # type: ignore[import-untyped]

    from fundamentals.ingest.tijori_documents import read_tijori_documents, tijori_document_request

    identity: dict[str, Any] = dict(
        slug="apar-industries-limited", expected_symbol="APARINDS", expected_company_id=4290
    )
    links = read_tijori_documents(page(), **identity)
    assert Counter(str(x.kind) for x in links) == dict(
        ANNUAL_REPORT=16, RESULTS=14, PRESENTATION=52, TRANSCRIPT=53
    )
    for kind, first in [("ANNUAL_REPORT", 2011), ("TRANSCRIPT", 2010)]:
        years = [int(x.period[-4:]) for x in links if x.kind == kind]
        assert (min(years), max(years)) == (first, 2026)
    assert all(
        x.url.startswith("https://files.tijorifinance.com/insight/india/4290/")
        and tijori_document_request(x)
        and document_request(x) is None
        for x in links
    )
    for key, value in [("expected_symbol", "APARIND"), ("expected_company_id", 4291)]:
        with pytest.raises(TijoriOverviewIdentityError):
            read_tijori_documents(page(), **(identity | {key: value}))
    prefix = "https://files.tijorifinance.com/insight/india/4291/a.pdf"
    for markup in [
        "<div/>",
        '<table id="companyFilings"><tbody><tr><td>Annual Report'
        f'<a href="{prefix}">FY26</a></td></tr></tbody></table>',
    ]:
        tree = html.fromstring(page())
        table = tree.xpath('//*[@id="companyFilings"]')[0]
        table.getparent().replace(table, html.fromstring(markup))
        with pytest.raises(ValueError):
            read_tijori_documents(html.tostring(tree), **identity)


@pytest.mark.parametrize(
    ("when", "states", "covered", "unresolved", "expected", "reason"),
    [
        (None, "", True, False, "UNDATED", ""),
        ("2022-01-01", "", False, False, "VENDOR_COPY", "nse-unlisted"),
        ("2026-07-01", "", True, False, "VENDOR_COPY", "nse-none"),
        ("2026-07-01", "", False, False, "NSE_PENDING", ""),
        ("2026-07-01", "PENDING,OK", True, False, "AMBIGUOUS", ""),
        ("2026-07-01", "", True, True, "AMBIGUOUS", ""),
        ("2022-01-01", "PENDING", True, False, "NSE_PENDING", ""),
        ("2022-01-01", "UNAVAILABLE", True, False, "NSE_UNAVAILABLE", ""),
        ("2022-01-01", "ZIP_UNREADABLE", True, False, "ZIP_UNREADABLE", ""),
        ("2022-01-01", "OK", True, False, "MISMATCH", ""),
    ],
)
def test_precedence(
    when: str | None, states: str, covered: bool, unresolved: bool, expected: str, reason: str
) -> None:
    from fundamentals.ingest.tijori_documents import cite

    candidates = [(None, s, ()) for s in states.split(",") if s]
    day = date.fromisoformat(when) if when else None
    result = cite(day, False, "same", candidates, unresolved=unresolved, covered=covered)
    assert result == (expected, reason)


def test_zip_matching_permutation_and_interval() -> None:
    from fundamentals.ingest.tijori_documents import cite, reach, zip_pdf_digests

    sha = hashlib.sha256(b"%PDF-same").hexdigest()
    stream = BytesIO()
    with ZipFile(stream, "w") as archive:
        archive.writestr("report.pdf", b"%PDF-same")
    members = zip_pdf_digests(stream.getvalue())
    assert members == (("report.pdf", sha),) and zip_pdf_digests(b"bad") is None
    candidates = [(n, "OK", members) for n in (8, 3)]
    for order in (candidates, candidates[::-1]):
        result = cite(DAY, True, sha, order, unresolved=True, covered=False)
        assert result == ("CORROBORATED", "3:report.pdf")
    result = cite(DAY, True, "different", candidates[:1], unresolved=False, covered=True)
    assert result == ("MISMATCH", "")
    for end, expected in [(7, "NSE_PENDING"), (8, "VENDOR_COPY")]:
        covered = reach([(date(2026, 6, 24), date(2026, 7, end))], date(2026, 6, 24)) > date(
            2026, 7, 8
        )
        assert cite(DAY, False, sha, [], unresolved=False, covered=covered)[0] == expected


@pytest.mark.retained
@pytest.mark.parametrize("path", ["4290/../4291/a.pdf", "4290/%2e%2E/4291/a.pdf", "4290/./a.pdf"])
def test_reader_refuses_dot_segments(path: str) -> None:
    """A link that leaves the company's folder after the prefix is another company's file."""
    from lxml import html

    from fundamentals.ingest.tijori_documents import read_tijori_documents

    tree = html.fromstring(page())
    tree.xpath('//*[@id="companyFilings"]//a[@href]')[0].set(
        "href", f"https://files.tijorifinance.com/insight/india/{path}"
    )
    with pytest.raises(ValueError, match="wrong company prefix"):
        read_tijori_documents(
            html.tostring(tree),
            slug="apar-industries-limited",
            expected_symbol="APARINDS",
            expected_company_id=4290,
        )


def test_zip_with_undecodable_member_name_is_unreadable() -> None:
    """A corrupt member name is one unreadable candidate, not a failed pass."""
    from fundamentals.ingest.tijori_documents import zip_pdf_digests

    stream = BytesIO()
    with ZipFile(stream, "w") as archive:
        archive.writestr("\u00e9.pdf", b"%PDF-same")
    assert zip_pdf_digests(stream.getvalue().replace("\u00e9".encode(), b"\xff\xfe")) is None


def test_zip_over_total_decompression_budget_is_unreadable() -> None:
    """Small members that together inflate past the archive budget are one unreadable candidate."""
    from fundamentals.ingest.tijori_documents import zip_pdf_digests

    stream = BytesIO()
    with ZipFile(stream, "w", ZIP_DEFLATED) as archive:
        for index in range(9):
            archive.writestr(f"{index}.pdf", bytes(8 * 1024 * 1024))
    assert len(stream.getvalue()) < 200_000 and zip_pdf_digests(stream.getvalue()) is None
