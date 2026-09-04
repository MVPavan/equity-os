"""Argument-parser registration and command surface for ``thesis`` + ``adjudicate``.

Beyond parser registration this module now owns the thesis command itself and
both dispatchers, extracted verbatim from :mod:`fundamentals.api.cli` so the
composition root stays inside its file-size bound. The two commands share the
default thesis directory and the adjudication queue file that lives beneath it,
so they belong together.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

import structlog

from fundamentals.api.adjudication_cli import (
    ADJUDICATE_COMMAND,
    dispatch_adjudication_command,
    load_adjudication_queue_or_exit,
    normalize_stock_quarter,
    resolve_beneath,
)
from fundamentals.api.watchlist_config import WatchlistConfig, Wave, load_watchlist_config
from fundamentals.api.wave_selection import _require_symbol_in_wave, _selected_wave
from fundamentals.reconcile.gold_file import DEFAULT_GOLD_DIR
from fundamentals.thesis import (
    ClaudeOpusClient,
    CodexSolClient,
    ThesisConfig,
    ThesisDocument,
    ThesisDocumentStatus,
    ThesisModelClient,
    build_thesis,
    from_gold_file,
    load_thesis_config,
    render_thesis_document,
)
from fundamentals.thesis.adjudication import (
    entries_for_stock_quarter,
    normalize_queue_key,
    upsert_discrepancies,
)

THESIS_COMMAND = "thesis"

_WAVE_CHOICES: tuple[str, ...] = tuple(wave.value for wave in Wave)

_CLI_LOGGER_NAME = "fundamentals.cli"
_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_THESIS_DIR = _REPO_ROOT / "docs" / "research" / "validation" / "thesis"
_ADJUDICATION_QUEUE_FILENAME = "adjudication-queue.json"
_MISSING_GOLD_REASON = "gold file does not exist"


def add_wave_arg(subparser: argparse.ArgumentParser) -> None:
    """Add the shared ``--wave`` filter to a watchlist-capable command."""
    subparser.add_argument(
        "--wave",
        choices=_WAVE_CHOICES,
        default=None,
        help="scope a run to one wave, e.g. Wave-1 (per-wave roll-ups never collide)",
    )


def add_thesis_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
    *,
    command: str,
    default_watchlist_path: Path,
) -> None:
    """Register the ``thesis`` parser without growing the composition root."""
    thesis = subparsers.add_parser(
        command,
        help="draft the non-authoritative cross-verified thesis from validated gold facts",
    )
    thesis_scope = thesis.add_mutually_exclusive_group()
    thesis_scope.add_argument(
        "--watchlist", action="store_true", help="draft a thesis for every watchlist stock"
    )
    thesis_scope.add_argument(
        "--symbol", default=None, help="draft a thesis for a single stock, e.g. MTARTECH"
    )
    add_wave_arg(thesis)
    thesis.add_argument(
        "--quarter",
        required=True,
        help="the reviewed quarter label, e.g. Q3FY25 (keys the gold file)",
    )
    thesis.add_argument(
        "--config",
        default=str(default_watchlist_path),
        help="path to watchlist.yaml (default: repo config/watchlist.yaml); resolves name/domain",
    )
    thesis.add_argument(
        "--thesis-config",
        default=None,
        help="path to non-secret thesis model settings YAML (default: built-in settings)",
    )
    thesis.add_argument(
        "--gold-dir",
        default=None,
        help="directory of <SYM>-<QUARTER>.json gold files (default: data/gold)",
    )
    thesis.add_argument(
        "--out-dir",
        default=None,
        help="directory for rendered thesis .md (default: docs/research/validation/thesis)",
    )
    thesis.add_argument(
        "--done-only",
        action="store_true",
        help="with --watchlist, draft only stocks whose local gold file exists",
    )


def _resolve_thesis_out_dir(args: argparse.Namespace) -> Path:
    """Resolve the directory the rendered thesis markdown is written to."""
    return Path(args.out_dir) if args.out_dir else _DEFAULT_THESIS_DIR


def _build_thesis_clients(config: ThesisConfig) -> tuple[ThesisModelClient, ...]:
    """Construct the two real, independent thesis model clients from config."""
    codex: ThesisModelClient = CodexSolClient(config.codex)
    claude: ThesisModelClient = ClaudeOpusClient(config.claude)
    return (codex, claude)


def _stock_name_domain(watchlist: WatchlistConfig, symbol: str) -> tuple[str, str]:
    """Resolve a symbol's display name and domain from the watchlist (best-effort)."""
    try:
        stock = watchlist.stock(symbol)
    except ValueError:
        return "", ""
    return stock.name, stock.domain


def _thesis_exit_code(docs: Sequence[ThesisDocument]) -> int:
    """Non-zero when any thesis is BLOCKED (no usable model draft was produced)."""
    return 1 if any(doc.status is ThesisDocumentStatus.BLOCKED for doc in docs) else 0


def thesis_command(
    args: argparse.Namespace,
    *,
    clients: Sequence[ThesisModelClient] | None = None,
    queue_path: Path | None = None,
) -> list[ThesisDocument]:
    """Draft the non-authoritative, cross-verified thesis from validated gold facts.

    Loads each requested stock's gold file (written by ``validate``), runs two
    independent models over the SAME facts, cross-verifies, and writes the sourced
    markdown to ``<out-dir>/<SYM>-<QUARTER>.md``. It never re-fetches or recomputes a
    number: a missing gold file fails closed (run ``validate`` first). The document
    still emits with the recorded gap when one model is unreachable (PARTIAL); when
    both fail (BLOCKED) it emits the facts only and the caller exits non-zero. Model
    clients are injectable so a unit test can pass fakes; the default path builds the
    two real clients (Codex Sol + Claude Opus) from config.
    """
    if not args.watchlist and not args.symbol:
        raise SystemExit("thesis requires either --watchlist or --symbol <X>")
    if args.done_only and not args.watchlist:
        raise SystemExit("--done-only requires --watchlist")

    try:
        _, quarter = normalize_stock_quarter("THESIS", args.quarter)
    except ValueError as error:
        raise SystemExit(str(error)) from error

    config_path = Path(args.config).resolve()
    watchlist: WatchlistConfig = load_watchlist_config(config_path)
    gold_dir = Path(args.gold_dir) if args.gold_dir else DEFAULT_GOLD_DIR
    out_dir = _resolve_thesis_out_dir(args)
    adjudication_queue_path = (
        queue_path if queue_path is not None else out_dir / _ADJUDICATION_QUEUE_FILENAME
    )
    load_adjudication_queue_or_exit(adjudication_queue_path)

    selected_wave = _selected_wave(args)
    if args.symbol:
        try:
            symbol, _ = normalize_stock_quarter(args.symbol, quarter)
        except ValueError as error:
            raise SystemExit(str(error)) from error
        if selected_wave is not None:
            _require_symbol_in_wave(watchlist.stock(symbol), selected_wave)
        symbols = [symbol]
    else:
        scoped = (
            watchlist.stocks_for_wave(selected_wave)
            if selected_wave is not None
            else watchlist.stocks
        )
        try:
            symbols = [normalize_stock_quarter(stock.symbol, quarter)[0] for stock in scoped]
        except ValueError as error:
            raise SystemExit(str(error)) from error

    try:
        gold_paths = {
            symbol: resolve_beneath(gold_dir, f"{symbol}-{quarter}.json") for symbol in symbols
        }
    except ValueError as error:
        raise SystemExit(str(error)) from error
    missing_symbols = [symbol for symbol in symbols if not gold_paths[symbol].is_file()]
    if args.symbol and missing_symbols:
        symbol = missing_symbols[0]
        raise SystemExit(
            f"gold file not found: {gold_paths[symbol]}. Run "
            f"`fundamentals validate --symbol {symbol} --quarter {quarter}` first."
        )
    if missing_symbols and not args.done_only:
        raise SystemExit(
            "gold files missing for watchlist symbols: "
            f"{', '.join(missing_symbols)}; rerun with --done-only to skip them"
        )

    thesis_config = (
        load_thesis_config(Path(args.thesis_config)) if args.thesis_config else ThesisConfig()
    )
    if clients is None:
        model_clients: list[ThesisModelClient] = list(_build_thesis_clients(thesis_config))
    else:
        model_clients = list(clients)
    logger = structlog.get_logger("fundamentals.thesis")
    generated_at = datetime.now(UTC)
    docs: list[ThesisDocument] = []
    for symbol in symbols:
        gold_path = gold_paths[symbol]
        if not gold_path.is_file():
            logger.warning(
                "thesis_skipped_no_gold",
                symbol=symbol,
                path=str(gold_path),
                reason=_MISSING_GOLD_REASON,
            )
            continue
        name, domain = _stock_name_domain(watchlist, symbol)
        fact_set = from_gold_file(gold_path, name=name, domain=domain)
        fact_key = (
            normalize_queue_key(fact_set.symbol),
            normalize_queue_key(fact_set.quarter),
        )
        if fact_key != (symbol, quarter):
            raise SystemExit(
                f"gold file identity {fact_set.symbol} {fact_set.quarter} does not match "
                f"requested stock-quarter {symbol} {quarter}"
            )
        doc = build_thesis(fact_set, model_clients, max_workers=thesis_config.max_workers)
        try:
            queue = upsert_discrepancies(
                adjudication_queue_path,
                stock=symbol,
                quarter=quarter,
                discrepancies=doc.cross_verification.discrepancies,
                update_supersession=doc.status is ThesisDocumentStatus.OK,
                now=generated_at,
            )
        except (OSError, ValueError) as error:
            raise SystemExit(
                f"invalid adjudication queue {adjudication_queue_path}: {error}"
            ) from error
        adjudications = entries_for_stock_quarter(queue, stock=symbol, quarter=quarter)
        markdown = render_thesis_document(
            doc,
            generated_at=generated_at,
            adjudications=adjudications,
        )
        out_dir.mkdir(parents=True, exist_ok=True)
        try:
            out_path = resolve_beneath(out_dir, f"{symbol}-{quarter}.md")
        except ValueError as error:
            raise SystemExit(str(error)) from error
        out_path.write_text(markdown, encoding="utf-8")
        docs.append(doc)
        logger.info(
            "thesis_written",
            symbol=symbol,
            path=str(out_path),
            status=doc.status.value,
            usable_drafts=doc.usable_draft_count,
        )
    return docs


def dispatch_adjudicate_command(args: argparse.Namespace) -> int | None:
    """Run the ``adjudicate`` command, or return ``None`` for any other command."""
    if args.command != ADJUDICATE_COMMAND:
        return None
    queue_path = _DEFAULT_THESIS_DIR / _ADJUDICATION_QUEUE_FILENAME
    output = dispatch_adjudication_command(
        args, queue_path=queue_path, thesis_dir=_DEFAULT_THESIS_DIR
    )
    sys.stdout.write(output + "\n")
    return 0


def dispatch_thesis_command(args: argparse.Namespace) -> int | None:
    """Run the ``thesis`` command, or return ``None`` for any other command."""
    if args.command != THESIS_COMMAND:
        return None
    logger = structlog.get_logger(_CLI_LOGGER_NAME)
    logger.info(
        "thesis_invoked",
        watchlist=args.watchlist,
        symbol=args.symbol,
        quarter=args.quarter,
        started_at=datetime.now(UTC).isoformat(),
    )
    docs = thesis_command(args)
    out_dir = _resolve_thesis_out_dir(args)
    for doc in docs:
        logger.info(
            "thesis_summary",
            symbol=doc.fact_set.symbol,
            status=doc.status.value,
            usable_drafts=doc.usable_draft_count,
        )
        sys.stdout.write(str(out_dir / f"{doc.fact_set.symbol}-{args.quarter}.md") + "\n")
    return _thesis_exit_code(docs)
