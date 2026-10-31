"""Pure NSE document readers and exact-origin document requests (DOCS-1)."""

from __future__ import annotations

import json
import re
from datetime import date, datetime
from enum import StrEnum
from typing import Any
from urllib.parse import parse_qs, urlencode, urlsplit
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict

from fundamentals.contracts.onboarding import VerificationUnit
from fundamentals.contracts.source_catalog import (
    DOCUMENT_HOSTS,
    DOCUMENT_LISTINGS,
    SCREENER_PAGE,
    TIJORI_OVERVIEW,
    DocumentKind,
)
from fundamentals.entity.discovery import Request

ANNOUNCEMENTS, MEETINGS, REPORTS = DOCUMENT_LISTINGS
VOLATILE_KEYS = ("difference", "diff", "sysTime")
MEETING_KEY = ("bm_symbol", "bm_purpose", "bm_timestamp")
CONCALL_CATEGORY = "Analysts/Institutional Investor Meet/Con. Call Updates"
CONCALL_SUBJECTS = {
    "about transcript": "TRANSCRIPT",
    "about schedule of meet": "CONCALL_SCHEDULE",
    "about link of recording": "CONCALL_RECORDING",
}
RESULTS_CATEGORIES = frozenset({"Outcome of Board Meeting", "Financial Result Updates"})
NSE_API = "https://www.nseindia.com/api/"
ENDPOINTS = {
    ANNOUNCEMENTS: "corporate-announcements",
    MEETINGS: "corporate-board-meetings",
    REPORTS: "annual-reports",
}
NSE_HOST = DOCUMENT_HOSTS["nse-documents"]
BSE_HOST = DOCUMENT_HOSTS["bse-documents"]
ANN_PDF_OPEN = "/stockinfo/AnnPdfOpen.aspx"
IST = ZoneInfo("Asia/Kolkata")
NSE_TIME = "%d-%b-%Y %H:%M:%S"
NSE_DATE = "%d-%b-%Y"


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
        found = (kind for subject, kind in CONCALL_SUBJECTS.items() if subject in text)
        return AnnouncementClass(next(found, AnnouncementClass.CONCALL_UNRESOLVED))
    if desc == "Investor Presentation":
        return AnnouncementClass.PRESENTATION
    if desc.startswith("Credit Rating"):
        return AnnouncementClass.CREDIT_RATING
    # NSE files the same results under either category (Apar: "Financial Result Updates"
    # until Jan 2025, "Outcome of Board Meeting" since).
    if desc in RESULTS_CATEGORIES and "financial results" in text:
        return AnnouncementClass.RESULTS
    return AnnouncementClass.OTHER


def observed_link(surface: str, payload: dict[str, Any]) -> DocumentLink | None:
    """The document an observed revision names: filed NSE archive attachments, annual-report
    entries and Screener links; board-meeting notices and other filings name none."""
    if surface in (SCREENER_PAGE[1], TIJORI_OVERVIEW[1]):
        return DocumentLink.model_validate(payload)
    if surface == REPORTS:
        url = payload["fileName"]
        return DocumentLink(
            kind=DocumentKind.ANNUAL_REPORT,
            period=str(payload["toYr"]),
            url=url,
            host=urlsplit(url).netloc,
            found_on=surface,
        )
    kind, url = classify_announcement(payload), payload.get("attchmntFile", "")
    if surface != ANNOUNCEMENTS or kind not in DocumentKind or urlsplit(url).netloc != NSE_HOST:
        return None
    return DocumentLink(
        kind=DocumentKind(kind),
        period=payload["an_dt"],
        url=url,
        host=NSE_HOST,
        found_on=surface,
        filed_at=datetime.strptime(payload["an_dt"], NSE_TIME).replace(tzinfo=IST),
    )


def stable_row(row: dict[str, Any]) -> dict[str, Any]:
    """Remove relative clocks before hashing a revision."""
    return {key: value for key, value in row.items() if key not in VOLATILE_KEYS}


def listing_rows(surface: str, body: bytes) -> list[tuple[str, dict[str, Any]]]:
    """Occurrence key and stable payload per row; an announcement without a sequence refuses
    the listing, so its span never proves absence."""
    parsed = json.loads(body)
    rows: list[dict[str, Any]] = parsed["data"] if surface == REPORTS else parsed
    if surface == ANNOUNCEMENTS:
        if not all(row.get("seq_id") for row in rows):
            raise ValueError("announcement without seq_id")
        return [(str(row["seq_id"]), stable_row(row)) for row in rows]
    if surface == REPORTS:
        return [(row["fileName"], stable_row(row)) for row in rows]
    return [("|".join(row[field] for field in MEETING_KEY), stable_row(row)) for row in rows]


def meeting_date(payload: dict[str, Any]) -> date | None:
    """Read the board meeting's claimed date, separately from its broadcast timestamp."""
    raw = payload.get("bm_date")
    return datetime.strptime(raw, NSE_DATE).date() if raw else None


def nse_listing_url(surface: str, symbol: str, from_date: date, to_date: date) -> str:
    """The wrapper's documented listing route with inclusive calendar dates."""
    query = {"index": "equities", "symbol": symbol}
    if surface != REPORTS:
        query |= {
            "from_date": from_date.strftime("%d-%m-%Y"),
            "to_date": to_date.strftime("%d-%m-%Y"),
        }
    return NSE_API + ENDPOINTS[surface] + "?" + urlencode(query)


def document_request(link: DocumentLink) -> Request | None:
    """Map only exact HTTPS exchange hosts; AnnPdfOpen names an AttachHis PDF."""
    parts, url = urlsplit(link.url), link.url
    source = next((s for s, host in DOCUMENT_HOSTS.items() if parts.netloc == host), None)
    if parts.scheme != "https" or source is None:
        return None
    if parts.netloc == BSE_HOST and parts.path == ANN_PDF_OPEN:
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
