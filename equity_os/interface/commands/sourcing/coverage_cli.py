"""The ``coverage`` command (plan D7): owner-chosen coverage, run as the owner login.

    coverage registry --instruments <upstox_instruments.raw.json.gz> --snapshot-root <dir>
        (load one retained instrument capture into the universe registry; a replay is a no-op)
    coverage export --screen <name> --snapshot-root <dir> [--screens config/coverage/screens.yaml]
        [--watchlist config/coverage/watchlist.yaml]
        (run the configured formulas at Screener and Tijori, then record both runs,
        every response as a capture and each row bound against the registry, and their pair;
        print them once that commits, then one other-vendor read per pending review item, then
        the review)
    coverage review --pair <id> --snapshot-root <dir> [--watchlist config/coverage/watchlist.yaml]
    [--read]
        (print the pair's pending review items, each member's values beside the other vendor's;
        ``--read`` first makes the read of each pending item that has none recorded)
    coverage dispose --pair <id> --member <id> --kind <kind> --reason <text> --evidence <ref>
        (append the owner's one disposition of a review item)
    coverage batch --screen-run <id> --members A,B,C --raw-root <dir> --snapshot-root <dir>
        [--config-root config]
        (declare a batch, replay each member's ``<raw-root>/<SYMBOL>/gen-<n>`` through
        ``onboard``, run its printed comparison when admitted, record each result, complete)

The composition root: the owner login comes from its credential file; onboarding and comparison
inside a batch keep their runtime pools. Only ``export`` and ``review --read`` request network
resources, the amendment's endpoints with the vendor session cookies from the environment;
nothing schedules anything. Any refusal exits ``EXIT_REFUSED`` with a structlog error carrying
only text this codebase or the database wrote, never a library's (which can quote a request
header); a batch interrupted that way stays incomplete.
"""

from __future__ import annotations

import argparse
import os
import shlex
import sys
import traceback
from collections.abc import Callable
from pathlib import Path

import psycopg
import structlog
from psycopg_pool import ConnectionPool
from pydantic import ValidationError

from equity_os.contracts.sourcing.snapshot import SnapshotError
from equity_os.contracts.storage.retention import OriginalExpiredError
from equity_os.contracts.verification.review_queue import DispositionKind
from equity_os.coverage.screens import screen_export, screen_review
from equity_os.coverage.screens.screen_export import (
    export_screener,
    export_tijori,
    load_screen_config,
    screen_sources,
)
from equity_os.coverage.screens.screens import (
    complete_batch,
    declare_batch,
    record_member_result,
    record_screen_run,
)
from equity_os.coverage.universe.registry import load_registry
from equity_os.extraction.vendors.screener.screener_session_models import ScreenerSessionError
from equity_os.interface.commands.companies.onboard_cli import (
    DEFAULT_CONFIG_ROOT,
    add_onboard_parser,
    onboard,
)
from equity_os.interface.commands.sourcing.screener_cli_dispatch import EXIT_OK, EXIT_REFUSED
from equity_os.interface.commands.verification.compare_cli import add_compare_parser, run_compare
from equity_os.interface.entry.env_credentials import (
    _screener_credentials_from_env,
    _tijori_credentials_from_env,
)
from equity_os.interface.entry.watchlist_config import StockConfig, load_watchlist_config
from equity_os.sourcing.transport.http_session import RequestPacer
from equity_os.sourcing.vendors.screener.screener_session import ScreenerSessionSource
from equity_os.sourcing.vendors.tijori.tijori_source import TijoriError, TijoriSource
from equity_os.storage.database.pool import DatabaseUnavailableError, open_pool
from equity_os.storage.database.role_secrets import RoleSecretError, load_login, secrets_dir
from equity_os.storage.database.settings import PgRole, PgSettings
from equity_os.storage.raw_files.snapshot_store import SnapshotStore

COVERAGE_COMMAND = "coverage"
REGISTRY_ACTION = "registry"
EXPORT_ACTION = "export"
DEFAULT_SCREENS = Path("config/coverage/screens.yaml")
BATCH_ACTION = "batch"
REVIEW_ACTION = "review"
DISPOSE_ACTION = "dispose"
DEFAULT_WATCHLIST = Path("config/coverage/watchlist.yaml")
_ACTION_DEST = "coverage_action"
_HELP = "owner-chosen coverage: the universe registry, screen runs and capture batches"
_REGISTRY_HELP = "load one retained Upstox instrument capture into the universe registry"
_EXPORT_HELP = "run a configured screen at Screener and Tijori and record both runs"
_BATCH_HELP = "onboard and compare exactly the chosen members of a screen run"
_REVIEW_HELP = "print a screen pair's pending review items beside the other vendor's values"
_DISPOSE_HELP = "dispose one review item of a screen pair"
_ITEM = "item\t{member}\t{vendor}\t{status}\t{reason}\t{candidates}"
_VALUE = "value\t{member}\t{column}\t{own}\t{other}"
_MEMBER = "{vendor}:{name}\t{resolution}{qualifier}"
_QUALIFIER = f" {screen_review.SLUG_NOT_VERIFIED}"
_UNVERIFIED = "slug_not_verified\t{member}"
_RESULT = "{symbol}\t{outcome} run {run}"
_LOADED = "load\t{load_id}\ncreated\t{created}\nnew_listings\t{new}\ncandidate_events\t{events}"
_FAILED_EVENT = "coverage_command_failed"
_OWN_MODULES = "equity_os."


def add_coverage_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register ``coverage`` with its ``registry`` action."""
    parser = subparsers.add_parser(COVERAGE_COMMAND, help=_HELP)
    actions = parser.add_subparsers(dest=_ACTION_DEST, required=True)
    registry = actions.add_parser(REGISTRY_ACTION, help=_REGISTRY_HELP)
    registry.add_argument("--instruments", type=Path, required=True)
    registry.add_argument("--snapshot-root", type=Path, required=True)
    export = actions.add_parser(EXPORT_ACTION, help=_EXPORT_HELP)
    export.add_argument("--screen", required=True)
    export.add_argument("--snapshot-root", type=Path, required=True)
    export.add_argument("--screens", type=Path, default=DEFAULT_SCREENS)
    export.add_argument("--watchlist", type=Path, default=DEFAULT_WATCHLIST)
    review = actions.add_parser(REVIEW_ACTION, help=_REVIEW_HELP)
    review.add_argument("--pair", type=int, required=True)
    review.add_argument("--snapshot-root", type=Path, required=True)
    review.add_argument("--watchlist", type=Path, default=DEFAULT_WATCHLIST)
    review.add_argument("--read", action="store_true")
    dispose = actions.add_parser(DISPOSE_ACTION, help=_DISPOSE_HELP)
    dispose.add_argument("--pair", type=int, required=True)
    dispose.add_argument("--member", type=int, required=True)
    dispose.add_argument(
        "--kind", type=DispositionKind, choices=screen_review.DISPOSITION_KINDS, required=True
    )
    dispose.add_argument("--reason", required=True)
    dispose.add_argument("--evidence", required=True)
    batch = actions.add_parser(BATCH_ACTION, help=_BATCH_HELP)
    batch.add_argument("--screen-run", type=int, required=True)
    batch.add_argument("--members", type=lambda value: value.split(","), required=True)
    batch.add_argument("--raw-root", type=Path, required=True)
    batch.add_argument("--snapshot-root", type=Path, required=True)
    batch.add_argument("--config-root", type=Path, default=Path(DEFAULT_CONFIG_ROOT))


def dispatch_coverage_command(args: argparse.Namespace) -> int | None:
    """Run a ``coverage`` action, or return ``None`` for any other command."""
    if args.command != COVERAGE_COMMAND:
        return None
    actions = {
        REGISTRY_ACTION: _registry,
        EXPORT_ACTION: _export,
        REVIEW_ACTION: _review,
        DISPOSE_ACTION: _dispose,
        BATCH_ACTION: _batch,
    }
    try:
        return actions[args.coverage_action](args)
    except (
        DatabaseUnavailableError,
        psycopg.Error,
        RoleSecretError,
        SnapshotError,
        ValidationError,
        OSError,
        LookupError,
        RuntimeError,
        ValueError,
        ScreenerSessionError,
        TijoriError,
        OriginalExpiredError,
    ) as failure:
        structlog.get_logger("fundamentals.coverage").error(
            _FAILED_EVENT, failure=type(failure).__name__, detail=_own_text(failure)
        )
        return EXIT_REFUSED


def _own_text(failure: Exception) -> str | None:
    """The failure's text when this codebase or the database raised it, else nothing: a
    library's message (``http.client`` quoting an invalid ``Cookie`` header) can carry a
    credential."""
    *_, (frame, _) = traceback.walk_tb(failure.__traceback__)
    own = str(frame.f_globals.get("__name__", "")).startswith(_OWN_MODULES)
    return str(failure) if own or isinstance(failure, psycopg.Error) else None


def _owner_pool() -> ConnectionPool:
    """A pool authenticating as the owner login from its credential file."""
    login = load_login(PgRole.OWNER, secrets_dir(os.environ))
    return open_pool(PgSettings(), PgRole.OWNER, login=login)


def _registry(args: argparse.Namespace) -> int:
    """Load one instrument capture as the owner and print what it wrote."""
    with _owner_pool() as pool:
        loaded = load_registry(pool, args.instruments, SnapshotStore(args.snapshot_root))
    text = _LOADED.format(
        load_id=loaded.load_id,
        created=loaded.created,
        new=loaded.new_listings,
        events=loaded.candidate_events,
    )
    sys.stdout.write(text + "\n")
    return EXIT_OK


def _export(args: argparse.Namespace) -> int:
    """Fetch both vendors' exports first (a refusal on either writes nothing), then record them
    as the owner and print the pair, both runs and each member's listing or reason at once; then
    read the other vendor once per pending item and print the review."""
    screen = load_screen_config(args.screens)[args.screen]
    stocks = _stocks(args.watchlist)
    sources = _sources()
    pacer = RequestPacer(screen_export.SPACING_SECONDS)
    exports = (
        export_screener(sources[0], screen.screener),
        export_tijori(sources[1], screen.tijori, pacer=pacer),
    )
    snapshots = SnapshotStore(args.snapshot_root)
    with _owner_pool() as pool:
        done = record_screen_run(pool, *exports, snapshots)
        lines = [f"pair\t{done.pair_id}"]
        for run in (done.screener, done.tijori):
            lines.append(f"{run.vendor.value.lower()}_run\t{run.run_id}")
            lines += [
                _MEMBER.format(
                    vendor=run.vendor.value,
                    name=member.name,
                    resolution=member.listing_id or member.reason,
                    qualifier=_QUALIFIER if member.slug_verified is False else "",
                )  # fmt: skip
                for member in run.members
            ]
        _print(lines)
        _read_missing(pool, snapshots, done.pair_id, stocks, sources, pacer)
        _print(_review_lines(pool, snapshots, done.pair_id))
    return EXIT_OK


def _review(args: argparse.Namespace) -> int:
    """Print the pair's pending review items as the owner, first reading the other vendor for
    any item without a recorded read when ``--read``."""
    snapshots = SnapshotStore(args.snapshot_root)
    with _owner_pool() as pool:
        if args.read:
            pacer = RequestPacer(screen_export.SPACING_SECONDS)
            stocks = _stocks(args.watchlist)
            _read_missing(pool, snapshots, args.pair, stocks, _sources(), pacer)
        _print(_review_lines(pool, snapshots, args.pair))
    return EXIT_OK


def _sources() -> tuple[ScreenerSessionSource, TijoriSource]:
    """Both vendors' transports with the session cookies from the environment."""
    return screen_sources(_screener_credentials_from_env(), _tijori_credentials_from_env())


def _read_missing(
    pool: ConnectionPool,
    snapshots: SnapshotStore,
    pair_id: int,
    stocks: dict[str, StockConfig],
    sources: tuple[ScreenerSessionSource, TijoriSource],
    pacer: RequestPacer,
) -> None:
    """One other-vendor read for each pending item that has none recorded; recorded reads are
    skipped, so an interrupted run completes by running again."""
    screener, tijori = sources
    for item in screen_review.pending_items(pool, pair_id):
        if item.read is None:
            stock = stocks.get(item.nse_code or "")
            read = screen_review.read_other_vendor(item, stock, tijori, pacer, screener)
            screen_review.record_read(pool, snapshots, item, read, stock)


def _print(lines: list[str]) -> None:
    """Write ``lines`` to stdout now, so what has committed shows even if a later step fails."""
    sys.stdout.write("".join(line + "\n" for line in lines))
    sys.stdout.flush()


def _stocks(watchlist: Path) -> dict[str, StockConfig]:
    """The watchlist's stocks by NSE symbol."""
    return {stock.symbol: stock for stock in load_watchlist_config(watchlist).stocks}


def _review_lines(pool: ConnectionPool, snapshots: SnapshotStore, pair_id: int) -> list[str]:
    """Each bound Tijori member without a verified slug; each pending item, then each column of
    its member's row beside the other vendor's corresponding field, ``FIELD_NOT_EXPOSED``, the
    item's read gap or ``READ_NOT_RECORDED``."""
    lines = [
        _UNVERIFIED.format(member=member)
        for member in screen_review.slug_not_verified(pool, pair_id)
    ]
    items = screen_review.pending_items(pool, pair_id)
    for item, values in screen_review.side_by_side(pool, snapshots, items):
        lines.append(
            _ITEM.format(
                member=item.member_id,
                vendor=item.vendor.value,
                status=item.status.value,
                reason=item.reason or "",
                candidates=",".join(map(str, item.candidate_member_ids)),
            )
        )
        lines += [
            _VALUE.format(member=item.member_id, column=column, own=own, other=other)
            for column, own, other in values
        ]
    return lines


def _dispose(args: argparse.Namespace) -> int:
    """Append the owner's disposition of one review item."""
    with _owner_pool() as pool:
        screen_review.dispose(pool, args.pair, args.member, args.kind, args.reason, args.evidence)
    sys.stdout.write(f"disposed\t{args.member}\n")
    return EXIT_OK


def _batch(args: argparse.Namespace) -> int:
    """Declare the batch, then per member onboard, compare when admitted and record the
    terminal result; complete once every member has one."""
    with _owner_pool() as pool:
        batch = declare_batch(pool, args.screen_run, args.members)
        sys.stdout.write(f"batch\t{batch.batch_id}\n")
        for symbol, member_id in batch.members.items():
            done = onboard(
                _parsed(
                    add_onboard_parser,
                    *("onboard", symbol, "--raw-root", str(args.raw_root / symbol)),
                    *("--snapshot-root", str(args.snapshot_root)),
                    *("--config-root", str(args.config_root)),
                )
            )
            run_id = None
            if done.compare is not None:
                compare = _parsed(add_compare_parser, *shlex.split(done.compare)[1:])
                run_id = run_compare(compare).run_id
            record_member_result(
                pool,
                batch.batch_id,
                member_id,
                outcome=done.outcome,
                entity_id=done.entity_id,
                onboarding_record_id=done.onboarding_record_id,
                run_id=run_id,
                exit_code=done.exit,
            )
            result = _RESULT.format(symbol=symbol, outcome=done.outcome.value, run=run_id)
            sys.stdout.write(result + "\n")
        complete_batch(pool, batch.batch_id)
    sys.stdout.write("complete\tTrue\n")
    return EXIT_OK


def _parsed(
    register: Callable[[argparse._SubParsersAction[argparse.ArgumentParser]], None], *argv: str
) -> argparse.Namespace:
    """``argv`` parsed by the one command ``register`` adds, exactly as the CLI would."""
    parser = argparse.ArgumentParser()
    register(parser.add_subparsers(dest="command"))
    return parser.parse_args(argv)
