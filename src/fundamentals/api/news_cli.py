"""CLI composition helpers for the provenance-first news lane."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unicodedata import category as unicode_category

import structlog

from fundamentals.api.watchlist_config import StockConfig, WatchlistConfig, load_watchlist_config
from fundamentals.contracts.news import (
    NewsEntity,
    NewsEvent,
    NewsFetchResult,
    NewsLaneResult,
    NewsObservation,
    NewsSourceFamily,
    NewsSourceHealthKind,
    NewsSourceWarning,
)
from fundamentals.ingest.news_bse import (
    OBSERVATION_SOURCE_PREFIX as BSE_OBSERVATION_SOURCE_PREFIX,
)
from fundamentals.ingest.news_bse import (
    SOURCE_ID as BSE_SOURCE_ID,
)
from fundamentals.ingest.news_bse import (
    BseNewsSource,
    parse_bse_announcements,
)
from fundamentals.ingest.news_common import NewsSourceError, NewsSourceSchemaError
from fundamentals.ingest.news_et import OBSERVATION_SOURCE_PREFIX as ET_OBSERVATION_SOURCE_PREFIX
from fundamentals.ingest.news_et import (
    SOURCE_ID as ET_SOURCE_ID,
)
from fundamentals.ingest.news_et import (
    EtMarketsNewsSource,
    parse_et_markets_rss,
)
from fundamentals.ingest.news_nse import OBSERVATION_SOURCE_PREFIX as NSE_OBSERVATION_SOURCE_PREFIX
from fundamentals.ingest.news_nse import (
    SOURCE_ID as NSE_SOURCE_ID,
)
from fundamentals.ingest.news_nse import (
    NseNewsSource,
    parse_nse_announcements,
)
from fundamentals.news.events import derive_news_events
from fundamentals.news.health import with_source_health
from fundamentals.news.store import NewsObservationStore, NewsStoreError

NEWS_COMMAND = "news"
_CLI_LOGGER_NAME = "fundamentals.cli"
DEFAULT_DAYS = 30
MAX_DAYS = 365
_CONTROL_CHARACTERS = frozenset(chr(code) for code in (*range(0, 32), *range(127, 160)))
_QUARANTINE_HEADER = "quarantine id | source | title | reason"

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_WATCHLIST_PATH = _REPO_ROOT / "config" / "watchlist.yaml"
_DEFAULT_FIXTURE_DIR = _REPO_ROOT / "tests" / "fundamentals" / "fixtures"
_DEFAULT_NEWS_DIR = _REPO_ROOT / "data" / "news"
_DEFAULT_RAW_DIR = _REPO_ROOT / "data" / "raw" / "news"
_BSE_FIXTURE = "synthetic_bse_announcements.json"
_NSE_FIXTURE = "synthetic_nse_announcements.json"
_ET_FIXTURE = "synthetic_et_markets_news.xml"
_BSE_SCRIP_FIELD = "bse_scrip"
_SOURCE_RECENCY_BOUNDS = {
    BSE_SOURCE_ID: timedelta(days=14),
    NSE_SOURCE_ID: timedelta(days=14),
    ET_SOURCE_ID: timedelta(days=14),
}
_NON_HEALTH_RESULTS = frozenset(
    {
        NewsSourceHealthKind.SKIPPED,
        NewsSourceHealthKind.STORE,
        NewsSourceHealthKind.UNREACHABLE,
    }
)

BseSourceFactory = Callable[[Path, NewsEntity], BseNewsSource]
NseSourceFactory = Callable[[Path, NewsEntity, tuple[NewsEntity, ...]], NseNewsSource]
EtSourceFactory = Callable[[tuple[NewsEntity, ...]], EtMarketsNewsSource]


def _days_argument(value: str) -> int:
    """Validate the bounded lookback at argparse's public boundary."""
    try:
        days = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("--days must be an integer") from error
    if not 1 <= days <= MAX_DAYS:
        raise argparse.ArgumentTypeError(f"--days must be between 1 and {MAX_DAYS}")
    return days


def add_news_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register the ``fundamentals news`` command."""
    parser = subparsers.add_parser(
        NEWS_COMMAND,
        help="fetch recent per-stock announcements and render derived events",
    )
    parser.add_argument("--symbol", required=True, help="watchlist NSE symbol, e.g. TITAN")
    parser.add_argument(
        "--days", type=_days_argument, default=DEFAULT_DAYS, help="lookback days (1-365)"
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--live", action="store_true", help="fetch each source once, politely")
    mode.add_argument(
        "--fixture",
        action="store_true",
        help="read committed synthetic source fixtures (default)",
    )
    parser.add_argument(
        "--all-categories",
        action="store_true",
        help="include all BSE categories instead of the material-event set",
    )
    parser.add_argument(
        "--show-quarantine",
        action="store_true",
        help="render retained unresolved identifier rows after the event table",
    )
    parser.add_argument(
        "--config",
        default=str(_DEFAULT_WATCHLIST_PATH),
        help="path to watchlist.yaml",
    )


def _entity(stock: StockConfig) -> NewsEntity:
    """Project watchlist identity into the downward news contract."""
    return NewsEntity(
        symbol=stock.symbol,
        bse_scrip=stock.identifiers.bse_scrip,
        isin=stock.identifiers.isin,
        aliases=stock.identifiers.news_aliases,
    )


def _entities(config: WatchlistConfig) -> tuple[NewsEntity, ...]:
    """Build every configured identity so alias matching can prove uniqueness."""
    return tuple(_entity(stock) for stock in config.stocks)


def _object_rows(raw: object) -> tuple[dict[str, object], ...]:
    """Validate a decoded fixture as a list of object rows."""
    if not isinstance(raw, list):
        raise ValueError("news fixture must contain a JSON row list")
    rows: list[dict[str, object]] = []
    for item in raw:
        if not isinstance(item, dict):
            raise ValueError("news fixture row must be an object")
        rows.append({str(key): value for key, value in item.items()})
    return tuple(rows)


def _fixture_sources(
    *,
    fixture_dir: Path,
    stock: StockConfig,
    entity: NewsEntity,
    entities: tuple[NewsEntity, ...],
    observed_at: datetime,
    all_categories: bool,
) -> tuple[NewsFetchResult, ...]:
    """Parse all committed synthetic fixtures without touching the network."""
    bse_raw: object = json.loads((fixture_dir / _BSE_FIXTURE).read_text(encoding="utf-8"))
    if not isinstance(bse_raw, dict):
        raise ValueError("BSE news fixture must be an object")
    bse_rows = _object_rows(bse_raw.get("Table"))
    nse_raw: object = json.loads((fixture_dir / _NSE_FIXTURE).read_text(encoding="utf-8"))
    nse_rows = _object_rows(nse_raw)
    et_payload = (fixture_dir / _ET_FIXTURE).read_bytes()
    bse_result = (
        _skipped_bse()
        if _BSE_SCRIP_FIELD in stock.identifiers.needs_verification
        else parse_bse_announcements(
            bse_rows,
            entity=entity,
            observed_at=observed_at,
            all_categories=all_categories,
        )
    )
    return (
        bse_result,
        parse_nse_announcements(nse_rows, entities=entities, observed_at=observed_at),
        parse_et_markets_rss(et_payload, entities=entities, observed_at=observed_at),
    )


def _unreachable(source_id: str, error: Exception) -> NewsFetchResult:
    """Represent an unavailable source without converting it to no news."""
    return NewsFetchResult(
        source_id=source_id,
        warnings=(
            NewsSourceWarning(
                source_id=source_id,
                kind=NewsSourceHealthKind.UNREACHABLE,
                message=str(error),
            ),
        ),
    )


def _skipped_bse() -> NewsFetchResult:
    """Represent an unverified BSE scrip without making a network request."""
    return NewsFetchResult(
        source_id=BSE_SOURCE_ID,
        warnings=(
            NewsSourceWarning(
                source_id=BSE_SOURCE_ID,
                kind=NewsSourceHealthKind.SKIPPED,
                message="scrip unverified; BSE source skipped",
            ),
        ),
    )


def _invalid_source(source_id: str, error: NewsSourceSchemaError) -> NewsFetchResult:
    """Surface an upstream schema drift without calling it an availability failure."""
    return NewsFetchResult(
        source_id=source_id,
        warnings=(
            NewsSourceWarning(
                source_id=source_id,
                kind=NewsSourceHealthKind.INVALID,
                message=str(error),
            ),
        ),
    )


def _with_composed_source_health(
    results: tuple[NewsFetchResult, ...],
    *,
    previous_had_data: dict[str, bool],
    observed_at: datetime,
) -> tuple[NewsFetchResult, ...]:
    """Apply shared source-health policy after adapters return pure source results."""
    composed: list[NewsFetchResult] = []
    for result in results:
        recency_bound = _SOURCE_RECENCY_BOUNDS.get(result.source_id)
        terminal_invalid = (
            result.raw_count == 0
            and not result.observations
            and not result.quarantined
            and any(warning.kind is NewsSourceHealthKind.INVALID for warning in result.warnings)
        )
        if (
            recency_bound is None
            or terminal_invalid
            or any(warning.kind in _NON_HEALTH_RESULTS for warning in result.warnings)
        ):
            composed.append(result)
            continue
        composed.append(
            with_source_health(
                result,
                published_times=tuple(item.published_at for item in result.observations),
                previous_had_data=previous_had_data[result.source_id],
                observed_at=observed_at,
                recency_bound=recency_bound,
            )
        )
    return tuple(composed)


def _store_failure(error: NewsStoreError) -> NewsFetchResult:
    """Surface a local store failure separately from exchange availability."""
    return NewsFetchResult(
        source_id="news-store",
        warnings=(
            NewsSourceWarning(
                source_id="news-store",
                kind=NewsSourceHealthKind.STORE,
                message=str(error),
            ),
        ),
    )


def _default_bse_source(raw_root: Path, entity: NewsEntity) -> BseNewsSource:
    """Construct the production BSE source from injected composition values."""
    return BseNewsSource(raw_root / "bse", entity=entity)


def _default_nse_source(
    raw_root: Path, entity: NewsEntity, entities: tuple[NewsEntity, ...]
) -> NseNewsSource:
    """Construct the production NSE source from injected composition values."""
    return NseNewsSource(raw_root / "nse", entity=entity, entities=entities)


def _default_et_source(entities: tuple[NewsEntity, ...]) -> EtMarketsNewsSource:
    """Construct the production ET source from injected composition values."""
    return EtMarketsNewsSource(entities=entities)


def _live_sources(
    *,
    stock: StockConfig,
    entity: NewsEntity,
    entities: tuple[NewsEntity, ...],
    observed_at: datetime,
    cutoff: datetime,
    all_categories: bool,
    raw_root: Path,
    bse_source_factory: BseSourceFactory,
    nse_source_factory: NseSourceFactory,
    et_source_factory: EtSourceFactory,
) -> tuple[NewsFetchResult, ...]:
    """Run one bounded pass per live source, isolating only external failures."""
    sources: list[tuple[str, Callable[[], NewsFetchResult]]] = []
    results: list[NewsFetchResult] = []
    if _BSE_SCRIP_FIELD in stock.identifiers.needs_verification:
        results.append(_skipped_bse())
    else:
        sources.append(
            (
                BSE_SOURCE_ID,
                lambda: bse_source_factory(raw_root, entity).fetch(
                    from_date=cutoff.date(),
                    to_date=observed_at.date(),
                    observed_at=observed_at,
                    all_categories=all_categories,
                ),
            )
        )
    sources.extend(
        (
            (
                NSE_SOURCE_ID,
                lambda: nse_source_factory(raw_root, entity, entities).fetch(
                    from_date=cutoff.date(),
                    to_date=observed_at.date(),
                    observed_at=observed_at,
                ),
            ),
            (
                ET_SOURCE_ID,
                lambda: et_source_factory(entities).fetch(
                    observed_at=observed_at,
                ),
            ),
        )
    )
    for source_id, fetch in sources:
        try:
            results.append(fetch())
        except NewsSourceSchemaError as error:
            results.append(_invalid_source(source_id, error))
        except (NewsSourceError, OSError, ValueError) as error:
            results.append(_unreachable(source_id, error))
    return tuple(results)


def _within_window(
    observations: tuple[NewsObservation, ...],
    *,
    symbol: str,
    cutoff: datetime,
) -> tuple[NewsObservation, ...]:
    """Select resolved observations for one stock inside the requested window."""
    wanted = symbol.upper()
    return tuple(
        item
        for item in observations
        if item.resolved and item.symbol == wanted and item.published_at >= cutoff
    )


def _store_history(store: NewsObservationStore, symbol: str) -> dict[str, bool]:
    """Read source history before fetches so store failures cannot impersonate exchanges."""
    return {
        BSE_SOURCE_ID: store.source_had_data(BSE_OBSERVATION_SOURCE_PREFIX, symbol=symbol),
        NSE_SOURCE_ID: store.source_had_data(NSE_OBSERVATION_SOURCE_PREFIX, symbol=symbol),
        ET_SOURCE_ID: store.source_had_data(ET_OBSERVATION_SOURCE_PREFIX, symbol=symbol),
    }


def run_news_command(
    args: argparse.Namespace,
    *,
    fixture_dir: Path | None = None,
    store_root: Path | None = None,
    raw_root: Path | None = None,
    observed_at: datetime | None = None,
    bse_source_factory: BseSourceFactory | None = None,
    nse_source_factory: NseSourceFactory | None = None,
    et_source_factory: EtSourceFactory | None = None,
) -> NewsLaneResult:
    """Collect one stock's news in fixture or live mode and derive events."""
    config_path = Path(args.config).resolve()
    config = load_watchlist_config(config_path)
    stock = config.stock(args.symbol)
    entity = _entity(stock)
    entities = _entities(config)
    current_time = observed_at or datetime.now(UTC)
    cutoff = current_time - timedelta(days=args.days)
    sources: tuple[NewsFetchResult, ...]

    if args.live:
        store = NewsObservationStore(store_root or _DEFAULT_NEWS_DIR)
        try:
            previous_had_data = _store_history(store, entity.symbol)
        except NewsStoreError as error:
            sources = (_store_failure(error),)
            return NewsLaneResult(
                events=(),
                observations=(),
                quarantined=(),
                warnings=sources[0].warnings,
                sources=sources,
            )
        sources = _live_sources(
            stock=stock,
            entity=entity,
            entities=entities,
            observed_at=current_time,
            cutoff=cutoff,
            all_categories=args.all_categories,
            raw_root=raw_root or _DEFAULT_RAW_DIR,
            bse_source_factory=bse_source_factory or _default_bse_source,
            nse_source_factory=nse_source_factory or _default_nse_source,
            et_source_factory=et_source_factory or _default_et_source,
        )
        sources = _with_composed_source_health(
            sources,
            previous_had_data=previous_had_data,
            observed_at=current_time,
        )
        try:
            store.append(
                tuple(
                    item
                    for source in sources
                    for item in (*source.observations, *source.quarantined)
                )
            )
            observations = _within_window(
                store.read(entity.symbol), symbol=entity.symbol, cutoff=cutoff
            )
            quarantined = store.read_quarantine()
        except NewsStoreError as error:
            sources = (*sources, _store_failure(error))
            observations = ()
            quarantined = ()
    else:
        sources = _fixture_sources(
            fixture_dir=fixture_dir or _DEFAULT_FIXTURE_DIR,
            stock=stock,
            entity=entity,
            entities=entities,
            observed_at=current_time,
            all_categories=args.all_categories,
        )
        sources = _with_composed_source_health(
            sources,
            previous_had_data={source_id: False for source_id in _SOURCE_RECENCY_BOUNDS},
            observed_at=current_time,
        )
        observations = _within_window(
            tuple(item for source in sources for item in source.observations),
            symbol=entity.symbol,
            cutoff=cutoff,
        )
        quarantined = tuple(item for source in sources for item in source.quarantined)

    warnings = tuple(item for source in sources for item in source.warnings)
    return NewsLaneResult(
        events=derive_news_events(observations),
        observations=observations,
        quarantined=quarantined,
        warnings=warnings,
        sources=sources,
    )


def _event_source_url(event: NewsEvent, by_id: dict[str, NewsObservation]) -> str:
    """Choose a first-party URL when one backs the event, otherwise the earliest link."""
    observations = [by_id[item] for item in event.observation_ids if item in by_id]
    observations.sort(
        key=lambda item: (
            item.source_family is not NewsSourceFamily.FIRST_PARTY,
            item.published_at,
            item.observation_id,
        )
    )
    return observations[0].source_url if observations else ""


def _cell(value: str) -> str:
    """Remove untrusted control characters before terminal-table rendering."""
    sanitized = "".join(
        character
        for character in value
        if character not in _CONTROL_CHARACTERS and unicode_category(character) != "Cf"
    )
    return " ".join(sanitized.split()).replace("|", "/")


def render_news_table(result: NewsLaneResult, *, show_quarantine: bool = False) -> str:
    """Render the required sourced, dated event table and optional quarantine rows."""
    lines = ["date | type | confirmed | title | source URL"]
    by_id = {item.observation_id: item for item in result.observations}
    for event in result.events:
        lines.append(
            " | ".join(
                (
                    event.published_at.date().isoformat(),
                    event.event_type.value,
                    "yes" if event.confirmed else "no",
                    _cell(event.title),
                    _cell(_event_source_url(event, by_id)),
                )
            )
        )
    if not result.events:
        lines.append("(no events in requested window)")
    if show_quarantine:
        lines.append("")
        lines.append(_QUARANTINE_HEADER)
        for item in result.quarantined:
            lines.append(
                " | ".join(
                    (
                        item.observation_id,
                        _cell(item.source_id),
                        _cell(item.raw_title),
                        _cell(item.identity_note or "unresolved issuer identifier"),
                    )
                )
            )
    return "\n".join(lines)


def dispatch_news_command(args: argparse.Namespace) -> int | None:
    """Run the ``news`` command, or return ``None`` for any other command."""
    if args.command != NEWS_COMMAND:
        return None
    logger = structlog.get_logger(_CLI_LOGGER_NAME)
    news_result = run_news_command(args)
    for source in news_result.sources:
        logger.info(
            "news_source_summary",
            source=source.source_id,
            observations=len(source.observations),
            quarantined=len(source.quarantined),
            raw_count=source.raw_count,
            dropped_count=source.dropped_count,
        )
    for warning in news_result.warnings:
        logger.warning(
            "news_source_health",
            source=warning.source_id,
            kind=warning.kind.value,
            detail=warning.message,
        )
    sys.stdout.write(render_news_table(news_result, show_quarantine=args.show_quarantine) + "\n")
    return 0
