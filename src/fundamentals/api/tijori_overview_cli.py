"""CLI composition helpers for typed Tijori overview-section acquisition."""

from __future__ import annotations

import argparse
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from urllib.parse import quote
from urllib.request import build_opener

import structlog

from fundamentals.api.artifact_writer import preflight_out_paths, write_json_no_clobber
from fundamentals.api.watchlist_config import StockConfig, load_watchlist_config
from fundamentals.contracts.snapshot import CaptureRecord
from fundamentals.ingest.tijori_overview import build_tijori_overview
from fundamentals.ingest.tijori_overview_models import (
    TijoriOverviewSection,
    TijoriOverviewSectionBase,
)
from fundamentals.ingest.tijori_source import TijoriCredentials
from fundamentals.ingest.tijori_tables import TijoriFetchError
from fundamentals.ingest.vendor_surface_capture import Request, capture, company_ids
from fundamentals.ingest.vendor_surface_fetch import (
    SITE_AUTHORITY,
    PgSiteLock,
    Site,
    SiteSession,
    VendorFetcher,
)
from fundamentals.ingest.vendor_surface_specs import load_specs
from fundamentals.pg.pool import open_pool
from fundamentals.pg.settings import PgRole, PgSettings
from fundamentals.store.snapshot_store import SnapshotStore
from fundamentals.store.vendor_values_store import VendorValuesStore

TIJORI_OVERVIEW_COMMAND = "tijori-overview"

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_WATCHLIST_PATH = _REPO_ROOT / "config" / "watchlist.yaml"
_DEFAULT_OUT_ROOT = _REPO_ROOT / "data" / "raw" / "watchlist" / "tijori-overview"
_SUMMARY_HEADER = "section\tisland\tstatus\telements\tplan_tier"
_UNKNOWN_PLAN_TIER = "unknown"
_NOT_BUILT = "-"
_STOP_DIR = Path("data")


def add_tijori_overview_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Register the ``fundamentals tijori-overview`` command."""
    parser = subparsers.add_parser(
        TIJORI_OVERVIEW_COMMAND,
        help="acquire the typed Tijori overview-page data sections for one watchlist stock",
    )
    parser.add_argument("--stock", required=True, help="watchlist NSE symbol, e.g. TITAN")
    parser.add_argument("--snapshot-root", type=Path, default=Path("data/raw/snapshots/v1"))
    parser.add_argument(
        "--section",
        choices=tuple(section.value for section in TijoriOverviewSection),
        default=None,
        help="one overview section (default: every section published on the page)",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="output directory (default: data/raw/watchlist/tijori-overview/<stock>)",
    )
    parser.add_argument(
        "--config",
        default=str(_DEFAULT_WATCHLIST_PATH),
        help="path to watchlist.yaml",
    )


def run_tijori_overview_command(
    args: argparse.Namespace,
    *,
    credentials: TijoriCredentials,
) -> tuple[TijoriOverviewSectionBase, ...]:
    """Resolve one stock, fetch one overview page, and write its section JSON files."""
    config_path = Path(args.config).resolve()
    watchlist = load_watchlist_config(config_path)
    try:
        stock = watchlist.stock(args.stock)
    except ValueError as error:
        raise SystemExit(str(error)) from error
    unverified = stock.identifiers.unverified_tijori_fields()
    if unverified:
        raise SystemExit(
            f"Tijori identifiers for {stock.symbol} are not verified: {', '.join(unverified)}"
        )

    record, raw, url = _capture_page(
        stock, credentials, args.snapshot_root, "company-overview", "/company/{slug}/"
    )
    with _sanitized_builder_logs("company-overview"):
        sections = build_tijori_overview(
            raw,
            slug=stock.identifiers.tijori_slug,
            expected_symbol=stock.symbol,
            expected_company_id=stock.identifiers.tijori_company_id,
            source_url=url,
            retrieved_at=record.retrieved_at,
            section=None if args.section is None else TijoriOverviewSection(args.section),
        )

    out_dir = Path(args.out).resolve() if args.out else _DEFAULT_OUT_ROOT / stock.symbol
    out_dir.mkdir(parents=True, exist_ok=True)
    out_paths = tuple(out_dir / f"{built.section.value}.json" for built in sections)
    preflight_out_paths(out_paths)
    logger = structlog.get_logger("fundamentals.tijori_overview")
    for built, out_path in zip(sections, out_paths, strict=True):
        write_json_no_clobber(out_path, built.model_dump_json(indent=2) + "\n")
        logger.info(
            "tijori_overview_section_written",
            stock=stock.symbol,
            section=built.section.value,
            island=built.island_id,
            elements=built.element_count,
            path=str(out_path),
        )
    return sections


def render_tijori_overview_summary(sections: tuple[TijoriOverviewSectionBase, ...]) -> str:
    """Render one deterministic line per section the page declares.

    Every section is listed, including the ones the page does not publish, so an
    absent section is visible in the run output rather than inferred from a
    missing file.
    """
    if not sections:
        return _SUMMARY_HEADER
    metadata = sections[0].metadata
    built = {section.section: section for section in sections}
    lines = [_SUMMARY_HEADER]
    lines.extend(
        "\t".join(
            (
                outcome.section.value,
                outcome.island_id,
                outcome.status.value,
                (
                    str(built[outcome.section].element_count)
                    if outcome.section in built
                    else _NOT_BUILT
                ),
                metadata.access.plan_tier or _UNKNOWN_PLAN_TIER,
            )
        )
        for outcome in metadata.section_outcomes
    )
    return "\n".join(lines)


def _capture_page(
    stock: StockConfig, credentials: TijoriCredentials, root: Path, surface: str, path: str
) -> tuple[CaptureRecord, bytes, str]:
    """Register one Tijori response and its reader outcome before building CLI artifacts."""
    assert credentials.session_cookie is not None
    session = SiteSession(
        site=Site.TIJORI, session_cookie=credentials.session_cookie, cookie_name="sessionid"
    )
    store = SnapshotStore(root)
    url = f"https://{SITE_AUTHORITY[Site.TIJORI]}" + path.format(
        slug=quote(stock.identifiers.tijori_slug, safe="")
    )
    request = Request(
        spec=next(
            spec
            for spec in load_specs(
                _REPO_ROOT / "config/vendor_surface/surfaces.yaml",
                _REPO_ROOT / "docs/research/vendor-surface/catalog.yaml",
            )
            if spec.site == Site.TIJORI and spec.id == surface
        ),
        url=url,
        ids=company_ids(stock),
        due_since=None,
    )
    with open_pool(PgSettings(), PgRole.RUNTIME) as pool:
        locks = PgSiteLock(pool)
        try:
            fetcher = VendorFetcher(store, {Site.TIJORI: session}, build_opener(), _STOP_DIR, locks)
            ref, body = capture(fetcher, store, pool, VendorValuesStore(pool), request)
            if body is None:
                raise TijoriFetchError("Tijori page capture is unusable")
            record = store.get_capture(ref.source_id, ref.surface, ref.request_key, ref.capture_id)
            return record, store.read_body(record), url
        finally:
            locks.close()


@contextmanager
def _sanitized_builder_logs(surface: str) -> Iterator[None]:
    """Apply the retained-reader log policy during CLI artifact building."""
    config = structlog.get_config()

    def sanitize(logger: Any, method: str, event: Any) -> dict[str, str]:
        return {"event": "vendor_surface_reader", "site": "tijori", "surface": surface}

    structlog.configure(processors=[sanitize, *config["processors"]])
    try:
        yield
    finally:
        structlog.configure(**config)
