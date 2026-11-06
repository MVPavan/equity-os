"""Code readers for vendor text surfaces: normalised text with each item's range and company."""

import re
from collections.abc import Callable, Iterable, Mapping, Sequence
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict

from equity_os.contracts.companies.entity_identity import IdentifierNamespace
from equity_os.extraction.vendors.screener.screener_session_page import (
    parse_document,
    read_identity,
)
from equity_os.sourcing.surfaces.vendor_surface_fetch import SITE_AUTHORITY, Site

ABOUT_XPATH = (
    '//div[contains(concat(" ",@class," ")," company-info ")]'
    '//div[contains(concat(" ",@class," ")," about ") or '
    'contains(concat(" ",@class," ")," commentary ")]//text()'
)
ANNOUNCEMENT_XPATH = '//ul[@class="list-links"]/li/a[@href]/text()'
FEED_ITEM_XPATH = '//div[contains(concat(" ",@class," ")," announcement-item ")]'
FEED_TEXT_XPATH = './/a[@href and not(starts-with(@href,"/company/"))]/text()'
FEED_COMPANY_XPATH = './/a[starts-with(@href,"/company/")]/@href'
SUMMARY_REGION_XPATH = (
    "/html/body/main/div[contains(concat(' ',normalize-space(@class),' '),' card ')]/article"
)
SUMMARY_COMPANY_XPATH = '/html/body/main/div[1]/ul/li/a[starts-with(@href,"/company/")]/@href'
UNSUPPORTED = "unsupported text surface"
WRONG_ADDRESS = "address does not match the text surface"


class CompanyRef(BaseModel):
    """The company an item names itself as, in one identifier namespace."""

    model_config = ConfigDict(frozen=True)
    namespace: IdentifierNamespace
    value: str


class TextItem(BaseModel):
    """Where one item's parts land in the reader text, end exclusive."""

    model_config = ConfigDict(frozen=True)
    start: int
    end: int
    company: CompanyRef


class ReaderText(BaseModel):
    """A reader's normalised text and its company-bound items."""

    model_config = ConfigDict(frozen=True)
    text: str
    items: tuple[TextItem, ...]


def _route(url: str, path: str) -> re.Match[str]:
    """The surface's route match on a Screener address, or ``ValueError``."""
    parts = urlsplit(url)
    match = re.fullmatch(path, parts.path)
    if parts.scheme != "https" or parts.netloc != SITE_AUTHORITY[Site.SCREENER] or not match:
        raise ValueError(WRONG_ADDRESS)
    return match


def _join(items: Iterable[tuple[Sequence[str], CompanyRef | None]]) -> ReaderText:
    """Whitespace-normalise each item's parts and lay the non-empty items end to end."""
    text, placed = "", []
    for parts, company in items:
        part = " ".join(" ".join(parts).split())
        if not part:
            continue
        start = len(text) + bool(text)
        text = f"{text} {part}" if text else part
        if company is not None:
            placed.append(TextItem(start=start, end=len(text), company=company))
    return ReaderText(text=text, items=tuple(placed))


def _slug(hrefs: Sequence[str]) -> CompanyRef | None:
    """The one ``/company/<slug>/`` the links name, or ``None`` when missing or ambiguous."""
    slugs = {href.split("/")[2] for href in hrefs}
    if len(slugs) != 1:
        return None
    return CompanyRef(namespace=IdentifierNamespace.SCREENER_SLUG, value=slugs.pop())


def company_page(body: bytes, url: str) -> ReaderText:
    """About and Key Points as one item bound by the page's own identity element."""
    _route(url, r"/company/[^/]+/(?:consolidated/)?")
    tree = parse_document(body.decode("utf-8"))
    company_id, _ = read_identity(tree)
    ref = CompanyRef(namespace=IdentifierNamespace.SCREENER_COMPANY_ID, value=str(company_id))
    return _join([(tree.xpath(ABOUT_XPATH), ref)])


def company_announcements(body: bytes, url: str) -> ReaderText:
    """Announcement subjects as one item bound by the company id in the registered address."""
    match = _route(url, r"/announcements/(?:recent|important|search)/([0-9]+)/")
    tree = parse_document(body.decode("utf-8"))
    ref = CompanyRef(namespace=IdentifierNamespace.SCREENER_COMPANY_ID, value=match[1])
    return _join([(tree.xpath(ANNOUNCEMENT_XPATH), ref)])


def announcements_feed(body: bytes, url: str) -> ReaderText:
    """One item per announcement, bound by its own company link."""
    _route(url, r"/announcements/(?:all/|results/)?")
    tree = parse_document(body.decode("utf-8"))
    return _join(
        (item.xpath(FEED_TEXT_XPATH), _slug(item.xpath(FEED_COMPANY_XPATH)))
        for item in tree.xpath(FEED_ITEM_XPATH)
    )


def concall_summary(body: bytes, url: str) -> ReaderText:
    """The summary article as one item bound by the breadcrumb's company link.

    A page with no summary region (a notice instead) reads as no text; nothing else is read.
    """
    _route(url, r"/concalls/summary/[0-9]+/")
    tree = parse_document(body.decode("utf-8"))
    regions = tree.xpath(SUMMARY_REGION_XPATH)
    if not regions:
        return ReaderText(text="", items=())
    [region] = regions
    [href] = tree.xpath(SUMMARY_COMPANY_XPATH)
    return _join([(region.xpath(".//text()"), _slug([href]))])


READERS: Mapping[tuple[Site, str], Callable[[bytes, str], ReaderText]] = {
    (Site.SCREENER, "company-page"): company_page,
    (Site.SCREENER, "company-announcements"): company_announcements,
    (Site.SCREENER, "announcements-feed"): announcements_feed,
    (Site.SCREENER, "concall-summary"): concall_summary,
}


def read_text(site: Site, surface: str, body: bytes, url: str) -> ReaderText:
    """Read one retained body through its surface's reader; ``ValueError`` if unsupported."""
    reader = READERS.get((site, surface))
    if reader is None:
        raise ValueError(UNSUPPORTED)
    return reader(body, url)
