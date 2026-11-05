"""The ``legacy`` command: import, reconcile and transition legacy SQLite fact stores.

    legacy preflight --manifest M --out P
    legacy import --manifest M --preflight P [--owner O]
    legacy reconcile --manifest M --out R
    legacy cutover|reopen|rollback --manifest M --report R [--owner O]
    legacy status --manifest M

Like ``db``, every action targets the database in ``PgSettings`` (``EQOS_PG_DB``). Manifest
paths resolve against the working directory. ``status`` prints each store's legal next commands.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import psycopg
import structlog

from equity_os.interface.commands.sourcing.screener_cli_dispatch import EXIT_OK, EXIT_REFUSED
from equity_os.storage.database.approvals import GatedOperation, GateRefusedError
from equity_os.storage.database.pool import DatabaseUnavailableError, open_pool
from equity_os.storage.database.settings import PgRole, PgSettings
from equity_os.storage.facts.cutover import (
    LEGAL_COMMANDS,
    TransitionRefusedError,
    reconcile,
    store_status,
    transition,
)
from equity_os.storage.facts.legacy_import import (
    LegacyImportRefusedError,
    import_legacy,
    load_manifest,
    origin_id_for,
    preflight,
)

LEGACY_COMMAND = "legacy"
PREFLIGHT_ACTION = "preflight"
IMPORT_ACTION = "import"
STATUS_ACTION = "status"
RECONCILE_ACTION = "reconcile"
TRANSITIONS = {
    "cutover": GatedOperation.CUTOVER,
    "reopen": GatedOperation.REOPEN,
    "rollback": GatedOperation.ROLLBACK,
}
NOT_IMPORTED = "NOT_IMPORTED"
NOT_IMPORTED_COMMANDS = "legacy preflight, then legacy import"

_ACTION_DEST = "legacy_action"
_HELP = "import, reconcile, transition or inspect legacy SQLite fact stores"
_PREFLIGHT_LINE = "preflight\t{path}\t{clean}"
_IMPORT_LINE = "imported\t{stores}\trows={rows}\tselections={selections}\tcreated={created}"
_RECONCILE_LINE = "reconciled\t{path}\tequal={equal}"
_TRANSITION_LINE = "{action}\t{operation}"
_STATUS_LINE = "{label}\t{store}\t{state}\t{commands}"
_REFUSED_EVENT = "legacy_command_refused"


def add_legacy_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register ``legacy`` and its actions."""
    parser = subparsers.add_parser(LEGACY_COMMAND, help=_HELP)
    actions = parser.add_subparsers(dest=_ACTION_DEST, required=True)
    names = (PREFLIGHT_ACTION, IMPORT_ACTION, RECONCILE_ACTION, STATUS_ACTION, *TRANSITIONS)
    for name in names:
        action = actions.add_parser(name)
        action.add_argument("--manifest", required=True, type=Path)
    for name in (PREFLIGHT_ACTION, RECONCILE_ACTION):
        actions.choices[name].add_argument("--out", required=True, type=Path)
    actions.choices[IMPORT_ACTION].add_argument("--preflight", required=True, type=Path)
    for name in (IMPORT_ACTION, *TRANSITIONS):
        actions.choices[name].add_argument("--owner", type=Path)
    for name in TRANSITIONS:
        actions.choices[name].add_argument("--report", required=True, type=Path)


def dispatch_legacy_command(args: argparse.Namespace) -> int | None:
    """Run the selected ``legacy`` action, or return ``None`` for any other command."""
    if args.command != LEGACY_COMMAND:
        return None
    settings, root, action = PgSettings(), Path.cwd(), getattr(args, _ACTION_DEST)
    try:
        with open_pool(settings, PgRole.RUNTIME) as pool:
            if action == IMPORT_ACTION:
                result = import_legacy(
                    args.manifest,
                    args.preflight,
                    root=root,
                    pool=pool,
                    settings=settings,
                    owner_path=args.owner,
                )
                line = _IMPORT_LINE.format(
                    stores=",".join(result.stores), **result.model_dump(exclude={"stores"})
                )
            elif action == PREFLIGHT_ACTION:
                with pool.connection() as conn:
                    report = preflight(args.manifest, root=root, conn=conn, settings=settings)
                args.out.write_bytes(report.to_yaml())
                line = _PREFLIGHT_LINE.format(path=args.out, clean=report.clean())
            elif action == RECONCILE_ACTION:
                reconciled = reconcile(args.manifest, root=root, pool=pool, settings=settings)
                args.out.write_bytes(reconciled.to_yaml())
                line = _RECONCILE_LINE.format(path=args.out, equal=reconciled.equal())
            elif action in TRANSITIONS:
                operation = transition(
                    TRANSITIONS[action],
                    args.manifest,
                    report_path=args.report,
                    owner_path=args.owner,
                    pool=pool,
                    settings=settings,
                    root=root,
                )
                line = _TRANSITION_LINE.format(action=action, operation=operation)
            else:
                files = load_manifest(args.manifest).files
                stores = [origin_id_for(file.sha256) for file in files]
                states = store_status(pool, stores)
                line = "\n".join(
                    _STATUS_LINE.format(
                        label=file.label,
                        store=store,
                        state=states.get(store, NOT_IMPORTED),
                        commands=(
                            LEGAL_COMMANDS[states[store]] if store in states
                            else NOT_IMPORTED_COMMANDS
                        ),
                    )
                    for file, store in zip(files, stores, strict=True)
                )  # fmt: skip
    except (
        GateRefusedError,
        LegacyImportRefusedError,
        TransitionRefusedError,
        DatabaseUnavailableError,
        psycopg.OperationalError,
    ) as refusal:
        structlog.get_logger("fundamentals.legacy").warning(
            _REFUSED_EVENT, refusal=type(refusal).__name__, detail=str(refusal)
        )
        return EXIT_REFUSED
    sys.stdout.write(line + "\n")
    return EXIT_OK
