"""NSE corporate-announcement ingestion through the installed ``nse`` wrapper."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit
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
from fundamentals.ingest.news_common import NewsSourceError, NewsSourceSchemaError, run_with_retries
from fundamentals.news.entity import resolve_news_entity

SOURCE_ID = "nse-announcements"
OBSERVATION_SOURCE_PREFIX = f"{SOURCE_ID}:"
PARSER_VERSION = "news-nse-v1"
NSE_ANNOUNCEMENTS_URL = "https://www.nseindia.com/companies-listing/corporate-filings-announcements"

DEFAULT_TIMEOUT_SECONDS = 15
DEFAULT_MAX_RETRIES = 2
DEFAULT_RETRY_BACKOFF_SECONDS = 1.0

_TIMESTAMP_FORMATS = (
    "%d-%b-%Y %H:%M:%S",
    "%d-%b-%Y %H:%M",
    "%Y-%m-%d %H:%M:%S",
)
_NSE_HOST_SUFFIX = ".nseindia.com"
_IST = ZoneInfo("Asia/Kolkata")


def _canonical_row(row: dict[str, object]) -> bytes:
    """Serialize one NSE wrapper row deterministically for provenance."""
    return json.dumps(
        row,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _first_text(row: dict[str, object], *keys: str) -> str:
    """Return the first non-empty text value among known wrapper keys."""
    for key in keys:
        value = str(row.get(key) or "").strip()
        if value:
            return value
    return ""


def _parse_nse_timestamp(row: dict[str, object]) -> datetime | None:
    """Parse an NSE announcement timestamp from the wrapper's known fields."""
    raw = _first_text(row, "an_dt", "sort_date", "exchdisstime", "broadcast_date")
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        parsed = None
    if parsed is not None:
        return (
            parsed.replace(tzinfo=_IST).astimezone(UTC)
            if parsed.tzinfo is None
            else parsed.astimezone(UTC)
        )
    for timestamp_format in _TIMESTAMP_FORMATS:
        try:
            return datetime.strptime(raw, timestamp_format).replace(tzinfo=_IST).astimezone(UTC)
        except ValueError:
            continue
    return None


def _nse_attachment_url(raw: str) -> str | None:
    """Allow only HTTP(S) URLs on NSE's own host family."""
    if not raw:
        return None
    parts = urlsplit(raw)
    host = (parts.hostname or "").casefold()
    if parts.scheme.casefold() not in {"http", "https"}:
        return None
    if host != "nseindia.com" and not host.endswith(_NSE_HOST_SUFFIX):
        return None
    return raw


def _fallback_sequence(
    row: dict[str, object], *, title: str, published_at: datetime, raw_url: str
) -> str:
    """Derive an occurrence identity from stable NSE announcement fields only."""
    identity = {
        "attachment_url": raw_url,
        "isin": _first_text(row, "isin", "sm_isin").upper(),
        "published_at": published_at.isoformat(),
        "scrip": _first_text(row, "scrip_code", "scripCode").upper(),
        "symbol": _first_text(row, "symbol", "sm_symbol").upper(),
        "title": " ".join(title.casefold().split()),
    }
    digest = hashlib.sha256(
        json.dumps(identity, ensure_ascii=True, separators=(",", ":"), sort_keys=True).encode()
    ).hexdigest()
    return f"fallback-{digest}"


def _parse_row(
    row: dict[str, object],
    *,
    entities: tuple[NewsEntity, ...],
    observed_at: datetime,
) -> tuple[NewsObservation | None, bool]:
    """Project one NSE row after independent issuer matching."""
    title = _first_text(row, "attchmntText", "subject", "headline", "desc")
    published_at = _parse_nse_timestamp(row)
    if not title or published_at is None:
        return None, False
    row_payload = _canonical_row(row)
    raw_published_at = _first_text(row, "an_dt", "sort_date", "exchdisstime", "broadcast_date")
    raw_url = _first_text(row, "attchmntFile", "attachment", "url")
    sequence = _first_text(row, "seq_id", "seqId", "news_id") or _fallback_sequence(
        row,
        title=title,
        published_at=published_at,
        raw_url=raw_url,
    )
    attachment_url = _nse_attachment_url(raw_url)
    entity, identity_note, contradictory = resolve_news_entity(
        entities,
        isin=_first_text(row, "isin", "sm_isin") or None,
        scrip=_first_text(row, "scrip_code", "scripCode") or None,
        symbol=_first_text(row, "symbol", "sm_symbol") or None,
        title=title,
    )
    if entity is None and not contradictory:
        return None, True
    return create_news_observation(
        symbol=entity.symbol if entity is not None else None,
        isin=entity.isin if entity is not None else None,
        issuer_id=entity.issuer_id if entity is not None else None,
        resolved=entity is not None and not contradictory,
        identity_note=identity_note,
        source_family=NewsSourceFamily.FIRST_PARTY,
        source_id=f"{OBSERVATION_SOURCE_PREFIX}{sequence}",
        source_url=(attachment_url or f"{NSE_ANNOUNCEMENTS_URL}?seq_id={sequence}"),
        attachment_url=attachment_url,
        published_at=published_at,
        observed_at=observed_at,
        raw_title=title,
        raw_category=_first_text(row, "desc", "category"),
        raw_subcategory=_first_text(row, "sub_desc", "subcategory"),
        raw_published_at=raw_published_at,
        raw_attachment_name=raw_url or None,
        raw_source_id=sequence,
        parser_version=PARSER_VERSION,
        payload=row_payload,
    ), False


def parse_nse_announcements(
    rows: tuple[dict[str, object], ...],
    *,
    entities: tuple[NewsEntity, ...],
    observed_at: datetime,
) -> NewsFetchResult:
    """Parse NSE rows, quarantining every occurrence that cannot resolve uniquely."""
    parsed: list[NewsObservation] = []
    dropped_count = 0
    for row in rows:
        observation, dropped = _parse_row(row, entities=entities, observed_at=observed_at)
        if observation is not None:
            parsed.append(observation)
        elif dropped:
            dropped_count += 1
    observations = tuple(item for item in parsed if item.resolved)
    quarantined = tuple(item for item in parsed if not item.resolved)
    warnings: list[NewsSourceWarning] = []
    invalid_count = len(rows) - len(parsed) - dropped_count
    if invalid_count:
        warnings.append(
            NewsSourceWarning(
                source_id=SOURCE_ID,
                kind=NewsSourceHealthKind.INVALID,
                message=f"skipped {invalid_count} NSE row(s) missing title or time",
            )
        )
    return NewsFetchResult(
        source_id=SOURCE_ID,
        observations=observations,
        quarantined=quarantined,
        warnings=tuple(warnings),
        raw_count=len(rows),
        dropped_count=dropped_count,
    )


class NseNewsSource:
    """Polite NSE announcement source with explicit timeout and bounded retries."""

    def __init__(
        self,
        download_folder: Path,
        *,
        entity: NewsEntity,
        entities: tuple[NewsEntity, ...],
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
        max_retries: int = DEFAULT_MAX_RETRIES,
        retry_backoff_seconds: float = DEFAULT_RETRY_BACKOFF_SECONDS,
    ) -> None:
        """Configure one per-symbol NSE announcement pass."""
        self._download_folder = download_folder
        self._entity = entity
        self._entities = entities
        self._timeout_seconds = timeout_seconds
        self._max_retries = max_retries
        self._retry_backoff_seconds = retry_backoff_seconds

    @staticmethod
    def _load_client_class() -> Any:
        """Load the existing NSE wrapper lazily, normalizing absence."""
        try:
            from nse import NSE  # type: ignore[import-untyped]
        except ImportError as error:
            raise NewsSourceError("the 'nse' package is required for live news") from error
        return NSE

    def _fetch_once(self, *, from_date: date, to_date: date) -> tuple[dict[str, object], ...]:
        """Call the wrapper's corporate-announcements endpoint once."""
        client_class = self._load_client_class()
        with client_class(self._download_folder, timeout=self._timeout_seconds) as client:
            response = client.announcements(
                index="equities",
                symbol=self._entity.symbol,
                from_date=datetime.combine(from_date, datetime.min.time()),
                to_date=datetime.combine(to_date, datetime.max.time()),
            )
        if not isinstance(response, list):
            raise NewsSourceSchemaError("NSE announcements response is not a list")
        return tuple(item for item in response if isinstance(item, dict))

    def fetch(
        self,
        *,
        from_date: date,
        to_date: date,
        observed_at: datetime,
    ) -> NewsFetchResult:
        """Fetch and parse one bounded NSE announcement window."""
        self._download_folder.mkdir(parents=True, exist_ok=True)
        rows = run_with_retries(
            "NSE announcements",
            lambda: self._fetch_once(from_date=from_date, to_date=to_date),
            max_retries=self._max_retries,
            retry_backoff_seconds=self._retry_backoff_seconds,
        )
        result = parse_nse_announcements(
            rows,
            entities=self._entities,
            observed_at=observed_at,
        )
        return result
