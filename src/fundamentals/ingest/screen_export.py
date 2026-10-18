"""Export one owner-saved screen from Screener (CSV) and Tijori (JSON) (amendment 2026-10-18).

Requests only the amendment's endpoints: Screener ``/explore/``, the saved screen page and that
page's one export form; Tijori's owner saved-query listing and ``advanced_search`` with the
stored query. Every check refuses with :class:`ScreenExportError` before anything is returned,
so a caller never holds a partial export. Values stay vendor text; nothing here interprets them.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from collections.abc import Callable
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlencode, urljoin

import yaml
from pydantic import BaseModel, ConfigDict

from fundamentals.ingest.http_session import RequestPacer
from fundamentals.ingest.screener_session import ScreenerSessionSource
from fundamentals.ingest.screener_session_models import (
    SCREENER_ORIGIN,
    ScreenerCredentials,
    ScreenerDocumentFetch,
    ScreenerSessionConfig,
)
from fundamentals.ingest.screener_session_page import assert_logged_in, parse_document
from fundamentals.ingest.screener_watchlist import cookie_state, export_form, read_watchlist_export
from fundamentals.ingest.screener_watchlist_models import CSRF_FORM_FIELD
from fundamentals.ingest.tijori_source import TijoriCredentials, TijoriSource, TijoriSourceConfig

SPACING_SECONDS = 2.0
ISIN_COLUMN = "ISIN Code"
EXPLORE_URL = f"{SCREENER_ORIGIN}/explore/"
TIJORI_LISTING_PATH = "/api/filter_queries/search/?owner=true&limit=100&offset=0"
TIJORI_RESULTS_PATH = "/api/filter_queries/advanced_search/"
# The flags the probe's saved-query run sent (filters.js defaults, checkboxes off).
TIJORI_FLAGS = {"is_checked": "False", "whales": "False", "is_sme": "False"}
TIJORI_SOURCE_NAME = "Advanced"
_YOUR_SCREENS = (
    ".//*[h2[normalize-space()='Your screens']]"
    "//a[contains(concat(' ', normalize-space(@class), ' '), ' screen-item ')]"
)
_SCREEN_LINK = re.compile(r"^/screens/[1-9][0-9]*/([^/]+)/$")
_DEFINITION = ".//textarea[@name='query']"
_PAGE_INFO = ".//*[@data-page-info]"
_RESULT_COUNT = re.compile(r"^([0-9]+) results? found")

_MATCHES = "{vendor} lists {count} saved screens named {name!r}, not exactly one"
_STATUS = "screener page returned HTTP {status}, not 200"
_ONE_DEFINITION = "screener screen page renders {count} query definitions, not exactly one"
_NO_COUNT = "screener screen page states no result count"
_COUNT_DIFFERS = "{vendor} states {stated} results but returned {rows} rows"
_NO_ISIN = "screener export has no ISIN Code column"
_TRUNCATED = "tijori saved-query listing is truncated (count {count}, {rows} returned, next {next})"
_NOT_ROWS = "tijori results carry no list of row objects"


class ScreenExportError(ValueError):
    """A vendor response is not the complete export of exactly one saved screen."""


class ScreenVendor(StrEnum):
    """The vendor a screen run was exported from."""

    SCREENER = "SCREENER"
    TIJORI = "TIJORI"


class ScreenConfig(BaseModel):
    """One configured screen: its Screener saved-screen slug and Tijori saved-query name."""

    model_config = ConfigDict(frozen=True)

    name: str
    screener: str
    tijori: str


class ScreenFetch(BaseModel):
    """One retained response: the URL requested, its bytes and when they arrived."""

    model_config = ConfigDict(frozen=True)

    url: str
    body: bytes
    retrieved_at: datetime


class VendorExport(BaseModel):
    """One vendor's export: the definition as fetched, both responses and the rows as text."""

    model_config = ConfigDict(frozen=True)

    vendor: ScreenVendor
    screen_text: str
    definition: ScreenFetch
    results: ScreenFetch
    rows: tuple[dict[str, str], ...]


def load_screen_config(path: Path) -> dict[str, ScreenConfig]:
    """The configured screens by name; a repeated name refuses."""
    screens = [ScreenConfig.model_validate(entry) for entry in yaml.safe_load(path.read_text())]
    repeated = [name for name, n in Counter(s.name for s in screens).items() if n > 1]
    if repeated:
        raise ScreenExportError(f"{path} repeats screen names {repeated}")
    return {screen.name: screen for screen in screens}


def screen_sources(
    screener: ScreenerCredentials | None, tijori: TijoriCredentials | None
) -> tuple[ScreenerSessionSource, TijoriSource]:
    """Both transports as the export uses them: Screener paced per attempt, Tijori not retried."""
    return (
        ScreenerSessionSource(
            ScreenerSessionConfig(credentials=screener, min_request_spacing_seconds=SPACING_SECONDS)
        ),
        TijoriSource(TijoriSourceConfig(credentials=tijori, max_retries=1)),
    )


def export_screener(source: ScreenerSessionSource, slug: str) -> VendorExport:
    """Find ``slug`` among the owner's screens, read its definition and count, POST its export."""
    explore = _logged_in_page(source, EXPLORE_URL)[1]
    hrefs = [link.get("href") or "" for link in explore.xpath(_YOUR_SCREENS)]
    paths = [href for href in hrefs if (m := _SCREEN_LINK.match(href)) and m.group(1) == slug]
    _one(paths, ScreenVendor.SCREENER, slug)
    page_url = SCREENER_ORIGIN + paths[0]
    page, root, set_cookies = _logged_in_page(source, page_url)
    definitions = root.xpath(_DEFINITION)
    if len(definitions) != 1:
        raise ScreenExportError(_ONE_DEFINITION.format(count=len(definitions)))
    stated = [m for e in root.xpath(_PAGE_INFO) if (m := _RESULT_COUNT.match(_text(e)))]
    if len(stated) != 1:
        raise ScreenExportError(_NO_COUNT)
    action, token = export_form(root)
    url = urljoin(page_url, action)
    export, content_type, disposition = source.post_form(
        url=url,
        fields={CSRF_FORM_FIELD: token},
        referer=page_url,
        cookies=cookie_state(set_cookies),
    )
    header, records = read_watchlist_export(
        export.raw_body,
        http_status=export.http_status,
        content_type=content_type,
        content_disposition=disposition,
    )
    if ISIN_COLUMN not in header:
        raise ScreenExportError(_NO_ISIN)
    _same_count(ScreenVendor.SCREENER, int(stated[0].group(1)), len(records))
    return VendorExport(
        vendor=ScreenVendor.SCREENER,
        screen_text=f"screener:{definitions[0].text_content()}",
        definition=_screen_fetch(page),
        results=_screen_fetch(export),
        rows=tuple(dict(zip(header, record, strict=True)) for record in records),
    )


def export_tijori(
    source: TijoriSource, name: str, *, pacer: RequestPacer | None = None
) -> VendorExport:
    """Find saved query ``name`` in the owner's listing and fetch its results, one attempt each."""
    wait = (pacer or RequestPacer(SPACING_SECONDS)).wait_for_slot
    base = source.config.base_url
    listing = _json_fetch(source, base + TIJORI_LISTING_PATH, wait)
    listed = json.loads(listing.body)
    entries = listed["results"]
    if listed["next"] is not None or listed["count"] != len(entries):
        raise ScreenExportError(
            _TRUNCATED.format(count=listed["count"], rows=len(entries), next=listed["next"])
        )
    matched = [entry for entry in entries if entry["name"] == name]
    _one(matched, ScreenVendor.TIJORI, name)
    query = {key: matched[0][key] for key in ("financial_query", "alt_query", "extra_cols")}
    columns = query["extra_cols"]
    params = {"financial": query["financial_query"], **TIJORI_FLAGS}
    if columns:
        params["columns"] = columns if isinstance(columns, str) else ",".join(columns)
    if query["alt_query"]:
        params["alternate"] = query["alt_query"]
    params |= {"source": TIJORI_SOURCE_NAME, "query_id": str(matched[0]["id"])}
    url = f"{base}{TIJORI_RESULTS_PATH}?{urlencode(params, quote_via=quote)}"
    results = _json_fetch(source, url, wait)
    payload = json.loads(results.body)
    data = payload.get("data")
    if not isinstance(data, list) or not all(isinstance(row, dict) for row in data):
        raise ScreenExportError(_NOT_ROWS)
    _same_count(ScreenVendor.TIJORI, payload.get("total_results"), len(data))
    text = json.dumps(query, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return VendorExport(
        vendor=ScreenVendor.TIJORI,
        screen_text=f"tijori:{text}",
        definition=listing,
        results=results,
        rows=tuple({key: _cell(value) for key, value in row.items()} for row in data),
    )


def _logged_in_page(
    source: ScreenerSessionSource, url: str
) -> tuple[ScreenerDocumentFetch, Any, tuple[str, ...]]:
    """GET one Screener page that must be a logged-in 200; its fetch, tree and cookies."""
    fetch, set_cookies = source.fetch_navigation(url=url)
    if fetch.http_status != 200:
        raise ScreenExportError(_STATUS.format(status=fetch.http_status))
    root = parse_document(fetch.raw_body.decode("utf-8", errors="replace"))
    assert_logged_in(root)
    return fetch, root, set_cookies


def _json_fetch(source: TijoriSource, url: str, wait: Callable[[], None]) -> ScreenFetch:
    """One paced Tijori JSON request."""
    wait()
    body = source.fetch_json(url)
    return ScreenFetch(url=url, body=body, retrieved_at=datetime.now(UTC))


def _one(matches: list[Any], vendor: ScreenVendor, name: str) -> None:
    """Refuse unless exactly one saved screen carries ``name``."""
    if len(matches) != 1:
        raise ScreenExportError(_MATCHES.format(vendor=vendor, count=len(matches), name=name))


def _same_count(vendor: ScreenVendor, stated: object, rows: int) -> None:
    """Refuse an export whose rows differ from the vendor's own result count."""
    if stated != rows:
        raise ScreenExportError(_COUNT_DIFFERS.format(vendor=vendor, stated=stated, rows=rows))


def _screen_fetch(fetch: ScreenerDocumentFetch) -> ScreenFetch:
    """A Screener response as a retained fetch."""
    return ScreenFetch(url=fetch.source_url, body=fetch.raw_body, retrieved_at=fetch.fetched_at)


def _text(element: Any) -> str:
    """An element's text with whitespace collapsed."""
    return " ".join(element.text_content().split())


def _cell(value: object) -> str:
    """A JSON cell as text: ``null`` is empty, everything else verbatim."""
    return "" if value is None else str(value)
