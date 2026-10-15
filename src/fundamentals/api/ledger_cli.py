"""The ``ledger`` command: decisions, claim checks, imports and export (plan D3 Tasks 3, 5, 6).

    ledger decide <subject kind> <subject id> <kind> [--key K --value V --unit U]
        [--stock <symbol> --snapshot-root <dir> [--watchlist config/watchlist.yaml]
        [--issuer-config <yaml>]...]
        (the verbatim ruling is read from stdin; an APPROVE checks the version's claims)
    ledger check --version <id> --stock <symbol> --snapshot-root <dir>
        [--mode as_known|retrospective] [--watchlist config/watchlist.yaml]
        [--issuer-config <yaml>]...
    ledger import --snapshot-root <dir> [--config config/ledger_import.yaml] [--repo .]
        [--watchlist config/watchlist.yaml] [--issuer-config <yaml>]...
    ledger export <version id> [--out PATH]   (narrative bytes; stdout unless --out)
    ledger export --stock <symbol> --out <dir> [--status-notes] [--memory]
        (every version's narrative, and its status note, and the promoted memory, under
        <dir>/<symbol>/)

The composition root: ``decide`` runs as the owner login from its credential file; ``check``
and ``export`` run as the runtime role and ``import`` as the panel login (no model call);
``check``, ``import`` and an approving ``decide`` get the stock's source catalog and the
snapshot store; each ``--issuer-config`` adds that config's PDF declarations to the catalog
(plan D4, Task 3b). Any refusal, or a
version that does not import, exits ``EXIT_REFUSED`` with a structlog error that names no
credential.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from collections.abc import Sequence
from decimal import Decimal
from pathlib import Path
from typing import Any

import psycopg
import structlog
from pydantic import ValidationError

from fundamentals.api.config import load_config
from fundamentals.api.screener_cli_dispatch import EXIT_OK, EXIT_REFUSED
from fundamentals.api.watchlist_config import load_watchlist_config, stock_catalog, with_issuer_pdfs
from fundamentals.contracts.evidence import RunMode
from fundamentals.contracts.ledger import DecisionKind, PolicyValue, SubjectKind
from fundamentals.contracts.memory import MemoryStatus
from fundamentals.contracts.source_catalog import SourceCatalog
from fundamentals.ledger.export import export_version, status_note, stock_versions
from fundamentals.ledger.importer import import_versions, load_import_config
from fundamentals.ledger.lifecycle import decide, validate
from fundamentals.memory.export import format_memory
from fundamentals.memory.pg_store import PgMemoryStore
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
ISSUER_CONFIG_FLAG = "--issuer-config"
_ACTION_DEST = "ledger_action"
_HELP = "decide report-ledger subjects and check report versions"
_DECIDE_HELP = "record an owner decision; the verbatim ruling is read from stdin"
_CHECK_HELP = "check every claim of a version and append the validation"
_IMPORT_HELP = "import the configured retained versions as the panel role"
_EXPORT_HELP = "write a version's narrative bytes, or a stock's narratives, notes and memory"
_POLICY_FIELDS = ("key", "value", "unit")
_DECISION = "decision\t{id}"
_VALIDATION = "validation\t{id}\nmode\t{mode}"
_STATE = "{key}\t{state}"
_IMPORTED = "{period}\t{kind}\t{version_id}\t{outcome}"
_FAILED_EVENT = "ledger_command_failed"
_MODES = {mode.value.lower(): mode for mode in RunMode}
_SNAPSHOT = "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"
_SAFE_NAME = re.compile(r"[A-Za-z0-9._-]+")
_STEM = "{period}-{report_kind}-v{position}"
_NARRATIVE = "{stem}.md"
_NOTE = "{stem}.status.md"
_MEMORY_FILE = "memory.md"
_NEEDS_OUT = "ledger export --stock needs --out <dir>"
_NEEDS_STOCK = "--status-notes and --memory need --stock"
_UNSAFE = "{name!r} is not a safe filename component"
_ESCAPES = "{path} is not under {out}"


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
    decision.add_argument("--stock")
    decision.add_argument("--snapshot-root", type=Path)
    decision.add_argument("--watchlist", type=Path, default=DEFAULT_WATCHLIST)
    decision.add_argument(ISSUER_CONFIG_FLAG, type=Path, action="append", default=[])
    check = actions.add_parser(CHECK_ACTION, help=_CHECK_HELP)
    check.add_argument("--version", type=int, required=True)
    check.add_argument("--stock", required=True)
    check.add_argument("--snapshot-root", type=Path, required=True)
    check.add_argument("--mode", choices=sorted(_MODES), default=RunMode.AS_KNOWN.value.lower())
    check.add_argument("--watchlist", type=Path, default=DEFAULT_WATCHLIST)
    check.add_argument(ISSUER_CONFIG_FLAG, type=Path, action="append", default=[])
    imports = actions.add_parser(IMPORT_ACTION, help=_IMPORT_HELP)
    imports.add_argument("--snapshot-root", type=Path, required=True)
    imports.add_argument("--config", type=Path, default=DEFAULT_IMPORT_CONFIG)
    imports.add_argument("--repo", type=Path, default=Path())
    imports.add_argument("--watchlist", type=Path, default=DEFAULT_WATCHLIST)
    imports.add_argument(ISSUER_CONFIG_FLAG, type=Path, action="append", default=[])
    export = actions.add_parser(EXPORT_ACTION, help=_EXPORT_HELP)
    target = export.add_mutually_exclusive_group(required=True)
    target.add_argument("version_id", type=int, nargs="?")
    target.add_argument("--stock")
    export.add_argument("--out", type=Path)
    export.add_argument("--status-notes", action="store_true")
    export.add_argument("--memory", action="store_true")


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
    sources = _sources(args) if args.stock and args.snapshot_root else {}
    login = load_login(PgRole.OWNER, secrets_dir(os.environ))
    with open_pool(PgSettings(), PgRole.OWNER, login=login) as pool:
        record = decide(
            pool,
            subject_kind=args.subject_kind,
            subject_id=args.subject_id,
            kind=args.kind,
            ruling=ruling,
            policy=policy,
            **sources,
        )
    sys.stdout.write(_DECISION.format(id=record.id) + "\n")
    return EXIT_OK


def _check(args: argparse.Namespace) -> int:
    """Check one version as the runtime role and print each claim's state."""
    with open_pool(PgSettings(), PgRole.RUNTIME) as pool:
        validation = validate(pool, args.version, mode=_MODES[args.mode], **_sources(args))
    lines = [_VALIDATION.format(id=validation.id, mode=validation.mode)]
    lines += [_STATE.format(key=key, state=state) for key, state in validation.claim_states]
    lines += [str(state) for state in validation.version_states]
    sys.stdout.write("\n".join(lines) + "\n")
    return EXIT_OK


def ledger_catalog(watchlist: Path, stock: str, issuer_configs: Sequence[Path]) -> SourceCatalog:
    """The stock's source catalog plus each issuer config's results and transcript PDFs."""
    catalog = stock_catalog(load_watchlist_config(watchlist).stock(stock))
    for path in issuer_configs:
        catalog = with_issuer_pdfs(catalog, load_config(path))
    return catalog


def _sources(args: argparse.Namespace) -> dict[str, Any]:
    """The ``--stock`` source catalog and the ``--snapshot-root`` store."""
    return {
        "catalog": ledger_catalog(args.watchlist, args.stock, args.issuer_config),
        "snapshots": SnapshotStore(args.snapshot_root.resolve()),
    }


def _import(args: argparse.Namespace) -> int:
    """Import the configured versions as the panel login and print each outcome."""
    config = load_import_config(args.config)
    catalog = ledger_catalog(args.watchlist, config.stock, args.issuer_config)
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
    """Write one version's narrative bytes as the runtime role, to ``--out`` or stdout, or with
    ``--stock`` the stock's files under ``--out``."""
    if args.stock is not None:
        return _export_stock(args)
    if args.status_notes or args.memory:
        raise ValueError(_NEEDS_STOCK)
    with open_pool(PgSettings(), PgRole.RUNTIME) as pool, pool.connection() as conn:
        body = export_version(conn.cursor(), args.version_id)
    if args.out is None:
        sys.stdout.buffer.write(body)
    else:
        args.out.write_bytes(body)
    return EXIT_OK


def _export_stock(args: argparse.Namespace) -> int:
    """Write every version's narrative (and status note) from one read-only snapshot, and the
    stock's promoted memory, under ``<out>/<stock>/``; refuse an unsafe name before any write."""
    if args.out is None:
        raise ValueError(_NEEDS_OUT)
    files: dict[str, bytes] = {}
    with open_pool(PgSettings(), PgRole.RUNTIME) as pool:
        with pool.connection() as conn, conn.transaction(), conn.cursor() as cursor:
            cursor.execute(_SNAPSHOT)
            versions = stock_versions(cursor, args.stock)
            for version in versions:
                stem = _STEM.format(**version.model_dump())
                files[_NARRATIVE.format(stem=stem)] = export_version(cursor, version.version_id)
                if args.status_notes:
                    note = status_note(cursor, version.version_id)
                    files[_NOTE.format(stem=stem)] = note.encode()
        if args.memory:
            items = PgMemoryStore(pool).retrieve(
                "",
                stock=versions[0].entity_id,
                kinds=None,
                statuses=frozenset({MemoryStatus.PROMOTED}),
                cutoff=None,
            )
            files[_MEMORY_FILE] = format_memory(items).encode()
    out = args.out.resolve()
    for name in (args.stock, *(version.period for version in versions)):
        if not _SAFE_NAME.fullmatch(name) or name in (".", ".."):
            raise ValueError(_UNSAFE.format(name=name))
    paths = {name: (out / args.stock / name).resolve() for name in files}
    for path in paths.values():
        if not path.is_relative_to(out):
            raise ValueError(_ESCAPES.format(path=path, out=out))
    (out / args.stock).mkdir(parents=True, exist_ok=True)
    for name, path in paths.items():
        path.write_bytes(files[name])
    return EXIT_OK
