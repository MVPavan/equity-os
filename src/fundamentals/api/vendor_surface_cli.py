"""Composition root for raw-first vendor capture and offline reparse."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import quote
from urllib.request import OpenerDirector, build_opener

from psycopg_pool import ConnectionPool

from fundamentals.api.env_credentials import (
    _screener_credentials_from_env,
    _tijori_credentials_from_env,
)
from fundamentals.api.watchlist_config import load_watchlist_config
from fundamentals.ingest.screener_session_models import Basis, ScreenerSessionError
from fundamentals.ingest.screener_session_page import assert_logged_in, read_identity
from fundamentals.ingest.vendor_surface_canary import NO_BASELINE, yield_drift
from fundamentals.ingest.vendor_surface_capture import (
    WATCHLIST,
    Request,
    RunReport,
    capture,
    company_ids,
    reparse,
)
from fundamentals.ingest.vendor_surface_fetch import (
    SITE_AUTHORITY,
    PgSiteLock,
    Site,
    SiteBusy,
    SiteSession,
    SiteStopped,
    VendorFetcher,
)
from fundamentals.ingest.vendor_surface_specs import SITE_NAME, load_specs
from fundamentals.pg.pool import open_pool
from fundamentals.pg.settings import PgRole, PgSettings
from fundamentals.store.snapshot_store import SnapshotStore
from fundamentals.store.vendor_values_store import USABLE, VendorValuesStore

SPECS = Path("config/vendor_surface/surfaces.yaml")
CATALOG = Path("docs/research/vendor-surface/catalog.yaml")
STOP_DIR = Path("data")


def add_vendor_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register the finite capture and offline reparse commands."""
    commands = subparsers.add_parser("vendor").add_subparsers(dest="vendor_command", required=True)
    for name in ("capture", "reparse"):
        parser = commands.add_parser(name)
        parser.add_argument("--surface", nargs="+", default=[], required=name == "reparse")
        parser.add_argument("--snapshot-root", type=Path, default=Path("data/raw/snapshots/v1"))
        if name == "capture":
            parser.add_argument("--symbol", required=True)
            parser.add_argument("--tijori-slug")

    canary = commands.add_parser("canary")
    canary.add_argument("--yield-only", action="store_true", required=True)


def sessions(sites: set[Site]) -> Mapping[Site, SiteSession]:
    """Resolve existing environment credential readers only at this CLI edge."""
    found = {}
    readers = {
        Site.SCREENER: _screener_credentials_from_env,
        Site.TIJORI: _tijori_credentials_from_env,
    }
    for site in sites:
        credentials = readers[site]()
        if credentials is not None and credentials.session_cookie is not None:
            found[site] = SiteSession(
                site=site, session_cookie=credentials.session_cookie, cookie_name="sessionid"
            )
    return found


def dispatch_vendor_command(
    args: argparse.Namespace,
    *,
    opener_factory: Callable[[], OpenerDirector] = build_opener,
    pool_factory: Callable[[], ConnectionPool] = lambda: open_pool(PgSettings(), PgRole.RUNTIME),
    store_factory: Callable[[Path], SnapshotStore] = SnapshotStore,
    sessions_factory: Callable[[set[Site]], Mapping[Site, SiteSession]] = sessions,
) -> int | None:
    """Construct the authorized boundaries, then capture or reparse finite specs."""
    if args.command != "vendor":
        return None
    if args.vendor_command == "canary":
        with pool_factory() as pool:
            drift = yield_drift(pool, datetime.min.replace(tzinfo=UTC))
        sys.stderr.write(
            "company cadence check skipped: covered_universe is unavailable before Task 14\n"
        )
        for item in drift:
            sys.stdout.write(item.model_dump_json() + "\n")
        return int(any(item.check != NO_BASELINE for item in drift))
    specs = load_specs(SPECS, CATALOG)
    selected = [
        spec
        for spec in specs
        if not args.surface or f"{SITE_NAME[spec.site]}:{spec.id}" in args.surface
    ]
    if not selected or (
        args.surface and set(args.surface) - {f"{SITE_NAME[s.site]}:{s.id}" for s in selected}
    ):
        raise ValueError("unknown vendor surface")
    resolved_sessions: Mapping[Site, SiteSession] = {}
    if args.vendor_command == "capture":
        required = {spec.site for spec in selected} | {Site.SCREENER}
        resolved_sessions = sessions_factory(required)
        for site in required - resolved_sessions.keys():
            raise ValueError(f"missing vendor session: {site}")
    store = store_factory(args.snapshot_root)
    with pool_factory() as pool:
        values = VendorValuesStore(pool)
        if args.vendor_command == "reparse":
            count = sum(reparse(store, pool, values, spec) for spec in selected)
            sys.stdout.write(json.dumps({"reparsed": count}) + "\n")
            return 0
        stock = next(
            stock
            for stock in load_watchlist_config(WATCHLIST).stocks
            if stock.symbol == args.symbol
        )
        ids = company_ids(stock)
        if args.tijori_slug:
            ids = ids.model_copy(update={"tijori_slug": args.tijori_slug})
        page = next(spec for spec in specs if spec.id == "company-page")
        chart = next((spec for spec in selected if spec.id == "chart-api"), None)
        url = f"https://{SITE_AUTHORITY[page.site]}/company/{quote(ids.nse_symbol, safe='')}/"
        pending = [Request(spec=page, url=url, ids=ids, basis=Basis.STANDALONE, due_since=None)]
        expected, completed = 1, 0
        refused: list[str] = []
        incomplete: list[str] = []
        stopped: list[Site] = []
        locks = PgSiteLock(pool)
        fetcher = VendorFetcher(
            store,
            resolved_sessions,
            opener_factory(),
            STOP_DIR,
            locks,
        )
        try:
            while pending:
                request = pending.pop(0)
                try:
                    ref, body = capture(fetcher, store, pool, values, request)
                except SiteStopped as error:
                    stopped.append(error.site)
                    incomplete.append(request.url)
                    refused.extend(item.url for item in pending if item.spec.site == error.site)
                    pending = [item for item in pending if item.spec.site != error.site]
                    continue
                except (SiteBusy, ValueError):
                    (incomplete if fetcher.remaining(request.spec.site) == 0 else refused).append(
                        request.url
                    )
                    continue
                with pool.connection() as conn:
                    outcomes = conn.execute(
                        "SELECT status FROM eqos.vendor_outcomes WHERE capture_ref_id=%s",
                        (ref.capture_ref_id,),
                    ).fetchall()
                usable = all(status in USABLE for (status,) in outcomes)
                completed += int(usable)
                if not usable:
                    incomplete.append(request.url)
                if request.spec.id == "company-page" and chart is not None and body is not None:
                    tree = body.tree()
                    try:
                        assert_logged_in(tree)
                        company, _ = read_identity(tree)
                    except ScreenerSessionError:
                        continue
                    if company != ids.screener_company_id:
                        continue
                    metrics = dict.fromkeys(
                        metric
                        for metric in tree.xpath('//*[@id="chart"]//*[@name="metrics"]/@value')
                        if metric
                    )
                    if not metrics:
                        expected += 1
                        incomplete.append("screener:chart-api discovery")
                    children = [
                        Request(
                            spec=chart,
                            url=f"https://{SITE_AUTHORITY[page.site]}"
                            + chart.path.format_map(
                                {
                                    "company_id": company,
                                    "metric-set": quote(metric, safe=""),
                                    "n": 10000,
                                }
                            ),
                            ids=ids,
                            due_since=None,
                        )
                        for metric in metrics
                    ]
                    expected += len(children)
                    pending.extend(children)
        finally:
            locks.close()
    report = RunReport(
        expected=expected,
        completed=completed,
        refused=tuple(refused),
        incomplete=tuple(incomplete),
        stopped_sites=tuple(stopped),
    )
    sys.stdout.write(report.model_dump_json() + "\n")
    return 0
