"""CLI composition helpers for one subscriber Screener company-page acquisition.

Slice 0 of the Screener build: it proves the session-authenticated transport,
the two-namespace identity assertion, and the basis fact end to end. It writes
the page's bytes and a metadata record; it parses no financials.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import structlog
from pydantic import BaseModel, ConfigDict

from fundamentals.api.artifact_writer import (
    preflight_out_paths,
    write_bytes_no_clobber,
    write_json_no_clobber,
)
from fundamentals.api.watchlist_config import StockConfig, load_watchlist_config
from fundamentals.ingest.screener_session import ScreenerSessionSource
from fundamentals.ingest.screener_session_models import (
    Basis,
    BasisTopology,
    PageOutcome,
    ScreenerCredentials,
    ScreenerPageFetch,
    ScreenerSessionConfig,
)

SCREENER_PAGE_COMMAND = "screener-page"

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_WATCHLIST_PATH = _REPO_ROOT / "config" / "watchlist.yaml"
_DEFAULT_OUT_ROOT = _REPO_ROOT / "data" / "raw" / "watchlist" / "screener-page"
META_FILENAME = "screener_page_meta.json"
RAW_FILENAME = "screener_page.raw.html"
_SUMMARY_HEADER = (
    "symbol\tbasis_requested\tbasis_observed\toutcome\tsingle_basis\t"
    "company_id\twarehouse_id\ttables_empty\tmarkers\tbytes\tsha256"
)
_ABSENT = "-"
_UNVERIFIED = "Screener identifiers for {symbol} are not verified: {fields}"
BASIS_UNAVAILABLE_EXIT = (
    "screener served no {basis} basis for {symbol}: the page carries "
    "{markers} and warehouse id {warehouse_id}; evidence retained at {path}"
)


class ScreenerPageRun(BaseModel):
    """One acquisition: what the page proved and where its evidence was written."""

    model_config = ConfigDict(frozen=True)

    fetch: ScreenerPageFetch
    meta_path: Path
    raw_path: Path


def add_screener_page_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Register the ``fundamentals screener-page`` command."""
    parser = subparsers.add_parser(
        SCREENER_PAGE_COMMAND,
        help="acquire one subscriber Screener company page for a watchlist stock",
    )
    parser.add_argument("--stock", required=True, help="watchlist NSE symbol, e.g. TITAN")
    parser.add_argument(
        "--basis",
        choices=tuple(basis.value for basis in Basis),
        default=Basis.CONSOLIDATED.value,
        help="which figures to request (default: consolidated)",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="output directory (default: data/raw/watchlist/screener-page/<stock>/<basis>)",
    )
    parser.add_argument(
        "--config",
        default=str(_DEFAULT_WATCHLIST_PATH),
        help="path to watchlist.yaml",
    )


def basis_topology(stock: StockConfig) -> BasisTopology:
    """The configured record of which bases one stock publishes.

    A ``None`` warehouse id means the company publishes no page on that basis (a
    standalone-only company has no consolidated one). Topology comes from here,
    never from the fetched page: an unmarked page is indistinguishable from a
    single-basis company's page, so inferring it would let drift be recorded as
    a structural fact about the issuer.
    """
    return BasisTopology(
        consolidated_warehouse_id=stock.identifiers.screener_warehouse_id_consolidated,
        standalone_warehouse_id=stock.identifiers.screener_warehouse_id_standalone,
    )


def run_screener_page_command(
    args: argparse.Namespace,
    *,
    credentials: ScreenerCredentials,
) -> ScreenerPageRun:
    """Fetch one company page on one basis and write its metadata beside its bytes."""
    watchlist = load_watchlist_config(Path(args.config).resolve())
    try:
        stock = watchlist.stock(args.stock)
    except ValueError as error:
        raise SystemExit(str(error)) from error
    unverified = stock.identifiers.unverified_screener_fields()
    if unverified:
        raise SystemExit(_UNVERIFIED.format(symbol=stock.symbol, fields=", ".join(unverified)))

    basis = Basis(args.basis)
    default_dir = _DEFAULT_OUT_ROOT / stock.symbol / basis.value
    out_dir = Path(args.out).resolve() if args.out else default_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    meta_path = out_dir / META_FILENAME
    raw_path = out_dir / RAW_FILENAME
    # Pre-flighted before the request: refusing an existing artifact after
    # fetching would spend a rate-limited request to discard its result.
    preflight_out_paths((raw_path, meta_path))

    source = ScreenerSessionSource(ScreenerSessionConfig(credentials=credentials))
    fetch = source.fetch_company_page(
        symbol=stock.symbol,
        slug=stock.identifiers.screener_slug,
        basis=basis,
        expected_company_id=stock.identifiers.screener_company_id,
        topology=basis_topology(stock),
    )

    _publish(fetch, raw_path=raw_path, meta_path=meta_path)
    structlog.get_logger("fundamentals.screener_page").info(
        "screener_page_written",
        stock=stock.symbol,
        basis_requested=basis.value,
        outcome=fetch.metadata.outcome.value,
        path=str(meta_path),
        raw_path=str(raw_path),
    )
    return ScreenerPageRun(fetch=fetch, meta_path=meta_path, raw_path=raw_path)


def _publish(fetch: ScreenerPageFetch, *, raw_path: Path, meta_path: Path) -> None:
    """Write the evidence first and the metadata last, or leave nothing of ours behind.

    The metadata is the completion marker: published only once the bytes it
    describes are on disk. A failure between the two writes would otherwise
    leave durable success metadata pointing at evidence that does not exist —
    and, because writes are no-clobber, block the retry that would fix it.

    Rollback removes only the paths **this** invocation created. Pre-flight runs
    before the fetch, so another process can publish into this directory while
    the request is in flight; unlinking a path by name would then delete that
    process's artifact, turning a no-clobber refusal into evidence loss. A path
    is recorded only once its write has returned, so a file whose ownership is
    uncertain is always left in place.
    """
    created: list[Path] = []
    try:
        write_bytes_no_clobber(raw_path, fetch.raw_body)
        created.append(raw_path)
        write_json_no_clobber(meta_path, fetch.metadata.model_dump_json(indent=2) + "\n")
        created.append(meta_path)
    except BaseException:
        for path in created:
            path.unlink(missing_ok=True)
        raise


def basis_unavailable_message(run: ScreenerPageRun) -> str:
    """The refusal text for a basis the company does not publish."""
    metadata = run.fetch.metadata
    return BASIS_UNAVAILABLE_EXIT.format(
        basis=metadata.basis_requested.value,
        symbol=metadata.symbol,
        markers=", ".join(metadata.markers) if metadata.markers else "no basis marker",
        warehouse_id=_ABSENT if metadata.warehouse_id_seen is None else metadata.warehouse_id_seen,
        path=run.meta_path,
    )


def render_screener_page_summary(run: ScreenerPageRun) -> str:
    """Render one deterministic line stating what the fetched page proved."""
    metadata = run.fetch.metadata
    row = (
        metadata.symbol,
        metadata.basis_requested.value,
        _ABSENT if metadata.basis_observed is None else metadata.basis_observed.value,
        metadata.outcome.value,
        str(metadata.single_basis).lower(),
        str(metadata.company_id_seen),
        _ABSENT if metadata.warehouse_id_seen is None else str(metadata.warehouse_id_seen),
        str(metadata.tables_empty).lower(),
        ", ".join(metadata.markers) if metadata.markers else _ABSENT,
        str(metadata.byte_count),
        metadata.content_sha256,
    )
    return "\n".join((_SUMMARY_HEADER, "\t".join(row)))


def is_basis_unavailable(run: ScreenerPageRun) -> bool:
    """True when the page did not carry the requested basis."""
    return run.fetch.metadata.outcome is not PageOutcome.OK
