"""The ``ledger`` command: decisions, claim checks, imports and export (plan D3 Tasks 3, 5, 6).

    ledger decide <subject kind> <subject id> <kind> [--key K --value V --unit U]
        (the verbatim ruling is read from stdin)
    ledger check --version <id> --stock <symbol> --snapshot-root <dir>
        [--mode as_known|retrospective] [--watchlist config/watchlist.yaml]
    ledger import --snapshot-root <dir> [--config config/ledger_import.yaml] [--repo .]
        [--watchlist config/watchlist.yaml]
    ledger export <version id> [--out PATH]   (narrative bytes; stdout unless --out)

The composition root: ``decide`` runs as the owner login from its credential file; ``check``
and ``export`` run as the runtime role and ``import`` as the panel login (no model call);
``check`` and ``import`` get the stock's source catalog and the snapshot store. Any refusal, or a
version that does not import, exits ``EXIT_REFUSED`` with a structlog error that names no
credential.
"""

from __future__ import annotations

import argparse
import os
import sys
from decimal import Decimal
from pathlib import Path

import psycopg
import structlog
from pydantic import ValidationError

from fundamentals.api.screener_cli_dispatch import EXIT_OK, EXIT_REFUSED
from fundamentals.api.watchlist_config import load_watchlist_config, stock_catalog
from fundamentals.contracts.evidence import RunMode
from fundamentals.contracts.ledger import DecisionKind, PolicyValue, SubjectKind
from fundamentals.ledger.export import export_version
from fundamentals.ledger.importer import import_versions, load_import_config
from fundamentals.ledger.lifecycle import decide, validate
from fundamentals.pg.pool import DatabaseUnavailableError, open_pool
from fundamentals.pg.role_secrets import RoleSecretError, load_login, secrets_dir
from fundamentals.pg.settings import PgRole, PgSettings
from fundamentals.store.snapshot_store import SnapshotStore

LEDGER_COMMAND = "ledger"
DECIDE_ACTION = "decide"
CHECK_ACTION = "check"
IMPORT_ACTION = "import"
EXPORT_ACTION = "export"
DEFAULT_WATCHLIST = Path("config") / "watchlist.yaml"
DEFAULT_IMPORT_CONFIG = Path("config") / "ledger_import.yaml"
_ACTION_DEST = "ledger_action"
_HELP = "decide report-ledger subjects and check report versions"
_DECIDE_HELP = "record an owner decision; the verbatim ruling is read from stdin"
_CHECK_HELP = "check every claim of a version and append the validation"
_IMPORT_HELP = "import the configured retained versions as the panel role"
_EXPORT_HELP = "write a version's deterministic narrative bytes"
_POLICY_FIELDS = ("key", "value", "unit")
_DECISION = "decision\t{id}"
_VALIDATION = "validation\t{id}\nmode\t{mode}"
_STATE = "{key}\t{state}"
_IMPORTED = "{period}\t{kind}\t{version_id}\t{outcome}"
_FAILED_EVENT = "ledger_command_failed"
_MODES = {mode.value.lower(): mode for mode in RunMode}


def add_ledger_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register ``ledger`` with its ``decide``, ``check``, ``import`` and ``export`` actions."""
    parser = subparsers.add_parser(LEDGER_COMMAND, help=_HELP)
    actions = parser.add_subparsers(dest=_ACTION_DEST, required=True)
    decision = actions.add_parser(DECIDE_ACTION, help=_DECIDE_HELP)
    decision.add_argument("subject_kind", type=SubjectKind)
    decision.add_argument("subject_id", type=int)
    decision.add_argument("kind", type=DecisionKind)
    decision.add_argument("--key")
    decision.add_argument("--value", type=Decimal)
    decision.add_argument("--unit")
    check = actions.add_parser(CHECK_ACTION, help=_CHECK_HELP)
    check.add_argument("--version", type=int, required=True)
    check.add_argument("--stock", required=True)
    check.add_argument("--snapshot-root", type=Path, required=True)
    check.add_argument("--mode", choices=sorted(_MODES), default=RunMode.AS_KNOWN.value.lower())
    check.add_argument("--watchlist", type=Path, default=DEFAULT_WATCHLIST)
    imports = actions.add_parser(IMPORT_ACTION, help=_IMPORT_HELP)
    imports.add_argument("--snapshot-root", type=Path, required=True)
    imports.add_argument("--config", type=Path, default=DEFAULT_IMPORT_CONFIG)
    imports.add_argument("--repo", type=Path, default=Path())
    imports.add_argument("--watchlist", type=Path, default=DEFAULT_WATCHLIST)
    export = actions.add_parser(EXPORT_ACTION, help=_EXPORT_HELP)
    export.add_argument("version_id", type=int)
    export.add_argument("--out", type=Path)


def dispatch_ledger_command(args: argparse.Namespace) -> int | None:
    """Run a ``ledger`` action, or return ``None`` for any other command."""
    if args.command != LEDGER_COMMAND:
        return None
    try:
        actions = {
            DECIDE_ACTION: _decide,
            CHECK_ACTION: _check,
            IMPORT_ACTION: _import,
            EXPORT_ACTION: _export,
        }
        return actions[args.ledger_action](args)
    except (
        DatabaseUnavailableError,
        psycopg.Error,
        RoleSecretError,
        ValidationError,
        OSError,
        ValueError,
        LookupError,
    ) as failure:
        structlog.get_logger("fundamentals.ledger").error(
            _FAILED_EVENT, failure=type(failure).__name__, detail=str(failure)
        )
        return EXIT_REFUSED


def _decide(args: argparse.Namespace) -> int:
    """Record one owner decision with the ruling read verbatim from stdin."""
    fields = {name: getattr(args, name) for name in _POLICY_FIELDS}
    policy = None if fields["key"] is None else PolicyValue.model_validate(fields)
    ruling = sys.stdin.read()
    login = load_login(PgRole.OWNER, secrets_dir(os.environ))
    with open_pool(PgSettings(), PgRole.OWNER, login=login) as pool:
        record = decide(
            pool,
            subject_kind=args.subject_kind,
            subject_id=args.subject_id,
            kind=args.kind,
            ruling=ruling,
            policy=policy,
        )
    sys.stdout.write(_DECISION.format(id=record.id) + "\n")
    return EXIT_OK


def _check(args: argparse.Namespace) -> int:
    """Check one version as the runtime role and print each claim's state."""
    catalog = stock_catalog(load_watchlist_config(args.watchlist).stock(args.stock))
    snapshots = SnapshotStore(args.snapshot_root.resolve())
    with open_pool(PgSettings(), PgRole.RUNTIME) as pool:
        validation = validate(
            pool, args.version, mode=_MODES[args.mode], catalog=catalog, snapshots=snapshots
        )
    lines = [_VALIDATION.format(id=validation.id, mode=validation.mode)]
    lines += [_STATE.format(key=key, state=state) for key, state in validation.claim_states]
    lines += [str(state) for state in validation.version_states]
    sys.stdout.write("\n".join(lines) + "\n")
    return EXIT_OK


def _import(args: argparse.Namespace) -> int:
    """Import the configured versions as the panel login and print each outcome."""
    config = load_import_config(args.config)
    catalog = stock_catalog(load_watchlist_config(args.watchlist).stock(config.stock))
    snapshots = SnapshotStore(args.snapshot_root.resolve())
    login = load_login(PgRole.PANEL, secrets_dir(os.environ))
    with open_pool(PgSettings(), PgRole.PANEL, login=login) as pool:
        results = import_versions(
            pool, config, repo=args.repo.resolve(), catalog=catalog, snapshots=snapshots
        )
    lines = [
        _IMPORTED.format(
            period=r.period, kind=r.kind, version_id=r.version_id, outcome=r.status or r.failure
        )
        for r in results
    ]
    sys.stdout.write("\n".join(lines) + "\n")
    return EXIT_REFUSED if any(r.failure for r in results) else EXIT_OK


def _export(args: argparse.Namespace) -> int:
    """Write one version's narrative bytes as the runtime role, to ``--out`` or stdout."""
    with open_pool(PgSettings(), PgRole.RUNTIME) as pool, pool.connection() as conn:
        body = export_version(conn.cursor(), args.version_id)
    if args.out is None:
        sys.stdout.buffer.write(body)
    else:
        args.out.write_bytes(body)
    return EXIT_OK
