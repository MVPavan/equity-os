"""Public event derivation for synthetic cross-exchange filing copies."""

from datetime import UTC, datetime, timedelta

import pytest

from fundamentals.contracts.news import (
    NewsEventType,
    NewsObservation,
    NewsSourceFamily,
    create_news_observation,
)
from fundamentals.news.events import derive_news_events

_PUBLISHED = datetime(2026, 8, 22, 10, 30, tzinfo=UTC)
_BODY = "Financial results for the quarter ended June 30 2026"
_WRAPPED = f"Titan Company Limited has informed the Exchange about {_BODY}"


def _filing(
    *,
    nse: bool = False,
    title: str | None = None,
    family: NewsSourceFamily = NewsSourceFamily.FIRST_PARTY,
    source_id: str | None = None,
    symbol: str = "TITAN",
    category: str = "Result",
    published_at: datetime = _PUBLISHED,
    resolved: bool = True,
) -> NewsObservation:
    """Build distinct synthetic attachment occurrences using real source markers."""
    marker = source_id or ("nse-announcements:42" if nse else "bse-announcements:42")
    url = f"https://{'nse' if nse else 'bse'}.example.test/results.pdf"
    return create_news_observation(
        symbol=symbol if resolved else None,
        isin=None,
        issuer_id=f"NSE:{symbol}" if resolved else None,
        resolved=resolved,
        source_family=family,
        source_id=marker,
        source_url=url,
        attachment_url=url,
        published_at=published_at,
        observed_at=_PUBLISHED + timedelta(hours=2 if nse else 1),
        raw_title=title if title is not None else (_WRAPPED if nse else _BODY),
        raw_category=category,
        raw_subcategory="",
        raw_published_at=published_at.isoformat(),
        raw_attachment_name="results.pdf",
        raw_source_id="42",
        parser_version="synthetic-news-v1",
        payload=b"synthetic public-shaped filing",
    )


def test_nse_wrapper_merges_filing_without_losing_evidence_or_identity() -> None:
    """The NSE notification wrapper must not split one disclosed filing."""
    bse, nse = _filing(), _filing(nse=True)
    before = (bse.model_dump(), nse.model_dump())

    events = derive_news_events((bse, nse))

    assert len(events) == 1
    assert set(events[0].observation_ids) == {bse.observation_id, nse.observation_id}
    assert events[0].confirmed is True
    assert events[0].event_type is NewsEventType.RESULTS
    assert events[0].title == _BODY
    assert events[0].event_id == derive_news_events((bse,))[0].event_id
    assert derive_news_events((nse, bse)) == events
    assert (bse.model_dump(), nse.model_dump()) == before


@pytest.mark.parametrize(
    "changes",
    [
        {"symbol": "OTHER"},
        {"category": "Board Meeting"},
        {"published_at": _PUBLISHED + timedelta(days=3, seconds=1)},
        {"title": "Titan Company Limited has informed the Exchange about auditor resignation"},
    ],
    ids=["issuer", "type", "outside-window", "unrelated-same-type-disclosure"],
)
def test_wrapper_does_not_override_disclosure_separation(changes: dict[str, object]) -> None:
    """Matching requires the original issuer, classification, time and title gates."""
    nse = _filing(nse=True)
    # Apply synthetic source differences while retaining a valid observation model.
    updates = {
        {"category": "raw_category", "title": "raw_title"}.get(key, key): value
        for key, value in changes.items()
    }
    if "symbol" in updates:
        updates["issuer_id"] = "NSE:OTHER"
    nse = NewsObservation.model_validate(nse.model_dump() | updates)

    events = derive_news_events((_filing(), nse))

    assert len(events) == 2
    assert {event.observation_ids for event in events} == {
        (_filing().observation_id,),
        (nse.observation_id,),
    }


@pytest.mark.parametrize(
    ("family", "source_id"),
    [
        (NewsSourceFamily.MEDIA, "nse-announcements:42"),
        (NewsSourceFamily.REGULATORY, "nse-announcements:42"),
        (NewsSourceFamily.FIRST_PARTY, "bse-announcements:43"),
        (NewsSourceFamily.FIRST_PARTY, "nse:42"),
        (NewsSourceFamily.FIRST_PARTY, "nse-announcements-imitation:42"),
    ],
)
def test_wrapper_requires_nse_first_party_source_markers(
    family: NewsSourceFamily, source_id: str
) -> None:
    """Media and other sources cannot opt into normalization by copying the title."""
    imitation = _filing(nse=True, family=family, source_id=source_id)

    events = derive_news_events((_filing(), imitation))

    assert len(events) == 2
    imitation_event = next(
        event for event in events if imitation.observation_id in event.observation_ids
    )
    assert imitation_event.confirmed is (family is NewsSourceFamily.FIRST_PARTY)


@pytest.mark.parametrize(
    "title",
    [
        f"Titan Company Limited notified the Exchange about {_BODY}",
        f"Titan Company Limited has informed investors about {_BODY}",
        "Titan Company Limited has informed the Exchange about",
        "Titan Company Limited has informed the Exchange about ...",
    ],
)
def test_unknown_or_empty_wrapper_does_not_collapse_into_filing(title: str) -> None:
    """Only the evidenced wrapper with a substantive body can match the filing."""
    assert len(derive_news_events((_filing(), _filing(nse=True, title=title)))) == 2


def test_empty_wrapper_retains_original_title_comparison() -> None:
    """An empty body must not erase an otherwise matching original title."""
    title = "Titan Company Limited has informed the Exchange about ..."
    bse, nse = _filing(title=title), _filing(nse=True, title=title)

    events = derive_news_events((bse, nse))

    assert len(events) == 1
    assert set(events[0].observation_ids) == {bse.observation_id, nse.observation_id}
    assert events[0].title == title


def test_wrapper_in_earlier_published_nse_anchor_keeps_bse_event_identity() -> None:
    """Comparison works in either direction without renaming the first-known event."""
    bse = _filing()
    nse = _filing(nse=True, published_at=_PUBLISHED - timedelta(hours=1))

    events = derive_news_events((bse, nse))

    assert len(events) == 1
    assert events[0].event_id == derive_news_events((bse,))[0].event_id
    assert set(events[0].observation_ids) == {bse.observation_id, nse.observation_id}


def test_unresolved_wrapper_is_excluded_from_resolved_event() -> None:
    """A quarantined occurrence cannot become backing evidence via its wrapper."""
    bse, nse = _filing(), _filing(nse=True, resolved=False)

    assert derive_news_events((bse, nse)) == derive_news_events((bse,))


def test_wrapper_stripping_does_not_change_raw_keyword_classification() -> None:
    """Issuer wording remains available to the existing raw-title classifier."""
    title = "Acquisition Holdings Limited has informed the Exchange about Routine update"
    nse = _filing(nse=True, title=title, category="")

    event = derive_news_events((nse,))[0]

    assert event.event_type is NewsEventType.MATERIAL_EVENT
    assert event.title == title
