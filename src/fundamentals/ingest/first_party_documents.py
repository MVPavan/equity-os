"""Pure NSE document readers and exact-origin document requests (DOCS-1)."""

from __future__ import annotations

import json
import re
import sys
from datetime import date, datetime
from enum import StrEnum
from typing import Any
from urllib.parse import parse_qs, urlencode, urlsplit
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, TypeAdapter

from fundamentals.contracts.onboarding import VerificationUnit
from fundamentals.contracts.source_catalog import DOCUMENT_HOSTS, DOCUMENT_LISTINGS, DocumentKind
from fundamentals.entity.discovery import Request

VOLATILE_KEYS = ("difference", "diff", "sysTime")
CONCALL_CATEGORY = "Analysts/Institutional Investor Meet/Con. Call Updates"
NSE_API = "https://www.nseindia.com/api/"
ENDPOINTS = dict(
    zip(
        DOCUMENT_LISTINGS,
        ("corporate-announcements", "corporate-board-meetings", "annual-reports"),
        strict=True,
    )
)
NSE_HOST = DOCUMENT_HOSTS["nse-documents"]
BSE_HOST = DOCUMENT_HOSTS["bse-documents"]
IST = ZoneInfo("Asia/Kolkata")
NSE_TIME = "%d-%b-%Y %H:%M:%S"
NSE_DATE = "%d-%b-%Y"
ROWS = TypeAdapter(list[dict[str, Any]])
CONCALL_SUBJECTS = {
    "about transcript": "TRANSCRIPT",
    "about schedule of meet": "CONCALL_SCHEDULE",
    "about link of recording": "CONCALL_RECORDING",
}


class DocumentLink(BaseModel):
    """A source-labelled link, without authority to fetch or interpret it."""

    model_config = ConfigDict(frozen=True)
    kind: DocumentKind
    period: str
    url: str
    host: str
    found_on: str
    filed_at: datetime | None = None


class AnnouncementClass(StrEnum):
    """Document filings and the notice classes that must stay visible."""

    TRANSCRIPT = "TRANSCRIPT"
    PRESENTATION = "PRESENTATION"
    ANNUAL_REPORT = "ANNUAL_REPORT"
    CREDIT_RATING = "CREDIT_RATING"
    RESULTS = "RESULTS"
    CONCALL_SCHEDULE = "CONCALL_SCHEDULE"
    CONCALL_RECORDING = "CONCALL_RECORDING"
    CONCALL_UNRESOLVED = "CONCALL_UNRESOLVED"
    OTHER = "OTHER"


def classify_announcement(row: dict[str, Any]) -> AnnouncementClass:
    """Classify only the retained category/subject combinations; unfamiliar concalls abstain."""
    desc, text = row.get("desc", ""), " ".join(row.get("attchmntText", "").lower().split())
    if desc == CONCALL_CATEGORY:
        return next(
            (
                AnnouncementClass(kind)
                for subject, kind in CONCALL_SUBJECTS.items()
                if subject in text
            ),
            AnnouncementClass.CONCALL_UNRESOLVED,
        )
    if desc == "Investor Presentation":
        return AnnouncementClass.PRESENTATION
    if desc.startswith("Credit Rating"):
        return AnnouncementClass.CREDIT_RATING
    if desc == "Outcome of Board Meeting" and "financial results" in text:
        return AnnouncementClass.RESULTS
    return AnnouncementClass.OTHER


def announcement_link(row: dict[str, Any]) -> DocumentLink | None:
    """Only classified document filings with the exact NSE archive attachment host."""
    kind, url = classify_announcement(row), row.get("attchmntFile", "")
    if kind.value not in DocumentKind or urlsplit(url).netloc != NSE_HOST:
        return None
    filed = datetime.strptime(row["an_dt"], NSE_TIME).replace(tzinfo=IST)
    return DocumentLink(
        kind=DocumentKind(kind),
        period=row["an_dt"],
        url=url,
        host=NSE_HOST,
        found_on=DOCUMENT_LISTINGS[0],
        filed_at=filed,
    )


def stable_row(row: dict[str, Any]) -> dict[str, Any]:
    """Remove relative clocks before hashing a revision."""
    return {key: value for key, value in row.items() if key not in VOLATILE_KEYS}


def listing_rows(surface: str, body: bytes) -> list[tuple[str, dict[str, Any]]]:
    """Parse occurrence keys; a missing announcement sequence is visibly refused."""
    parsed = json.loads(body)
    rows = ROWS.validate_python(parsed["data"] if surface == DOCUMENT_LISTINGS[2] else parsed)
    result = []
    for row in rows:
        if surface == DOCUMENT_LISTINGS[0]:
            if not row.get("seq_id"):
                sys.stderr.write("refused announcement without seq_id\n")
                continue
            key = str(row["seq_id"])
        elif surface == DOCUMENT_LISTINGS[1]:
            key = "|".join(row[field] for field in ("bm_symbol", "bm_purpose", "bm_timestamp"))
        else:
            key = row["fileName"]
        result.append((key, stable_row(row)))
    return result


def meeting_date(payload: dict[str, Any]) -> date | None:
    """Read the board meeting's claimed date, separately from its broadcast timestamp."""
    raw = payload.get("bm_date")
    return datetime.strptime(raw, NSE_DATE).date() if raw else None


def annual_report_links(body: bytes) -> list[DocumentLink]:
    """One annual-report link per NSE entry, including retained ZIP originals."""
    return [
        DocumentLink(
            kind=DocumentKind.ANNUAL_REPORT,
            period=str(row["toYr"]),
            url=row["fileName"],
            host=urlsplit(row["fileName"]).netloc,
            found_on=DOCUMENT_LISTINGS[2],
        )
        for _, row in listing_rows(DOCUMENT_LISTINGS[2], body)
    ]


def nse_listing_url(surface: str, symbol: str, from_date: date, to_date: date) -> str:
    """The wrapper's documented listing route with inclusive calendar dates."""
    query = {"index": "equities", "symbol": symbol}
    if surface != DOCUMENT_LISTINGS[2]:
        query |= {
            "from_date": from_date.strftime("%d-%m-%Y"),
            "to_date": to_date.strftime("%d-%m-%Y"),
        }
    return NSE_API + ENDPOINTS[surface] + "?" + urlencode(query)


def document_request(link: DocumentLink) -> Request | None:
    """Map only exact HTTPS exchange hosts; AnnPdfOpen names an AttachHis PDF."""
    parts, url = urlsplit(link.url), link.url
    source = next((source for source, host in DOCUMENT_HOSTS.items() if parts.netloc == host), None)
    if parts.scheme != "https" or source is None:
        return None
    if parts.netloc == BSE_HOST and parts.path == "/stockinfo/AnnPdfOpen.aspx":
        name = parse_qs(parts.query).get("Pname", [""])[0]
        if not re.fullmatch(r"[\w.-]+\.pdf", name):
            return None
        url = f"https://{BSE_HOST}/xml-data/corpfiling/AttachHis/{name}"
    return Request(
        unit=VerificationUnit.EXCHANGE,
        source_id=source,
        surface=f"{source[:3].upper()}_{link.kind}",
        url=url,
    )
