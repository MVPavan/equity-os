"""PILOT-E2E support (``test_pilot_e2e.py``): the frozen pilot manifest, and the PILOT-1,
PILOT-2, PILOT-9, PILOT-10 and PILOT-13 checks over one pilot database.

Every expected number is read from ``pilot_manifest.yaml`` or the ``stage1_manifest.yaml`` it
pins; every failing assertion begins ``PILOT-n:``.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import re
from collections import defaultdict
from datetime import date
from fractions import Fraction
from pathlib import Path
from typing import Any

import psycopg
import pytest
import stage1_e2e_support as s1
import test_data_stage3_e2e as s3
from evidence_support import CONFIG
from pg_support import mint_name
from pilot_manifest_check import ASSUMED, COLUMN, UNIT_SCALE, doc, sha, sha_of
from pilot_manifest_check import CONFIGS as PILOT_CONFIGS
from prep2b_support import PINS, STOCK, Pilot
from stage1_e2e_support import MANIFEST as STAGE1
from stage1_e2e_support import RUNS, SCREENER, SECTIONS, SNAPSHOTS, VERSION, row_key
from stage3_data_support import SCR, VENDORS, companion
from stage5_support import cli
from test_backup_restore import use_env
from test_evidence_vendor import screener, tijori
from test_frozen_manifests import DATA3, REPO, load, source, xbrl_index
from test_shareholding_filing import RAW
from vendor_retained_support import retained_page, stage_registered

import equity_os.interface.entry.cli as fundamentals_cli
from equity_os.contracts.measurement.canonical import (
    ApplicabilityStatus,
    Basis,
    PeriodNature,
    Representation,
    StatementFamily,
)
from equity_os.contracts.measurement.evidence import FilingFamily
from equity_os.contracts.measurement.observation import AccountingFramework
from equity_os.contracts.publication.ledger import VersionDraft
from equity_os.contracts.storage.retention import HoldRoot
from equity_os.contracts.verification.comparison import CorroborationStatus, PairKind, SourceState
from equity_os.extraction.packages.capture_intake import parse_filed_at
from equity_os.extraction.surfaces.vendor_ingest import VendorIngestRequest, ingest_vendor
from equity_os.interface.commands.sourcing.shareholding_cli import _entity
from equity_os.interface.commands.verification.compare_cli import add_compare_parser, run_compare
from equity_os.normalisation.dictionary.dictionary import CanonicalDictionary, FormulaOperand
from equity_os.storage.backup.backup import RestoreCheck
from equity_os.storage.backup.restore_check import replay
from equity_os.storage.database.settings import PgRole
from equity_os.storage.database.test_databases import drop_test_database
from equity_os.storage.raw_files.snapshot_store import SnapshotStore
from equity_os.storage.records.repository import EvidenceRepository
from equity_os.storage.retention.eligibility import eligible_blobs
from equity_os.storage.retention.holds import capture_facts, pinned_roots
from equity_os.verification.comparison.run import load_results
from equity_os.verification.comparison.run_config import load_run_config
from equity_os.verification.comparison.run_models import ResultRow
from equity_os.verification.comparison.tables import PairResult, SourceQualifiedPair
from equity_os.verification.review_queue.queue import overlay_boundary, read_overlay
from equity_os.verification.review_queue.routing import route_pair_draft, route_status_draft

PILOT_PATH = "tests/fundamentals/fixtures/data_foundation/pilot_manifest.yaml"
MANIFEST = load(REPO / PILOT_PATH)
QUARTERS = tuple(PILOT_CONFIGS)
Q0, Q1, Q2, Q3 = QUARTERS
H3_ROW = "opex_excl_finance_and_da|Q|-|DERIVED"  # stage1 pre_registered H3 (PILOT-2)
OPM_ROW = "opm_pct|Q|-|DERIVED"  # stage1 pre_registered C7_OPM (PILOT-1)
SEGMENT_BLOCK = "segment_revenue"  # the PQ3 PDF block eqos-ghv leaves unlocated
TIJORI = "tijori/financials"
SIDES = {Representation.XBRL, Representation.PDF}  # an admission run's first-party sides
EVIDENCE = (1,)  # a placeholder attempt id: routing reads no evidence, a draft needs one
ALL_CITED = (
    "SELECT source_sha256 FROM eqos.numeric_claims WHERE source_sha256 IS NOT NULL UNION "
    "SELECT c.blob_sha256 FROM eqos.numeric_claims n JOIN eqos.capture_refs c "
    "ON c.id = n.capture_ref_id"
)
CAPTURES = "SELECT source_id, surface, request_key, capture_id, blob_sha256 FROM eqos.capture_refs"
SHP = MANIFEST["shareholding"]
SHP_LABELS = {source["sha256"]: source["label"] for source in MANIFEST["header"]["sources"]}
IDENTITY = load(REPO / "config/companies/identity/aparinds.yaml")
NODE = ("file", "periodicity", "path", "source_node_id", "column")  # a vendor side's evidence
ROLES = (("sebi_promoter", "promoter"), ("public", "non_institutions"), "institutions")  # R12


def fail(prefix: str, check: Any, *args: Any) -> None:
    """Run a manifest-check predicate, prefixing its refusal with the PILOT check code."""
    try:
        check(*args)
    except AssertionError as error:
        raise AssertionError(f"{prefix}: {error}") from None


def frozen_value(quarter: str, key: str) -> Fraction:
    """A claim's frozen value: exact, or ``pct``/``calc.3`` as emitted (0.01, half-even)."""
    value = Fraction(MANIFEST["quarters"][quarter]["claims"][key]["v"])
    return Fraction(round(value * 100), 100) if key.endswith(".pct") or key == "calc.3" else value


def compare_run(quarter: str, pilot: Pilot) -> int:
    """The quarter's admission comparison run, named by its run argv."""
    argv = pilot.registered(quarter)[1]
    return int(argv[argv.index("--compare-run") + 1])


# PILOT-1 -----------------------------------------------------------------------------------


def inventory(dictionary: CanonicalDictionary, quarter: str) -> set[tuple[str, str, str, str]]:
    """The quarter's expected row identities (canonical id, period, dims, value identity) from
    the pinned dictionary — non-deprecated rows outside shareholding over the quarter,
    year-to-date and closing-instant periods, a fiscal Q4's additive flows also derived
    (FY − 9M) — templated rows at the members the package discloses, templated formulas where
    every operand is disclosed."""
    span = doc(PILOT_CONFIGS[quarter])["quarter"]
    start, end = date.fromisoformat(span["period_start"]), date.fromisoformat(span["period_end"])
    year = date(end.year - (end.month < 4), 4, 1)
    durations, instant = {f"{begin}..{end}" for begin in {start, year}}, str(end)
    reported = disclosed(quarter, durations, instant)
    rows = {(*row, "REPORTED") for row in reported}
    for row in dictionary.rows:
        if row.family is StatementFamily.SHAREHOLDING or row.deprecated_by:
            continue
        identity = "DERIVED" if row.family is StatementFamily.DERIVED else "REPORTED"
        if row.dimension_template is None:
            nature = {instant} if row.period_nature is PeriodNature.INSTANT else durations
            found = {(period, "-") for period in nature}
        elif row.formula is None:
            found = {(p, d) for c, p, d in reported if c == row.canonical_id}
        else:
            found = set.intersection(*(members(reported, op) for op in row.formula.operands))
        rows |= {(row.canonical_id, p, d, identity) for p, d in found}
        if end.month == 3 and (row.period_aggregation or "").endswith("ADDITIVE_DURATION"):
            rows |= {
                (row.canonical_id, p, d, "DERIVED") for p, d in found if p == f"{start}..{end}"
            }
    return rows


def members(reported: set[tuple[str, str, str]], operand: FormulaOperand) -> set[tuple[str, str]]:
    """A formula operand's disclosed (period, dims), an aggregated axis set to its output."""
    found = {(p, d) for c, p, d in reported if c == operand.canonical_id}
    if (aggregation := operand.aggregation) is None:
        return found
    member = f"{aggregation.axis}={aggregation.output_member}"
    return {(p, re.sub(f"{aggregation.axis}=[^,]+", member, d)) for p, d in found}


def disclosed(quarter: str, durations: set[str], instant: str) -> set[tuple[str, str, str]]:
    """The quarter's disclosed dimensioned row identities (canonical id, period, dims): each
    pinned-mapping ``XBRL_DESCRIPTION`` entry's concept on its axis in the retained XBRL, the
    member named by its ``DescriptionOfReportableSegment`` as the dictionary's segment template
    instantiates it; and each pinned PDF entry's fixed members at its column periods."""
    mappings = REPO / "config/normalisation/mappings"
    files = load(mappings / f"{PINS[-1]}.yaml")["entry_files"]
    entries = {f: load(mappings / f)["entries"] for f in files if f.startswith(("xbrl/", "pdf/"))}
    index = xbrl_index(source(MANIFEST, f"X-{quarter}")[0])
    facts = [(concept, *fact) for (concept, _), found in index.items() for fact in found]
    names = {
        dims[0].split("=")[1]: re.sub(r"[^a-z0-9]+", "_", (element.text or "").lower()).strip("_")
        for concept, element, _, dims in facts
        if concept == "DescriptionOfReportableSegment"
    }
    rows: set[tuple[str, str, frozenset[tuple[str, str]]]] = set()
    for f, found in entries.items():
        for entry in found:
            canonical, selector = entry["canonical_id"], entry["selector"]
            fixed = entry.get("dimension_members", {})
            if entry.get("member_source") == "XBRL_DESCRIPTION":
                for concept, _, period, dims in facts:
                    if concept == selector["native_field"] and len(dims) == 1:
                        axis, member = dims[0].split("=")
                        if axis == selector["dimension_axis"] and period in durations | {instant}:
                            pairs = fixed | {"segment": names[member]}
                            rows.add((canonical, period, frozenset(pairs.items())))
            elif fixed and f.startswith("pdf/"):
                periods = durations if entry["period_rule"] == "COLUMN_DURATION" else {instant}
                rows |= {(canonical, period, frozenset(fixed.items())) for period in periods}
    return {(c, p, ",".join(f"{k}={v}" for k, v in sorted(d))) for c, p, d in rows}


def pilot1(
    pilot: Pilot, quarter: str, dictionary: CanonicalDictionary, version: VersionDraft
) -> None:
    """PILOT-1: the admission run's row identities are the expected inventory, each applicable
    row has its XBRL and PDF sides, each located manifest figure is a ``VALUE`` at its lexeme on
    exactly those two sides, nothing is zero-filled, and PQ0's frozen PBT, OPM and PQ3's
    segment block hold."""
    with pilot.pg_db.runtime_pool() as pool:
        rows = load_results(compare_run(quarter, pilot), pool=pool)
    expected = inventory(dictionary, quarter)
    found = set()
    for row in rows:
        canonical, period, _, dims, identity = row.row_id.split("|")
        found.add((canonical, period, dims, identity))
        sides = {side.representation for side in row.source_values}
        applicable = row.applicability is not ApplicabilityStatus.NOT_APPLICABLE
        assert sides == (SIDES if applicable else set()), f"PILOT-1: {row.row_id} sides {sides}"
        for side in row.source_values:
            assert side.state is SourceState.VALUE or side.value is None, (
                f"PILOT-1: {row.row_id} carries a value with no extraction (zero fill)"
            )
    missing, extra = sorted(expected - found), sorted(found - expected)
    assert not missing and not extra, f"PILOT-1: {quarter} missing {missing[:5]} extra {extra[:5]}"
    claims = {claim.claim_key: claim for claim in version.claims}
    for key, node in MANIFEST["quarters"][quarter]["claims"].items():
        if not key.startswith("fact."):
            continue
        measured = claims[key].measurement_key
        assert measured is not None, f"PILOT-1: {quarter} {key} has no measurement key"
        (row,) = [
            r
            for r in rows
            if (r.key.canonical_id, r.key.period) == (measured.canonical_id, measured.period)
            and not r.key.dimensions.pairs
            and r.value_identity.value == "REPORTED"
        ]
        (located,) = node["at"]
        lexemes = {
            Representation.XBRL: Fraction(located["lex"]),
            Representation.PDF: Fraction(node["pdf"]["lex"].replace(",", ""))
            * UNIT_SCALE[located["u"]],
        }
        assert sorted(side.representation for side in row.source_values) == sorted(SIDES), (
            f"PILOT-1: {quarter} {key} sides are not one XBRL and one PDF"
        )
        for side in row.source_values:
            want = lexemes[side.representation]
            assert side.state is SourceState.VALUE and Fraction(side.value or 0) == want, (
                f"PILOT-1: {quarter} {key} {side.representation.value} side is not VALUE {want}"
            )
    if quarter == Q0:
        pilot1 = MANIFEST["pilot_checks"]["PILOT-1"]
        for pointer in (pilot1["pbt"], pilot1["pbt_after_associates"]):
            at, key = pointer.split()
            assert Fraction(claims[key].value or 0) == frozen_value(at, key), f"PILOT-1: {pointer}"
        run = RUNS["APARINDS-Q2FY26"]
        (opm,) = [row for row in rows if row_key(run, row) == OPM_ROW]
        (xbrl,) = [s for s in opm.source_values if s.representation is Representation.XBRL]
        literal = Fraction(pilot1["opm"]["lex"])
        assert round(Fraction(xbrl.value or 0), 2) == literal, f"PILOT-1: {OPM_ROW} ≠ {literal}"
    if quarter == Q3:
        segments = [row for row in expected if row[0] == SEGMENT_BLOCK and row[2] != "-"]
        assert segments, "PILOT-1: PQ3 has no segments"
        for row in rows:
            for side in row.source_values:
                if row.key.dimensions.pairs and side.representation is Representation.PDF:
                    block = row.key.canonical_id == SEGMENT_BLOCK
                    explicit = side.state is SourceState.INVALID and side.reason
                    assert side.state is not SourceState.VALUE and (explicit or not block), (
                        f"PILOT-1: PQ3 segment {row.row_id} is valued or not an explicit failure"
                    )


# PILOT-2 -----------------------------------------------------------------------------------


def vendor_captures(pilot: Pilot) -> list[tuple[tuple[str, ...], Any]]:
    """A-SCR staged and A-TIJ copied into the pilot's snapshot store, each capture with its
    adapter (Screener once per page section)."""
    snapshots = SnapshotStore(pilot.rig.snapshots)
    with pilot.pg_db.runtime_pool() as pool:
        page = stage_registered(retained_page(STOCK)[0], EvidenceRepository(pool), snapshots)
    captures = [
        ((*SCREENER, page.request_key, page.capture_id), screener(STOCK, Basis.CONSOLIDATED, part))
        for part in SECTIONS
    ]
    parts = source(STAGE1, "A-TIJ")[0].relative_to(SNAPSHOTS).parts[:4]
    snapshots.put_capture(*SnapshotStore(SNAPSHOTS).read_capture_verified(*parts))
    return [*captures, (parts, tijori(parts[2], STOCK))]


def proposed_routes(rows: tuple[ResultRow, ...]) -> dict[str, set[tuple[str, str]]]:
    """Per key digest, the (pair identity, routing reason) of every item the routing policy
    proposes: extraction by status, each other pair, then corroboration unless a pair carries
    its ``NOT_COMPARABLE``; nothing for an inapplicable row."""
    proposed: dict[str, set[tuple[str, str]]] = defaultdict(set)
    for row in rows:
        if row.applicability is ApplicabilityStatus.NOT_APPLICABLE:
            continue
        pairs = [pair for pair in row.pairs if pair.pair_kind is not PairKind.EXTRACTION]
        drafts = [route_status_draft(row.extraction_status, key=row.key, attempt_ids=EVIDENCE)]
        for pair in pairs:
            result = PairResult.model_validate(
                pair.model_dump(include=set(PairResult.model_fields))
            )
            qualified = SourceQualifiedPair(
                pair_kind=pair.pair_kind,
                left=pair.left,
                right=pair.right,
                result=result,
                attempt_ids=EVIDENCE,
            )
            drafts.append(route_pair_draft(qualified, key=row.key))
        if not (row.corroboration_status is CorroborationStatus.NOT_COMPARABLE and pairs):
            status = row.corroboration_status
            drafts.append(route_status_draft(status, key=row.key, attempt_ids=EVIDENCE))
        proposed[row.key.digest()] |= {
            (draft.pair_identity, draft.routing_reason) for draft in drafts if draft is not None
        }
    return {digest: routes for digest, routes in proposed.items() if routes}


def pilot2(
    pilot: Pilot,
    quarter: str,
    captures: list[tuple[tuple[str, ...], Any]],
    version: VersionDraft,
) -> int:
    """PILOT-2: both vendors ingested for the quarter end and compared in a separate run under
    the pilot pins; each vendor identity is present in a ``COMPLETE`` run, each role has a
    vendor side or is filing-only, an unavailable side keeps its attempt, each row's queue items
    are exactly the routing policy's, and PQ0's H3 cell is the frozen outcome. Returns the run."""
    config = load_run_config(CONFIG, fundamentals_cli.PILOT_VERSIONS)
    end = pilot.period_ends[quarter]
    with pilot.pg_db.runtime_pool() as pool:
        repository = EvidenceRepository(pool)
        for capture, adapter in captures:
            ingest_vendor(
                VendorIngestRequest(
                    source_id=capture[0],
                    surface=capture[1],
                    request_key=capture[2],
                    capture_id=capture[3],
                    representation=Representation.HTML,
                    entity_id=pilot.entity_id,
                    period_end=end,
                    basis=Basis.CONSOLIDATED,
                    framework=AccountingFramework.IND_AS,
                ),
                extract=adapter,
                extractor_version=VERSION[capture[0]],
                snapshot_store=SnapshotStore(pilot.rig.snapshots),
                repository=repository,
                dictionary=config.dictionary,
                mapping_set=config.mapping_set,
                policy=config.normalisation_policy,
                rounding_policy=config.rounding,
                fiscal_year_end_month=3,
            )
        command = ["compare", "run", "--entity", STOCK, "--basis", "consolidated", *PINS]
        command += ["--period-end", str(end), "--alignment-rules", "v2", "--config-root"]
        command += [str(CONFIG), "--vendor", "/".join(SCREENER), "--vendor", TIJORI]
        parser = argparse.ArgumentParser()
        add_compare_parser(parser.add_subparsers())
        record = run_compare(parser.parse_args(command))
        rows = load_results(record.run_id, pool=pool)
        overlay = read_overlay(pool, run_id=record.run_id, as_of=overlay_boundary(pool))
    vendors = {SCREENER[0], TIJORI.split("/")[0]}
    seen = {side.source_id for row in rows for side in row.source_values} & vendors
    status = record.manifest.status.value
    assert seen == vendors and status == "COMPLETE", (
        f"PILOT-2: {quarter} vendors {seen} in a {status} run"
    )
    assert not record.manifest.operational_failures, f"PILOT-2: {quarter} operational failure"
    roles = {
        (claim.measurement_key.canonical_id, claim.measurement_key.period)
        for claim in version.claims
        if claim.claim_key.startswith("fact.") and claim.measurement_key is not None
    }
    for row in rows:
        if (row.key.canonical_id, row.key.period) in roles and row.row_id.endswith("|-|REPORTED"):
            vendor_side = any(side.source_id in vendors for side in row.source_values)
            filing_only = row.corroboration_status is CorroborationStatus.FILING_ONLY
            assert vendor_side or filing_only, f"PILOT-2: {row.row_id} has no vendor side or status"
        for side in row.source_values:
            assert side.state is not SourceState.UNAVAILABLE or side.attempt_id is not None, (
                f"PILOT-2: {row.row_id} is UNAVAILABLE without its failure evidence"
            )
    stored: dict[str, set[tuple[str, str]]] = defaultdict(set)
    for item in (*overlay.open_items, *overlay.disposed_items):
        if item.key is not None:
            stored[item.key.digest()].add((item.pair_identity, item.routing_reason))
    proposed = proposed_routes(rows)
    differing = sorted(k for k in set(stored) | set(proposed) if stored.get(k) != proposed.get(k))
    assert not differing, f"PILOT-2: {quarter} queue items are not the routing policy's"
    if quarter == Q0:
        want = {name: node["lex"] for name, node in MANIFEST["pilot_checks"]["PILOT-2"].items()}
        (h3,) = [row for row in rows if row_key(RUNS["APARINDS-Q2FY26"], row) == H3_ROW]
        (pair,) = [
            pair
            for pair in h3.pairs
            if pair.pair_kind is PairKind.CORROBORATION and SCREENER[0] == pair.right.source_id
        ]
        got = {
            "pair": pair.outcome.value,
            "triage": pair.triage.value if pair.triage else None,
            "queue": "none" if h3.key.digest() not in stored else "item",
        }
        assert got == want, f"PILOT-2: {H3_ROW} {got} ≠ {want}"
    return record.run_id


# PILOT-9 ------------------------------------------------------------------------------------


def shp_frozen(quarter: str) -> tuple[Any, ...]:
    """A quarter's frozen run, point checks, vendor sides and readings (a probe's ``_vendor`` or the
    hashed companion), nodes (file as SHA-256), package, hash→label map; FY27_Q1's from Stage 3."""
    frozen, pin = SHP["quarters"][quarter], SHP["companion"]
    if "package" in frozen:
        assert "_vendor" in MANIFEST or sha(pin["path"]) == pin["sha256"], "PILOT-9: companion"
        own = (MANIFEST.get("_vendor") or doc(pin["path"]))["runs"][frozen["run"]["run"]]
        nodes = {i: n | {"file": sha_of(MANIFEST, n["file"])} for i, n in own["nodes"].items()}
        found = frozen["run"], frozen["point_checks"], own["sides"], own["point_checks"], nodes
        return *found, frozen["package"], SHP_LABELS
    pinned = sha(str(DATA3.relative_to(REPO))) == sha_of(MANIFEST, SHP["stage3"])
    assert source(MANIFEST, SHP["stage3"])[0] == DATA3 and pinned, "PILOT-9: the Stage 3 pin"
    (run,) = [run for run in s3.MANIFEST["runs"] if run["run"] == frozen["run"]]
    vendor, day, name = companion(s3.MANIFEST), date.fromisoformat(frozen["instant"]), run["run"]
    gen2 = {Path(s["path"]).name: s for s in s3.HEADER["sources"] if f"{STOCK}/gen-2" in s["path"]}
    nodes = {
        n["id"]: n
        | {"file": f["sha256"], "column": day.strftime(COLUMN[f["kind"]])}
        | {"source_node_id": n["source_node_id"] or n["label"]}
        for tree in vendor["tree"][STOCK].values()
        for n in tree
        if (f := gen2[n["file"]])["kind"] in COLUMN  # aggregate tables, not drill-downs
    }
    head = run, s3.MANIFEST["point_checks"][name], vendor["sides"][name]
    return *head, vendor["point_checks"][name], nodes, s3.MANIFEST["packages"][STOCK], s3.LABELS


def pilot9(pilot: Pilot, quarter: str) -> int:
    """PILOT-9 at a quarter's instant: issuer identity, then the CLI ingest, run and report against
    the frozen rows, filing, vendor evidence and point lines. Returns the run id."""
    run, checks, sides, readings, nodes, package, labels = shp_frozen(quarter)
    frozen, where = SHP["quarters"][quarter], f"PILOT-9: {quarter}"
    instant, day = frozen["instant"], date.fromisoformat(frozen["instant"])
    with pilot.pg_db.runtime_pool() as pool:
        held = EvidenceRepository(pool).issuer_identifiers(pilot.entity_id, as_of=day)
        found = (_entity(pool, STOCK, day), held.isin, held.nse_symbol, held.bse_scrip)
    assert found == (pilot.entity_id, IDENTITY["isin"], STOCK, IDENTITY["bse_scrip"]), where
    slots = {"<INSTANT>": instant, "<GEN>": str(frozen["generation"])}
    slots |= {"<tmp>": str(pilot.rig.snapshots), "data/raw/shareholding": str(RAW)}
    fill = re.compile("|".join(slots))  # the recorded command, slots filled
    argv = {c: fill.sub(lambda m: slots[m[0]], text).split()[1:] for c, text in SHP["cli"].items()}
    assert s3._cli(*argv["ingest"])[0] == 0, f"{where} ingest"
    code, out = s3._cli(*argv["run"])
    run_id = int(out.split("\n")[0].split("\t")[1])
    assert code == run["exit"], f"{where} run exit {code}"
    with pilot.pg_db.runtime_pool() as pool:
        repository = EvidenceRepository(pool)
        rows = load_results(run_id, pool=pool)
        items = list(read_overlay(pool, run_id=run_id, as_of=overlay_boundary(pool)).open_items)
        packages = repository.list_packages(pilot.entity_id, FilingFamily.SHAREHOLDING, day)
        interpreted = repository.get_interpretations(  # the vendor sides' readings
            [i for r in rows for v in r.source_values if v.source_id and (i := v.interpretation_id)]
        )
        occurrences = repository.get_occurrences([o for r in interpreted if (o := r.occurrence_id)])
    by_id, evidence = {o.occurrence_id: o for o in occurrences}, {}
    for reading in interpreted:  # each vendor side's capture, native node and labels
        cell = by_id[reading.occurrence_id]
        context: dict[str, Any] = {**cell.native_context, "file": cell.capture.blob_sha256}
        context |= {"column": context.get("period_label"), "path": list(context["path"])}
        at = {field: context[field] for field in NODE}
        evidence[reading.interpretation_id] = {"at": at, "labels": s3._labels(reading)}
    rich = copy.deepcopy(run)
    for key, name, side in ((k, n, s) for k, named in sides.items() for n, s in named.items()):
        rich["rows"][key]["vendors"][name] |= {"v": side["v"], "iv": s3._printed(side)}
    drift = s1.diff(s1.expected(rich, pilot.entity_id, s3.MANIFEST), s1.actual(run, rows, items))
    assert not (drift := [line.split(":")[0] for line in drift]), f"{where} {drift}"  # no values
    formal = {(p.outcome.value, p.reason and p.reason.value) for r in rows for p in r.pairs}
    assert formal <= {("NOT_COMPARABLE", "PRECISION_UNSUPPORTED")}, f"{where} pairs {formal}"
    stored = [
        (x["instance"], x["lineage"], x["links"], parse_filed_at(x["at"][2]["lex"].title()))
        for x in package["stored"]
    ]
    assert [s3._package(p, labels) for p in packages] == stored, f"{where} filing"
    bound = {
        s3._key(row.key): {
            f"{v.source_id}/{v.surface}": evidence[v.interpretation_id]
            for v in row.source_values
            if v.source_id is not None and v.interpretation_id is not None
        }
        for row in rows
    }
    want_bound = {
        key: {
            name: {"at": {f: nodes[side["at"]["node"]][f] for f in NODE}, "labels": side["labels"]}
            for name, side in row.get("vendors", {}).items()
            if "at" in side
        }
        for key, row in run["rows"].items()
    }
    assert bound == want_bound, f"{where} vendor evidence"
    code, out = s3._cli(*argv["report"])
    shown = code == 0 and f"run\t{run_id}\n" in out and f"status\t{run['status']}" in out
    assert shown, f"{where} report run or status"
    printed = [s3._point(line) for line in out.splitlines() if line.startswith("point\t")]
    selected = packages[package["selected"]].package_id
    frozen_points = zip(checks, readings, strict=True)
    want_points = [s3._want_point(c, r, selected, instant=instant) for c, r in frozen_points]
    order = lambda line: (line["key"], line["source"])  # noqa: E731
    same = sorted(printed, key=order) == sorted(want_points, key=order)
    assert same, f"{where} point lines"  # a bare name: no vendor value is introspected
    assert all(line["labels"].startswith(ASSUMED) for line in printed), f"{where} labels"
    for vendor in (SCR, VENDORS["tijori"]):  # R12: promoter, public and institution lines
        named = {line["key"].rsplit("=", 1)[1] for line in printed if line["source"] == vendor}
        assert all(any(n.startswith(r) for n in named) for r in ROLES), f"{where} {vendor} R12"
    return run_id


def pilot13(pool: Any, runs: list[int], where: str) -> None:
    """PILOT-13: every admission and vendor run replays to its stored results."""
    assert replay(tuple(runs), pool, CONFIG) == ((), ()), f"PILOT-13: {where} replay differs"


def no_fetch(url: str) -> bytes:
    """The purge's live fetcher: the pilot fetches nothing."""
    raise AssertionError(f"PILOT-10: the purge fetched {url}")


def pilot10(pilot: Pilot, monkeypatch: pytest.MonkeyPatch, runs: list[int]) -> None:
    """PILOT-10 under the real store clock: classify, back up, list exactly the eligible blobs
    and none held, purge only listed captures, ``db restore --replay-runs`` into a fresh test
    database (PILOT-13: every run replays there) and verify every held blob's hash there."""
    root, sets, settings = pilot.rig.snapshots, pilot.tmp_path / "sets", pilot.pg_db.settings
    assert cli("retention", "classify")[0] == 0, "PILOT-10: classify failed"
    code, out = cli("db", "backup", "--out", str(sets), "--snapshot-root", str(root))
    assert code == 0, f"PILOT-10: backup failed: {out}"
    set_dir = Path(out.split("\t")[1].strip())
    code, out = cli("retention", "purge", "--dry-run", "--snapshot-root", str(root))
    lines = [line.split("\t") for line in out.splitlines() if line.startswith("eligible\t")]
    pinned = pinned_roots(CONFIG)
    with psycopg.connect(settings.conninfo(PgRole.ADMIN, dbname=pilot.pg_db.dbname)) as conn:
        ((now,),) = conn.execute("SELECT eqos.store_now()").fetchall()
        blobs = eligible_blobs(capture_facts(conn, pinned), now)
    listed = {(line[1], line[2]) for line in lines}
    assert code == 0 and listed == {(b.source_id, b.blob_sha256) for b in blobs}, (
        f"PILOT-10: the dry run lists {len(listed)} blobs, not the {len(blobs)} eligible"
    )
    manifest = pinned[HoldRoot.MANIFEST_INPUT]
    packages = {m["sha256"] for q in MANIFEST["quarters"].values() for m in q["package"]}
    held = manifest | {row[0] for row in pilot.query(ALL_CITED)}
    assert packages <= manifest, "PILOT-10: holds.yaml does not hold the pilot packages"
    assert not {blob for _, blob in listed} & held, "PILOT-10: a held blob is listed"
    monkeypatch.setattr("equity_os.interface.commands.storage.retention_cli.live_fetch", no_fetch)
    code, out = cli("retention", "purge", "--snapshot-root", str(root), "--backup-dir", str(sets))
    expired = {line.split("\t")[1] for line in out.splitlines() if line.startswith("expired\t")}
    assert code == 0 and expired <= {c for line in lines for c in line[4].split(",")}, (
        f"PILOT-10: the purge expired unlisted captures: {out}"
    )
    target, restored = mint_name(settings), pilot.tmp_path / "restored"
    replayed: list[int] = []

    def spy(run_ids: tuple[int, ...], *args: Any) -> tuple[tuple[int, ...], tuple[int, ...]]:
        replayed.extend(run_ids)
        return replay(run_ids, *args)

    monkeypatch.setattr("equity_os.storage.backup.backup.replay", spy)
    try:
        use_env(monkeypatch, pilot.pg_db, settings.db)  # restore names only its target
        code, out = cli(
            *("db", "restore", "--set", str(set_dir), "--database", target),
            *("--snapshot-root", str(restored), "--live-snapshot-root", str(root)),
            *("--backup-dir", str(sets), "--replay-runs", "--config-root", str(CONFIG)),
        )
        use_env(monkeypatch, pilot.pg_db, pilot.pg_db.dbname)
        check = RestoreCheck.model_validate_json(out.strip().splitlines()[-1])
        assert code == 0 and check.ok and not check.replay_expired, f"PILOT-10: restore {check}"
        assert set(runs) <= set(replayed), "PILOT-13: the restore did not replay every run"
        with psycopg.connect(settings.conninfo(PgRole.ADMIN, dbname=target)) as conn:
            captures = conn.execute(CAPTURES).fetchall()
        snapshots = SnapshotStore(restored)
        for source_id, surface, key, capture, blob in captures:
            if blob in held:
                body = snapshots.read_capture_verified(source_id, surface, key, capture)[1]
                assert hashlib.sha256(body).hexdigest() == blob, f"PILOT-10: {capture} hash"
    finally:
        drop_test_database(settings, target)
