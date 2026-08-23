"""CLI parsing and commands for the persistent thesis adjudication queue."""

from __future__ import annotations

import argparse
import re
from datetime import datetime
from enum import StrEnum
from pathlib import Path

from pydantic import ValidationError

from fundamentals.thesis.adjudication import (
    AdjudicationEntry,
    AdjudicationQueue,
    AdjudicationStatus,
    entries_for_stock_quarter,
    load_adjudication_queue,
    resolve_adjudication,
)
from fundamentals.thesis.render import apply_adjudications_to_markdown, markdown_table_cell

ADJUDICATE_COMMAND = "adjudicate"


class AdjudicationAction(StrEnum):
    """Supported adjudication CLI actions."""

    LIST = "list"
    RESOLVE = "resolve"
    APPLY = "apply"


class AdjudicationAcceptance(StrEnum):
    """Human-facing tokens accepted by ``adjudicate resolve``."""

    A = "a"
    B = "b"
    MERGED = "merged"
    REJECTED = "rejected"


_ACCEPTANCE_STATUSES: dict[AdjudicationAcceptance, AdjudicationStatus] = {
    AdjudicationAcceptance.A: AdjudicationStatus.ACCEPTED_A,
    AdjudicationAcceptance.B: AdjudicationStatus.ACCEPTED_B,
    AdjudicationAcceptance.MERGED: AdjudicationStatus.MERGED,
    AdjudicationAcceptance.REJECTED: AdjudicationStatus.REJECTED,
}
_SYMBOL_TOKEN = re.compile(r"[A-Z0-9][A-Z0-9&_-]*")
_QUARTER_TOKEN = re.compile(r"[A-Z0-9][A-Z0-9_-]*")


def normalize_stock_quarter(symbol: str, quarter: str) -> tuple[str, str]:
    """Validate untrusted CLI tokens and return their canonical uppercase key."""
    normalized_symbol = symbol.upper()
    normalized_quarter = quarter.upper()
    if (
        _SYMBOL_TOKEN.fullmatch(normalized_symbol) is None
        or _QUARTER_TOKEN.fullmatch(normalized_quarter) is None
    ):
        raise ValueError("invalid symbol or quarter")
    return normalized_symbol, normalized_quarter


def resolve_beneath(root: Path, filename: str) -> Path:
    """Resolve one child path and reject traversal or symlinks outside its root."""
    resolved_root = root.resolve()
    candidate = (resolved_root / filename).resolve()
    if not candidate.is_relative_to(resolved_root):
        raise ValueError(f"path escapes configured root: {candidate}")
    return candidate


def load_adjudication_queue_or_exit(path: Path) -> AdjudicationQueue:
    """Load durable queue state or convert corruption into a clean CLI exit."""
    try:
        return load_adjudication_queue(path)
    except (OSError, ValidationError, ValueError) as error:
        raise SystemExit(f"invalid adjudication queue {path}: {error}") from error


def add_adjudication_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Register the nested ``adjudicate`` command tree."""
    adjudicate = subparsers.add_parser(
        ADJUDICATE_COMMAND,
        help="list, resolve, or apply thesis discrepancy adjudications",
    )
    actions = adjudicate.add_subparsers(dest="adjudication_action", required=True)
    list_action = actions.add_parser(AdjudicationAction.LIST.value, help="list queue entries")
    list_action.add_argument("--symbol", default=None, help="filter by stock symbol")
    list_action.add_argument(
        "--status",
        choices=tuple(status.value for status in AdjudicationStatus),
        default=None,
        help="filter by queue status, e.g. OPEN",
    )

    resolve = actions.add_parser(
        AdjudicationAction.RESOLVE.value,
        help="record a human resolution for one discrepancy",
    )
    resolve.add_argument("--id", required=True, help="stable discrepancy ID")
    resolve.add_argument(
        "--accept",
        required=True,
        choices=tuple(acceptance.value for acceptance in AdjudicationAcceptance),
        help="accept model a, model b, a merged view, or reject both",
    )
    resolve.add_argument("--note", default=None, help="optional human adjudication note")

    apply_action = actions.add_parser(
        AdjudicationAction.APPLY.value,
        help="fold current resolutions into a rendered thesis document",
    )
    apply_action.add_argument("--symbol", required=True, help="stock symbol")
    apply_action.add_argument("--quarter", required=True, help="reviewed quarter label")


def adjudication_list_command(args: argparse.Namespace, *, queue_path: Path) -> str:
    """Render queue entries matching the optional symbol and status filters."""
    queue = load_adjudication_queue_or_exit(queue_path)
    symbol = args.symbol.upper() if args.symbol else None
    status = AdjudicationStatus(args.status) if args.status else None
    entries = [
        entry
        for entry in queue.entries
        if (symbol is None or entry.stock == symbol) and (status is None or entry.status is status)
    ]
    lines = [
        "| ID | Stock | Section | Divergence | Status |",
        "| --- | --- | --- | --- | --- |",
    ]
    lines.extend(
        f"| {entry.id} | {markdown_table_cell(entry.stock)} | "
        f"{markdown_table_cell(entry.discrepancy.section)} | "
        f"{markdown_table_cell(entry.discrepancy.detail)} | "
        f"{'SUPERSEDED (' + entry.status.value + ')' if entry.superseded else entry.status.value} |"
        for entry in entries
    )
    return "\n".join(lines)


def adjudication_resolve_command(
    args: argparse.Namespace,
    *,
    queue_path: Path,
    now: datetime | None = None,
) -> AdjudicationEntry:
    """Resolve one queue entry from the CLI's acceptance token."""
    acceptance = AdjudicationAcceptance(args.accept)
    try:
        queue = resolve_adjudication(
            queue_path,
            entry_id=args.id,
            status=_ACCEPTANCE_STATUSES[acceptance],
            note=args.note,
            now=now,
        )
    except (OSError, ValidationError, ValueError) as error:
        raise SystemExit(str(error)) from error
    return next(entry for entry in queue.entries if entry.id == args.id)


def adjudication_apply_command(
    args: argparse.Namespace,
    *,
    queue_path: Path,
    thesis_dir: Path,
) -> Path:
    """Fold durable resolutions into one existing rendered thesis document."""
    try:
        symbol, quarter = normalize_stock_quarter(args.symbol, args.quarter)
        document_path = resolve_beneath(thesis_dir, f"{symbol}-{quarter}.md")
    except ValueError as error:
        raise SystemExit(str(error)) from error
    if not document_path.is_file():
        raise SystemExit(f"thesis document not found: {document_path}")
    if not queue_path.exists():
        raise SystemExit(f"adjudication queue not found: {queue_path}")
    queue = load_adjudication_queue_or_exit(queue_path)
    entries = entries_for_stock_quarter(queue, stock=symbol, quarter=quarter)
    if not entries:
        raise SystemExit(
            f"no adjudication entries match stock-quarter {symbol} {quarter}; "
            "document left unchanged"
        )
    try:
        rendered = apply_adjudications_to_markdown(
            document_path.read_text(encoding="utf-8"), entries
        )
    except ValueError as error:
        raise SystemExit(str(error)) from error
    document_path.write_text(rendered, encoding="utf-8")
    return document_path


def dispatch_adjudication_command(
    args: argparse.Namespace,
    *,
    queue_path: Path,
    thesis_dir: Path,
) -> str:
    """Dispatch one parsed adjudication action and return its stdout line(s)."""
    action = AdjudicationAction(args.adjudication_action)
    if action is AdjudicationAction.LIST:
        return adjudication_list_command(args, queue_path=queue_path)
    if action is AdjudicationAction.RESOLVE:
        entry = adjudication_resolve_command(args, queue_path=queue_path)
        return f"{entry.id} {entry.status.value}"
    return str(
        adjudication_apply_command(
            args,
            queue_path=queue_path,
            thesis_dir=thesis_dir,
        )
    )
