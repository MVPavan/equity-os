"""CLI composition helpers for Tijori's site-level and timeline event surfaces."""

from __future__ import annotations

import argparse
from pathlib import Path

import structlog
from pydantic import BaseModel, ConfigDict

from fundamentals.api.artifact_writer import preflight_out_paths, write_json_no_clobber
from fundamentals.api.watchlist_config import WatchlistConfig, load_watchlist_config
from fundamentals.ingest.tijori_events_models import (
    BREADTH_SURFACES,
    COMPANY_SURFACES,
    COMPANY_TIMELINE_NEEDS_STOCK,
    CONCALL_NOT_STATIC_REASON,
    NOT_STATIC_SURFACES,
    TijoriEventsCapabilityState,
    TijoriEventsFetch,
    TijoriEventsOutcome,
    TijoriEventsScope,
    TijoriEventsSurface,
    capabilities_of,
)
from fundamentals.ingest.tijori_source import (
    TijoriCredentials,
    TijoriSource,
    TijoriSourceConfig,
)

TIJORI_EVENTS_COMMAND = "tijori-events"

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_WATCHLIST_PATH = _REPO_ROOT / "config" / "watchlist.yaml"
_DEFAULT_OUT_ROOT = _REPO_ROOT / "data" / "raw" / "watchlist" / "tijori-events"
_MARKET_WIDE_DIRNAME = "market"
_SUMMARY_HEADER = "capability\tsurface\tscope\tstate\toutcome\telements\traw\tnote"
_RAW_SUFFIX = ".raw.html"
_ABSENT = "-"

# Surfaces a caller may name. The concall monitor is deliberately absent: its
# document carries nothing to parse, so offering it would promise an acquisition
# this adapter has verified it cannot make.
SELECTABLE_SURFACES: tuple[TijoriEventsSurface, ...] = tuple(
    surface for surface in TijoriEventsSurface if surface not in NOT_STATIC_SURFACES
)


class SkippedSurface(BaseModel):
    """One surface a run did not attempt, and why.

    A skipped surface is reported, never omitted: a caller who cannot see that
    the concall monitor was skipped would read its absence as the market having
    had no concalls.
    """

    model_config = ConfigDict(frozen=True)

    surface: TijoriEventsSurface
    outcome: TijoriEventsOutcome
    reason: str


class EventsRun(BaseModel):
    """Everything one ``tijori-events`` invocation acquired and declined."""

    model_config = ConfigDict(frozen=True)

    fetched: tuple[TijoriEventsFetch, ...]
    skipped: tuple[SkippedSurface, ...]


def add_tijori_events_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Register the ``fundamentals tijori-events`` command."""
    parser = subparsers.add_parser(
        TIJORI_EVENTS_COMMAND,
        help="acquire the typed Tijori site-level and timeline event surfaces",
    )
    parser.add_argument(
        "--surface",
        choices=tuple(surface.value for surface in SELECTABLE_SURFACES),
        default=None,
        help="one event surface (default: every market-wide surface)",
    )
    parser.add_argument(
        "--stock",
        default=None,
        help="watchlist NSE symbol, e.g. TITAN; required for company-timeline",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="output directory (default: data/raw/watchlist/tijori-events/<stock or market>)",
    )
    parser.add_argument(
        "--config",
        default=str(_DEFAULT_WATCHLIST_PATH),
        help="path to watchlist.yaml",
    )


def _watchlist_slugs(watchlist: WatchlistConfig) -> dict[str, str]:
    """Map every verified watchlist Tijori slug to its NSE symbol.

    A market-wide listing names companies this repo does not track, so this map
    only decides which rows get a recorded match. A slug flagged as unverified is
    left out: cross-linking on an unconfirmed identifier would manufacture a
    match this repo has not checked.
    """
    return {
        stock.identifiers.tijori_slug: stock.symbol
        for stock in watchlist.stocks
        if not stock.identifiers.unverified_tijori_fields()
    }


def _plan(
    args: argparse.Namespace,
) -> tuple[tuple[TijoriEventsSurface, ...], tuple[SkippedSurface, ...]]:
    """Resolve what this invocation fetches and what it declines, with reasons."""
    skipped = [
        SkippedSurface(
            surface=surface,
            outcome=TijoriEventsOutcome.NOT_STATIC,
            reason=CONCALL_NOT_STATIC_REASON,
        )
        for surface in NOT_STATIC_SURFACES
    ]
    if args.surface is not None:
        surface = TijoriEventsSurface(args.surface)
        if surface in COMPANY_SURFACES and args.stock is None:
            raise SystemExit(COMPANY_TIMELINE_NEEDS_STOCK)
        return (surface,), tuple(skipped)

    requested = list(BREADTH_SURFACES)
    for surface in COMPANY_SURFACES:
        if args.stock is None:
            skipped.append(
                SkippedSurface(
                    surface=surface,
                    outcome=TijoriEventsOutcome.SKIPPED,
                    reason=COMPANY_TIMELINE_NEEDS_STOCK,
                )
            )
        else:
            requested.append(surface)
    return tuple(requested), tuple(sorted(skipped, key=lambda skip: skip.surface.value))


def _surface_scope(surface: TijoriEventsSurface) -> TijoriEventsScope:
    """The scope a surface would report, so a skipped row still names its scope."""
    if surface in COMPANY_SURFACES:
        return TijoriEventsScope.COMPANY
    return TijoriEventsScope.MARKET_WIDE


def _artifact_name(surface: TijoriEventsSurface) -> str:
    """Name one artifact after the surface it was acquired from."""
    return f"{surface.value}.json"


def _raw_name(artifact_name: str) -> str:
    """Name the retained response body beside its artifact."""
    return f"{artifact_name.removesuffix('.json')}{_RAW_SUFFIX}"


def run_tijori_events_command(
    args: argparse.Namespace,
    *,
    credentials: TijoriCredentials,
) -> EventsRun:
    """Fetch the requested event surfaces and write their JSON beside their bytes."""
    watchlist = load_watchlist_config(Path(args.config).resolve())
    surfaces, skipped = _plan(args)
    slug: str | None = None
    symbol: str | None = None
    company_id: int | None = None
    out_name = _MARKET_WIDE_DIRNAME
    if args.stock is not None:
        try:
            stock = watchlist.stock(args.stock)
        except ValueError as error:
            raise SystemExit(str(error)) from error
        unverified = stock.identifiers.unverified_tijori_fields()
        if unverified:
            raise SystemExit(
                f"Tijori identifiers for {stock.symbol} are not verified: {', '.join(unverified)}"
            )
        slug = stock.identifiers.tijori_slug
        symbol = stock.symbol
        company_id = stock.identifiers.tijori_company_id
        out_name = stock.symbol

    source = TijoriSource(TijoriSourceConfig(credentials=credentials))
    slugs = _watchlist_slugs(watchlist)
    fetched = tuple(
        source.fetch_events(
            surface=surface,
            watchlist_slugs=slugs,
            slug=slug if surface in COMPANY_SURFACES else None,
            symbol=symbol if surface in COMPANY_SURFACES else None,
            company_id=company_id if surface in COMPANY_SURFACES else None,
        )
        for surface in surfaces
    )

    out_dir = Path(args.out).resolve() if args.out else _DEFAULT_OUT_ROOT / out_name
    out_dir.mkdir(parents=True, exist_ok=True)
    names = tuple(_artifact_name(surface) for surface in surfaces)
    # The artifact and its source bytes are pre-flighted together: retaining one
    # without the other would leave a recorded body hash with nothing to check.
    out_paths = tuple(out_dir / name for name in names) + tuple(
        out_dir / _raw_name(name) for name in names
    )
    preflight_out_paths(out_paths)
    logger = structlog.get_logger("fundamentals.tijori_events")
    for fetch, name in zip(fetched, names, strict=True):
        artifact = fetch.artifact
        write_json_no_clobber(out_dir / name, artifact.model_dump_json(indent=2) + "\n")
        write_json_no_clobber(out_dir / _raw_name(name), fetch.raw_body.decode("utf-8"))
        logger.info(
            "tijori_events_surface_written",
            surface=artifact.surface.value,
            scope=artifact.metadata.scope.value,
            outcome=artifact.outcome.value,
            elements=artifact.element_count,
            path=str(out_dir / name),
            raw_path=str(out_dir / _raw_name(name)),
        )
    for skip in skipped:
        logger.info(
            "tijori_events_surface_skipped",
            surface=skip.surface.value,
            outcome=skip.outcome.value,
            reason=skip.reason,
        )
    return EventsRun(fetched=fetched, skipped=skipped)


def render_tijori_events_summary(run: EventsRun) -> str:
    """Render one deterministic line per CAPABILITY, acquired or not.

    A surface is a page; a capability is one dataset that page offers, and the
    two do not correspond. Reporting per surface overstated what a run got: a
    single ``timeline ok 15`` line read as fifteen market events when those
    fifteen are filter types and viewer lists, and the page's event feed was
    never served statically at all. Every capability now states what it is,
    whether this adapter can acquire it, and how many elements it yielded.
    """
    lines = [_SUMMARY_HEADER]
    for fetch in run.fetched:
        artifact = fetch.artifact
        raw = _raw_name(_artifact_name(artifact.surface))
        for capability in artifact.capabilities:
            acquired = capability.state is TijoriEventsCapabilityState.ACQUIRED
            lines.append(
                "\t".join(
                    (
                        capability.capability.value,
                        capability.surface.value,
                        artifact.metadata.scope.value,
                        capability.state.value,
                        artifact.outcome.value if acquired else _ABSENT,
                        _ABSENT
                        if capability.element_count is None
                        else str(capability.element_count),
                        raw,
                        (artifact.note or capability.note) if acquired else capability.note,
                    )
                )
            )
    lines.extend(
        "\t".join(
            (
                declaration.capability.value,
                declaration.surface.value,
                _surface_scope(declaration.surface).value,
                declaration.state.value,
                skip.outcome.value,
                _ABSENT,
                _ABSENT,
                skip.reason,
            )
        )
        for skip in run.skipped
        for declaration in capabilities_of(skip.surface)
    )
    return "\n".join(lines)
