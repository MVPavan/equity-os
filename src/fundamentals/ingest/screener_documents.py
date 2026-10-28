"""Identity-checked Screener document links; the exchange fetch rule grants authority."""

from collections.abc import Mapping
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict

from fundamentals.contracts.source_catalog import DocumentKind
from fundamentals.ingest.first_party_documents import DocumentLink
from fundamentals.ingest.screener_session_page import parse_document, read_identity

SECTION = '//section[@id="documents"]'
CHIPS = {"Transcript": DocumentKind.TRANSCRIPT, "PPT": DocumentKind.PRESENTATION}
SECTIONS = {
    "annual-reports": DocumentKind.ANNUAL_REPORT,
    "credit-ratings": DocumentKind.CREDIT_RATING,
}
CLASS = 'contains(concat(" ", normalize-space(@class), " "), " {name} ")'
SCREENER_HOSTS = {"www.screener.in", "screener.in"}


class ScreenerDocuments(BaseModel):
    """Discovered links, missing document chips and available recording count."""

    model_config = ConfigDict(frozen=True)
    links: tuple[DocumentLink, ...]
    absent: Mapping[DocumentKind, int]
    recordings: int


def read_screener_documents(page: bytes, *, expected_company_id: int) -> ScreenerDocuments:
    """Read document anchors only after the page proves its company identity."""
    root = parse_document(page.decode())
    if read_identity(root)[0] != expected_company_id:
        raise ValueError("refused screener identity")
    links = []
    absent = dict.fromkeys(CHIPS.values(), 0)
    recordings = 0
    for section, kind in SECTIONS.items():
        for anchor in root.xpath(f"{SECTION}//*[{CLASS.format(name=section)}]//li/a"):
            label = " ".join(anchor.text_content().split())
            links.append(
                (
                    kind,
                    label.split()[-1] if kind is DocumentKind.ANNUAL_REPORT else label,
                    anchor.get("href", ""),
                )
            )
    for row in root.xpath(f"{SECTION}//*[{CLASS.format(name='concalls')}]//li"):
        period = " ".join(row.xpath("./div[1]")[0].text_content().split())
        for anchor in row.xpath(f".//a[{CLASS.format(name='button-chip')}]"):
            label = anchor.text_content().strip()
            if label in CHIPS:
                links.append((CHIPS[label], period, anchor.get("href", "")))
            recordings += label == "REC"
        for chip in row.xpath(f".//div[{CLASS.format(name='button-chip')}]"):
            label = chip.text_content().strip()
            if label in CHIPS:
                absent[CHIPS[label]] += 1
    return ScreenerDocuments(
        links=tuple(
            DocumentLink(
                kind=kind,
                period=period,
                url=url,
                host=urlsplit(url).netloc,
                found_on="SCREENER_PAGE",
            )
            for kind, period, url in links
            if urlsplit(url).scheme in ("http", "https")
            and urlsplit(url).hostname not in SCREENER_HOSTS
        ),
        absent=absent,
        recordings=recordings,
    )
