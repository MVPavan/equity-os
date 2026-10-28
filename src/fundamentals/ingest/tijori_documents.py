"""Identity-checked Tijori filings and read-time NSE corroboration (DOCS-1 A1)."""

import calendar
import hashlib
import zipfile
import zlib
from collections.abc import Sequence
from datetime import date, datetime, timedelta
from io import BytesIO
from typing import cast
from urllib.parse import quote, unquote, urlsplit, urlunsplit

from lxml import html  # type: ignore[import-untyped]

from fundamentals.contracts.onboarding import VerificationUnit
from fundamentals.contracts.source_catalog import TIJORI_KINDS, DocumentKind
from fundamentals.entity.discovery import Request
from fundamentals.ingest.first_party_documents import IST, DocumentLink
from fundamentals.ingest.tijori_overview_models import TijoriOverviewSection
from fundamentals.ingest.tijori_source import TijoriSource

TIJORI_SKIPPED = {"conference-call-summary"}
HOST = "files.tijorifinance.com"


def read_tijori_documents(
    page: bytes, *, slug: str, expected_symbol: str, expected_company_id: int
) -> tuple[DocumentLink, ...]:
    TijoriSource.parse_overview_bytes(
        page,
        slug=slug,
        expected_symbol=expected_symbol,
        expected_company_id=expected_company_id,
        section=TijoriOverviewSection.COMPANY_DETAILS,
    )
    tables = html.fromstring(page).xpath('//*[@id="companyFilings"]')
    if not tables or not any(c.text_content().strip() for c in tables[0].xpath("./tbody/tr/td[1]")):
        raise ValueError("missing companyFilings headings")
    years, found = tables[0].xpath("./thead/tr/th"), []
    for row in tables[0].xpath("./tbody/tr"):
        cells = row.xpath("./td")
        heading = cells[0].text_content().strip()
        if set(cells[0].get("class", "").split()) & TIJORI_SKIPPED:
            continue
        if row.xpath(".//a[@href]") and heading not in TIJORI_KINDS:
            raise ValueError("unknown filing heading")
        for index, cell in enumerate(cells):
            for anchor in cell.xpath(".//a[@href]"):
                url, kind = anchor.get("href"), TIJORI_KINDS[heading]
                segments = set(unquote(urlsplit(url).path).split("/"))
                prefix = f"https://{HOST}/insight/india/{expected_company_id}/"
                if not url.startswith(prefix) or segments & {".", ".."}:
                    raise ValueError("wrong company prefix")
                year, label = years[index].text_content().strip(), anchor.text_content().strip()
                period = year if kind == DocumentKind.ANNUAL_REPORT else f"{label} {year}"
                month = any(m in label.split() for m in calendar.month_abbr[1:])
                fmt = "%d %b %Y" if len(label.split()) == 2 else "%b %Y"
                filed = datetime.strptime(period, fmt).replace(tzinfo=IST) if month else None
                found.append((kind, period, url, filed))
    return tuple(
        DocumentLink(kind=k, period=p, url=u, host=HOST, found_on="tijori", filed_at=f)
        for k, p, u, f in found
    )


def tijori_document_request(link: DocumentLink) -> Request | None:
    parts = urlsplit(link.url)
    if parts.scheme != "https" or parts.netloc != HOST:
        return None
    return Request(
        unit=VerificationUnit.EXCHANGE,
        source_id="tijori-documents",
        surface=f"TIJORI_{link.kind}",
        url=urlunsplit(parts._replace(path=quote(parts.path, safe="/%"))),
    )


def zip_pdf_digests(body: bytes) -> tuple[tuple[str, str], ...] | None:
    try:
        digests, budget = [], 64 * 1024 * 1024
        with zipfile.ZipFile(BytesIO(body)) as archive:
            for member in archive.infolist():
                if member.flag_bits & 1:
                    return None
                if member.filename.lower().endswith(".pdf"):
                    budget -= member.file_size
                    if budget < 0:
                        return None
                    with archive.open(member) as stream:
                        digest = hashlib.file_digest(
                            cast(zipfile.ZipExtFile, stream), "sha256"
                        ).hexdigest()
                    digests.append((member.filename, digest))
        return tuple(digests)
    except (
        zipfile.BadZipFile,
        RuntimeError,
        NotImplementedError,
        EOFError,
        OSError,
        zlib.error,
        UnicodeDecodeError,
    ):
        return None


CITATIONS = (
    "CORROBORATED VENDOR_COPY AMBIGUOUS NSE_PENDING NSE_UNAVAILABLE "
    + "MISMATCH UNDATED ZIP_UNREADABLE"
).split()
CITABLE = {"CORROBORATED", "VENDOR_COPY"}
Candidate = tuple[int | None, str, tuple[tuple[str, str], ...]]


def cite(
    row_date: date | None,
    annual: bool,
    tijori_sha256: str,
    candidates: Sequence[Candidate],
    *,
    unresolved: bool,
    covered: bool,
) -> tuple[str, str]:
    if row_date is None:
        return "UNDATED", ""
    matches = sorted(
        (ref, name)
        for ref, _, digests in candidates
        for name, sha in digests
        if sha == tijori_sha256
    )
    if matches:
        ref, name = matches[0]
        return "CORROBORATED", f"{ref}" + (f":{name}" if name else "")
    historical = row_date < date(2023, 7, 1)
    if not candidates and (historical or not unresolved and covered):
        return "VENDOR_COPY", "nse-unlisted" if historical else "nse-none"
    if len(candidates) >= 2 or unresolved:
        return "AMBIGUOUS", ""
    state = candidates[0][1] if candidates else "PENDING"
    outcome = {"PENDING": "NSE_PENDING", "UNAVAILABLE": "NSE_UNAVAILABLE", "OK": "MISMATCH"}
    return outcome.get(state, state), ""


def reach(spans: Sequence[tuple[date, date]], start: date) -> date:
    """The first day from `start` that the joined spans do not cover."""
    for first, last in sorted(spans):
        if first > start:
            break
        start = max(start, last + timedelta(days=1))
    return start
