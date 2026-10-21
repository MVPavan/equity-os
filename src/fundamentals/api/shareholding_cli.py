"""``fundamentals shareholding acquire|ingest`` (plan D8 Task 4, R8).

``acquire`` writes the next generation under ``<raw-root>/<SYMBOL>/`` through the live
transport (an operator run, never scheduled). ``ingest`` replays one generation: a failed
listing or SHP request is recorded as its acquisition attempt and the command stops before
any capture is registered (exit non-zero); otherwise every successful capture is registered
and the first-party submissions are ingested against the issuer held at the instant. Then each
vendor capture is interpreted by its tree extractor (Task 6), bound to the issuer's share class
at the instant; a failed vendor request is its capture-less attempt (R8), and decides nothing
here.
"""

from __future__ import annotations

import argparse
import sys
import time
from collections.abc import Sequence
from datetime import UTC, date, datetime
from functools import partial
from pathlib import Path

import psycopg
import structlog
from psycopg_pool import ConnectionPool

from fundamentals.api.onboard_cli import live_transport
from fundamentals.api.watchlist_config import load_watchlist_config
from fundamentals.compare.run_config import VENDOR_EXTRACTORS, LoadedConfig, load_run_config
from fundamentals.compare.run_models import RunExitStatus
from fundamentals.contracts.acquisition_outcome import ExtractionOutcome
from fundamentals.contracts.config_versions import ConfigVersions
from fundamentals.contracts.entity_identity import IdentifierNamespace
from fundamentals.contracts.evidence import AcquisitionAttempt, CaptureReference
from fundamentals.contracts.retention import OriginalExpiredError
from fundamentals.contracts.snapshot import SnapshotError
from fundamentals.contracts.source_catalog import (
    SCREENER_INVESTORS,
    SCREENER_SHAREHOLDING,
    SHP_LISTING,
    SHP_XBRL,
    TIJORI_SHAREHOLDING,
    UPSTOX_SHAREHOLDING,
    surface_authority,
)
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
from fundamentals.evidence.capture_retention import ingest_vendor_retained
from fundamentals.evidence.repository import EvidenceRepository
from fundamentals.evidence.shareholding_ingest import (
    BASIS,
    FRAMEWORK,
    ShareholdingGeneration,
    failed_attempt,
    ingest_shareholding,
    shareholding_pins,
)
from fundamentals.evidence.vendor_ingest import VendorIngestRequest
from fundamentals.evidence.vendor_shareholding import (
    ShareholdingBinding,
    extract_vendor_shareholding,
)
from fundamentals.ingest.shareholding_filing import acquire
from fundamentals.pg.identity_seed import SettingKey
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
_VENDOR = (SCREENER_SHAREHOLDING, SCREENER_INVESTORS, TIJORI_SHAREHOLDING, UPSTOX_SHAREHOLDING)
_NO_FISCAL_YEAR_END = "entity {entity_id} has no evidenced fiscal-year-end month"
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
        identifiers = repository.issuer_identifiers(entity_id, as_of=args.instant)
        report = ingest_shareholding(
            ShareholdingGeneration(
                entity_id=entity_id,
                instant=args.instant,
                identifiers=identifiers,
                listing=next(ref for item, ref in registered if _pair(item) == SHP_LISTING),
                filings=tuple(
                    (item.request.url, ref) for item, ref in registered if _pair(item) == SHP_XBRL
                ),
            ),
            repository=repository,
            snapshots=store,
            config=config,
        )
        complete = all(item.outcome is ExtractionOutcome.COMPLETE for item in report.attempts)
        vendor = []
        if complete and report.packages:
            binding = _binding(args, captures, _share_class(pool, entity_id, args.instant))
            vendor = _vendors(
                args, captures, registered, binding, entity_id, repository, store, config
            )
    for attempt in (*report.attempts, *vendor):
        sys.stdout.write(f"shareholding {args.symbol}: {attempt.outcome.value} ")
        sys.stdout.write(f"{attempt.reason or ''}\n")
    sys.stdout.write(f"packages {list(report.packages)} selected {report.selected}\n")
    return RunExitStatus.SUCCESS if complete and report.packages else RunExitStatus.FAILURE


def _binding(
    args: argparse.Namespace, captures: Sequence[Capture], isin: str | None
) -> ShareholdingBinding:
    """The configured vendor identities, the share class at the instant and the Screener page."""
    ids = load_watchlist_config(args.config_root / WATCHLIST).stock(args.symbol).identifiers
    pages = [item.response.body for item in captures if _pair(item) == SCREENER_SHAREHOLDING]
    page = next((body for body in pages if body), b"")
    return ShareholdingBinding(
        symbol=args.symbol,
        security_isin=isin,
        screener_company_id=ids.screener_company_id,
        tijori_slug=ids.tijori_slug,
        tijori_company_id=ids.tijori_company_id,
        page=page,
    )


def _vendors(
    args: argparse.Namespace,
    captures: Sequence[Capture],
    registered: Sequence[tuple[Capture, CaptureReference]],
    binding: ShareholdingBinding,
    entity_id: int,
    repository: EvidenceRepository,
    store: SnapshotStore,
    config: LoadedConfig,
) -> list[AcquisitionAttempt]:
    """Each vendor request's attempt: its tree ingest, or its failure (R8)."""
    year_end = repository.settings_as_of(
        entity_id, SettingKey.FISCAL_YEAR_END_MONTH, repository.store_clock(), args.instant
    )
    if year_end is None:
        raise LookupError(_NO_FISCAL_YEAR_END.format(entity_id=entity_id))
    refs = {item.request.key: ref for item, ref in registered}
    attempts: list[AcquisitionAttempt] = []
    for item in captures:
        pair = _pair(item)
        if pair not in _VENDOR:
            continue
        if item.response.outcome != OK:
            failed = failed_attempt(
                *pair,
                item.request.key,
                item.response.outcome,
                entity_id=entity_id,
                instant=args.instant,
            )
            attempts += repository.put_attempts([failed])
            continue
        ref = refs[item.request.key]
        request = VendorIngestRequest(
            source_id=pair[0],
            surface=pair[1],
            request_key=ref.request_key,
            capture_id=ref.capture_id,
            representation=surface_authority(*pair).representation,
            entity_id=entity_id,
            period_end=args.instant,
            basis=BASIS,
            framework=FRAMEWORK,
        )
        extract = partial(
            extract_vendor_shareholding,
            binding=binding.model_copy(update={"url": item.request.url}),
        )
        report = ingest_vendor_retained(
            request,
            repository=repository,
            extract=extract,
            extractor_version=VENDOR_EXTRACTORS[pair][0],
            snapshot_store=store,
            dictionary=config.dictionary,
            mapping_set=config.mapping_set,
            policy=config.normalisation_policy,
            rounding_policy=config.rounding,
            fiscal_year_end_month=int(year_end.value_text),
        )
        attempts.append(report.attempt)
    return attempts


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


def _share_class(pool: ConnectionPool, entity_id: int, instant: date) -> str | None:
    """The one security ISIN the entity holds at the instant; with several, none (R4 Share
    class: vendor occurrences stay keyless)."""
    with pool.connection() as conn:
        held = {
            item.value
            for item in latest_slice(conn, instant)
            if item.entity_id == entity_id and item.namespace is IdentifierNamespace.ISIN
        }
    return held.pop() if len(held) == 1 else None


def _pair(item: Capture) -> tuple[str, str]:
    """A capture's ``(source, surface)``."""
    return item.request.source_id, item.request.surface
