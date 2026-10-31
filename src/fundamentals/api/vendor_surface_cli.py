"""Composition root for raw-first vendor capture and offline reparse."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from urllib.request import OpenerDirector, build_opener

import yaml
from psycopg_pool import ConnectionPool
from pydantic import SecretStr

from fundamentals.api.env_credentials import (
    _screener_credentials_from_env,
    _tijori_credentials_from_env,
)
from fundamentals.api.watchlist_config import load_watchlist_config
from fundamentals.canon.dictionary import load_dictionary
from fundamentals.ingest.vendor_surface_canary import (
    NO_BASELINE,
    overdue,
    run_canaries,
    yield_drift,
)
from fundamentals.ingest.vendor_surface_capture import (
    IDENTITY_PAGES,
    WATCHLIST,
    capture_company,
    company_ids,
    registered_ids,
    reparse,
)
from fundamentals.ingest.vendor_surface_claims import extract_text
from fundamentals.ingest.vendor_surface_due import capture_due
from fundamentals.ingest.vendor_surface_expand import lineage
from fundamentals.ingest.vendor_surface_fetch import (
    PgSiteLock,
    Site,
    SiteSession,
    VendorFetcher,
)
from fundamentals.ingest.vendor_surface_labels import map_labels
from fundamentals.ingest.vendor_surface_market import capture_market
from fundamentals.ingest.vendor_surface_model import ChatCompletionsModel, ModelSettings
from fundamentals.ingest.vendor_surface_parse import register_tables
from fundamentals.ingest.vendor_surface_specs import SITE_NAME, ParseGroup, load_specs
from fundamentals.pg.pool import open_pool
from fundamentals.pg.settings import PgRole, PgSettings
from fundamentals.store.snapshot_store import SnapshotStore
from fundamentals.store.vendor_values_store import VendorValuesStore

SPECS = Path("config/vendor_surface/surfaces.yaml")
CATALOG = Path("docs/research/vendor-surface/catalog.yaml")
STOP_DIR = Path("data")
MODEL_CONFIG = Path("config/vendor_surface/model.yaml")
CELL_SECTIONS = frozenset({"section-insights"})


def add_vendor_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register the finite capture and offline reparse commands."""
    commands = subparsers.add_parser("vendor").add_subparsers(dest="vendor_command", required=True)
    for name in ("capture", "reparse"):
        parser = commands.add_parser(name)
        parser.add_argument("--surface", nargs="+", default=[], required=name == "reparse")
        parser.add_argument("--snapshot-root", type=Path, default=Path("data/raw/snapshots/v1"))
        if name == "capture":
            target = parser.add_mutually_exclusive_group(required=True)
            target.add_argument("--symbol")
            target.add_argument("--market", action="store_true")
            parser.add_argument("--tijori-slug")

    labels = commands.add_parser("map-labels")
    labels.add_argument("--site", choices=tuple(SITE_NAME.values()), required=True)
    labels.add_argument("--surface", required=True)

    text = commands.add_parser("extract-text")
    text.add_argument("--snapshot-root", type=Path, default=Path("data/raw/snapshots/v1"))

    due = commands.add_parser("capture-due")
    due.add_argument("--snapshot-root", type=Path, default=Path("data/raw/snapshots/v1"))

    canary = commands.add_parser("canary")
    canary.add_argument("--yield-only", action="store_true")
    canary.add_argument("--snapshot-root", type=Path, default=Path("data/raw/snapshots/v1"))


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
    if args.vendor_command in ("map-labels", "extract-text"):
        settings = ModelSettings.model_validate(yaml.safe_load(MODEL_CONFIG.read_text()))
        if not settings.model_id:
            sys.stderr.write("owner-selected model is not configured\n")
            return 2
        if args.vendor_command == "map-labels":
            site = next(site for site, name in SITE_NAME.items() if name == args.site)
            if not any(
                s.site == site
                and (
                    s.id == args.surface
                    and s.group == ParseGroup.CELLS
                    or args.surface in s.sections
                    and args.surface in CELL_SECTIONS
                )
                for s in load_specs(SPECS, CATALOG)
            ):
                raise ValueError("label mapping requires a G3 surface")
        key = (
            Path(os.environ.get("EQOS_SECRETS_DIR", "~/.secrets")).expanduser() / settings.key_file
        )
        model = ChatCompletionsModel(
            settings.model_id, settings.base_url, SecretStr(key.read_text().strip())
        )
        if args.vendor_command == "extract-text":
            with pool_factory() as pool:
                count = extract_text(pool, store_factory(args.snapshot_root), model, settings)
            sys.stdout.write(json.dumps({"processed": count}) + "\n")
            return 0
        dictionary = load_dictionary(Path("config/dictionary"), settings.dictionary_version)
        fields = {row.canonical_id: row.value_kind for row in dictionary.rows}
        with pool_factory() as pool:
            count = map_labels(pool, model, settings, site, args.surface, fields)
        sys.stdout.write(json.dumps({"proposed": count}) + "\n")
        return 0
    if args.vendor_command == "canary":
        now = datetime.now(UTC)
        store = store_factory(args.snapshot_root)
        with pool_factory() as pool:
            if args.yield_only:
                drift = yield_drift(pool, datetime.min.replace(tzinfo=UTC))
            else:
                resolved = sessions_factory(set(Site))
                if set(Site) - resolved.keys():
                    raise ValueError("missing vendor session for canaries")
                locks = PgSiteLock(pool)
                try:
                    drift = run_canaries(
                        VendorFetcher(store, resolved, opener_factory(), STOP_DIR, locks),
                        store,
                        pool,
                    )
                finally:
                    locks.close()
            drift += overdue(pool, store, load_specs(SPECS, CATALOG), now)
        for item in drift:
            sys.stdout.write(item.model_dump_json() + "\n")
        return int(any(item.check != NO_BASELINE for item in drift))
    if args.vendor_command == "capture-due":
        now = datetime.now(UTC)
        specs = load_specs(SPECS, CATALOG)
        register_tables(specs)
        resolved = sessions_factory({spec.site for spec in specs})
        for site in {spec.site for spec in specs} - resolved.keys():
            raise ValueError(f"missing vendor session: {site}")
        store = store_factory(args.snapshot_root)
        with pool_factory() as pool:
            locks = PgSiteLock(pool)
            fetcher = VendorFetcher(store, resolved, opener_factory(), STOP_DIR, locks)
            try:
                report = capture_due(fetcher, store, pool, VendorValuesStore(pool), specs, now)
            finally:
                locks.close()
        sys.stdout.write(report.model_dump_json() + "\n")
        return int(bool(report.stopped_sites or report.refused))
    specs = load_specs(SPECS, CATALOG)
    register_tables(specs)
    explicit = {(s.site, s.id) for s in specs}
    specs += tuple(
        s.model_copy(
            update={
                "id": section,
                "path": s.path + "#" + section,
                "group": ParseGroup.READER,
                "sections": (),
                "expand": None,
            }
        )
        for s in specs
        for section in s.sections
        if (s.site, section) not in explicit
    )
    selected = [
        spec
        for spec in specs
        if not args.surface or f"{SITE_NAME[spec.site]}:{spec.id}" in args.surface
    ]
    if not selected or (
        args.surface and set(args.surface) - {f"{SITE_NAME[s.site]}:{s.id}" for s in selected}
    ):
        raise ValueError("unknown vendor surface")
    if args.vendor_command == "capture":
        needed = {(p.site, p.id) for s in selected for p in lineage(s, specs)}
        sites = {s.site for s in selected}
        selected = [
            s
            for s in specs
            if (s.site, s.id) in needed or s.site in sites and s.id in IDENTITY_PAGES
        ]
    resolved_sessions: Mapping[Site, SiteSession] = {}
    if args.vendor_command == "capture":
        required = {spec.site for spec in selected}
        resolved_sessions = sessions_factory(required)
        for site in required - resolved_sessions.keys():
            raise ValueError(f"missing vendor session: {site}")
    store = store_factory(args.snapshot_root)
    with pool_factory() as pool:
        values = VendorValuesStore(pool)
        if args.vendor_command == "reparse":
            count = sum(reparse(store, pool, values, spec, specs) for spec in selected)
            sys.stdout.write(json.dumps({"reparsed": count}) + "\n")
            return 0
        if args.market:
            locks = PgSiteLock(pool)
            fetcher = VendorFetcher(store, resolved_sessions, opener_factory(), STOP_DIR, locks)
            try:
                report = capture_market(fetcher, store, pool, values, tuple(selected))
            finally:
                locks.close()
            sys.stdout.write(report.model_dump_json() + "\n")
            return 0
        stock = next(
            (
                stock
                for stock in load_watchlist_config(WATCHLIST).stocks
                if stock.symbol == args.symbol
            ),
            None,
        )
        ids = company_ids(stock) if stock is not None else registered_ids(pool, store, args.symbol)
        if args.tijori_slug:
            ids = ids.model_copy(update={"tijori_slug": args.tijori_slug})
        locks = PgSiteLock(pool)
        fetcher = VendorFetcher(store, resolved_sessions, opener_factory(), STOP_DIR, locks)
        try:
            report = capture_company(fetcher, store, pool, values, tuple(selected), ids)
        finally:
            locks.close()
    sys.stdout.write(report.model_dump_json() + "\n")
    return 0
