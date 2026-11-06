"""Composition root for raw-first vendor capture and offline reparse."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Callable, Mapping
from datetime import UTC, date, datetime
from pathlib import Path
from urllib.request import OpenerDirector, build_opener

import yaml
from psycopg_pool import ConnectionPool
from pydantic import SecretStr

from equity_os.contracts.measurement.canonical import Basis
from equity_os.contracts.sourcing.acquisition_outcome import ExtractionOutcome
from equity_os.contracts.verification.config_versions import ConfigVersions
from equity_os.extraction.model.vendor_surface_claims import extract_text
from equity_os.extraction.model.vendor_surface_labels import map_labels
from equity_os.extraction.model.vendor_surface_model import ChatCompletionsModel, ModelSettings
from equity_os.extraction.surfaces.vendor_surface_parse import register_tables
from equity_os.interface.commands.extraction.evidence_cli import EXIT_INCOMPLETE
from equity_os.interface.commands.sourcing.vendor_reingest import (
    ReingestIncompleteError,
    reingest,
)
from equity_os.interface.commands.verification.compare_cli import _aware_cutoff, _code_version
from equity_os.interface.entry.env_credentials import (
    _screener_credentials_from_env,
    _tijori_credentials_from_env,
)
from equity_os.interface.entry.watchlist_config import load_watchlist_config
from equity_os.normalisation.dictionary.dictionary import load_dictionary
from equity_os.sourcing.surfaces.vendor_surface_canary import (
    NO_BASELINE,
    overdue,
    run_canaries,
    yield_drift,
)
from equity_os.sourcing.surfaces.vendor_surface_capture import (
    IDENTITY_PAGES,
    WATCHLIST,
    capture_company,
    company_ids,
    registered_ids,
    reparse,
)
from equity_os.sourcing.surfaces.vendor_surface_due import capture_due, covered_universe
from equity_os.sourcing.surfaces.vendor_surface_expand import lineage
from equity_os.sourcing.surfaces.vendor_surface_fetch import (
    PgSiteLock,
    Site,
    SiteSession,
    VendorFetcher,
)
from equity_os.sourcing.surfaces.vendor_surface_market import capture_market
from equity_os.sourcing.surfaces.vendor_surface_specs import SITE_NAME, ParseGroup, load_specs
from equity_os.storage.database.pool import open_pool
from equity_os.storage.database.settings import PgRole, PgSettings
from equity_os.storage.raw_files.snapshot_store import SnapshotStore
from equity_os.storage.records.vendor_values_store import VendorValuesStore
from equity_os.verification.admission.eligibility import (
    EligibilityError,
    counted_runs,
    coverage,
    measure,
)

SPECS = Path("config/sourcing/vendor_surface/surfaces.yaml")
CATALOG = Path("docs/research/vendor-surface/catalog.yaml")
STOP_DIR = Path("data")
MODEL_CONFIG = Path("config/sourcing/vendor_surface/model.yaml")
CELL_SECTIONS = frozenset({"section-insights"})
BASES = {basis.value.lower(): basis for basis in Basis}


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
            parser.add_argument("--frozen", type=Path)
            parser.add_argument("--budget", type=int)

    labels = commands.add_parser("map-labels")
    labels.add_argument("--site", choices=tuple(SITE_NAME.values()), required=True)
    labels.add_argument("--surface", required=True)

    text = commands.add_parser("extract-text")
    text.add_argument("--snapshot-root", type=Path, default=Path("data/raw/snapshots/v1"))

    due = commands.add_parser("capture-due")
    due.add_argument("--snapshot-root", type=Path, default=Path("data/raw/snapshots/v1"))

    again = commands.add_parser("reingest")
    again.add_argument("--entity", required=True)
    again.add_argument("--period-end", required=True, type=date.fromisoformat)
    again.add_argument("--basis", required=True, choices=tuple(BASES))
    again.add_argument("--mapping-set", required=True)
    again.add_argument("--dictionary", required=True)
    again.add_argument("--snapshot-root", type=Path, default=Path("data/raw/snapshots/v1"))
    again.add_argument("--config-root", type=Path, default=Path("config"))
    again.add_argument("--captures-of", type=date.fromisoformat)

    measured = commands.add_parser("measure")
    measured.add_argument("--available-from", required=True, type=_aware_cutoff)
    measured.add_argument("--out", required=True, type=Path)
    measured.add_argument("--config-root", type=Path, default=Path("config"))

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
        dictionary = load_dictionary(
            Path("config/normalisation/dictionary"), settings.dictionary_version
        )
        fields = {row.canonical_id: row.value_kind for row in dictionary.rows}
        with pool_factory() as pool:
            count = map_labels(pool, model, settings, site, args.surface, fields)
        sys.stdout.write(json.dumps({"proposed": count}) + "\n")
        return 0
    if args.vendor_command == "reingest":
        with pool_factory() as pool:
            try:
                reports = reingest(
                    pool,
                    store_factory(args.snapshot_root),
                    args.config_root,
                    ConfigVersions(dictionary=args.dictionary, mapping_set=args.mapping_set),
                    entity=args.entity,
                    period_end=args.period_end,
                    basis=BASES[args.basis],
                    captures_of=args.captures_of,
                )
            except ReingestIncompleteError as gap:
                sys.stderr.write(f"INCOMPLETE: {gap}\n")
                return EXIT_INCOMPLETE
        for done in reports:
            line = {"surface": done.attempt.surface, "outcome": done.attempt.outcome.value}
            sys.stdout.write(json.dumps(line | {"interpretations": len(done.interpretations)}))
            sys.stdout.write("\n")
        return int(any(r.attempt.outcome is not ExtractionOutcome.COMPLETE for r in reports))
    if args.vendor_command == "measure":
        with pool_factory() as pool:
            try:
                artifact = measure(
                    pool,
                    args.available_from,
                    config_root=args.config_root,
                    code_version=_code_version(),
                )
            except EligibilityError as error:
                sys.stderr.write(f"measure refused: {error}\n")
                return 2
            args.out.write_text(yaml.safe_dump(artifact.model_dump(mode="json"), sort_keys=False))
            for run_id, _ in counted_runs(pool):
                found = coverage(pool, run_id, config_root=args.config_root)
                counts = (found.expected, found.three_way, len(found.refused), found.missing)
                sys.stdout.write(" ".join(map(str, ("COVERAGE", run_id, *counts))) + "\n")
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
                covered = tuple(
                    i.tijori_company_id
                    for i in covered_universe(pool, store)
                    if i.tijori_company_id
                )
                report = capture_market(
                    fetcher, store, pool, values, tuple(selected), covered=covered
                )
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
        limit, frozen_file = getattr(args, "budget", None), getattr(args, "frozen", None)
        budget = {} if limit is None else {"site_budget": limit}
        fetcher = VendorFetcher(
            store, resolved_sessions, opener_factory(), STOP_DIR, locks, **budget
        )
        frozen = None if frozen_file is None else frozenset(frozen_file.read_text().split())
        try:
            report = capture_company(
                fetcher, store, pool, values, tuple(selected), ids, frozen=frozen
            )
        finally:
            locks.close()
    sys.stdout.write(report.model_dump_json() + "\n")
    budget_stop = (
        limit is not None
        and bool(report.incomplete)
        and any(fetcher.remaining(site) <= 0 for site in Site)
    )
    return int(bool(report.frozen_stop) or budget_stop)
