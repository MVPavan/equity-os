"""The Stage 1 end-to-end harness: one isolated database per manifest run, the real pipeline
over the retained captures, and the manifest-shaped projection of its results.

The expected side is the manifest alone (``test_frozen_manifests.expanded_rows``); the engine
side is normalised into the same shape so one comparator diffs the two by row key.
"""

from __future__ import annotations

import hashlib
import json
import math
import shutil
from collections import Counter
from collections.abc import Callable
from datetime import date, datetime, timedelta
from fractions import Fraction
from pathlib import Path
from typing import Any

import pytest
from retained_support import (
    MarkedEdit,
    apar_catalog,
    apar_intake,
    apar_original,
    marked_copy,
    seed_apar,
)
from test_compare_runs import seed_netweb
from test_evidence_vendor import screener, tijori, upstox
from test_frozen_manifests import REPO, STAGE1, expanded_rows, load, source
from test_watchlist_xbrl_ingest import _seed
from vendor_retained_support import RAW_ROOT, retained_page, stage_registered

from equity_os.contracts.measurement.canonical import Basis, Representation
from equity_os.contracts.measurement.evidence import FilingFamily, Interpretation, Occurrence
from equity_os.contracts.measurement.observation import AccountingFramework
from equity_os.contracts.sourcing.source_catalog import EvidenceRole, SourceClass, SourceDescriptor
from equity_os.contracts.verification.comparison import (
    PairKind,
    SourceRole,
)
from equity_os.contracts.verification.review_queue import QueueOverlay
from equity_os.extraction.packages.capture_intake import (
    MARKED_SOURCE_PREFIX,
    retained_intake_from_manifest,
)
from equity_os.extraction.packages.first_party_ingest import ingest_first_party
from equity_os.extraction.results_pdf.pdf_statement_pages import specs_from_config
from equity_os.extraction.surfaces.vendor_ingest import VendorIngestRequest, ingest_vendor
from equity_os.extraction.vendors.screener.screener_financials_models import Section
from equity_os.extraction.vendors.tijori import vendor_tijori
from equity_os.interface.entry.cli import main
from equity_os.interface.entry.config import load_config
from equity_os.storage.raw_files.snapshot_store import SnapshotStore
from equity_os.storage.records.repository import EvidenceRepository
from equity_os.verification.comparison.run import (
    DatabaseIdentity,
    RunRecord,
    execute_run,
    exit_status,
    load_results,
    replay_run,
    request_for,
)
from equity_os.verification.comparison.run_config import (
    ConfigVersions,
    LoadedConfig,
    load_run_config,
)
from equity_os.verification.comparison.run_models import ResultRow, RunRequest, SourceRef
from equity_os.verification.review_queue.queue import overlay_boundary, read_overlay
from equity_os.verification.review_queue.trust import trusted

MANIFEST = load(STAGE1)
CONFIG = REPO / "config"
SNAPSHOTS = REPO / "data/raw/snapshots/v1"
VERSIONS = ConfigVersions(dictionary="v2", mapping_set="v4")
SCREENER = ("screener-subscriber", "SCREENER_FINANCIALS")
SECTIONS = (Section.QUARTERS, Section.PROFIT_LOSS, Section.BALANCE_SHEET, Section.CASH_FLOW)
VERSION = {
    "screener-subscriber": "screener-v1",
    "tijori": vendor_tijori.EXTRACTOR_VERSION,
    "upstox": "upstox-v2",
}
RUNS = {run["run"]: run for run in MANIFEST["runs"]}


class Stage:
    """One isolated database with one seeded entity, its evidence and its runs."""

    def __init__(self, pg_db: Any, pool: Any, tmp_path: Path, run: dict[str, Any]) -> None:
        self.pg_db, self.pool, self.tmp_path, self.run = pg_db, pool, tmp_path, run
        self.repository = EvidenceRepository(pool)
        self.config: LoadedConfig = load_run_config(CONFIG, VERSIONS)
        self.config_root, self.versions = CONFIG, VERSIONS  # what runs pin (C6 edits a copy)
        self.end = date.fromisoformat(run["period_end"])
        self.entity_id = self._seed()
        (tmp_path / "staged").mkdir(mode=0o700)

    def _seed(self) -> int:
        entity = self.run["entity"]
        if entity == "APARINDS":
            return seed_apar(self.pg_db)
        if entity == "NETWEB":
            return seed_netweb(self.pool)
        manifest = RAW_ROOT / entity.lower() / "retrieval-manifest.json"
        (entry,) = json.loads(manifest.read_bytes())["entries"]
        return _seed(self.pool, entity, entry)

    def first_party(
        self,
        *edits: MarkedEdit,
        quarter: str = "FY26_Q2",
        members: dict[Representation, str] | None = None,
        end: date | None = None,
        supersedes: int | None = None,
        pdf: Path | None = None,
    ) -> int:
        """Ingest one first-party package under the run's pins: the run's own members unless
        given, the XBRL optionally a marked copy (test-private, not a source reading)."""
        entity, config = self.run["entity"], self.config
        catalog = apar_catalog()
        if entity == "APARINDS":
            members = members or {
                Representation.XBRL: "xbrl-consolidated",
                Representation.PDF: "results",
            }
            marked: dict[Representation, Path] = {} if pdf is None else {Representation.PDF: pdf}
            if edits:
                path = apar_original(quarter, members[Representation.XBRL])
                for edit in edits:
                    path = marked_copy(path, edit=edit, tmp_path=self.tmp_path)
                marked[Representation.XBRL] = path
            issuer = CONFIG / f"runs/aparinds-{quarter.lower().replace('_', '-')}.yaml"
            intake = apar_intake(
                self.tmp_path, quarter, members, marked=marked, issuer_config=issuer
            )
            specs = None
            if Representation.PDF in members:
                loaded = load_config(issuer)
                specs = specs_from_config(loaded.pdf_parse)
                catalog = catalog.extend(
                    SourceDescriptor(
                        source_id=loaded.results_pdf.source_id,
                        source_class=SourceClass.FIRST_PARTY,
                        evidence_role=EvidenceRole.RECONCILABLE,
                    )
                )
            store = SnapshotStore(self.tmp_path / "store")
        else:
            inputs, root = self.tmp_path / "inputs", self.tmp_path / "store"
            (inputs / "nse").mkdir(mode=0o700, parents=True)
            root.mkdir(mode=0o700)
            manifest = RAW_ROOT / entity.lower() / "retrieval-manifest.json"
            (entry,) = json.loads(manifest.read_bytes())["entries"]
            shutil.copyfile(
                manifest.parent / "nse" / entry["filename"], inputs / "nse" / entry["filename"]
            )
            intake = retained_intake_from_manifest(
                manifest,
                issuer=entity,
                quarter="FY25_Q3",
                kinds={Representation.XBRL: "xbrl-consolidated"},
                store_root=root.absolute(),
                input_root=inputs.absolute(),
                issuer_config=None,
            )
            if edits:
                (binding,) = intake.bindings
                copy = inputs / binding.relative_path
                for edit in edits:
                    copy = marked_copy(copy, edit=edit, tmp_path=inputs / "nse")
                update = {
                    "source_id": f"{MARKED_SOURCE_PREFIX}xbrl",
                    "relative_path": copy.relative_to(inputs),
                    "expected_sha256": hashlib.sha256(copy.read_bytes()).hexdigest(),
                }
                intake = intake.model_copy(
                    update={"bindings": (binding.model_copy(update=update),)}
                )
            specs, store = None, SnapshotStore(root)
        report = ingest_first_party(
            intake=intake,
            catalog=catalog,
            snapshot_store=store,
            repository=self.repository,
            dictionary=config.dictionary,
            mapping_set=config.mapping_set,
            policy=config.normalisation_policy,
            entity_id=self.entity_id,
            basis=Basis.CONSOLIDATED,
            framework=AccountingFramework.IND_AS,
            family=FilingFamily.FINANCIAL_RESULTS,
            reporting_period_end=end or self.end,
            pdf_specs=specs,
            supersedes_package_id=supersedes,
        )
        assert report.package_id is not None
        return report.package_id

    def vendors(self) -> None:
        """Ingest every vendor capture the run names (Screener once per page section)."""
        for vendor, label in self.run["vendor_inputs"].items():
            self.vendor(vendor, label.split()[0])

    def vendor(
        self,
        vendor: str,
        label: str,
        capture_id: str | None = None,
        store: Path = SNAPSHOTS,
        end: date | None = None,
        basis: Basis = Basis.CONSOLIDATED,
    ) -> Any:
        """Ingest one named vendor capture, or another capture id of its route (a marked
        failed or test-private attempt)."""
        entity = self.run["entity"]
        capture: tuple[str, ...]
        if vendor == "/".join(SCREENER):
            request, _, _ = retained_page(entity)
            staged = SnapshotStore(self.tmp_path / "staged")
            page = stage_registered(request, self.repository, staged)
            capture = (*SCREENER, page.request_key, page.capture_id)
            for section in SECTIONS:
                adapter = screener(entity, Basis.CONSOLIDATED, section)
                self._ingest(capture, staged, adapter, end, Basis.CONSOLIDATED)
            return None
        parts = source(MANIFEST, label)[0].relative_to(SNAPSHOTS).parts
        capture = (*parts[:3], capture_id or parts[3])
        adapter = tijori(capture[2], entity) if capture[0] == "tijori" else upstox(basis)
        return self._ingest(capture, SnapshotStore(store), adapter, end, basis)

    def _ingest(
        self,
        capture: tuple[str, ...],
        store: SnapshotStore,
        adapter: Any,
        end: date | None,
        basis: Basis,
    ) -> Any:
        config = self.config
        return ingest_vendor(
            VendorIngestRequest(
                source_id=capture[0],
                surface=capture[1],
                request_key=capture[2],
                capture_id=capture[3],
                representation=Representation.JSON
                if capture[0] == "upstox"
                else Representation.HTML,
                entity_id=self.entity_id,
                period_end=end or self.end,
                basis=basis,
                framework=AccountingFramework.IND_AS,
            ),
            extract=adapter,
            extractor_version=VERSION[capture[0]],
            snapshot_store=store,
            repository=self.repository,
            dictionary=config.dictionary,
            mapping_set=config.mapping_set,
            policy=config.normalisation_policy,
            rounding_policy=config.rounding,
            fiscal_year_end_month=3,
        )

    def request(
        self,
        end: date | None = None,
        vendors: list[str] | None = None,
        cutoff: datetime | None = None,
    ) -> RunRequest:
        """The run request: the manifest's period end and vendor flags unless given."""
        settings = self.pg_db.settings
        flags = self.run["vendor_flags"] if vendors is None else vendors
        return request_for(
            self.entity_id,
            end or self.end,
            Basis.CONSOLIDATED,
            cutoff=cutoff or self.repository.store_clock(),
            config_root=self.config_root,
            code_version="test-commit",
            database_identity=DatabaseIdentity(
                host=settings.host, port=settings.port, name=self.pg_db.dbname
            ),
            vendors=tuple((flag.split("/")[0], flag.split("/")[1]) for flag in flags),
            versions=self.versions,
        )

    def execute(
        self, cutoff: datetime | None = None, vendors: list[str] | None = None
    ) -> RunRecord:
        """Execute the run request."""
        request = self.request(vendors=vendors, cutoff=cutoff)
        return execute_run(request, pool=self.pool, config_root=self.config_root)


# --- normalisation ---------------------------------------------------------------------------


MONETARY = ("crore", "INR/share")
UNITS = {"crore": (10**7, 2), "INR/share": (1, 2), "%": (1, 2), "days": (1, 2), "shares": (1, 0)}


def stored(value: Any, unit: tuple[int, int], how: str = "exact") -> Fraction | None:
    """A manifest number in the stored unit. Reported values are stored exactly; a computed one
    at rounding policy v1's scale, point half-even and bounds outward
    (``config/normalisation/rounding_policy/v1.yaml``)."""
    if value is None:
        return None
    factor, places = unit
    scale = Fraction(10) ** places
    units = Fraction(str(value)) * factor * scale
    if how == "exact":
        return units / scale
    rounding: dict[str, Callable[[Fraction], int]] = {
        "point": round,
        "lower": math.floor,
        "upper": math.ceil,
    }
    return Fraction(rounding[how](units)) / scale


def expected(
    run: dict[str, Any], entity_id: int, manifest: dict[str, Any] = MANIFEST
) -> dict[str, Any]:
    """The manifest's rows, projected onto the compared fields in stored units; the key's
    entity is the run's seeded entity, its basis and framework the header pins'."""
    found: dict[str, Any] = {}
    pins, kinds = manifest["header"]["pins"], manifest["header"]["units"]
    for key, row in expanded_rows(run).items():
        unit_name = manifest["header"]["row_units"][key.split("|")[0]]
        unit = UNITS[unit_name]
        sides = {name: row[name] for name in run["source_vector"]["first_party"]}
        sides |= row.get("vendors", {})
        found[key] = {
            "key": (
                entity_id,
                pins["basis"],
                pins["framework"],
                next(kind for kind, text in kinds.items() if text.split()[0] == unit_name),
            ),
            "applicability": row.get("applicability", "APPLICABLE"),
            # notation: currency INR on monetary rows only; a row's key_currency overrides
            "currency": row.get("key_currency", "INR" if unit_name in MONETARY else None),
            "ext": _status(row["ext"], unit),
            "cor": _status(row["cor"], unit),
            "sides": {name: _side(side, unit) for name, side in sides.items()},
            "pairs": sorted((_pair(pair, unit) for pair in row.get("pairs", [])), key=str),
            "queue": sorted(
                (tuple(sorted(item.items())) for item in row.get("queue", [])), key=str
            ),
        }
    return found


def _status(record: dict[str, Any], unit: tuple[int, int]) -> dict[str, Any]:
    return {
        "status": record["status"],
        "why": record.get("why"),
        "diff": stored(record.get("diff"), unit),
        "gap": stored(record.get("gap"), unit),
        "triage": record.get("triage"),
    }


def _side(side: dict[str, Any], unit: tuple[int, int]) -> dict[str, Any]:
    lower, upper = side.get("iv") or (None, None)
    computed = side.get("calc") == "COMPUTED"
    return {
        "s": side["s"],
        "why": side.get("why"),
        "v": stored(side.get("v"), unit, "point" if computed else "exact"),
        "iv": None
        if lower is None
        else (
            stored(lower, unit, "lower" if computed else "exact"),
            stored(upper, unit, "upper" if computed else "exact"),
        ),
        "calc": side.get("calc"),
    }


def _pair(pair: dict[str, Any], unit: tuple[int, int]) -> tuple[Any, ...]:
    return (
        pair["a"],
        pair["b"],
        pair["out"],
        pair.get("why"),
        pair.get("triage"),
        stored(pair.get("diff"), unit),
        stored(pair.get("gap"), unit),
        bool(pair.get("diag")),
    )


def _alias(run: dict[str, Any], row: ResultRow) -> str:
    period = row.key.period
    for alias, spec in run["keys"].items():
        if "instant" in spec and period.instant == date.fromisoformat(spec["instant"]):
            return str(alias)
        if "start" in spec and (period.start, period.end) == (
            date.fromisoformat(spec["start"]),
            date.fromisoformat(spec["end"]),
        ):
            return str(alias)
    return f"?{row.row_id}"


def row_key(run: dict[str, Any], row: ResultRow) -> str:
    """The manifest row key of one result row."""
    dims = ",".join(f"{axis}={member}" for axis, member in row.key.dimensions.pairs) or "-"
    return "|".join((row.key.canonical_id, _alias(run, row), dims, row.value_identity.value))


def _name(ref: SourceRef) -> str:
    if ref.source_role is SourceRole.REPORTED_COUNTERPART:
        return "reported"
    if ref.source_role is SourceRole.FIRST_PARTY:
        return ref.representation.value.lower()
    return f"{ref.source_id}/{ref.surface}"


def actual(run: dict[str, Any], rows: tuple[ResultRow, ...], items: list[Any]) -> dict[str, Any]:
    """The engine's rows in the manifest's shape."""
    found: dict[str, Any] = {}
    by_digest: dict[str, list[str]] = {}  # a Q4 key holds a reported and a derived row
    rules = run.get("applicability", {}).get("not_applicable_by_rule", {})
    excluded = {canonical for ids in rules.values() for canonical in ids}
    absent = {"xbrl", "pdf"} - set(run["source_vector"]["first_party"])
    for row in rows:
        if row.key.canonical_id in excluded and row.applicability.value == "NOT_APPLICABLE":
            continue  # the manifest lists applicable rows; these are frozen by rule
        key = row_key(run, row)
        by_digest.setdefault(row.key.digest(), []).append(key)
        sides = {}
        for value in row.source_values:
            if _name(value) in absent and value.state.value == "NO_VALUE" and not value.reason:
                continue  # a representation the package has no member of (source_vector)
            numbers = value.state.value == "VALUE"
            sides[_name(value)] = {
                "s": value.state.value,
                "why": value.reason,
                "v": Fraction(value.value) if numbers and value.value is not None else None,
                "iv": (Fraction(value.lower), Fraction(value.upper))
                if numbers and value.lower is not None and value.upper is not None
                else None,
                "calc": value.calculation_state.value if value.calculation_state else None,
            }
        ext: dict[str, Any] = {
            "status": row.extraction_status.value,
            "why": row.extraction_reason.value if row.extraction_reason else None,
            "diff": None,
            "gap": None,
            "triage": None,
        }
        pairs = []
        for pair in row.pairs:
            # The engine stores first minus other; the manifest records b - a.
            diff = None if pair.difference is None else -Fraction(pair.difference)
            gap = None if pair.interval_gap is None else Fraction(pair.interval_gap)
            if pair.pair_kind is PairKind.EXTRACTION:
                ext |= {
                    "diff": diff,
                    "gap": gap,
                    "triage": pair.triage.value if pair.triage else None,
                }
                continue
            pairs.append(
                (
                    _name(pair.left),
                    _name(pair.right),
                    pair.outcome.value,
                    pair.reason.value if pair.reason else None,
                    pair.triage.value if pair.triage else None,
                    diff,
                    gap,
                    pair.pair_kind is PairKind.DIAGNOSTIC,
                    *(() if pair.pair_kind is not PairKind.REPORTED_VS_DERIVED else ("RVD",)),
                )
            )
        found[key] = {
            "key": (
                row.key.entity_id,
                row.key.basis.value,
                row.key.framework.value,
                row.key.value_kind.value,
            ),
            "applicability": row.applicability.value,
            "currency": row.key.currency,
            "ext": ext,
            "cor": {
                "status": row.corroboration_status.value,
                "why": row.corroboration_reason.value if row.corroboration_reason else None,
                "diff": None,
                "gap": None,
                "triage": None,
            },
            "sides": sides,
            "pairs": sorted(pairs, key=str),
            "queue": [],
        }
    for item in items:
        if item.key is None:
            continue  # UNMAPPED: compared by ``unmapped``
        on = (
            "pair"
            if item.pair_identity[:7] != "status:"
            else ("extraction" if "ExtractionStatus" in item.pair_identity else "corroboration")
        )
        entry = {"on": on, "sev": item.severity.value, "out": item.outcome}
        if on == "pair":
            entry |= {"a": _name(item.source_refs[0]), "b": _name(item.source_refs[1])}
            if item.diagnostic:
                entry["diag"] = True
        keys = by_digest[item.key.digest()]
        if on == "pair":  # the row that carries the pair
            keys = [
                k
                for k in keys
                if any(p[:3] == (entry["a"], entry["b"], item.outcome) for p in found[k]["pairs"])
            ]
        found[keys[-1]]["queue"].append(tuple(sorted(entry.items())))
    for row in found.values():
        row["queue"].sort(key=str)
    return found


SOURCES = {entry["sha256"]: entry["label"] for entry in MANIFEST["header"]["sources"]}
BLOCKS = {"summary": "income_statement"}


def _json(value: Any) -> dict[str, Any]:
    """A stored JSON object (anchor, native context) as a plain dict."""
    return dict(value)


def _column(src: str, anchor: dict[str, Any], manifest: dict[str, Any] = MANIFEST) -> str:
    """The manifest column id whose x band holds the cell's centre."""
    centre = (anchor["column_x0"] + anchor["column_x1"]) / 2
    columns = manifest["header"]["pdf_columns"][src][anchor["page"]]["cols"]
    return next(
        str(name) for name, band in columns.items() if band["x"][0] <= centre < band["x"][1]
    )


def unmapped(
    cells: list[Occurrence], instances: dict[Any, list[int]], manifest: dict[str, Any]
) -> tuple[tuple[str, Any], ...]:
    """One key-less queue item's occurrences as the manifest's unmapped entry."""
    first = cells[0]
    sources = {entry["sha256"]: entry["label"] for entry in manifest["header"]["sources"]}
    src = sources[first.capture.blob_sha256]
    anchor, context = _json(first.anchor), _json(first.native_context)
    cols = [cell.anchor.get("column_label") for cell in cells]
    entry: dict[str, Any]
    if first.representation is Representation.XBRL:
        entry = {"c": context["local_name"], "ctx": anchor["context_ref"]}
    elif first.representation is Representation.PDF:
        entry = {
            "pg": anchor["page"],
            "label": first.native_field,
            "col": _column(src, anchor, manifest),
        }
        entry |= {"lex": first.raw_value_text or ""}
        lines = instances[(anchor["page"], first.native_field)]
        if len(lines) > 1:
            entry["n"] = lines.index(anchor["line"]) + 1
    elif first.capture.source_id == "tijori":
        entry = {"tbl": anchor["table_key"], "row": anchor["row_key"], "cols": cols}
    elif first.capture.source_id == "upstox":
        block = BLOCKS.get(anchor["table_key"], anchor["table_key"])
        entry = {"block": block, "item": anchor["row_label"], "cols": cols, "diag": True}
    else:
        section, row = anchor["table_id"].split(":")[0], anchor["row_path"].split(":", 1)[1]
        entry = {"sec": section, "row": row, "cols": cols}
    return tuple(sorted((key, json.dumps(value)) for key, value in (entry | {"src": src}).items()))


def unmapped_items(
    stage: Stage, items: list[Any], manifest: dict[str, Any] = MANIFEST
) -> list[tuple[tuple[str, Any], ...]]:
    """Every open key-less item of the run, in the manifest's unmapped shape."""
    with stage.pool.connection() as conn:
        captures = [row[0] for row in conn.execute("SELECT id FROM eqos.capture_refs")]
    printed = {
        (_json(cell.anchor)["page"], cell.native_field, _json(cell.anchor)["line"])
        for capture in captures
        for cell in stage.repository.list_capture_occurrences(capture)
        if cell.representation is Representation.PDF
    }
    # pdf_locator n: a label's instances are the page's lines starting with its first token
    # and carrying every one of its tokens (header.notation), top-down.
    instances = {
        (page, label): sorted(
            line
            for other_page, other, line in printed
            if other_page == page
            and other.split()[0] == label.split()[0]
            and set(label.split()) <= set(other.split())
        )
        for page, label, _ in printed
    }
    found = []
    with stage.pool.connection() as conn:
        for item in items:
            if item.key is not None:
                continue
            ids = [
                row[0]
                for row in conn.execute(
                    "SELECT occurrence_id FROM eqos.queue_item_inputs"
                    " WHERE item_id = %s AND occurrence_id IS NOT NULL ORDER BY occurrence_id",
                    (item.item_id,),
                )
            ]
            cells = sorted(
                stage.repository.get_occurrences(ids),
                key=lambda cell: int(_json(cell.anchor).get("column_index", 0)),
            )
            found.append(unmapped(list(cells), instances, manifest))
    return sorted(found)


def diff(want: dict[str, Any], got: dict[str, Any]) -> list[str]:
    """Readable differences, one line per differing row and field."""
    lines = [f"missing row {key}" for key in sorted(want.keys() - got.keys())]
    lines += [f"extra row {key}: {got[key]}" for key in sorted(got.keys() - want.keys())]
    for key in sorted(want.keys() & got.keys()):
        for field in want[key]:
            if want[key][field] != got[key][field]:
                lines.append(f"{key} {field}:\n  want {want[key][field]}\n  got  {got[key][field]}")
    return lines


class Outcome:
    """One executed run: its record, rows, open overlay and normalised rows; replay checked."""

    def __init__(
        self, stage: Stage, cutoff: datetime | None = None, vendors: list[str] | None = None
    ) -> None:
        self.stage, self.record = stage, stage.execute(cutoff, vendors)
        pool = stage.pool
        self.rows = load_results(self.record.run_id, pool=pool)
        self.overlay = read_overlay(pool, run_id=self.record.run_id, as_of=overlay_boundary(pool))
        self.items = list(self.overlay.open_items)
        self.got = actual(stage.run, self.rows, self.items)
        self.status = self.record.manifest.status.value
        self.exit = exit_status(self.record, self.overlay).value
        replayed = replay_run(self.record.run_id, pool=pool, config_root=stage.config_root)
        assert replayed == self.rows

    def row(self, key: str) -> ResultRow:
        """The result row at one manifest row key."""
        return next(row for row in self.rows if row_key(self.stage.run, row) == key)

    def interpretation(self, key: str, side: str) -> Interpretation:
        """The stored interpretation one side of one row selected."""
        (value,) = [value for value in self.row(key).source_values if _name(value) == side]
        assert value.interpretation_id is not None
        (found,) = self.stage.repository.get_interpretations([value.interpretation_id])
        return found

    def trusted(self, key: str, overlay: QueueOverlay | None = None) -> bool:
        """The trust view of one row under the run's (or a given) overlay."""
        row = self.row(key)
        (xbrl,) = [value for value in row.source_values if _name(value) == "xbrl"]
        return trusted(
            run_id=self.record.run_id,
            key=row.key,
            extraction=row.extraction_status,
            corroboration=row.corroboration_status,
            first_party_state=xbrl.state,
            overlay=overlay or self.overlay,
        ).trusted

    def check(self, expect: dict[str, dict[str, Any]]) -> list[str]:
        """Differences from named fields of named rows (``pair:a>b`` = outcome, reason)."""
        return [
            f"{key} {path}: want {want} got {_at(self.got.get(key), path)}"
            for key, fields in expect.items()
            for path, want in fields.items()
            if _at(self.got.get(key), path) != want
        ]


def _at(row: dict[str, Any] | None, path: str) -> Any:
    if row is None:
        return "no row"
    if path.startswith("pair:"):
        found = [
            pair[2:4] for pair in row["pairs"] if "|".join(pair[:2]) == path[5:].replace(">", "|")
        ]
        return found[0] if found else None
    value: Any = row
    for part in path.split("."):
        value = value.get(part) if isinstance(value, dict) else None
    return value


def manifest_lines(outcome: Outcome, manifest: dict[str, Any] = MANIFEST) -> list[str]:
    """Every difference between one run and its manifest entry (rows, UNMAPPED, run)."""
    stage, run = outcome.stage, outcome.stage.run
    lines = diff(expected(run, stage.entity_id, manifest), outcome.got)
    want = Counter(
        tuple(sorted((key, json.dumps(value)) for key, value in entry.items()))
        for entry in run["unmapped"]
    )
    got = Counter(unmapped_items(stage, outcome.items, manifest))
    lines += [f"missing unmapped {dict(entry)} x{n}" for entry, n in (want - got).items()]
    lines += [f"extra unmapped {dict(entry)} x{n}" for entry, n in (got - want).items()]
    severities = Counter(
        item.severity.value + ("_diagnostic" if item.diagnostic else "") for item in outcome.items
    )
    found = {"status": outcome.status, "exit": outcome.exit, "queue": dict(severities)}
    wanted = {"status": run["status"], "exit": run["exit"], "queue": run["counts"]["queue"]}
    return lines + [
        f"run {key}: want {wanted[key]} got {found[key]}"
        for key in found
        if found[key] != wanted[key]
    ]


def cli(stage: Stage, monkeypatch: pytest.MonkeyPatch, *args: str) -> int:
    """``fundamentals compare <args>`` in process against the test database."""
    for name, value in stage.pg_db.cli_env().items():
        monkeypatch.setenv(name, value)
    return main(["compare", *args])


def cli_run(stage: Stage, monkeypatch: pytest.MonkeyPatch) -> int:
    """``fundamentals compare run`` over the stage's entity, period and vendors."""
    vendors = [arg for flag in stage.run["vendor_flags"] for arg in ("--vendor", flag)]
    return cli(
        stage,
        monkeypatch,
        "run",
        "--entity",
        stage.run["entity"],
        "--period-end",
        str(stage.end),
        "--basis",
        "consolidated",
        "--dictionary",
        VERSIONS.dictionary,
        "--mapping-set",
        VERSIONS.mapping_set,
        *vendors,
    )


def full_run(stage: Stage) -> Outcome:
    """The manifest run's own inputs, executed."""
    if stage.run["first_party"]["members"]:
        stage.first_party()
    stage.vendors()
    return Outcome(stage)


def mark(stage: Stage, original: Interpretation, label: str, **update: Any) -> Interpretation:
    """Store a marked copy of one interpretation (new id, marked digest, value verbatim)."""
    (new_id,) = stage.repository.reserve_interpretation_ids(1)
    copy = original.model_copy(
        update={
            "interpretation_id": new_id,
            "input_digest": hashlib.sha256(f"test-marked {label}".encode()).hexdigest(),
            "recorded_at": stage.repository.store_clock() + timedelta(microseconds=1),
            **update,
        }
    )
    stage.repository.put_interpretations([copy])
    return copy


FY25_END = date(2025, 3, 31)
APAR_FY25 = {  # the unmarked Apar FY25 runs of E9 / E16 (not manifest runs)
    "period_end": FY25_END.isoformat(),
    "keys": {
        "Q": {"start": "2025-01-01", "end": "2025-03-31"},
        "Y": {"start": "2024-04-01", "end": "2025-03-31"},
        "I": {"instant": "2025-03-31"},
    },
    "source_vector": {"first_party": ["xbrl"], "vendors": {}},
    "vendor_flags": [],
}
FY25_XBRL = {Representation.XBRL: "xbrl-consolidated-comparator"}


def fy25(stage: Stage, vendors: list[str]) -> None:
    """Point the stage at Apar's FY25 period end."""
    stage.run = stage.run | APAR_FY25 | {"vendor_flags": vendors}
    stage.end = FY25_END


def fixture_side(spec: dict[str, Any], computed: bool) -> tuple[Any, Any]:
    """A manifest fixture side's value and interval in stored units."""
    side = _side(spec | {"s": "VALUE", "calc": "COMPUTED" if computed else None}, UNITS["crore"])
    return side["v"], side["iv"]
