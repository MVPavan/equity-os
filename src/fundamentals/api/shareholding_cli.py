"""``fundamentals shareholding acquire|ingest`` (plan D8 Task 4, R8).

``acquire`` writes the next generation under ``<raw-root>/<SYMBOL>/`` through the live
transport (an operator run, never scheduled). ``ingest`` replays one generation: a failed
listing or SHP request is recorded as its acquisition attempt and the command stops before
any capture is registered (exit non-zero); otherwise every successful capture is registered
and the first-party submissions are ingested against the issuer held at the instant. Vendor
bodies are registered only; Task 6 interprets them.
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import UTC, date, datetime
from pathlib import Path

import psycopg
import structlog
from psycopg_pool import ConnectionPool

from fundamentals.api.onboard_cli import live_transport
from fundamentals.api.watchlist_config import load_watchlist_config
from fundamentals.compare.run_config import load_run_config
from fundamentals.compare.run_models import RunExitStatus
from fundamentals.contracts.acquisition_outcome import ExtractionOutcome
from fundamentals.contracts.config_versions import ConfigVersions
from fundamentals.contracts.entity_identity import IdentifierNamespace
from fundamentals.contracts.retention import OriginalExpiredError
from fundamentals.contracts.snapshot import SnapshotError
from fundamentals.contracts.source_catalog import SHP_LISTING, SHP_XBRL
from fundamentals.entity.discovery import (
    MANIFEST_NAME,
    OK,
    Capture,
    DiscoveryManifest,
    Request,
    acquiring_fetch,
    replay_fetch,
    store_captures,
    write_generation,
)
from fundamentals.entity.identity_layers import latest_slice
from fundamentals.evidence.repository import EvidenceRepository
from fundamentals.evidence.shareholding_ingest import (
    ShareholdingGeneration,
    failed_attempt,
    ingest_shareholding,
    shareholding_pins,
)
from fundamentals.ingest.shareholding_filing import acquire
from fundamentals.pg.pool import DatabaseUnavailableError, open_pool
from fundamentals.pg.settings import PgRole, PgSettings
from fundamentals.store.snapshot_store import SnapshotStore

SHAREHOLDING_COMMAND = "shareholding"
ACQUIRE, INGEST = "acquire", "ingest"
DEFAULT_CONFIG_ROOT = "config"
WATCHLIST = "watchlist.yaml"
GENERATION_PREFIX = "gen-"
AUTHORIZATION = "fundamentals shareholding acquire (plan D8 Task 4)"
PAUSE_SECONDS = 3  # the probe's spacing between live requests (d8-probe.md §1)
# Dictionary v3, mapping set v7 and normalisation policy v2 (plan D8 Task 3).
SHAREHOLDING_VERSIONS = ConfigVersions(dictionary="v3", mapping_set="v7", normalisation_policy="v2")
_FIRST_PARTY = (SHP_LISTING, SHP_XBRL)
_NO_ENTITY = "no entity holds NSE symbol {symbol} at {instant}"
_FAILURES = (
    OSError,
    LookupError,
    ValueError,
    psycopg.Error,
    DatabaseUnavailableError,
    SnapshotError,
)


def add_shareholding_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Register ``shareholding acquire`` and ``shareholding ingest``."""
    parser = subparsers.add_parser(SHAREHOLDING_COMMAND, help="shareholding filings (D8)")
    actions = parser.add_subparsers(dest="shareholding_command", required=True)
    for name in (ACQUIRE, INGEST):
        action = actions.add_parser(name)
        action.add_argument("--symbol", required=True)
        action.add_argument("--instant", required=True, type=date.fromisoformat)
        action.add_argument("--raw-root", required=True, type=Path)
        action.add_argument("--config-root", type=Path, default=Path(DEFAULT_CONFIG_ROOT))
    ingest = actions.choices[INGEST]
    ingest.add_argument("--snapshot-root", required=True, type=Path)
    ingest.add_argument("--generation", type=int)


def dispatch_shareholding_command(args: argparse.Namespace) -> int | None:
    """Run a ``shareholding`` command, or return ``None`` for any other command."""
    if args.command != SHAREHOLDING_COMMAND:
        return None
    try:
        return _acquire(args) if args.shareholding_command == ACQUIRE else _ingest(args)
    except OriginalExpiredError as error:  # R13: names the expired capture
        sys.stderr.write(f"shareholding {args.symbol} refused: {error}\n")
        return RunExitStatus.FAILURE
    except _FAILURES as error:
        structlog.get_logger().error("shareholding_failed", error=type(error).__name__)
        return RunExitStatus.FAILURE


def _acquire(args: argparse.Namespace) -> int:
    """Acquire the next generation for one symbol and instant (live)."""
    slug = load_watchlist_config(args.config_root / WATCHLIST).stock(args.symbol)
    root: Path = args.raw_root / args.symbol
    taken = [
        int(path.name.removeprefix(GENERATION_PREFIX))
        for path in root.glob(f"{GENERATION_PREFIX}*")
    ]
    generation = max(taken, default=0) + 1
    send = live_transport()

    def paced(request: Request) -> tuple[int, bytes]:
        time.sleep(PAUSE_SECONDS)
        return send(request)

    fetch = acquiring_fetch(paced, lambda: datetime.now(UTC), [])
    log = acquire(args.symbol, args.instant, fetch, tijori_slug=slug.identifiers.tijori_slug)
    folder = root / f"{GENERATION_PREFIX}{generation}"
    write_generation(folder, args.symbol, AUTHORIZATION, generation, log)
    failed = [item for item in log if item.response.outcome != OK]
    sys.stdout.write(f"shareholding {args.symbol}: {folder} ({len(log)} requests, ")
    sys.stdout.write(f"{len(failed)} failed)\n")
    return RunExitStatus.SUCCESS if not failed else RunExitStatus.INCOMPLETE


def _ingest(args: argparse.Namespace) -> int:
    """Replay one generation and ingest it (see module docstring)."""
    captures = _replayed(args.raw_root / args.symbol, args.generation)
    config = load_run_config(args.config_root, SHAREHOLDING_VERSIONS)
    with open_pool(PgSettings(), PgRole.RUNTIME) as pool:
        repository = EvidenceRepository(pool)
        repository.pin_versions(shareholding_pins(config))
        entity_id = _entity(pool, args.symbol, args.instant)
        failed = [
            failed_attempt(
                item.request.source_id,
                item.request.surface,
                item.request.key,
                item.response.outcome,
                entity_id=entity_id,
                instant=args.instant,
            )
            for item in captures
            if (item.request.source_id, item.request.surface) in _FIRST_PARTY
            and item.response.outcome != OK
        ]
        if failed:
            for attempt in repository.put_attempts(failed):
                sys.stderr.write(f"shareholding {args.symbol}: {attempt.reason}\n")
            return RunExitStatus.FAILURE
        store = SnapshotStore(args.snapshot_root)
        usable = [item for item in captures if item.response.outcome == OK]
        with store.prepare_ordinary_output():
            refs = [ref for _, ref in store_captures(store, repository, usable)]
        registered = list(zip(usable, refs, strict=True))
        report = ingest_shareholding(
            ShareholdingGeneration(
                entity_id=entity_id,
                instant=args.instant,
                identifiers=repository.issuer_identifiers(entity_id, as_of=args.instant),
                listing=next(ref for item, ref in registered if _pair(item) == SHP_LISTING),
                filings=tuple(
                    (item.request.url, ref) for item, ref in registered if _pair(item) == SHP_XBRL
                ),
            ),
            repository=repository,
            snapshots=store,
            config=config,
        )
    for attempt in report.attempts:
        sys.stdout.write(f"shareholding {args.symbol}: {attempt.outcome.value} ")
        sys.stdout.write(f"{attempt.reason or ''}\n")
    sys.stdout.write(f"packages {list(report.packages)} selected {report.selected}\n")
    complete = all(item.outcome is ExtractionOutcome.COMPLETE for item in report.attempts)
    return RunExitStatus.SUCCESS if complete and report.packages else RunExitStatus.FAILURE


def _replayed(root: Path, generation: int | None) -> list[Capture]:
    """Every request of a generation (the latest when unnamed) with its recorded response."""
    if generation is None:
        generation = max(
            int(path.parent.name.removeprefix(GENERATION_PREFIX))
            for path in root.glob(f"{GENERATION_PREFIX}*/{MANIFEST_NAME}")
        )
    folder = root / f"{GENERATION_PREFIX}{generation}"
    manifest = DiscoveryManifest.model_validate_json((folder / MANIFEST_NAME).read_bytes())
    fetch = replay_fetch(folder)
    requests = [Request.model_validate(entry, from_attributes=True) for entry in manifest.entries]
    return [Capture(request=request, response=fetch(request, True)) for request in requests]


def _entity(pool: ConnectionPool, symbol: str, instant: date) -> int:
    """The one entity holding the NSE symbol at the instant."""
    with pool.connection() as conn:
        held = {
            item.entity_id
            for item in latest_slice(conn, instant)
            if item.namespace is IdentifierNamespace.NSE_SYMBOL and item.value == symbol
        }
    if len(held) != 1:
        raise LookupError(_NO_ENTITY.format(symbol=symbol, instant=instant))
    return held.pop()


def _pair(item: Capture) -> tuple[str, str]:
    """A capture's ``(source, surface)``."""
    return item.request.source_id, item.request.surface
