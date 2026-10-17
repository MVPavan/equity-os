"""The ``coverage`` command (plan D7): owner-chosen coverage, run as the owner login.

    coverage registry --instruments <upstox_instruments.raw.json.gz> --snapshot-root <dir>
        (load one retained instrument capture into the universe registry; a replay is a no-op)

The composition root: the owner login comes from its credential file. Any refusal exits
``EXIT_REFUSED`` with a structlog error that names no credential.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import psycopg
import structlog
from pydantic import ValidationError

from fundamentals.api.screener_cli_dispatch import EXIT_OK, EXIT_REFUSED
from fundamentals.contracts.snapshot import SnapshotError
from fundamentals.coverage.registry import load_registry
from fundamentals.pg.pool import DatabaseUnavailableError, open_pool
from fundamentals.pg.role_secrets import RoleSecretError, load_login, secrets_dir
from fundamentals.pg.settings import PgRole, PgSettings
from fundamentals.store.snapshot_store import SnapshotStore

COVERAGE_COMMAND = "coverage"
REGISTRY_ACTION = "registry"
_ACTION_DEST = "coverage_action"
_HELP = "owner-chosen coverage: the universe registry"
_REGISTRY_HELP = "load one retained Upstox instrument capture into the universe registry"
_LOADED = "load\t{load_id}\ncreated\t{created}\nnew_listings\t{new}\ncandidate_events\t{events}"
_FAILED_EVENT = "coverage_command_failed"


def add_coverage_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register ``coverage`` with its ``registry`` action."""
    parser = subparsers.add_parser(COVERAGE_COMMAND, help=_HELP)
    actions = parser.add_subparsers(dest=_ACTION_DEST, required=True)
    registry = actions.add_parser(REGISTRY_ACTION, help=_REGISTRY_HELP)
    registry.add_argument("--instruments", type=Path, required=True)
    registry.add_argument("--snapshot-root", type=Path, required=True)


def dispatch_coverage_command(args: argparse.Namespace) -> int | None:
    """Run a ``coverage`` action, or return ``None`` for any other command."""
    if args.command != COVERAGE_COMMAND:
        return None
    try:
        return _registry(args)
    except (
        DatabaseUnavailableError,
        psycopg.Error,
        RoleSecretError,
        SnapshotError,
        ValidationError,
        OSError,
        ValueError,
    ) as failure:
        structlog.get_logger("fundamentals.coverage").error(
            _FAILED_EVENT, failure=type(failure).__name__, detail=str(failure)
        )
        return EXIT_REFUSED


def _registry(args: argparse.Namespace) -> int:
    """Load one instrument capture as the owner and print what it wrote."""
    login = load_login(PgRole.OWNER, secrets_dir(os.environ))
    with open_pool(PgSettings(), PgRole.OWNER, login=login) as pool:
        loaded = load_registry(pool, args.instruments, SnapshotStore(args.snapshot_root))
    text = _LOADED.format(
        load_id=loaded.load_id,
        created=loaded.created,
        new=loaded.new_listings,
        events=loaded.candidate_events,
    )
    sys.stdout.write(text + "\n")
    return EXIT_OK
