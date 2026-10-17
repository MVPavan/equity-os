"""The ``coverage`` command (plan D7): owner-chosen coverage, run as the owner login.

    coverage registry --instruments <upstox_instruments.raw.json.gz> --snapshot-root <dir>
        (load one retained instrument capture into the universe registry; a replay is a no-op)
    coverage screen-run --screen <txt> --csv <owner export> --snapshot-root <dir>
        (record a screen run: the CSV as a capture, each row resolved against the registry)
    coverage batch --screen-run <id> --members A,B,C --raw-root <dir> --snapshot-root <dir>
        [--config-root config]
        (declare a batch, replay each member's ``<raw-root>/<SYMBOL>/gen-<n>`` through
        ``onboard``, run its printed comparison when admitted, record each result, complete)

The composition root: the owner login comes from its credential file; onboarding and comparison
inside a batch keep their runtime pools. Nothing here requests a network resource or schedules
anything. Any refusal exits ``EXIT_REFUSED`` with a structlog error that names no credential; a
batch interrupted that way stays incomplete.
"""

from __future__ import annotations

import argparse
import os
import shlex
import sys
from collections.abc import Callable
from pathlib import Path

import psycopg
import structlog
from psycopg_pool import ConnectionPool
from pydantic import ValidationError

from fundamentals.api.compare_cli import add_compare_parser, run_compare
from fundamentals.api.onboard_cli import DEFAULT_CONFIG_ROOT, add_onboard_parser, onboard
from fundamentals.api.screener_cli_dispatch import EXIT_OK, EXIT_REFUSED
from fundamentals.contracts.snapshot import SnapshotError
from fundamentals.coverage.registry import load_registry
from fundamentals.coverage.screens import (
    complete_batch,
    declare_batch,
    record_member_result,
    record_screen_run,
)
from fundamentals.pg.pool import DatabaseUnavailableError, open_pool
from fundamentals.pg.role_secrets import RoleSecretError, load_login, secrets_dir
from fundamentals.pg.settings import PgRole, PgSettings
from fundamentals.store.snapshot_store import SnapshotStore

COVERAGE_COMMAND = "coverage"
REGISTRY_ACTION = "registry"
SCREEN_RUN_ACTION = "screen-run"
BATCH_ACTION = "batch"
_ACTION_DEST = "coverage_action"
_HELP = "owner-chosen coverage: the universe registry, screen runs and capture batches"
_REGISTRY_HELP = "load one retained Upstox instrument capture into the universe registry"
_SCREEN_RUN_HELP = "record a screen run from an owner-exported Screener CSV"
_BATCH_HELP = "onboard and compare exactly the chosen members of a screen run"
_MEMBER = "{name}\t{resolution}"
_RESULT = "{symbol}\t{outcome} run {run}"
_LOADED = "load\t{load_id}\ncreated\t{created}\nnew_listings\t{new}\ncandidate_events\t{events}"
_FAILED_EVENT = "coverage_command_failed"


def add_coverage_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register ``coverage`` with its ``registry`` action."""
    parser = subparsers.add_parser(COVERAGE_COMMAND, help=_HELP)
    actions = parser.add_subparsers(dest=_ACTION_DEST, required=True)
    registry = actions.add_parser(REGISTRY_ACTION, help=_REGISTRY_HELP)
    registry.add_argument("--instruments", type=Path, required=True)
    registry.add_argument("--snapshot-root", type=Path, required=True)
    screen_run = actions.add_parser(SCREEN_RUN_ACTION, help=_SCREEN_RUN_HELP)
    screen_run.add_argument("--screen", type=Path, required=True)
    screen_run.add_argument("--csv", type=Path, required=True)
    screen_run.add_argument("--snapshot-root", type=Path, required=True)
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
    actions = {REGISTRY_ACTION: _registry, SCREEN_RUN_ACTION: _screen_run, BATCH_ACTION: _batch}
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
    ) as failure:
        structlog.get_logger("fundamentals.coverage").error(
            _FAILED_EVENT, failure=type(failure).__name__, detail=str(failure)
        )
        return EXIT_REFUSED


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


def _screen_run(args: argparse.Namespace) -> int:
    """Record a screen run as the owner and print each member's listing or reason."""
    with _owner_pool() as pool:
        run = record_screen_run(
            pool, args.screen.read_text(), args.csv, SnapshotStore(args.snapshot_root)
        )
    lines = [f"screen_run\t{run.run_id}"] + [
        _MEMBER.format(name=member.name, resolution=member.listing_id or member.reason)
        for member in run.members
    ]
    sys.stdout.write("\n".join(lines) + "\n")
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
