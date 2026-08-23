"""ET Markets RSS metadata ingestion with local fail-closed entity matching."""

from __future__ import annotations

import json
import urllib.request
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit

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

SOURCE_ID = "et-markets-rss"
OBSERVATION_SOURCE_PREFIX = f"{SOURCE_ID}:"
PARSER_VERSION = "news-et-rss-v1"
ET_MARKETS_RSS_URL = "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms"
RAW_CATEGORY = "Media"
RAW_SUBCATEGORY = "ET Markets"
_HTTP_SCHEMES = frozenset({"http", "https"})
DEFAULT_TIMEOUT_SECONDS = 15
DEFAULT_MAX_RETRIES = 2
DEFAULT_RETRY_BACKOFF_SECONDS = 1.0
DEFAULT_MAX_RESPONSE_BYTES = 2_000_000
DEFAULT_USER_AGENT = "Equity-OS/0.0 (personal non-commercial news metadata reader)"
_USER_AGENT_HEADER = "User-Agent"


class EtNewsFetchError(NewsSourceError):
    """The ET metadata feed could not be parsed into trustworthy occurrences."""


class EtNewsSchemaError(NewsSourceSchemaError):
    """An otherwise-successful ET response has an unusable RSS shape."""


def _item_text(item: ET.Element, name: str) -> str:
    """Return one stripped RSS child value."""
    child = item.find(name)
    return (child.text or "").strip() if child is not None else ""


def _published_at(raw: str) -> datetime | None:
    """Parse one RFC-2822 publication time as an aware UTC timestamp."""
    if not raw:
        return None
    try:
        parsed = parsedate_to_datetime(raw)
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(UTC)


def _metadata_payload(*, title: str, link: str, guid: str, published: str) -> bytes:
    """Serialize only permitted RSS metadata for the occurrence digest."""
    return json.dumps(
        {"guid": guid, "link": link, "published": published, "title": title},
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _observation(
    *,
    item: ET.Element,
    entities: tuple[NewsEntity, ...],
    observed_at: datetime,
) -> tuple[NewsObservation | None, bool]:
    """Parse one RSS item, returning ``None`` when required metadata is invalid."""
    title = _item_text(item, "title")
    link = _item_text(item, "link")
    guid = _item_text(item, "guid") or link
    published_raw = _item_text(item, "pubDate")
    published_at = _published_at(published_raw)
    if not title or not guid or published_at is None:
        return None, False
    url = urlsplit(link)
    if url.scheme.casefold() not in _HTTP_SCHEMES or not url.hostname:
        return None, False
    entity, identity_note, contradictory = resolve_news_entity(entities, title=title)
    if entity is None and not contradictory:
        return None, True
    payload = _metadata_payload(
        title=title,
        link=link,
        guid=guid,
        published=published_raw,
    )
    return create_news_observation(
        symbol=entity.symbol if entity is not None else None,
        isin=entity.isin if entity is not None else None,
        issuer_id=entity.issuer_id if entity is not None else None,
        resolved=entity is not None and not contradictory,
        identity_note=identity_note,
        source_family=NewsSourceFamily.MEDIA,
        source_id=f"{OBSERVATION_SOURCE_PREFIX}{guid}",
        source_url=link,
        attachment_url=None,
        published_at=published_at,
        observed_at=observed_at,
        raw_title=title,
        raw_category=RAW_CATEGORY,
        raw_subcategory=RAW_SUBCATEGORY,
        raw_published_at=published_raw,
        raw_attachment_name=None,
        raw_source_id=guid,
        parser_version=PARSER_VERSION,
        payload=payload,
    ), False


def parse_et_markets_rss(
    payload: bytes,
    *,
    entities: tuple[NewsEntity, ...],
    observed_at: datetime,
) -> NewsFetchResult:
    """Parse ET RSS metadata, quarantining every unresolved issuer occurrence."""
    try:
        root = ET.fromstring(payload)
    except ET.ParseError as error:
        raise EtNewsSchemaError(f"ET Markets RSS is malformed: {error}") from error
    parsed: list[NewsObservation] = []
    dropped_count = 0
    invalid_count = 0
    for item in root.findall("./channel/item"):
        observation, dropped = _observation(item=item, entities=entities, observed_at=observed_at)
        if observation is not None:
            parsed.append(observation)
        elif dropped:
            dropped_count += 1
        else:
            invalid_count += 1
    observations = tuple(item for item in parsed if item.resolved)
    quarantined = tuple(item for item in parsed if not item.resolved)
    warnings: tuple[NewsSourceWarning, ...] = ()
    if invalid_count:
        warnings = (
            NewsSourceWarning(
                source_id=SOURCE_ID,
                kind=NewsSourceHealthKind.INVALID,
                message=f"skipped {invalid_count} ET item(s) missing valid metadata",
            ),
        )
    return NewsFetchResult(
        source_id=SOURCE_ID,
        observations=observations,
        quarantined=quarantined,
        warnings=warnings,
        raw_count=len(root.findall("./channel/item")),
        dropped_count=dropped_count,
    )


class EtMarketsNewsSource:
    """Polite bounded ET Markets RSS metadata source."""

    def __init__(
        self,
        *,
        entities: tuple[NewsEntity, ...],
        feed_url: str = ET_MARKETS_RSS_URL,
        user_agent: str = DEFAULT_USER_AGENT,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
        max_retries: int = DEFAULT_MAX_RETRIES,
        retry_backoff_seconds: float = DEFAULT_RETRY_BACKOFF_SECONDS,
        max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
    ) -> None:
        """Configure an allowlisted feed URL and bounded network policy."""
        parts = urlsplit(feed_url)
        if parts.scheme != "https" or parts.hostname != "economictimes.indiatimes.com":
            raise ValueError("ET feed URL must be the configured HTTPS economictimes host")
        self._entities = entities
        self._feed_url = feed_url
        self._user_agent = user_agent
        self._timeout_seconds = timeout_seconds
        self._max_retries = max_retries
        self._retry_backoff_seconds = retry_backoff_seconds
        self._max_response_bytes = max_response_bytes

    def _fetch_once(self) -> bytes:
        """Fetch one RSS body under an explicit timeout and size cap."""
        request = urllib.request.Request(
            self._feed_url,
            headers={_USER_AGENT_HEADER: self._user_agent},
        )
        with urllib.request.urlopen(request, timeout=self._timeout_seconds) as response:
            status = getattr(response, "status", 200)
            if status != 200:
                raise EtNewsFetchError(f"ET Markets RSS returned HTTP {status}", status_code=status)
            payload: bytes = response.read(self._max_response_bytes + 1)
        if not payload:
            raise EtNewsFetchError("ET Markets RSS returned an empty body")
        if len(payload) > self._max_response_bytes:
            raise EtNewsFetchError("ET Markets RSS exceeded the response-size cap")
        return payload

    def fetch(
        self,
        *,
        observed_at: datetime,
    ) -> NewsFetchResult:
        """Fetch and parse one ET metadata feed pass."""
        payload = run_with_retries(
            "ET Markets RSS",
            self._fetch_once,
            max_retries=self._max_retries,
            retry_backoff_seconds=self._retry_backoff_seconds,
        )
        result = parse_et_markets_rss(
            payload,
            entities=self._entities,
            observed_at=observed_at,
        )
        return result
