"""Run one owner-authored screen formula at Screener (CSV) and Tijori (JSON) (amendment 2026-10-18).

Requests only the amendment's endpoints: Screener's raw-query page for the formula and that page's
one export form; Tijori's ``advanced_search`` for the formula. Each vendor's echo of the formula
must equal the configured one, and every check refuses with :class:`ScreenExportError` before
anything is returned, so a caller never holds a partial export. Values stay vendor text.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from collections.abc import Sequence
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, quote, urlencode, urljoin, urlsplit

import yaml
from pydantic import BaseModel, ConfigDict, TypeAdapter

from fundamentals.ingest.http_session import RequestPacer
from fundamentals.ingest.screener_session import ScreenerSessionSource
from fundamentals.ingest.screener_session_models import (
    SCREENER_ORIGIN,
    ScreenerCredentials,
    ScreenerDocumentFetch,
    ScreenerSessionConfig,
)
from fundamentals.ingest.screener_session_page import assert_logged_in, parse_document
from fundamentals.ingest.screener_watchlist import (
    cookie_state,
    export_form,
    read_export_csv,
    read_watchlist_export,
)
from fundamentals.ingest.screener_watchlist_models import (
    CSRF_FORM_FIELD,
    EXPORT_PATH,
)
from fundamentals.ingest.tijori_screen_fetch import fetch_json
from fundamentals.ingest.tijori_source import TijoriCredentials, TijoriSource, TijoriSourceConfig

SPACING_SECONDS = 2.0
ISIN_COLUMN = "ISIN Code"
SCREENER_RAW_PATH = "/screen/raw/"
QUERY_KEY, URL_NAME_KEY, RAW_QUERY_URL_NAME = "query", "url_name", "raw_query"
_ACTION_KEYS = (QUERY_KEY, URL_NAME_KEY)
TIJORI_RESULTS_PATH = "/api/filter_queries/advanced_search/"
TIJORI_FORMULA_KEY = "financial"
# The flags the probe's run sent (filters.js defaults, checkboxes off).
TIJORI_FLAGS = {"is_checked": "False", "whales": "False", "is_sme": "False"}
_ECHO = ".//textarea[@name='query']"
_PAGE_INFO = ".//*[@data-page-info]"
_RESULT_COUNT = re.compile(r"^([0-9]+) results? found")

HTML_MEDIA_TYPE = "text/html"

_EMPTY = "screen formula is empty"
_BLANK = "{path} has a screen with a blank name or formula"
_STATUS = "screener page returned HTTP {status} {media_type}, not a 200 text/html page"
_ECHO_DIFFERS = "screener page echoes {count} query definitions, not exactly the formula"
_NO_COUNT = "screener page states no single result count"
_ACTION_DIFFERS = "screener export action is not exactly the formula's raw-query export"
_COUNT_DIFFERS = "{vendor} states {stated} results but returned {rows} rows"
_NO_ISIN = "screener export has no ISIN Code column"
_REPEATED_COLUMNS = "screener export repeats columns {columns}"
_NOT_ROWS = "tijori results carry no list of row objects"
_TIJORI_ECHO_DIFFERS = "tijori results do not echo exactly the formula"


class ScreenExportError(ValueError):
    """A vendor response is not the complete export of exactly the configured formula."""


class ScreenVendor(StrEnum):
    """The vendor a screen run was exported from."""

    SCREENER = "SCREENER"
    TIJORI = "TIJORI"


class ScreenConfig(BaseModel):
    """One configured screen: its owner-authored Screener and Tijori formulas."""

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
    """One vendor's export: the formula, the definition and results responses, rows as text."""

    model_config = ConfigDict(frozen=True)

    vendor: ScreenVendor
    screen_text: str
    definition: ScreenFetch
    results: ScreenFetch


def load_screen_config(path: Path) -> dict[str, ScreenConfig]:
    """The configured screens by name; a blank field or a repeated name refuses."""
    try:
        loaded = yaml.safe_load(path.read_text())
    except yaml.YAMLError as error:
        raise ScreenExportError(f"{path} is not valid YAML") from error
    screens = TypeAdapter(list[ScreenConfig]).validate_python(loaded)
    if not all(_normal(s.name) and _normal(s.screener) and _normal(s.tijori) for s in screens):
        raise ScreenExportError(_BLANK.format(path=path))
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


def export_screener(source: ScreenerSessionSource, formula: str) -> VendorExport:
    """Run ``formula`` on Screener's raw-query page, check its echo and count, POST its export."""
    wanted = _formula(formula)
    page_url = f"{SCREENER_ORIGIN}{SCREENER_RAW_PATH}?{urlencode({QUERY_KEY: formula})}"
    page, root, set_cookies = _logged_in_page(source, page_url)
    echoes = root.xpath(_ECHO)
    if len(echoes) != 1 or _normal(echoes[0].text_content()) != wanted:
        raise ScreenExportError(_ECHO_DIFFERS.format(count=len(echoes)))
    stated = [
        m for e in root.xpath(_PAGE_INFO) if (m := _RESULT_COUNT.match(_normal(e.text_content())))
    ]
    if len(stated) != 1:
        raise ScreenExportError(_NO_COUNT)
    action, token = export_form(root)
    parts = urlsplit(action)
    query = parse_qsl(parts.query, keep_blank_values=True)
    values = dict(query)
    if (
        (parts.scheme, parts.netloc, parts.path, parts.fragment) != ("", "", EXPORT_PATH, "")
        or sorted(key for key, _ in query) != sorted(_ACTION_KEYS)
        or _normal(values[QUERY_KEY]) != wanted
        or values[URL_NAME_KEY] != RAW_QUERY_URL_NAME
    ):
        raise ScreenExportError(_ACTION_DIFFERS)
    export, content_type, disposition = source.post_form(
        url=urljoin(page_url, action),
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
    _columns(header)
    _same_count(ScreenVendor.SCREENER, int(stated[0].group(1)), len(records))
    return VendorExport(
        vendor=ScreenVendor.SCREENER,
        screen_text=f"screener:{formula}",
        definition=_screen_fetch(page),
        results=_screen_fetch(export),
    )


def export_tijori(
    source: TijoriSource, formula: str, *, pacer: RequestPacer | None = None
) -> VendorExport:
    """Run ``formula`` in Tijori's advanced search, one attempt; the response echoes it."""
    wanted = _formula(formula)
    params = urlencode({TIJORI_FORMULA_KEY: formula, **TIJORI_FLAGS}, quote_via=quote)
    url = f"{source.config.base_url}{TIJORI_RESULTS_PATH}?{params}"
    (pacer or RequestPacer(SPACING_SECONDS)).wait_for_slot()
    results = ScreenFetch(url=url, body=fetch_json(source, url), retrieved_at=datetime.now(UTC))
    payload = json.loads(results.body)
    if not isinstance(payload, dict):
        raise ScreenExportError(_NOT_ROWS)
    data = payload.get("data")
    if not isinstance(data, list) or not all(isinstance(row, dict) for row in data):
        raise ScreenExportError(_NOT_ROWS)
    _same_count(ScreenVendor.TIJORI, payload.get("total_results"), len(data))
    echo, alternate = payload.get("financial_q"), payload.get("alternate_q")
    if not isinstance(echo, str) or _normal(echo) != wanted or alternate not in (None, ""):
        raise ScreenExportError(_TIJORI_ECHO_DIFFERS)
    return VendorExport(
        vendor=ScreenVendor.TIJORI,
        screen_text=f"tijori:{formula}",
        definition=results,
        results=results,
    )


def result_rows(vendor: ScreenVendor, body: bytes) -> tuple[dict[str, str], ...]:
    """A results capture's rows as text, in export order (a member's row number)."""
    if vendor is ScreenVendor.TIJORI:
        data = json.loads(body, parse_float=str)["data"]
        return tuple({key: _cell(value) for key, value in row.items()} for row in data)
    header, records = read_export_csv(body)
    _columns(header)
    return tuple(dict(zip(header, record, strict=True)) for record in records)


def _logged_in_page(
    source: ScreenerSessionSource, url: str
) -> tuple[ScreenerDocumentFetch, Any, tuple[str, ...]]:
    """GET one Screener page that must be a logged-in 200 HTML page; its fetch, tree and
    cookies."""
    fetch, set_cookies, content_type = source.fetch_navigation(url=url)
    media_type = (content_type or "").split(";", 1)[0].strip().lower()
    if fetch.http_status != 200 or media_type != HTML_MEDIA_TYPE:
        raise ScreenExportError(_STATUS.format(status=fetch.http_status, media_type=media_type))
    root = parse_document(fetch.raw_body.decode("utf-8", errors="replace"))
    assert_logged_in(root)
    return fetch, root, set_cookies


def _columns(header: Sequence[str]) -> None:
    """Refuse a Screener header without the ISIN column or repeating a column, whose fields
    would otherwise collapse into one."""
    if ISIN_COLUMN not in header:
        raise ScreenExportError(_NO_ISIN)
    if repeated := sorted(name for name, n in Counter(header).items() if n > 1):
        raise ScreenExportError(_REPEATED_COLUMNS.format(columns=repeated))


def _same_count(vendor: ScreenVendor, stated: object, rows: int) -> None:
    """Refuse an export whose rows differ from the vendor's own result count."""
    if stated != rows:
        raise ScreenExportError(_COUNT_DIFFERS.format(vendor=vendor, stated=stated, rows=rows))


def _screen_fetch(fetch: ScreenerDocumentFetch) -> ScreenFetch:
    """A Screener response as a retained fetch."""
    return ScreenFetch(url=fetch.source_url, body=fetch.raw_body, retrieved_at=fetch.fetched_at)


def _normal(text: str) -> str:
    """Text with whitespace runs collapsed to one space and the ends stripped."""
    return " ".join(text.split())


def _formula(formula: str) -> str:
    """The normalised formula; an empty one refuses before any request."""
    if not (wanted := _normal(formula)):
        raise ScreenExportError(_EMPTY)
    return wanted


def _cell(value: object) -> str:
    """A JSON cell as text: ``null`` is empty, everything else verbatim."""
    return "" if value is None else str(value)
