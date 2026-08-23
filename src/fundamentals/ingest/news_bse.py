"""BSE corporate-announcement ingestion for the material-event news lane."""

from __future__ import annotations

import json
import os
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import quote
from zoneinfo import ZoneInfo

from fundamentals.contracts.news import (
    NewsEntity,
    NewsFetchResult,
    NewsObservation,
    NewsSourceFamily,
    NewsSourceHealthKind,
    NewsSourceWarning,
    create_news_observation,
)
from fundamentals.ingest.news_common import (
    NewsSourceError,
    NewsSourceSchemaError,
    reject_terminal_http_status,
    run_with_retries,
)

SOURCE_ID = "bse-announcements"
OBSERVATION_SOURCE_PREFIX = f"{SOURCE_ID}:"
PARSER_VERSION = "news-bse-v1"
BSE_ANNOUNCEMENTS_URL = "https://www.bseindia.com/corporates/ann.html"
BSE_ATTACHMENT_URL = "https://www.bseindia.com/xml-data/corpfiling/AttachHis/{name}"
MATERIAL_CATEGORIES = frozenset(
    {
        "Result",
        "Board Meeting",
        "Corp. Action",
        "Company Update",
        "AGM/EGM",
        "Insider Trading / SAST",
        "Others",
    }
)

DEFAULT_MAX_RETRIES = 2
DEFAULT_RETRY_BACKOFF_SECONDS = 1.0
DEFAULT_MAX_PAGES = 10

_TABLE_KEY = "Table"
_SUMMARY_KEY = "Table1"
_ROW_COUNT_KEY = "ROWCNT"
_IST = ZoneInfo("Asia/Kolkata")
_INVALID_ROWS_FILENAME = "invalid_bse_rows.jsonl"


class _HttpResponse(Protocol):
    """Typed response surface used by the requests response hook."""

    status_code: int


def _reject_terminal_response(
    response: _HttpResponse, *_args: object, **_kwargs: object
) -> _HttpResponse:
    """Intercept BSE policy blocks before the wrapper erases HTTP status metadata."""
    reject_terminal_http_status(response.status_code, description="BSE announcements")
    return response


def _canonical_row(row: dict[str, object]) -> bytes:
    """Serialize one wrapper row deterministically for its provenance digest."""
    return json.dumps(
        row,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _parse_bse_timestamp(raw: object) -> datetime | None:
    """Parse BSE's ISO-like announcement time into aware UTC."""
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        parsed = datetime.fromisoformat(raw.strip())
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=_IST).astimezone(UTC)
    return parsed.astimezone(UTC)


def _attachment_url(raw: object) -> str | None:
    """Build a first-party BSE attachment URL from a safe basename."""
    name = str(raw or "").strip().replace("\\", "/").rsplit("/", maxsplit=1)[-1]
    if not name:
        return None
    return BSE_ATTACHMENT_URL.format(name=quote(name, safe=""))


def _parse_row(
    row: dict[str, object],
    *,
    entity: NewsEntity,
    observed_at: datetime,
) -> NewsObservation | None:
    """Project one complete BSE row into an immutable first-party occurrence."""
    news_id = str(row.get("NEWSID") or "").strip()
    title = str(row.get("HEADLINE") or "").strip()
    published_at = _parse_bse_timestamp(row.get("NEWS_DT"))
    if not news_id or not title or published_at is None:
        return None
    attachment_url = _attachment_url(row.get("ATTACHMENTNAME"))
    return create_news_observation(
        symbol=entity.symbol,
        isin=entity.isin,
        issuer_id=entity.issuer_id,
        resolved=True,
        source_family=NewsSourceFamily.FIRST_PARTY,
        source_id=f"{OBSERVATION_SOURCE_PREFIX}{news_id}",
        source_url=(attachment_url or f"{BSE_ANNOUNCEMENTS_URL}?newsid={quote(news_id, safe='')}"),
        attachment_url=attachment_url,
        published_at=published_at,
        observed_at=observed_at,
        raw_title=title,
        raw_category=str(row.get("CATEGORYNAME") or "").strip(),
        raw_subcategory=str(row.get("SUBCATNAME") or "").strip(),
        raw_published_at=str(row.get("NEWS_DT") or "").strip(),
        raw_attachment_name=str(row.get("ATTACHMENTNAME") or "").strip() or None,
        raw_source_id=news_id,
        parser_version=PARSER_VERSION,
        payload=_canonical_row(row),
    )


def _has_required_row_fields(row: dict[str, object]) -> bool:
    """Whether a BSE row has the minimum fields needed for an immutable observation."""
    return bool(
        str(row.get("NEWSID") or "").strip()
        and str(row.get("HEADLINE") or "").strip()
        and _parse_bse_timestamp(row.get("NEWS_DT")) is not None
    )


def parse_bse_announcements(
    rows: tuple[dict[str, object], ...],
    *,
    entity: NewsEntity,
    observed_at: datetime,
    all_categories: bool = False,
) -> NewsFetchResult:
    """Parse one BSE pass, retaining raw categories without subcategory routing."""
    selected = [
        row
        for row in rows
        if all_categories or str(row.get("CATEGORYNAME") or "").strip() in MATERIAL_CATEGORIES
    ]
    parsed = tuple(
        observation
        for row in selected
        if (observation := _parse_row(row, entity=entity, observed_at=observed_at)) is not None
    )
    warnings: list[NewsSourceWarning] = []
    invalid_count = len(selected) - len(parsed)
    if invalid_count:
        warnings.append(
            NewsSourceWarning(
                source_id=SOURCE_ID,
                kind=NewsSourceHealthKind.INVALID,
                message=f"skipped {invalid_count} BSE row(s) missing identity, title, or time",
            )
        )
    return NewsFetchResult(
        source_id=SOURCE_ID,
        observations=parsed,
        warnings=tuple(warnings),
        raw_count=len(rows),
    )


class BseNewsSource:
    """Polite paginated BSE source using the installed wrapper's 10-second timeout."""

    def __init__(
        self,
        download_folder: Path,
        *,
        entity: NewsEntity,
        max_retries: int = DEFAULT_MAX_RETRIES,
        retry_backoff_seconds: float = DEFAULT_RETRY_BACKOFF_SECONDS,
        max_pages: int = DEFAULT_MAX_PAGES,
    ) -> None:
        """Configure one bounded per-stock BSE announcement pass."""
        self._download_folder = download_folder
        self._entity = entity
        self._max_retries = max_retries
        self._retry_backoff_seconds = retry_backoff_seconds
        self._max_pages = max_pages

    @staticmethod
    def _load_client_class() -> Any:
        """Load the existing BSE wrapper lazily, normalizing absence."""
        try:
            from bse import BSE  # type: ignore[import-untyped]
        except ImportError as error:
            raise NewsSourceError("the 'bse' package is required for live news") from error
        return BSE

    def _fetch_once(self, *, from_date: date, to_date: date) -> tuple[dict[str, object], ...]:
        """Collect every page for one scrip within a hard page bound."""
        client_class = self._load_client_class()
        client = client_class(download_folder=self._download_folder)
        client.session.hooks["response"].append(_reject_terminal_response)
        rows: list[dict[str, object]] = []
        try:
            for page_number in range(1, self._max_pages + 1):
                response = client.announcements(
                    page_no=page_number,
                    from_date=datetime.combine(from_date, datetime.min.time()),
                    to_date=datetime.combine(to_date, datetime.max.time()),
                    scripcode=self._entity.bse_scrip,
                    category="-1",
                )
                if not isinstance(response, dict) or not isinstance(response.get(_TABLE_KEY), list):
                    raise NewsSourceSchemaError("BSE announcements response has no 'Table' list")
                page_rows = [item for item in response[_TABLE_KEY] if isinstance(item, dict)]
                rows.extend(page_rows)
                summary = response.get(_SUMMARY_KEY, [])
                if not isinstance(summary, list) or not summary or not isinstance(summary[0], dict):
                    raise NewsSourceSchemaError(
                        "BSE announcements response has no valid ROWCNT summary"
                    )
                try:
                    total = int(summary[0][_ROW_COUNT_KEY])
                except (KeyError, TypeError, ValueError) as error:
                    raise NewsSourceSchemaError(
                        "BSE announcements response has an invalid ROWCNT summary"
                    ) from error
                if total < 0 or len(rows) > total:
                    raise NewsSourceSchemaError(
                        "BSE announcements response has an inconsistent ROWCNT summary"
                    )
                if not page_rows:
                    if len(rows) < total:
                        raise NewsSourceSchemaError(
                            "BSE announcements response ended before its ROWCNT total"
                        )
                    return tuple(rows)
                if len(rows) >= total:
                    return tuple(rows)
        finally:
            client.exit()
        raise NewsSourceError(f"BSE announcements exceeded the bounded {self._max_pages}-page pass")

    def _retain_invalid_rows(self, rows: tuple[dict[str, object], ...]) -> None:
        """Append raw BSE rows missing mandatory observation fields for later inspection."""
        invalid_rows = tuple(row for row in rows if not _has_required_row_fields(row))
        if not invalid_rows:
            return
        path = self._download_folder / _INVALID_ROWS_FILENAME
        try:
            with path.open("ab") as handle:
                for row in invalid_rows:
                    handle.write(_canonical_row(row) + b"\n")
                handle.flush()
                os.fsync(handle.fileno())
        except OSError as error:
            raise NewsSourceError(f"could not retain invalid BSE row bytes: {error}") from error

    def fetch(
        self,
        *,
        from_date: date,
        to_date: date,
        observed_at: datetime,
        all_categories: bool = False,
    ) -> NewsFetchResult:
        """Fetch and parse one bounded per-stock BSE announcement window."""
        self._download_folder.mkdir(parents=True, exist_ok=True)
        rows = run_with_retries(
            "BSE announcements",
            lambda: self._fetch_once(from_date=from_date, to_date=to_date),
            max_retries=self._max_retries,
            retry_backoff_seconds=self._retry_backoff_seconds,
        )
        self._retain_invalid_rows(rows)
        result = parse_bse_announcements(
            rows,
            entity=self._entity,
            observed_at=observed_at,
            all_categories=all_categories,
        )
        return result
