"""D8 stage D8.3 (Task 6): vendor shareholding trees, pairing, failures and diagnostics.

Each test ingests the retained gen-2 generations (or a marked copy) through ``fundamentals
shareholding ingest`` and runs ``fundamentals compare`` with the four vendor surfaces into
``eqos_test_*`` databases with the socket guard on.
"""

from __future__ import annotations

import json
import shutil
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
import yaml
from lxml import html  # type: ignore[import-untyped]
from onboarding_support import count
from pg_support import PgTestDatabase
from test_shareholding_compare import CONFIG_ROOT, SHP_ARGS, _compare
from test_shareholding_filing import (
    COMPANIES,
    EVIDENCE_TABLES,
    GEN,
    INSTANT,
    RAW,
    _ingest,
    _marked,
    _seed,
)
from test_shareholding_filing import guarded as guarded  # the fixture, re-exported
from test_shareholding_filing import ingested as ingested  # the fixture, re-exported

from fundamentals.api import shareholding_cli
from fundamentals.api.cli import main
from fundamentals.compare import run_config
from fundamentals.compare.queue import item_inputs, overlay_boundary, read_overlay
from fundamentals.compare.report import ASSUMPTION_LABELS
from fundamentals.compare.routing import route_run
from fundamentals.compare.run import (
    ResultRow,
    RunExitStatus,
    RunStatus,
    load_results,
    replay_inputs,
    replay_run,
)
from fundamentals.compare.run_config import vendor_extractor_pin
from fundamentals.compare.run_store import RunStore
from fundamentals.contracts.acquisition_outcome import ExtractionOutcome
from fundamentals.contracts.comparison import PairOutcome, ReasonCode, SourceRole, SourceState
from fundamentals.contracts.config_versions import ConfigVersions
from fundamentals.contracts.evidence import (
    AcquisitionAttempt,
    AttemptStage,
    Interpretation,
    InterpretationStatus,
    MissingValueState,
    Occurrence,
)
from fundamentals.contracts.measurement_key import PeriodInterval
from fundamentals.contracts.source_catalog import (
    SCREENER_INVESTORS,
    SCREENER_SHAREHOLDING,
    TIJORI_SHAREHOLDING,
    UPSTOX_SHAREHOLDING,
)
from fundamentals.entity.discovery import MANIFEST_NAME
from fundamentals.evidence.interpret import input_digest
from fundamentals.evidence.mapping_models import MappingAssumption
from fundamentals.evidence.repository import EvidenceRepository

APAR = "APARINDS"


VENDOR = (SCREENER_SHAREHOLDING, SCREENER_INVESTORS, TIJORI_SHAREHOLDING, UPSTOX_SHAREHOLDING)
# d8-probe.md §13.4 node counts per company; Screener as (nodes, drill-down holders).
SCREENER_TREE = {"APARINDS": (120, 109), "ETERNAL": (109, 97), "TITAN": (865, 851)}
TIJORI_TREE = {"APARINDS": 29, "ETERNAL": 21, "TITAN": 35}
CUSTODIANS_DR = "SharesheldbyCustodians-DR"  # Tijori myid; a dash in every column (§13.4)
# The existing vendor extractor pins, computed at HEAD 2e22dec before Task 6.
EXISTING_PINS = {
    ("screener-subscriber", "SCREENER_FINANCIALS"): (
        "screener-v1",
        "9ffad9ac400ba8913edf7bdc69151ce24448ed53311ee4d9c7e82f64d90b15a0",
    ),
    ("tijori", "financials"): (
        "tijori-v4",
        "f7f3689c338667cae8a99adcc2ba4bf0fade9294a3ccea690c3b63c57f099901",
    ),
    ("upstox", "income-statement"): (
        "upstox-v2",
        "351b2aed43565d6191d1afb5ffeeb568f9d03ede9cd55a41ba96b06611249478",
    ),
}
Evidence = list[tuple[AcquisitionAttempt, tuple[Occurrence, ...], dict[int | None, Interpretation]]]


def _vendor(db: PgTestDatabase, entity_id: int) -> Evidence:
    """Each vendor attempt at the instant, with its capture's occurrences and interpretations."""
    found: Evidence = []
    with db.runtime_pool() as pool:
        repository = EvidenceRepository(pool)
        for attempt in repository.list_attempts(entity_id, INSTANT):
            if (attempt.source_id, attempt.surface) not in VENDOR or attempt.capture is None:
                continue
            ref = attempt.capture.capture_ref_id
            assert ref is not None
            rows = {row.occurrence_id: row for row in repository.list_capture_interpretations(ref)}
            found.append((attempt, repository.list_capture_occurrences(ref), rows))
    return found


def _entries(root: Path, symbol: str) -> list[dict[str, Any]]:
    return list(json.loads((root / symbol / GEN / MANIFEST_NAME).read_bytes())["entries"])


def _node(occurrence: Occurrence) -> tuple[Any, ...]:
    context = occurrence.native_context
    return tuple(context["path"]), context["source_node_id"], context["periodicity"]


def _offered(raw: dict[str, Any]) -> list[str]:
    return [key for key in raw if key != "setAttributes"]


@pytest.mark.pg
@pytest.mark.retained
def test_tree_every_node_and_printed_cell_is_one_occurrence(
    ingested: tuple[PgTestDatabase, Path, dict[str, int]],
) -> None:
    """Owner amendment (R11): over gen-2 every vendor node has one node occurrence and one cell
    occurrence per printed cell, with label, parent, path, depth and periodicity. The inventory
    equals §13.4 and the retained bodies: Tijori's custodians row keeps its dashes, a holder
    lacking a period has no cell for it, Apar's empty bucket has no holder, and no value is a
    zero that was not printed."""
    db, _, entities = ingested
    late_holder = False
    for symbol, entity_id in entities.items():
        bodies = {e["sha256"]: e for e in _entries(RAW, symbol) if e["filename"]}
        nodes: dict[str, list[dict[str, Any]]] = {"screener-subscriber": [], "tijori": []}
        empty = 0
        for attempt, occurrences, rows in _vendor(db, entity_id):
            assert attempt.outcome is ExtractionOutcome.COMPLETE and attempt.capture is not None
            entry = bodies[attempt.capture.blob_sha256]
            body = (RAW / symbol / GEN / entry["filename"]).read_bytes()
            heads: dict[tuple[Any, ...], dict[str, Any]] = {}
            cells: dict[tuple[Any, ...], list[str]] = {}
            for occurrence in occurrences:
                row, context = rows[occurrence.occurrence_id], occurrence.native_context
                path = context["path"]
                assert context["label"] == path[-1] and context["depth"] == len(path)
                assert context["parent"] == (path[-2] if len(path) > 1 else None)
                if context["kind"] == "NODE":
                    assert occurrence.raw_value_text is None and row.key is None
                    assert row.status is InterpretationStatus.UNMAPPED
                    assert _node(occurrence) not in heads
                    heads[_node(occurrence)] = context
                else:
                    cells.setdefault(_node(occurrence), []).append(context["period_label"])
                if row.value == 0:
                    assert occurrence.missing_state is MissingValueState.ZERO_PRINTED
                    assert Decimal(str(occurrence.raw_value_text).rstrip("%")) == 0
                if occurrence.missing_state is not MissingValueState.VALUE:
                    assert row.value in (None, 0)
            assert set(cells) <= set(heads)
            assert all(cells.get(key, []) == head["periods"] for key, head in heads.items())
            if attempt.source_id == "upstox":
                assert {h["label"]: h["periods"] for h in heads.values()} == {
                    item["category"]: [point["period"] for point in item["history"]]
                    for item in json.loads(body)["data"]
                }
                continue
            nodes[attempt.source_id].extend(heads.values())
            if attempt.surface == SCREENER_INVESTORS[1]:
                holders = json.loads(body)
                assert {h["label"]: h["periods"] for h in heads.values()} == {
                    name: _offered(values) for name, values in holders.items()
                }
                empty += not holders
                late_holder |= any(
                    h["periodicity"] == "quarterly" and "Jun 2026" not in h["periods"]
                    for h in heads.values()
                )
            elif attempt.surface == SCREENER_SHAREHOLDING[1]:
                root = html.fromstring(body)
                for periodicity in ("quarterly", "yearly"):
                    table = root.xpath(f"//div[@id='{periodicity}-shp']//table")[0]
                    labels = [th.text_content().strip() for th in table.xpath(".//thead//th")[1:]]
                    page = [h for h in heads.values() if h["periodicity"] == periodicity]
                    assert len(page) == len(table.xpath(".//tbody/tr[td]"))
                    assert all(h["periods"] == labels for h in page)
            else:
                rows_html = html.fromstring(body).xpath(
                    "//table[@id='company_detailed']//tr[@myid]"
                )
                assert len(heads) == len(rows_html) == TIJORI_TREE[symbol]
                (dr,) = [key for key in heads if key[1] == CUSTODIANS_DR]
                dashes = [
                    o for o in occurrences if _node(o) == dr and o.native_context["kind"] == "CELL"
                ]
                assert dashes and all(o.missing_state is MissingValueState.DASH for o in dashes)
                assert {o.raw_value_text for o in dashes} == {"—"}
        screener = nodes["screener-subscriber"]
        holders = [node for node in screener if node["depth"] == 2]
        assert (len(screener), len(holders)) == SCREENER_TREE[symbol]
        if symbol == APAR:  # quarterly ``public`` and yearly ``government`` are ``{}`` (§13.4)
            assert empty == 2
            quarterly = [n for n in screener if n["periodicity"] == "quarterly"]
            assert any(n["path"] == ["Public"] for n in quarterly)
            assert not any(n["parent"] == "Public" for n in quarterly)
    assert late_holder


@pytest.mark.pg
@pytest.mark.retained
def test_tree_cells_land_at_v7_keys_and_off_quarter_months_are_ambiguous(
    ingested: tuple[PgTestDatabase, Path, dict[str, int]],
) -> None:
    """A ruled quarterly cell is keyed at its v7 category, the assumed denominator and the share
    class, with the assumption traced; the yearly row is a diagnostic; Apar's ``Aug 2026``
    column (Upstox, d8-probe.md §6) is ``PERIOD_AMBIGUOUS`` and keyless."""
    db, _, entities = ingested
    cells = {
        (attempt.surface, *_node(o)[0::2], o.native_context["period_label"]): rows[o.occurrence_id]
        for attempt, occurrences, rows in _vendor(db, entities[APAR])
        for o in occurrences
        if o.native_context["kind"] == "CELL"
    }
    members = {
        "shareholding_category": "sebi_promoter_group",
        "denominator": "TOTAL_SHARES",
        "share_class": COMPANIES[APAR][0],
    }
    for surface, label in (("SCREENER_SHAREHOLDING", "Promoters"), ("share-holdings", "promoters")):
        june = cells[(surface, (label,), "quarterly", "Jun 2026")]
        assert june.key is not None and june.period == PeriodInterval.at(INSTANT)
        assert dict(june.key.dimensions.pairs) == members
        assert june.transform_trace["assumptions"] == ["DENOMINATOR_ASSUMED"]
    yearly = cells[("SCREENER_SHAREHOLDING", ("Promoters",), "yearly", "Mar 2026")]
    assert yearly.status is InterpretationStatus.UNMAPPED and yearly.key is None
    august = cells[("share-holdings", ("promoters",), "quarterly", "Aug 2026")]
    assert august.status is InterpretationStatus.PERIOD_AMBIGUOUS and august.key is None
    assert august.canonical_id == "shp_holding_pct"


@pytest.mark.pg
@pytest.mark.retained
def test_tree_a_deeper_drilldown_level_is_unsupported_schema(
    guarded: PgTestDatabase, tmp_path: Path
) -> None:
    """A drill-down holder carrying ``isExpandable`` is an unread level: the body is refused
    ``UNSUPPORTED_SCHEMA`` with no occurrence, never read short (R11 Depth)."""
    entity_id = _seed(guarded, APAR)
    (bucket,) = [e for e in _entries(RAW, APAR) if e["url"].endswith("/promoters/quarterly/")]

    def edit(folder: Path, entries: list[dict[str, Any]]) -> None:
        path = folder / bucket["filename"]
        path.write_bytes(path.read_bytes().replace(b'": {"', b'": {"isExpandable": true, "', 1))

    assert _ingest(_marked(tmp_path / "raw", APAR, edit), tmp_path / "snapshots", APAR) == 0
    evidence = _vendor(guarded, entity_id)
    refused = [(a, o) for a, o, _ in evidence if a.outcome is not ExtractionOutcome.COMPLETE]
    ((attempt, occurrences),) = refused
    assert (attempt.source_id, attempt.surface) == SCREENER_INVESTORS
    assert attempt.outcome is ExtractionOutcome.UNSUPPORTED_SCHEMA
    assert attempt.reason is not None and "isExpandable" in attempt.reason
    assert occurrences == ()


@pytest.mark.pg
@pytest.mark.retained
def test_pins_existing_vendor_extractors_are_unchanged_and_tree_sources_are_pinned(
    guarded: PgTestDatabase, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The ``screener-v1``, ``tijori-v4`` and ``upstox-v2`` pins equal HEAD's. The tree surfaces
    pin their own versions, and one changed byte in the tree extractor under its pinned version
    is drift, refused before any vendor evidence is written."""
    for pair, pinned in EXISTING_PINS.items():
        pin = vendor_extractor_pin(*pair)
        assert (pin.version, pin.content_sha256) == pinned
    versions = {pair: vendor_extractor_pin(*pair).version for pair in VENDOR}
    assert set(versions.values()) == {"screener-shp-v1", "tijori-shp-v1", "upstox-shp-v1"}
    _seed(guarded, APAR)
    snapshots = tmp_path / "snapshots"
    assert _ingest(RAW, snapshots, APAR) == 0
    source = tmp_path / "src"
    shutil.copytree(run_config._SOURCE_ROOT, source, ignore=shutil.ignore_patterns("__pycache__"))
    extractor = source / "evidence" / "vendor_shareholding.py"
    extractor.write_bytes(extractor.read_bytes() + b"\n")
    monkeypatch.setattr(run_config, "_SOURCE_ROOT", source)
    before = {table: count(guarded, table) for table in EVIDENCE_TABLES}
    assert _ingest(RAW, snapshots, APAR) != 0
    assert {table: count(guarded, table) for table in EVIDENCE_TABLES} == before
    for pair, pinned in EXISTING_PINS.items():
        pin = vendor_extractor_pin(*pair)
        assert (pin.version, pin.content_sha256) == pinned


def _fail_first(pair: tuple[str, str]) -> Any:
    """The first request on ``pair`` answered HTTP 503 with no body; a failed Screener page
    offers no drill-down, so its bucket requests are not made."""

    def edit(folder: Path, entries: list[dict[str, Any]]) -> None:
        entry = next(e for e in entries if (e["source_id"], e["surface"]) == pair)
        (folder / entry["filename"]).unlink()
        entry.update(outcome="HTTP_503", filename=None, sha256=None, bytes=None)
        if pair == SCREENER_SHAREHOLDING:
            entries[:] = [
                e for e in entries if (e["source_id"], e["surface"]) != SCREENER_INVESTORS
            ]

    return edit


@pytest.mark.pg
@pytest.mark.retained
@pytest.mark.parametrize(
    "pair", [SCREENER_SHAREHOLDING, SCREENER_INVESTORS, UPSTOX_SHAREHOLDING], ids=lambda p: p[1]
)
def test_vendor_failed_request_is_its_attempt(
    guarded: PgTestDatabase, tmp_path: Path, pair: tuple[str, str]
) -> None:
    """R8: after a complete generation, a later one whose Screener page, drill-down or Upstox
    request failed records that request as one capture-less attempt; ingest still succeeds and
    the earlier evidence is untouched (its run consequences are Task 6's run half)."""
    entity_id = _seed(guarded, APAR)
    snapshots = tmp_path / "snapshots"
    assert _ingest(RAW, snapshots, APAR) == 0
    before = _vendor(guarded, entity_id)
    raw = _marked(tmp_path / "raw", APAR, _fail_first(pair))
    (entry,) = [e for e in _entries(raw, APAR) if e["outcome"] != "OK"]
    assert _ingest(raw, snapshots, APAR) == 0
    with guarded.runtime_pool() as pool:
        attempts = EvidenceRepository(pool).list_attempts(entity_id, INSTANT)
    (failed,) = [a for a in attempts if a.capture is None]
    identity = {"source_id": pair[0], "surface": pair[1], "request_key": entry["request_key"]}
    assert (failed.stage, failed.source_id, failed.surface) == (AttemptStage.ACQUISITION, *pair)
    assert failed.outcome is ExtractionOutcome.FAILED and failed.period_end == INSTANT
    assert failed.reason is not None and entry["request_key"] in failed.reason
    assert failed.input_sha256 == input_digest({**identity, "capture_id": None})
    assert _vendor(guarded, entity_id) == before


# --- Task 6b: pairing, diagnostics and the R12 point check ------------------------------------

CATEGORY = "shareholding_category"
D = ASSUMPTION_LABELS[MappingAssumption.DENOMINATOR_ASSUMED]
BD = ASSUMPTION_LABELS[MappingAssumption.BOUNDARY_ASSUMED]
SCREENER, TIJORI, UPSTOX = (
    "/".join(pair) for pair in (SCREENER_SHAREHOLDING, TIJORI_SHAREHOLDING, UPSTOX_SHAREHOLDING)
)
RESIDUALS = {  # each vendor residual label's one ruled key (d8-probe.md §13.5 S5, T4, U3)
    "screener.shp.public": "non_institutions",
    "tijori.shp.public_shareholding": "public_shareholding_plus_employee_benefit_trust",
    "upstox.shp.retail_and_other": "non_institutions_plus_employee_benefit_trust",
}
DII_SUBCATEGORIES = {"dii", "mutual_funds", "other_dii", "insurance"}
MARKED = ConfigVersions(dictionary="v3", mapping_set="v99", normalisation_policy="v2")


def _vendor_run(symbol: str, *extra: str, vendors: tuple[Any, ...] = VENDOR) -> tuple[int, int]:
    """``compare run`` of one company's instant with the vendor surfaces: exit code, run id."""
    scope = ("--entity", symbol, "--period-end", INSTANT.isoformat(), "--basis", "standalone")
    named = [arg for pair in vendors for arg in ("--vendor", "/".join(pair))]
    code, out = _compare("run", *scope, *SHP_ARGS, *named, *extra)
    assert code != RunExitStatus.FAILURE, out
    return code, int(out.split("\n")[0].split("\t")[1])


@pytest.fixture(scope="module")
def runs(ingested: tuple[PgTestDatabase, Path, dict[str, int]]) -> dict[str, int]:
    """Each company's shareholding run with all four vendor surfaces."""
    return {symbol: _vendor_run(symbol)[1] for symbol in COMPANIES}


def _results(db: PgTestDatabase, run_id: int) -> tuple[ResultRow, ...]:
    with db.runtime_pool() as pool:
        return load_results(run_id, pool=pool)


def _status(db: PgTestDatabase, run_id: int) -> RunStatus:
    with db.runtime_pool() as pool:
        return RunStore(pool).read_manifest(run_id).status


def _readings(db: PgTestDatabase, rows: tuple[ResultRow, ...]) -> dict[int | None, Interpretation]:
    """Every interpretation a row's side names, by id."""
    ids = sorted({v.interpretation_id for r in rows for v in r.source_values} - {None})
    with db.runtime_pool() as pool:
        return {i.interpretation_id: i for i in EvidenceRepository(pool).get_interpretations(ids)}


def _printed(run_id: int, root: Path = CONFIG_ROOT) -> list[str]:
    """``compare report``'s lines for a run."""
    code, out = _compare("report", "--run", str(run_id), "--config-root", str(root))
    assert code == RunExitStatus.SUCCESS, out
    return out.splitlines()


def _marked_config(root: Path, edits: dict[str, dict[str, Any] | None]) -> Path:
    """A config copy whose mapping set v99 is v7 with entries changed (``None``: dropped)."""
    shutil.copytree(CONFIG_ROOT, root)
    maps = root / "mappings"
    index = yaml.safe_load((maps / "v7.yaml").read_text(encoding="utf-8"))
    files = []
    for name in index["entry_files"]:
        doc = yaml.safe_load((maps / name).read_text(encoding="utf-8"))
        if any(entry["entry_id"] in edits for entry in doc["entries"]):
            doc["entries"] = [
                {**entry, **(edits.get(entry["entry_id"]) or {})}
                for entry in doc["entries"]
                if edits.get(entry["entry_id"], {}) is not None
            ]
            name = str(Path(name).parent.parent / "v99" / Path(name).name)
            (maps / name).parent.mkdir(parents=True, exist_ok=True)
            (maps / name).write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
        files.append(name)
    index.update(version="v99", entry_files=files)
    (maps / "v99.yaml").write_text(yaml.safe_dump(index, sort_keys=False), encoding="utf-8")
    return root


def _ingest_marked(
    monkeypatch: pytest.MonkeyPatch, root: Path, snapshots: Path, symbol: str
) -> tuple[int, int]:
    """Ingest gen-2 under the marked mapping set v99, then run it: exit code, run id."""
    monkeypatch.setattr(shareholding_cli, "SHAREHOLDING_VERSIONS", MARKED)
    argv = ["shareholding", "ingest", "--symbol", symbol, "--instant", INSTANT.isoformat()]
    argv += ["--raw-root", str(RAW), "--snapshot-root", str(snapshots), "--generation", "2"]
    assert main([*argv, "--config-root", str(root)]) == 0
    return _vendor_run(symbol, "--mapping-set", "v99", "--config-root", str(root))


@pytest.mark.pg
@pytest.mark.retained
def test_denominators_never_pair(
    runs: dict[str, int],
    ingested: tuple[PgTestDatabase, Path, dict[str, int]],
    guarded: PgTestDatabase,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A ``VOTING_RIGHTS`` key has no vendor side or pair even where its value equals the
    ``TOTAL_SHARES`` one; a marked set declaring Screener Promoters at ``VOTING_RIGHTS`` moves
    that side to the ``VOTING_RIGHTS`` key and the ``TOTAL_SHARES`` key loses it."""
    db = ingested[0]
    for run_id in runs.values():
        for row in _results(db, run_id):
            if dict(row.key.dimensions.pairs).get("denominator") == "VOTING_RIGHTS":
                vendor = [v for v in row.source_values if v.source_id is not None]
                assert {(v.state, v.interpretation_id) for v in vendor} == {
                    (SourceState.NO_VALUE, None)
                }
                assert row.pairs == ()
    voting = {
        "dimension_members": {CATEGORY: "sebi_promoter_group", "denominator": "VOTING_RIGHTS"}
    }
    root = _marked_config(tmp_path / "config", {"screener.shp.promoters": voting})
    _seed(guarded, APAR)
    _, run_id = _ingest_marked(monkeypatch, root, tmp_path / "snapshots", APAR)
    sides = {
        dict(row.key.dimensions.pairs)["denominator"]: {
            v.surface for v in row.source_values if v.interpretation_id is not None
        }
        for row in _results(guarded, run_id)
        if dict(row.key.dimensions.pairs).get(CATEGORY) == "sebi_promoter_group"
    }
    assert SCREENER_SHAREHOLDING[1] in sides["VOTING_RIGHTS"]
    assert SCREENER_SHAREHOLDING[1] not in sides["TOTAL_SHARES"]


@pytest.mark.pg
@pytest.mark.retained
def test_vendor_public_maps_only_to_its_aggregate(
    runs: dict[str, int], ingested: tuple[PgTestDatabase, Path, dict[str, int]]
) -> None:
    """Each vendor residual sits only at its ruled key; B (never ruled) has no vendor side; a
    refused label (Tijori custodians, LLP) is ``UNMAPPED`` and keyless."""
    db, _, entities = ingested
    for symbol, run_id in runs.items():
        rows = _results(db, run_id)
        readings = _readings(db, rows)
        placed: dict[str, set[str]] = {}
        for row in rows:
            for value in row.source_values:
                entry = (
                    readings[value.interpretation_id].mapping_entry_id
                    if value.interpretation_id
                    else None
                )
                if entry in RESIDUALS:
                    placed.setdefault(entry, set()).add(dict(row.key.dimensions.pairs)[CATEGORY])
                if dict(row.key.dimensions.pairs).get(CATEGORY) == "public_shareholding":
                    assert value.source_id is None or value.interpretation_id is None
        assert placed == {entry: {key} for entry, key in RESIDUALS.items()}
        refused = [
            rows_by_id[o.occurrence_id]
            for attempt, occurrences, rows_by_id in _vendor(db, entities[symbol])
            for o in occurrences
            if attempt.surface == TIJORI_SHAREHOLDING[1]
            and o.native_context["kind"] == "CELL"
            and o.native_context["label"] in ("Shares held by Custodians - DR", "LLP")
        ]
        assert refused and {(r.status, r.key) for r in refused} == {
            (InterpretationStatus.UNMAPPED, None)
        }


@pytest.mark.pg
@pytest.mark.retained
def test_no_dii_key_from_subcategories(
    runs: dict[str, int], ingested: tuple[PgTestDatabase, Path, dict[str, int]]
) -> None:
    """Upstox ``mutual_funds`` and ``other_dii`` stay ``UNMAPPED`` and keyless, and no key in any
    run carries a DII subcategory member (R5 DII — probe ruling)."""
    db, _, entities = ingested
    for symbol, run_id in runs.items():
        lines = [
            rows[o.occurrence_id]
            for attempt, occurrences, rows in _vendor(db, entities[symbol])
            for o in occurrences
            if attempt.surface == UPSTOX_SHAREHOLDING[1]
            and o.native_context["label"] in ("mutual_funds", "other_dii")
        ]
        assert lines and all(
            (r.status, r.key) == (InterpretationStatus.UNMAPPED, None) for r in lines
        )
        members = {dict(r.key.dimensions.pairs).get(CATEGORY) for r in _results(db, run_id)}
        assert not members & DII_SUBCATEGORIES


@pytest.mark.pg
@pytest.mark.retained
def test_upstox_is_diagnostic_and_vendor_pairs_not_comparable(
    runs: dict[str, int], ingested: tuple[PgTestDatabase, Path, dict[str, int]]
) -> None:
    """R10: every formed vendor pair is ``NOT_COMPARABLE / PRECISION_UNSUPPORTED``; Upstox is
    diagnostic, so dropping it changes no row status and not the run's."""
    db = ingested[0]
    for symbol, run_id in runs.items():
        rows = _results(db, run_id)
        upstox = [v for r in rows for v in r.source_values if v.surface == UPSTOX_SHAREHOLDING[1]]
        assert upstox and {v.source_role for v in upstox} == {SourceRole.DIAGNOSTIC}
        pairs = {(p.outcome, p.reason) for r in rows for p in r.pairs}
        assert pairs == {(PairOutcome.NOT_COMPARABLE, ReasonCode.PRECISION_UNSUPPORTED)}
        _, without = _vendor_run(symbol, vendors=VENDOR[:3])
        statuses = [
            [(r.row_id, r.corroboration_status, r.corroboration_reason) for r in _results(db, i)]
            for i in (run_id, without)
        ]
        assert statuses[0] == statuses[1]
        assert _status(db, run_id) is _status(db, without)


def _second_security(db: PgTestDatabase, symbol: str) -> None:
    """A marked second equity security of the issuer: an ISIN only, so identity still resolves
    but the share class at the instant does not."""
    with db.runtime_pool() as pool, pool.connection() as conn:
        conn.execute(
            "INSERT INTO eqos.securities (entity_id, isin, share_class, evidence_input_id) "
            "SELECT entity_id, %s, share_class, evidence_input_id FROM eqos.securities "
            "WHERE isin = %s",
            ("INE000M01099", COMPANIES[symbol][0]),
        )


@pytest.mark.pg
@pytest.mark.retained
def test_unresolved_share_class_is_keyless(guarded: PgTestDatabase, tmp_path: Path) -> None:
    """With a second equity security held at the instant no share class resolves: every vendor
    cell is keyless and the run has no vendor side or pair (R4 Share class)."""
    entity_id = _seed(guarded, APAR)
    _second_security(guarded, APAR)
    assert _ingest(RAW, tmp_path / "snapshots", APAR) == 0
    cells = [
        rows[o.occurrence_id]
        for _, occurrences, rows in _vendor(guarded, entity_id)
        for o in occurrences
        if o.native_context["kind"] == "CELL"
    ]
    assert cells and all(item.key is None for item in cells)
    rows = _results(guarded, _vendor_run(APAR)[1])
    vendor = [v for r in rows for v in r.source_values if v.source_id is not None]
    assert vendor and {(v.state, v.interpretation_id) for v in vendor} == {
        (SourceState.NO_VALUE, None)
    }
    assert all(r.pairs == () for r in rows)


@pytest.mark.pg
@pytest.mark.retained
@pytest.mark.parametrize(
    "pair", [SCREENER_SHAREHOLDING, SCREENER_INVESTORS, UPSTOX_SHAREHOLDING], ids=lambda p: p[1]
)
def test_vendor_failure_in_the_run(
    guarded: PgTestDatabase, tmp_path: Path, pair: tuple[str, str]
) -> None:
    """After a complete generation, a later failed Screener page decides its sides: no stale
    value, run ``INCOMPLETE``. A failed drill-down or Upstox request is a failed diagnostic
    attempt in the run's inputs and leaves the run status unchanged."""
    entity_id = _seed(guarded, APAR)
    snapshots = tmp_path / "snapshots"
    assert _ingest(RAW, snapshots, APAR) == 0
    before = _status(guarded, _vendor_run(APAR)[1])
    assert _ingest(_marked(tmp_path / "raw", APAR, _fail_first(pair)), snapshots, APAR) == 0
    with guarded.runtime_pool() as pool:
        attempts = EvidenceRepository(pool).list_attempts(entity_id, INSTANT)
    (failed,) = [a for a in attempts if a.capture is None]
    _, run_id = _vendor_run(APAR)
    with guarded.runtime_pool() as pool:
        manifest = RunStore(pool).read_manifest(run_id)
    assert (failed.attempt_id, "FAILED_ATTEMPT") in {
        (item.ref_id, item.disposition.value) for item in manifest.inputs
    }
    sides = [v for r in _results(guarded, run_id) for v in r.source_values if v.surface == pair[1]]
    if pair == SCREENER_INVESTORS:
        assert manifest.status is before
        return
    assert sides and all(
        (v.state, v.attempt_id, v.value) == (SourceState.UNAVAILABLE, failed.attempt_id, None)
        for v in sides
    )
    expected = RunStatus.INCOMPLETE if pair == SCREENER_SHAREHOLDING else before
    assert manifest.status is expected


@pytest.mark.pg
@pytest.mark.retained
def test_holders_are_unmapped_queue_items_of_their_bucket(
    runs: dict[str, int], ingested: tuple[PgTestDatabase, Path, dict[str, int]]
) -> None:
    """Owner amendment (R11): Screener holders from at least two buckets are ``UNMAPPED`` queue
    items bound to their bucket capture, in the stored run, its report and over replay."""
    db = ingested[0]
    run_id = runs[APAR]
    with db.runtime_pool() as pool:
        items = [
            item
            for item in read_overlay(pool, run_id=run_id, as_of=overlay_boundary(pool)).open_items
            if item.key is None and item.source_refs[0].surface == SCREENER_INVESTORS[1]
        ]
        repository = EvidenceRepository(pool)
        held = [
            repository.get_occurrences(item_inputs(pool, item.item_id)["occurrence_id"])
            for item in items
        ]
        frozen = replay_inputs(run_id, pool=pool, config_root=CONFIG_ROOT)
        replayed = route_run(
            frozen[0], replay_run(run_id, pool=pool, config_root=CONFIG_ROOT), frozen[1].pinned
        )
    buckets = set()
    for occurrences in held:
        assert len({o.capture.capture_ref_id for o in occurrences}) == 1
        assert {(o.capture.surface, o.native_context["depth"]) for o in occurrences} == {
            (SCREENER_INVESTORS[1], 2)
        }
        buckets |= {o.disclosure["bucket"] for o in occurrences}
    assert len(buckets) >= 2
    assert {
        d.pair_identity
        for d in replayed
        if d.source_refs and d.source_refs[0].surface == SCREENER_INVESTORS[1]
    } == {i.pair_identity for i in items}
    queued = [line for line in _printed(run_id) if line.startswith("queue\t")]
    assert sum("SCREENER_INVESTORS" in line for line in queued) == len(items)


@pytest.mark.pg
@pytest.mark.retained
def test_assumed_denominator_is_labelled(
    runs: dict[str, int], ingested: tuple[PgTestDatabase, Path, dict[str, int]]
) -> None:
    """R10: each Screener, Tijori and Upstox side at a ruled key traces ``DENOMINATOR_ASSUMED``
    and ``compare report`` prints the label on that side."""
    db = ingested[0]
    for run_id in runs.values():
        rows = _results(db, run_id)
        readings = _readings(db, rows)
        values = [v for r in rows for v in r.source_values if v.source_id and v.interpretation_id]
        assert {v.source_id for v in values} == {"screener-subscriber", "tijori", "upstox"}
        assert all(
            "DENOMINATOR_ASSUMED" in readings[v.interpretation_id].transform_trace["assumptions"]
            for v in values
        )
        printed = [line for line in _printed(run_id) if "interpretation=" in line]
        for value in values:
            (line,) = [x for x in printed if f"interpretation={value.interpretation_id}\t" in x]
            assert f"assumed={D}" in line
