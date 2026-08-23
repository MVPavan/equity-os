"""News-lane contracts, derivation, ingestion, storage, and CLI acceptance tests."""

from __future__ import annotations

import hashlib
import json
from argparse import Namespace
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from fundamentals.contracts.news import (
    NewsEntity,
    NewsFetchResult,
    NewsObservation,
    NewsSourceFamily,
    NewsSourceHealthKind,
    create_news_observation,
)

_PUBLISHED_AT = datetime(2026, 8, 22, 10, 30, tzinfo=UTC)
_OBSERVED_AT = datetime(2026, 8, 23, 12, 0, tzinfo=UTC)


def _observation(
    family: NewsSourceFamily,
    *,
    source_id: str,
    title: str = "Titan announces quarterly results",
    url: str = "https://example.test/titan-results",
    published_at: datetime = _PUBLISHED_AT,
    payload: bytes | None = None,
) -> NewsObservation:
    """Build a literal source occurrence for event-derivation tests."""
    return create_news_observation(
        symbol="TITAN",
        isin=None,
        issuer_id="NSE:TITAN",
        resolved=True,
        source_family=family,
        source_id=source_id,
        source_url=url,
        attachment_url=None,
        published_at=published_at,
        observed_at=_OBSERVED_AT,
        raw_title=title,
        raw_category="Result" if family is NewsSourceFamily.FIRST_PARTY else "",
        raw_subcategory="Financial Results" if family is NewsSourceFamily.FIRST_PARTY else "",
        raw_published_at=published_at.isoformat(),
        raw_attachment_name=None,
        raw_source_id=source_id,
        parser_version="test-v1",
        payload=payload or source_id.encode(),
    )


def _news_entity(
    symbol: str = "TITAN", *, bse_scrip: str = "500114", isin: str | None = None
) -> NewsEntity:
    """Build a news entity with the explicit multi-word alias used by parser tests."""
    return NewsEntity(
        symbol=symbol, bse_scrip=bse_scrip, isin=isin, aliases=("Titan Company Limited",)
    )


def _news_args(symbol: str = "TITAN", *, days: int = 30, live: bool = False) -> Namespace:
    """Build the news CLI namespace after argparse validation has completed."""
    return Namespace(
        symbol=symbol,
        days=days,
        live=live,
        fixture=not live,
        all_categories=False,
        config="config/watchlist.yaml",
    )


class _FixtureBse:
    def __init__(self, response: dict[str, object]) -> None:
        self._response = response
        self.session = _FixtureSession()

    def announcements(self, **_: object) -> dict[str, object]:
        return self._response

    def exit(self) -> None:
        pass


class _FixtureSession:
    """Model the public response-hook surface exposed by requests.Session."""

    def __init__(self) -> None:
        self.hooks: dict[str, list[object]] = {"response": []}


class _StaticNewsSource:
    """Return an empty, otherwise successful source result for composition tests."""

    def __init__(self, source_id: str) -> None:
        self._source_id = source_id

    def fetch(self, **_: object) -> NewsFetchResult:
        return NewsFetchResult(source_id=self._source_id)


def test_news_observation_is_immutable_and_hashes_its_source_payload() -> None:
    """An occurrence retains a digest of source bytes and cannot be mutated."""
    payload = b'{"NEWSID":"42","HEADLINE":"Quarterly result"}'
    observation = _observation(
        NewsSourceFamily.FIRST_PARTY,
        source_id="bse:42",
        title="Quarterly result",
        payload=payload,
    )

    assert observation.payload_sha256 == hashlib.sha256(payload).hexdigest()
    refreshed = _observation(
        NewsSourceFamily.FIRST_PARTY,
        source_id="bse:42",
        title="Quarterly result",
        payload=b'{"NEWSID":"42","response_elapsed_ms":999}',
    )
    assert refreshed.observation_id == observation.observation_id
    assert refreshed.payload_sha256 != observation.payload_sha256
    with pytest.raises(ValidationError):
        observation.raw_title = "changed"  # type: ignore[misc]


@pytest.mark.parametrize(
    ("family", "confirmed"),
    [
        (NewsSourceFamily.MEDIA, False),
        (NewsSourceFamily.FIRST_PARTY, True),
    ],
)
def test_event_confirmation_comes_only_from_first_party(
    family: NewsSourceFamily, *, confirmed: bool
) -> None:
    """Media stays contextual while a first-party occurrence confirms an event."""
    from fundamentals.news.events import derive_news_events

    events = derive_news_events((_observation(family, source_id=f"source:{family.value}"),))

    assert len(events) == 1
    assert events[0].confirmed is confirmed
    assert events[0].context_only is (not confirmed)


@pytest.mark.parametrize(
    "title",
    [
        "Titan reorganizes its fragmented retail operations",
        "Titan reports no impact from the regional disaster",
    ],
)
def test_keyword_classification_does_not_match_fragments_inside_words(title: str) -> None:
    """AGM and SAST abbreviations classify only complete normalized tokens."""
    from fundamentals.contracts.news import NewsEventType
    from fundamentals.news.events import derive_news_events

    event = derive_news_events(
        (_observation(NewsSourceFamily.MEDIA, source_id=f"et:{title}", title=title),)
    )[0]

    assert event.event_type is NewsEventType.OTHER


def test_deduplication_retains_every_backing_observation() -> None:
    """Clustering removes duplicate events without discarding occurrences."""
    from fundamentals.news.events import derive_news_events

    media = _observation(
        NewsSourceFamily.MEDIA,
        source_id="et:42",
        url="https://economictimes.example/titan-results",
    )
    filing = _observation(
        NewsSourceFamily.FIRST_PARTY,
        source_id="bse:42",
        url="https://bse.example/titan-results",
    )

    events = derive_news_events((media, filing))

    assert len(events) == 1
    assert events[0].confirmed is True
    assert set(events[0].observation_ids) == {
        media.observation_id,
        filing.observation_id,
    }


def test_deduplication_requires_title_match_for_distinct_urls() -> None:
    """Distinct URLs cannot collapse unrelated same-type announcements."""
    from fundamentals.news.events import derive_news_events

    acquisition = _observation(
        NewsSourceFamily.MEDIA,
        source_id="et:acquisition",
        title="Titan acquires a manufacturing subsidiary",
        url="https://example.test/acquisition",
    )
    litigation = _observation(
        NewsSourceFamily.MEDIA,
        source_id="et:litigation",
        title="Titan receives notice in tax litigation",
        url="https://example.test/litigation",
    )

    events = derive_news_events((acquisition, litigation))

    assert len(events) == 2
    assert events[0].event_id != events[1].event_id


def test_event_id_is_stable_when_a_second_first_party_title_and_time_variant_joins() -> None:
    """Fuzzy matching enrichment cannot rename an existing event."""
    from fundamentals.news.events import derive_news_events

    filing = _observation(NewsSourceFamily.FIRST_PARTY, source_id="bse:42")
    original_id = derive_news_events((filing,))[0].event_id
    second_filing = _observation(
        NewsSourceFamily.FIRST_PARTY,
        source_id="nse:42",
        title="A Titan announces quarterly results",
        url="https://a.example/titan-results",
        published_at=_PUBLISHED_AT - timedelta(hours=12),
    ).model_copy(update={"observed_at": _OBSERVED_AT + timedelta(minutes=1)})

    updated_id = derive_news_events((filing, second_filing))[0].event_id

    assert updated_id == original_id


def test_event_id_keeps_first_known_type_when_same_url_enrichment_changes_display_type() -> None:
    """A better display classification cannot rename the already observed occurrence."""
    from fundamentals.contracts.news import NewsEventType
    from fundamentals.news.events import derive_news_events

    media = _observation(
        NewsSourceFamily.MEDIA,
        source_id="et:type-change",
        title="Titan announces quarterly results",
        url="https://example.test/type-change",
    )
    original = derive_news_events((media,))[0]
    filing = _observation(
        NewsSourceFamily.FIRST_PARTY,
        source_id="bse:type-change",
        title="Titan announces a material acquisition",
        url=media.source_url,
    ).model_copy(
        update={
            "observed_at": _OBSERVED_AT + timedelta(minutes=1),
            "raw_category": "Company Update",
        }
    )

    enriched = derive_news_events((media, filing))[0]

    assert original.event_type is NewsEventType.RESULTS
    assert enriched.event_type is NewsEventType.MATERIAL_EVENT
    assert enriched.event_id == original.event_id


def test_repeated_occurrences_outside_window_have_distinct_event_ids() -> None:
    """A later repeat notice is a distinct event even when its display fields match."""
    from fundamentals.news.events import derive_news_events

    original = _observation(NewsSourceFamily.FIRST_PARTY, source_id="bse:42")
    repeated = _observation(
        NewsSourceFamily.FIRST_PARTY,
        source_id="bse:42",
        published_at=_PUBLISHED_AT + timedelta(days=4),
    )

    events = derive_news_events((original, repeated))

    assert len(events) == 2
    assert events[0].event_id != events[1].event_id


def test_deduplication_window_is_rolling_not_fixed_bucket() -> None:
    """Items seconds apart cannot split only because they cross an epoch bucket."""
    from fundamentals.news.events import derive_news_events

    window_seconds = 3 * 24 * 60 * 60
    bucket_start = datetime.fromtimestamp(
        (int(_PUBLISHED_AT.timestamp()) // window_seconds) * window_seconds,
        tz=UTC,
    )
    before = _observation(
        NewsSourceFamily.MEDIA,
        source_id="et:before",
        published_at=bucket_start - timedelta(seconds=1),
    )
    after = _observation(
        NewsSourceFamily.MEDIA,
        source_id="et:after",
        published_at=bucket_start + timedelta(seconds=1),
    )

    assert len(derive_news_events((before, after))) == 1


def test_unmatched_media_item_is_counted_but_not_quarantined() -> None:
    """Market-wide media noise is dropped rather than buried in identity quarantine."""
    from fundamentals.ingest.news_et import parse_et_markets_rss

    payload = b"""<?xml version="1.0"?>
    <rss><channel><item>
      <title>Unrelated issuer expands capacity</title>
      <link>https://economictimes.example/unrelated</link>
      <guid>et-unrelated-1</guid>
      <pubDate>Sat, 22 Aug 2026 10:30:00 GMT</pubDate>
    </item></channel></rss>"""
    entities = (_news_entity(),)

    result = parse_et_markets_rss(payload, entities=entities, observed_at=_OBSERVED_AT)

    assert result.observations == ()
    assert result.quarantined == ()
    assert result.raw_count == 1
    assert result.dropped_count == 1


def test_et_invalid_metadata_is_reported_as_invalid_not_empty() -> None:
    """Malformed RSS metadata is counted explicitly instead of looking like an empty feed."""
    from fundamentals.ingest.news_et import parse_et_markets_rss

    result = parse_et_markets_rss(
        b"""<rss><channel><item><title>Titan Company Limited update</title>
        <link>https://economictimes.example/titan</link><guid>bad-date</guid>
        <pubDate>not-a-date</pubDate></item></channel></rss>""",
        entities=(_news_entity(),),
        observed_at=_OBSERVED_AT,
    )

    assert result.observations == ()
    assert result.dropped_count == 0
    assert result.warnings[0].kind is NewsSourceHealthKind.INVALID
    assert "skipped 1 ET item" in result.warnings[0].message


def test_source_health_warns_on_bootstrap_zero_resolved_and_observed_time_staleness() -> None:
    """Health cannot treat a first-run empty or entirely unresolved feed as clean."""
    from fundamentals.news.health import assess_source_health

    def assess(**counts: object) -> tuple[object, ...]:
        return assess_source_health(
            source_id="nse-announcements",
            observed_at=_OBSERVED_AT,
            recency_bound=timedelta(days=14),
            **counts,
        )

    first_empty = assess(raw_count=0, resolved_count=0, published_times=(), previous_had_data=False)
    after_success = assess(
        raw_count=0, resolved_count=0, published_times=(), previous_had_data=True
    )
    zero_resolved = assess(
        raw_count=19, resolved_count=0, published_times=(_PUBLISHED_AT,), previous_had_data=False
    )
    stale = assess(
        raw_count=1,
        resolved_count=1,
        published_times=(_OBSERVED_AT - timedelta(days=20),),
        previous_had_data=True,
    )

    assert first_empty[0].kind is NewsSourceHealthKind.NO_HISTORY
    assert after_success[0].kind is NewsSourceHealthKind.EMPTY
    assert zero_resolved[0].kind is NewsSourceHealthKind.ZERO_RESOLVED
    assert stale[0].kind is NewsSourceHealthKind.STALE


def test_news_store_is_append_only_idempotent_and_keeps_quarantine(tmp_path: Path) -> None:
    """Repeated fetches do not duplicate occurrences and unresolved rows remain kept."""
    from fundamentals.news.store import NewsObservationStore

    resolved = _observation(NewsSourceFamily.FIRST_PARTY, source_id="bse:42")
    unresolved = create_news_observation(
        symbol=None,
        isin=None,
        issuer_id=None,
        resolved=False,
        source_family=NewsSourceFamily.MEDIA,
        source_id="et:unresolved",
        source_url="https://example.test/unresolved",
        attachment_url=None,
        published_at=_PUBLISHED_AT,
        observed_at=_OBSERVED_AT,
        raw_title="Unrelated issuer",
        raw_category="Media",
        raw_subcategory="ET Markets",
        raw_published_at=_PUBLISHED_AT.isoformat(),
        raw_attachment_name=None,
        raw_source_id="unresolved",
        parser_version="test-v1",
        payload=b"unresolved",
    )
    store = NewsObservationStore(tmp_path)

    assert store.append((resolved, unresolved)) == 2
    assert store.append((resolved, unresolved)) == 0
    assert store.read("TITAN") == (resolved,)
    assert store.read_quarantine() == (unresolved,)


def test_news_store_recovers_a_torn_line_to_a_sidecar(tmp_path: Path) -> None:
    """One malformed line is retained for inspection without bricking future writes."""
    from fundamentals.news.store import NewsObservationStore

    observation = _observation(NewsSourceFamily.FIRST_PARTY, source_id="bse:torn")
    path = tmp_path / "TITAN.jsonl"
    path.write_bytes(b'{"observation_id":"torn"\n')
    store = NewsObservationStore(tmp_path)

    assert store.append((observation,)) == 1
    assert store.read("TITAN") == (observation,)
    assert path.with_name("TITAN.jsonl.corrupt").read_bytes() == b'{"observation_id":"torn"\n'


def test_news_store_serializes_concurrent_duplicate_appends(tmp_path: Path) -> None:
    """Concurrent writers cannot both report or retain the same immutable observation id."""
    from fundamentals.news.store import NewsObservationStore

    observation = _observation(NewsSourceFamily.FIRST_PARTY, source_id="bse:concurrent")
    stores = tuple(NewsObservationStore(tmp_path) for _ in range(8))
    with ThreadPoolExecutor(max_workers=len(stores)) as executor:
        writes = tuple(executor.map(lambda store: store.append((observation,)), stores))

    assert sum(writes) == 1
    assert NewsObservationStore(tmp_path).read("TITAN") == (observation,)


def test_bse_parser_keeps_raw_material_category_fields_and_payload_hash() -> None:
    """BSE material rows retain the exact routing fields and canonical row digest."""
    from fundamentals.ingest.news_bse import parse_bse_announcements

    row = {
        "CATEGORYNAME": "Company Update",
        "SUBCATNAME": "Acquisition",
        "HEADLINE": "Titan Company Limited acquires a subsidiary",
        "NEWS_DT": "2026-08-22T10:30:00",
        "ATTACHMENTNAME": "titan-update.pdf",
        "NEWSID": "42",
    }
    entity = _news_entity()

    result = parse_bse_announcements((row,), entity=entity, observed_at=_OBSERVED_AT)

    assert len(result.observations) == 1
    observation = result.observations[0]
    expected_payload = json.dumps(
        row, ensure_ascii=True, separators=(",", ":"), sort_keys=True
    ).encode()
    assert observation.raw_category == "Company Update"
    assert observation.raw_subcategory == "Acquisition"
    assert observation.raw_title == "Titan Company Limited acquires a subsidiary"
    assert observation.source_id == "bse-announcements:42"
    assert observation.issuer_id == "NSE:TITAN"
    assert observation.parser_version == "news-bse-v1"
    assert observation.raw_published_at == "2026-08-22T10:30:00"
    assert observation.raw_attachment_name == "titan-update.pdf"
    assert observation.raw_source_id == "42"
    assert observation.payload_sha256 == hashlib.sha256(expected_payload).hexdigest()


def test_exchange_timestamps_are_interpreted_as_ist_before_utc_storage() -> None:
    """A pre-dawn exchange timestamp keeps its prior UTC calendar date."""
    from fundamentals.ingest.news_bse import parse_bse_announcements
    from fundamentals.ingest.news_nse import parse_nse_announcements

    entity = _news_entity()
    bse = parse_bse_announcements(
        (
            {
                "CATEGORYNAME": "Result",
                "HEADLINE": "Titan announces quarterly results",
                "NEWS_DT": "2026-08-22T02:00:00",
                "NEWSID": "ist-bse",
            },
        ),
        entity=entity,
        observed_at=_OBSERVED_AT,
    )
    nse = parse_nse_announcements(
        (
            {
                "symbol": "TITAN",
                "sm_isin": "INE280A01028",
                "seq_id": "ist-nse",
                "an_dt": "22-Aug-2026 02:00:00",
                "desc": "Financial Results",
                "attchmntText": "Titan announces quarterly results",
            },
        ),
        entities=(entity,),
        observed_at=_OBSERVED_AT,
    )

    assert bse.observations[0].published_at == datetime(2026, 8, 21, 20, 30, tzinfo=UTC)
    assert nse.observations[0].published_at == datetime(2026, 8, 21, 20, 30, tzinfo=UTC)
    from fundamentals.api.news_cli import render_news_table
    from fundamentals.contracts.news import NewsLaneResult
    from fundamentals.news.events import derive_news_events

    rendered = render_news_table(
        NewsLaneResult(
            events=derive_news_events(bse.observations),
            observations=bse.observations,
            quarantined=(),
            warnings=(),
            sources=(bse,),
        )
    )

    assert "2026-08-21 | RESULTS | yes" in rendered


def test_bse_missing_row_count_is_non_retried_invalid_through_live_composition(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A successful BSE response without ROWCNT is schema-invalid, not unreachable."""
    from fundamentals.api.news_cli import run_news_command
    from fundamentals.ingest.news_bse import BseNewsSource

    class CountingBse(_FixtureBse):
        def __init__(self) -> None:
            super().__init__({"Table": [{"NEWSID": "page-one"}]})
            self.calls = 0

        def announcements(self, **kwargs: object) -> dict[str, object]:
            self.calls += 1
            return super().announcements(**kwargs)

    client = CountingBse()

    def bse_factory(raw_root: Path, entity: NewsEntity) -> BseNewsSource:
        source = BseNewsSource(raw_root / "bse", entity=entity, retry_backoff_seconds=0)
        monkeypatch.setattr(source, "_load_client_class", lambda: lambda **_: client)
        return source

    result = run_news_command(
        _news_args(live=True),
        store_root=tmp_path / "news",
        raw_root=tmp_path / "raw",
        observed_at=_OBSERVED_AT,
        bse_source_factory=bse_factory,
        nse_source_factory=lambda *_: _StaticNewsSource("nse-announcements"),
        et_source_factory=lambda *_: _StaticNewsSource("et-markets-rss"),
    )

    bse = next(source for source in result.sources if source.source_id == "bse-announcements")
    assert client.calls == 1
    assert bse.warnings[0].kind is NewsSourceHealthKind.INVALID
    assert all(warning.kind is not NewsSourceHealthKind.UNREACHABLE for warning in bse.warnings)


def test_bse_positive_row_count_cannot_end_with_an_empty_page(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A claimed positive total cannot be accepted when the next page is empty."""
    from fundamentals.ingest.news_bse import BseNewsSource
    from fundamentals.ingest.news_common import NewsSourceSchemaError

    source = BseNewsSource(tmp_path, entity=_news_entity(), retry_backoff_seconds=0)
    monkeypatch.setattr(
        source,
        "_load_client_class",
        lambda: lambda **_: _FixtureBse({"Table": [], "Table1": [{"ROWCNT": 1}]}),
    )

    with pytest.raises(NewsSourceSchemaError, match="ended before"):
        source.fetch(
            from_date=_PUBLISHED_AT.date(),
            to_date=_PUBLISHED_AT.date(),
            observed_at=_OBSERVED_AT,
        )


def test_malformed_et_xml_is_invalid_through_live_composition(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A successful ET fetch with malformed XML is schema-invalid, never unreachable."""
    from fundamentals.api.news_cli import run_news_command
    from fundamentals.ingest.news_et import EtMarketsNewsSource

    def et_factory(entities: tuple[NewsEntity, ...]) -> EtMarketsNewsSource:
        source = EtMarketsNewsSource(entities=entities, retry_backoff_seconds=0)
        monkeypatch.setattr(source, "_fetch_once", lambda: b"<rss><channel>")
        return source

    result = run_news_command(
        _news_args(live=True),
        store_root=tmp_path / "news",
        raw_root=tmp_path / "raw",
        observed_at=_OBSERVED_AT,
        bse_source_factory=lambda *_: _StaticNewsSource("bse-announcements"),
        nse_source_factory=lambda *_: _StaticNewsSource("nse-announcements"),
        et_source_factory=et_factory,
    )

    et = next(source for source in result.sources if source.source_id == "et-markets-rss")
    assert et.warnings[0].kind is NewsSourceHealthKind.INVALID
    assert all(warning.kind is not NewsSourceHealthKind.UNREACHABLE for warning in et.warnings)


def test_bse_missing_mandatory_fields_retain_raw_row_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Rows that cannot become observations remain durably inspectable in the raw lane."""
    from fundamentals.ingest.news_bse import BseNewsSource

    raw_row = {"CATEGORYNAME": "Result", "HEADLINE": "missing id", "NEWS_DT": "2026-08-22T10:30:00"}

    source = BseNewsSource(
        tmp_path,
        entity=_news_entity(),
        max_retries=1,
    )
    monkeypatch.setattr(
        source,
        "_load_client_class",
        lambda: lambda **_: _FixtureBse({"Table": [raw_row], "Table1": [{"ROWCNT": 1}]}),
    )

    result = source.fetch(
        from_date=_PUBLISHED_AT.date(),
        to_date=_PUBLISHED_AT.date(),
        observed_at=_OBSERVED_AT,
    )

    assert result.warnings[0].kind is NewsSourceHealthKind.INVALID
    assert b'"HEADLINE":"missing id"' in (tmp_path / "invalid_bse_rows.jsonl").read_bytes()


def test_nse_parser_resolves_exact_symbol_and_drops_unrelated_rows() -> None:
    """NSE quarantine is reserved for contradiction, not a row about another issuer."""
    from fundamentals.ingest.news_nse import parse_nse_announcements

    entities = (_news_entity(),)
    rows = (
        {
            "symbol": "TITAN",
            "seq_id": "nse-42",
            "an_dt": "22-Aug-2026 10:30:00",
            "desc": "Financial Results",
            "attchmntText": "Titan announces quarterly results",
            "attchmntFile": "https://nsearchives.nseindia.com/corporate/titan.pdf",
        },
        {
            "symbol": "OTHER",
            "seq_id": "nse-43",
            "an_dt": "22-Aug-2026 11:30:00",
            "desc": "Company Update",
            "attchmntText": "Other Limited expands capacity",
            "attchmntFile": "https://nsearchives.nseindia.com/corporate/other.pdf",
        },
    )

    result = parse_nse_announcements(rows, entities=entities, observed_at=_OBSERVED_AT)

    assert len(result.observations) == 1
    assert result.observations[0].symbol == "TITAN"
    assert result.quarantined == ()
    assert result.dropped_count == 1


def test_nse_missing_upstream_id_uses_payload_independent_fallback_identity() -> None:
    """Wrapper metadata churn cannot rename an occurrence with no NSE sequence ID."""
    from fundamentals.ingest.news_nse import parse_nse_announcements

    row = {
        "symbol": "TITAN",
        "an_dt": "22-Aug-2026 10:30:00",
        "desc": "Financial Results",
        "attchmntText": "Titan announces quarterly results",
        "attchmntFile": "https://nsearchives.nseindia.com/corporate/titan.pdf",
        "response_elapsed_ms": 10,
    }
    first = parse_nse_announcements(
        (row,), entities=(_news_entity(),), observed_at=_OBSERVED_AT
    ).observations[0]
    refreshed = parse_nse_announcements(
        ({**row, "response_elapsed_ms": 999},),
        entities=(_news_entity(),),
        observed_at=_OBSERVED_AT,
    ).observations[0]

    assert first.raw_source_id.startswith("fallback-")
    assert refreshed.observation_id == first.observation_id
    assert refreshed.payload_sha256 != first.payload_sha256


def test_nse_contradictory_isin_cannot_fall_through_to_symbol() -> None:
    """A mismatched stronger identifier quarantines even when the symbol text matches."""
    from fundamentals.ingest.news_nse import parse_nse_announcements

    entities = (_news_entity(isin="INE280A01028"),)
    row = {
        "symbol": "TITAN",
        "sm_isin": "INE999999999",
        "seq_id": "nse-contradiction",
        "an_dt": "22-Aug-2026 10:30:00",
        "desc": "Financial Results",
        "attchmntText": "Titan announces quarterly results",
    }

    result = parse_nse_announcements((row,), entities=entities, observed_at=_OBSERVED_AT)

    assert result.observations == ()
    assert len(result.quarantined) == 1


def test_nse_unverifiable_isin_falls_through_to_symbol_with_a_note() -> None:
    """An unconfigured ISIN is recorded but cannot block an exact symbol match."""
    from fundamentals.ingest.news_nse import parse_nse_announcements

    entities = (_news_entity(),)
    row = {
        "symbol": "TITAN",
        "sm_isin": "INE280A01028",
        "seq_id": "nse-unverifiable",
        "an_dt": "22-Aug-2026 10:30:00",
        "desc": "Financial Results",
        "attchmntText": "Titan announces quarterly results",
    }

    result = parse_nse_announcements((row,), entities=entities, observed_at=_OBSERVED_AT)

    assert len(result.observations) == 1
    assert result.observations[0].symbol == "TITAN"
    assert "unverified ISIN" in result.observations[0].identity_note
    assert result.quarantined == ()


def test_media_matching_uses_only_curated_multiword_aliases() -> None:
    """Common ticker words and XBRL rename identifiers cannot attach media stories."""
    from fundamentals.api.news_cli import _entity
    from fundamentals.api.watchlist_config import load_watchlist_config
    from fundamentals.news.entity import match_news_entity

    entities = (
        NewsEntity(symbol="ETERNAL", bse_scrip="543320", isin=None, aliases=("Eternal Limited",)),
        NewsEntity(
            symbol="TITAN", bse_scrip="500114", isin=None, aliases=("Titan Company Limited",)
        ),
        NewsEntity(symbol="THERMAX", bse_scrip="500411", isin=None, aliases=("Thermax Limited",)),
    )

    assert match_news_entity(entities, title="the eternal question of rate cuts") is None
    assert match_news_entity(entities, title="OceanGate Titan submersible inquiry") is None
    assert match_news_entity(entities, title="Thermax of the rally") is None
    assert match_news_entity(entities, title="Titan Company Limited posts strong Q1") == entities[1]

    titan = load_watchlist_config(Path("config/watchlist.yaml")).stock("TITAN")
    assert titan.identifiers.news_aliases == ("Titan Company Limited",)
    assert _entity(titan).aliases == ("Titan Company Limited",)


def test_fixture_mode_skips_an_unverified_bse_scrip() -> None:
    """Synthetic fixture runs must not promote a flagged BSE scrip to first-party news."""
    from fundamentals.api.news_cli import run_news_command

    result = run_news_command(_news_args("MTARTECH"), observed_at=_OBSERVED_AT)

    bse = next(source for source in result.sources if source.source_id == "bse-announcements")
    assert bse.observations == ()
    assert bse.warnings[0].kind is NewsSourceHealthKind.SKIPPED
    assert "scrip unverified" in bse.warnings[0].message


def test_live_news_composition_injects_paths_degrades_and_skips_unverified_bse(
    tmp_path: Path,
) -> None:
    """The live seam persists fake data, filters its window, and isolates each source."""
    from fundamentals.api.news_cli import run_news_command
    from fundamentals.contracts.news import NewsFetchResult
    from fundamentals.ingest.news_common import NewsSourceError

    recent = _observation(NewsSourceFamily.FIRST_PARTY, source_id="nse:recent").model_copy(
        update={"symbol": "MTARTECH", "issuer_id": "NSE:MTARTECH"}
    )
    old = _observation(
        NewsSourceFamily.FIRST_PARTY,
        source_id="nse:old",
        published_at=_PUBLISHED_AT - timedelta(days=31),
    ).model_copy(update={"symbol": "MTARTECH", "issuer_id": "NSE:MTARTECH"})
    calls: list[str] = []

    class FakeNse:
        def fetch(self, **_: object) -> NewsFetchResult:
            calls.append("nse")
            return NewsFetchResult(source_id="nse-announcements", observations=(recent, old))

    class FakeEt:
        def fetch(self, **_: object) -> NewsFetchResult:
            calls.append("et")
            raise NewsSourceError("synthetic ET outage")

    def bse_factory(*_: object) -> object:
        calls.append("bse")
        raise AssertionError("unverified BSE scrip must not be fetched")

    result = run_news_command(
        _news_args("MTARTECH", live=True),
        store_root=tmp_path / "news",
        raw_root=tmp_path / "raw",
        observed_at=_OBSERVED_AT,
        bse_source_factory=bse_factory,
        nse_source_factory=lambda *_: FakeNse(),
        et_source_factory=lambda *_: FakeEt(),
    )

    assert calls == ["nse", "et"]
    assert result.observations == (recent,)
    assert any(warning.kind is NewsSourceHealthKind.SKIPPED for warning in result.warnings)
    assert any(warning.kind is NewsSourceHealthKind.UNREACHABLE for warning in result.warnings)
    assert (tmp_path / "news" / "MTARTECH.jsonl").is_file()


def test_live_news_composition_applies_persisted_history_as_source_health(
    tmp_path: Path,
) -> None:
    """Persisted success history reaches each composed health outcome, not adapter parameters."""
    from fundamentals.api.news_cli import run_news_command
    from fundamentals.ingest.news_bse import OBSERVATION_SOURCE_PREFIX as BSE_PREFIX
    from fundamentals.ingest.news_et import OBSERVATION_SOURCE_PREFIX as ET_PREFIX
    from fundamentals.ingest.news_nse import OBSERVATION_SOURCE_PREFIX as NSE_PREFIX
    from fundamentals.news.store import NewsObservationStore

    store_root = tmp_path / "news"
    seed = NewsObservationStore(store_root)
    seed.append(
        (
            _observation(NewsSourceFamily.FIRST_PARTY, source_id=f"{BSE_PREFIX}history"),
            _observation(NewsSourceFamily.FIRST_PARTY, source_id=f"{NSE_PREFIX}history"),
            _observation(NewsSourceFamily.MEDIA, source_id=f"{ET_PREFIX}history"),
        )
    )
    calls: dict[str, dict[str, object]] = {}

    class EmptySource:
        def __init__(self, source_id: str) -> None:
            self._source_id = source_id

        def fetch(self, **kwargs: object) -> NewsFetchResult:
            calls[self._source_id] = kwargs
            return NewsFetchResult(source_id=self._source_id)

    result = run_news_command(
        _news_args(live=True),
        store_root=store_root,
        raw_root=tmp_path / "raw",
        observed_at=_OBSERVED_AT,
        bse_source_factory=lambda *_: EmptySource("bse-announcements"),
        nse_source_factory=lambda *_: EmptySource("nse-announcements"),
        et_source_factory=lambda *_: EmptySource("et-markets-rss"),
    )

    assert all("previous_had_data" not in call for call in calls.values())
    empty_source_ids = {
        warning.source_id
        for warning in result.warnings
        if warning.kind is NewsSourceHealthKind.EMPTY
    }
    assert empty_source_ids == {
        "bse-announcements",
        "nse-announcements",
        "et-markets-rss",
    }
    assert all(warning.kind is not NewsSourceHealthKind.NO_HISTORY for warning in result.warnings)


def test_live_news_composition_keeps_stale_health_with_a_partial_invalid_parser_result(
    tmp_path: Path,
) -> None:
    """One skipped parser row cannot hide staleness in the valid remainder of a feed."""
    from fundamentals.api.news_cli import run_news_command
    from fundamentals.ingest.news_nse import parse_nse_announcements

    stale_row = {
        "symbol": "TITAN",
        "seq_id": "nse-stale",
        "an_dt": "03-Aug-2026 10:30:00",
        "desc": "Financial Results",
        "attchmntText": "Titan announces quarterly results",
        "attchmntFile": "https://nsearchives.nseindia.com/corporate/titan.pdf",
    }
    invalid_row = {"symbol": "TITAN", "seq_id": "nse-invalid"}

    class PartialNseSource:
        def fetch(self, **_: object) -> NewsFetchResult:
            return parse_nse_announcements(
                (stale_row, invalid_row),
                entities=(_news_entity(),),
                observed_at=_OBSERVED_AT,
            )

    result = run_news_command(
        _news_args(live=True),
        store_root=tmp_path / "news",
        raw_root=tmp_path / "raw",
        observed_at=_OBSERVED_AT,
        bse_source_factory=lambda *_: _StaticNewsSource("bse-announcements"),
        nse_source_factory=lambda *_: PartialNseSource(),
        et_source_factory=lambda *_: _StaticNewsSource("et-markets-rss"),
    )

    nse = next(source for source in result.sources if source.source_id == "nse-announcements")

    assert {warning.kind for warning in nse.warnings} == {
        NewsSourceHealthKind.INVALID,
        NewsSourceHealthKind.STALE,
    }


def test_news_table_can_render_retained_quarantine_rows() -> None:
    """Operators can inspect retained identity evidence without raw-storage access."""
    from fundamentals.api.news_cli import render_news_table
    from fundamentals.contracts.news import NewsLaneResult

    unresolved = create_news_observation(
        symbol=None,
        isin=None,
        issuer_id=None,
        resolved=False,
        identity_note="contradictory issuer identifiers",
        source_family=NewsSourceFamily.FIRST_PARTY,
        source_id="nse-announcements:bad",
        source_url="https://nse.example/bad",
        attachment_url=None,
        published_at=_PUBLISHED_AT,
        observed_at=_OBSERVED_AT,
        raw_title="Conflicting issuer row",
        raw_category="",
        raw_subcategory="",
        raw_published_at="",
        raw_attachment_name=None,
        raw_source_id="bad",
        parser_version="test-v1",
        payload=b"bad",
    )
    rendered = render_news_table(
        NewsLaneResult(
            events=(), observations=(), quarantined=(unresolved,), warnings=(), sources=()
        ),
        show_quarantine=True,
    )

    assert "quarantine id | source | title | reason" in rendered
    assert unresolved.observation_id in rendered
    assert (
        "nse-announcements:bad | Conflicting issuer row | contradictory issuer identifiers"
        in rendered
    )


def test_news_cli_forwards_show_quarantine_to_the_renderer(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The public CLI flag exposes the inspection table even when its fixture is empty."""
    from fundamentals.api.cli import main

    assert main(["news", "--symbol", "TITAN", "--fixture", "--show-quarantine"]) == 0
    assert "quarantine id | source | title | reason" in capsys.readouterr().out


def test_fixture_mode_uses_the_same_observed_time_cutoff_as_live_mode() -> None:
    """Fixture dates are not silently rebased to their newest row for lookback filtering."""
    from fundamentals.api.news_cli import run_news_command

    result = run_news_command(
        _news_args(days=1),
        observed_at=_OBSERVED_AT + timedelta(days=3),
    )

    assert result.observations == ()
    assert result.events == ()


def test_programmatic_news_runner_does_not_raise_system_exit_for_prevalidated_args() -> None:
    """Argparse owns CLI validation; the callable news runner always returns a lane result."""
    from fundamentals.api.news_cli import run_news_command

    assert run_news_command(_news_args(days=0), observed_at=_OBSERVED_AT).events == ()


def test_programmatic_main_uses_argparse_for_invalid_news_arguments(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The public ``main`` entry point preserves argparse's invalid-argument exit semantics."""
    from fundamentals.api.cli import main

    with pytest.raises(SystemExit) as error:
        main(["news", "--symbol", "TITAN", "--days", "0", "--fixture"])

    assert error.value.code == 2
    assert "--days must be between 1 and 365" in capsys.readouterr().err


def test_store_failure_is_not_rendered_as_an_exchange_outage(tmp_path: Path) -> None:
    """A malformed local store root yields STORE health without invoking source factories."""
    from fundamentals.api.news_cli import run_news_command

    blocked_root = tmp_path / "not-a-directory"
    blocked_root.write_text("not a directory", encoding="utf-8")
    result = run_news_command(
        _news_args(live=True),
        store_root=blocked_root,
        observed_at=_OBSERVED_AT,
        bse_source_factory=lambda *_: pytest.fail("source must not start after a store failure"),
        nse_source_factory=lambda *_: pytest.fail("source must not start after a store failure"),
        et_source_factory=lambda *_: pytest.fail("source must not start after a store failure"),
    )

    assert result.warnings[0].kind is NewsSourceHealthKind.STORE
    assert all(warning.kind is not NewsSourceHealthKind.UNREACHABLE for warning in result.warnings)


def test_news_table_strips_terminal_controls_from_untrusted_title() -> None:
    """A feed title cannot inject ANSI or Unicode format controls into terminal cells."""
    from fundamentals.api.news_cli import render_news_table
    from fundamentals.contracts.news import NewsLaneResult
    from fundamentals.news.events import derive_news_events

    observation = _observation(
        NewsSourceFamily.MEDIA,
        source_id="et:ansi",
        title="Titan Company Limited \x1b[31mre\u202epaint\u200b\x1b[0m",
    )
    rendered = render_news_table(
        NewsLaneResult(
            events=derive_news_events((observation,)),
            observations=(observation,),
            quarantined=(),
            warnings=(),
            sources=(),
        )
    )

    assert "\x1b" not in rendered
    assert "\u202e" not in rendered
    assert "\u200b" not in rendered
    assert "Titan Company Limited [31mrepaint[0m" in rendered


def test_retry_policy_uses_typed_http_status_and_never_retries_schema_drift() -> None:
    """Message text cannot classify access policy, and programmer/schema faults fail immediately."""
    from fundamentals.ingest.news_common import (
        NewsSourceError,
        NewsSourceHardBlockError,
        run_with_retries,
    )

    type_error_calls = 0

    def schema_drift() -> None:
        nonlocal type_error_calls
        type_error_calls += 1
        raise TypeError("unexpected announcement schema")

    class TypedHttpError(OSError):
        status_code = 403

    with pytest.raises(TypeError, match="unexpected announcement schema"):
        run_with_retries("schema", schema_drift, max_retries=2, retry_backoff_seconds=0)
    with pytest.raises(NewsSourceHardBlockError):
        run_with_retries(
            "blocked",
            lambda: (_ for _ in ()).throw(TypedHttpError("provider response")),
            max_retries=2,
            retry_backoff_seconds=0,
        )
    assert type_error_calls == 1
    assert NewsSourceError is not NewsSourceHardBlockError


@pytest.mark.parametrize(
    ("status_code", "expected_calls", "expected_error"),
    [
        (401, 1, "hard"),
        (403, 1, "hard"),
        (407, 1, "hard"),
        (451, 1, "hard"),
        (503, 2, "transient"),
    ],
)
def test_bse_response_hook_preserves_typed_status_before_wrapper_conversion(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    status_code: int,
    expected_calls: int,
    expected_error: str,
) -> None:
    """BSE policy blocks stop once, while transient wrapper failures retain bounded retries."""
    from fundamentals.ingest.news_bse import BseNewsSource
    from fundamentals.ingest.news_common import NewsSourceError, NewsSourceHardBlockError

    class Response:
        def __init__(self, code: int) -> None:
            self.status_code = code

    class ConvertingBse:
        def __init__(self) -> None:
            self.session = _FixtureSession()
            self.calls = 0

        def announcements(self, **_: object) -> dict[str, object]:
            self.calls += 1
            response = Response(status_code)
            for hook in self.session.hooks["response"]:
                hook(response)  # type: ignore[operator]
            raise ConnectionError("wrapper discarded the HTTP status")

        def exit(self) -> None:
            pass

    client = ConvertingBse()
    source = BseNewsSource(tmp_path, entity=_news_entity(), retry_backoff_seconds=0)
    monkeypatch.setattr(source, "_load_client_class", lambda: lambda **_: client)
    error_type = NewsSourceHardBlockError if expected_error == "hard" else NewsSourceError

    with pytest.raises(error_type):
        source.fetch(
            from_date=_PUBLISHED_AT.date(),
            to_date=_PUBLISHED_AT.date(),
            observed_at=_OBSERVED_AT,
        )

    assert client.calls == expected_calls


def test_news_cli_fixture_renders_sourced_event_table(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The public fixture command renders dated confirmed and contextual events."""
    from fundamentals.api.cli import main

    code = main(["news", "--symbol", "TITAN", "--days", "30", "--fixture"])

    captured = capsys.readouterr()
    assert code == 0
    assert captured.out == (
        "date | type | confirmed | title | source URL\n"
        "2026-08-22 | OTHER | no | Titan Company Limited opens a new store | "
        "https://economictimes.example/markets/titan-store\n"
        "2026-08-22 | RESULTS | yes | Titan announces quarterly results | "
        "https://www.bseindia.com/xml-data/corpfiling/AttachHis/titan-results.pdf\n"
    )
