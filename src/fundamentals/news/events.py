"""Deterministic classification and derivation of news events."""

from __future__ import annotations

import hashlib
import re
from datetime import timedelta
from difflib import SequenceMatcher
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from fundamentals.contracts.news import (
    NewsEvent,
    NewsEventType,
    NewsObservation,
    NewsSourceFamily,
)

_NON_ALPHANUMERIC = re.compile(r"[^a-z0-9]+")
_DEDUPE_WINDOW = timedelta(days=3)
_TITLE_SIMILARITY_THRESHOLD = 0.86

_CATEGORY_TYPES: dict[str, NewsEventType] = {
    "result": NewsEventType.RESULTS,
    "board meeting": NewsEventType.BOARD_MEETING,
    "corp action": NewsEventType.CORP_ACTION,
    "company update": NewsEventType.MATERIAL_EVENT,
    "agm egm": NewsEventType.AGM_EGM,
    "insider trading sast": NewsEventType.INSIDER_SAST,
    "others": NewsEventType.OTHER,
}

_KEYWORD_TYPES: tuple[tuple[tuple[str, ...], NewsEventType], ...] = (
    (
        (
            "financial result",
            "financial results",
            "quarterly result",
            "quarterly results",
            "earnings",
        ),
        NewsEventType.RESULTS,
    ),
    (("board meeting",), NewsEventType.BOARD_MEETING),
    (("dividend", "bonus", "stock split", "buyback", "rights issue"), NewsEventType.CORP_ACTION),
    (("agm", "egm", "annual general meeting"), NewsEventType.AGM_EGM),
    (("insider trading", "sast", "promoter pledge"), NewsEventType.INSIDER_SAST),
    (
        ("regulation 30", "material event", "acquisition", "litigation"),
        NewsEventType.MATERIAL_EVENT,
    ),
)


def normalize_news_text(value: str) -> str:
    """Normalize a title or category for deterministic comparison."""
    return " ".join(_NON_ALPHANUMERIC.sub(" ", value.casefold()).split())


def classify_news_event(observation: NewsObservation) -> NewsEventType:
    """Classify an occurrence from raw category first, then bounded keywords."""
    category = normalize_news_text(observation.raw_category)
    category_type = _CATEGORY_TYPES.get(category)
    if category_type is not None:
        return category_type
    text = normalize_news_text(
        " ".join((observation.raw_category, observation.raw_subcategory, observation.raw_title))
    )
    bounded_text = f" {text} "
    for keywords, event_type in _KEYWORD_TYPES:
        if any(f" {keyword} " in bounded_text for keyword in keywords):
            return event_type
    return NewsEventType.OTHER


def normalize_news_url(value: str) -> str:
    """Normalize a URL while dropping fragments and tracking parameters."""
    parts = urlsplit(value.strip())
    query = urlencode(
        sorted(
            (key, item)
            for key, item in parse_qsl(parts.query, keep_blank_values=True)
            if not key.casefold().startswith("utm_")
        )
    )
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme.casefold(), parts.netloc.casefold(), path, query, ""))


def _event_id(cluster: list[NewsObservation]) -> str:
    """Build an enrichment-stable identifier from the first-known occurrence."""
    anchor = min(cluster, key=lambda item: (item.observed_at, item.observation_id))
    anchor_date = anchor.published_at.date().isoformat()
    anchor_type = classify_news_event(anchor)
    identity = "|".join(
        (
            anchor.symbol or "",
            anchor_type.value,
            anchor_date,
            anchor.observation_id,
        )
    )
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


def _same_event(
    observation: NewsObservation,
    event_type: NewsEventType,
    cluster: list[NewsObservation],
) -> bool:
    """Whether an occurrence matches a cluster on issuer, type, title/URL, and time."""
    anchor = cluster[0]
    if abs(observation.published_at - anchor.published_at) > _DEDUPE_WINDOW:
        return False
    same_url = normalize_news_url(observation.source_url) == normalize_news_url(anchor.source_url)
    if same_url:
        return True
    if observation.issuer_id != anchor.issuer_id:
        return False
    if event_type is not classify_news_event(anchor):
        return False
    title_similarity = SequenceMatcher(
        None,
        normalize_news_text(observation.raw_title),
        normalize_news_text(anchor.raw_title),
    ).ratio()
    return title_similarity >= _TITLE_SIMILARITY_THRESHOLD


def _event_from_cluster(cluster: list[NewsObservation]) -> NewsEvent:
    """Build one event while retaining every occurrence identity in the cluster."""
    ordered = sorted(cluster, key=lambda item: (item.published_at, item.observation_id))
    canonical_order = sorted(
        cluster,
        key=lambda item: (
            item.source_family is not NewsSourceFamily.FIRST_PARTY,
            normalize_news_url(item.source_url),
            normalize_news_text(item.raw_title),
            item.source_id,
        ),
    )
    canonical = canonical_order[0]
    first_party = [item for item in cluster if item.source_family is NewsSourceFamily.FIRST_PARTY]
    event_type = classify_news_event(canonical)
    return NewsEvent(
        event_id=_event_id(cluster),
        event_type=event_type,
        symbol=canonical.symbol or "",
        title=canonical.raw_title,
        published_at=ordered[0].published_at,
        observation_ids=tuple(sorted(item.observation_id for item in ordered)),
        confirmed=bool(first_party),
    )


def derive_news_events(observations: tuple[NewsObservation, ...]) -> tuple[NewsEvent, ...]:
    """Deduplicate resolved occurrences into deterministic provenance-backed events."""
    clusters: list[list[NewsObservation]] = []
    ordered = sorted(observations, key=lambda item: (item.published_at, item.observation_id))
    for observation in ordered:
        if not observation.resolved or observation.symbol is None:
            continue
        event_type = classify_news_event(observation)
        for cluster in clusters:
            if _same_event(observation, event_type, cluster):
                cluster.append(observation)
                break
        else:
            clusters.append([observation])
    events = [_event_from_cluster(cluster) for cluster in clusters]
    return tuple(sorted(events, key=lambda item: (item.published_at, item.event_id), reverse=True))
