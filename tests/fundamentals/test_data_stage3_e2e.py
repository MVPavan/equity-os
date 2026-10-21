"""D8.5: the data Stage 3 end-to-end (plan D8, Task 8).

Every step goes through the CLI on one fresh ``eqos_test_*`` database with the socket guard on:
the three gen-2 shareholding generations are ingested, and each company's shareholding run with
every vendor surface is compared with the frozen Stage 3 manifest. Vendor readings come from the
manifest's private companion at test time (hash-bound); none is written here. ``compare report``
must print every R12 point check with its labels, never as an error, beside the formal
``NOT_COMPARABLE / PRECISION_UNSUPPORTED`` outcome, and every unmappable node and holder as an
``UNMAPPED`` diagnostic.
"""

from __future__ import annotations

import contextlib
import copy
import hashlib
import io
from collections import Counter
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from pg_support import PgTestDatabase
from stage1_e2e_support import actual, diff, expected
from stage3_data_support import companion, entries
from test_frozen_manifests import DATA3, load
from test_shareholding_filing import COMPANIES, RAW, _seed
from test_shareholding_filing import guarded as guarded  # the fixture, re-exported

from fundamentals.api.cli import main
from fundamentals.compare.queue import item_inputs, overlay_boundary, read_overlay
from fundamentals.compare.report import ASSUMPTION_LABELS, NONE_TEXT
from fundamentals.compare.run import load_results
from fundamentals.contracts.canonical import Representation
from fundamentals.contracts.evidence import FilingFamily, FilingPackage, Interpretation
from fundamentals.contracts.measurement_key import MeasurementKey
from fundamentals.evidence.capture_intake import parse_filed_at
from fundamentals.evidence.interpret import TRACE_ASSUMPTIONS
from fundamentals.evidence.mapping_models import MappingAssumption
from fundamentals.evidence.repository import EvidenceRepository

pytestmark = [pytest.mark.pg, pytest.mark.retained]

MANIFEST = load(DATA3)
HEADER = MANIFEST["header"]
INSTANT = date.fromisoformat(HEADER["instant"])
TREE_NAMES = {"screener-subscriber": "screener", "tijori": "tijori", "upstox": "upstox"}
LABELS = {source["sha256"]: source["label"] for source in HEADER["sources"]}


def _cli(*argv: str) -> tuple[int, str]:
    """``fundamentals <argv>`` in process: its exit code and stdout."""
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = main(list(argv))
    return code, out.getvalue()


def _recorded(command: str, **slots: str) -> list[str]:
    """A header.cli command's argv (after ``fundamentals``), slots filled: run as recorded."""
    text = HEADER["cli"][command].replace("data/raw/shareholding", str(RAW))
    for slot, value in slots.items():
        text = text.replace(f"<{slot}>", value)
    return text.split()[1:]


def _labels(reading: Interpretation) -> list[str]:
    listed = reading.transform_trace.get(TRACE_ASSUMPTIONS) or []
    return [ASSUMPTION_LABELS[MappingAssumption(item)] for item in listed]


def _printed(side: dict[str, Any]) -> list[str]:
    """A printed vendor number's interval: half a unit of its last printed place either side."""
    exponent = Decimal(side["lex"].rstrip("%")).as_tuple().exponent
    half = Decimal(5).scaleb(int(exponent) - 1)
    return [str(Decimal(side["v"]) - half), str(Decimal(side["v"]) + half)]


def _package(package: FilingPackage, labels: dict[str, str] = LABELS) -> tuple[Any, ...]:
    """A stored package as the manifest records it: instance (its label in ``labels``), lineage,
    links and knowledge time (the listing's broadcast, ``at[2]`` in stage3_data_support.LISTED
    order)."""
    xbrl = package.members[Representation.XBRL].capture.blob_sha256
    links = [member.value.lower() for member in package.members]
    return labels[xbrl], package.supersedes_package_id, links, package.knowledge_time


def _key(key: MeasurementKey) -> str:
    """A key in the manifest's row-key notation (header.notation.row_key)."""
    dims = ",".join(f"{axis}={member}" for axis, member in key.dimensions.pairs) or "-"
    kind = "DERIVED" if key.canonical_id in HEADER["baskets"] else "REPORTED"
    return f"{key.canonical_id}|I|{dims}|{kind}"


def _tree(
    repository: EvidenceRepository, entity_id: int, symbol: str, vendor: dict[str, Any]
) -> tuple[dict[str, Any], dict[int, str]]:
    """Every stored vendor node rebuilt in the companion's shape (ruled key and labels from its
    cells' interpretations), and each vendor occurrence's companion node id."""
    files = {entry["sha256"]: entry["filename"] for entry in entries(symbol)}
    ids = {
        (name, node["periodicity"], tuple(node["path"]), node["source_node_id"]): node["id"]
        for name, nodes in _inventory(vendor, symbol).items()
        for node in nodes
    }
    built: dict[str, Any] = {}
    keys: dict[str, set[tuple[str, tuple[str, ...]]]] = {}
    where: dict[int, str] = {}
    for attempt in repository.list_attempts(entity_id, INSTANT):
        if attempt.source_id not in TREE_NAMES or attempt.capture is None:
            continue
        ref = attempt.capture.capture_ref_id
        assert ref is not None
        readings = {r.occurrence_id: r for r in repository.list_capture_interpretations(ref)}
        for occurrence in repository.list_capture_occurrences(ref):
            context, path = occurrence.native_context, tuple(occurrence.native_context["path"])
            name = TREE_NAMES[attempt.source_id]
            node_id = ids[(name, context["periodicity"], path, context["source_node_id"])]
            assert occurrence.occurrence_id is not None
            where[occurrence.occurrence_id] = node_id
            node = built.setdefault(node_id, {"id": node_id, "periods": {}})
            node |= {"file": files[occurrence.capture.blob_sha256], "path": list(path)}
            node |= {field: context[field] for field in ("label", "parent", "depth")}
            node |= {field: context[field] for field in ("periodicity", "source_node_id")}
            if context["kind"] == "CELL":
                node["periods"][context["period_label"]] = occurrence.raw_value_text
                reading = readings[occurrence.occurrence_id]
                if reading.key is not None:
                    ruled = (_key(reading.key), tuple(_labels(reading)))
                    keys.setdefault(node_id, set()).add(ruled)
    for node_id, node in built.items():
        ((key, labels),) = keys.get(node_id, {("UNMAPPED", ())})
        node |= {"key": key, "labels": list(labels)}
    return built, where


def _inventory(vendor: dict[str, Any], symbol: str) -> dict[str, list[dict[str, Any]]]:
    """The companion's tree; a node with no native id (a bucketless Screener row) is stored
    under its label, so the label stands in for the companion's null."""
    return {
        name: [node | {"source_node_id": node["source_node_id"] or node["label"]} for node in nodes]
        for name, nodes in vendor["tree"][symbol].items()
    }


def _keyless(
    pool: Any, repository: EvidenceRepository, items: list[Any], where: dict[int, str]
) -> dict[str, Any]:
    """The run's keyless items in the manifest's ``keyless`` shape (header.notation.keyless)."""
    facts: list[str] = []
    lines: dict[str, list[str]] = {}
    grouped: dict[str, Counter[str]] = {}
    for item in (item for item in items if item.key is None):
        assert item.outcome == "UNMAPPED", item
        found = repository.get_occurrences(item_inputs(pool, item.item_id)["occurrence_id"])
        for occurrence in found:
            assert occurrence.occurrence_id is not None
            if occurrence.representation is Representation.XBRL:
                context = occurrence.native_context
                facts.append(f"{context['local_name']}|{occurrence.anchor['context_ref']}")
                continue
            surface = f"{occurrence.capture.source_id}/{occurrence.capture.surface}"
            kind, node = occurrence.native_context["kind"], where[occurrence.occurrence_id]
            cell = "" if kind == "NODE" else f"|{occurrence.native_context['period_label']}"
            lines.setdefault(surface, []).append(f"{kind}|{node}{cell}")
        for kind in {o.native_context.get("kind") for o in found} - {None}:
            surface = f"{found[0].capture.source_id}/{found[0].capture.surface}"
            grouped.setdefault(surface, Counter())[kind] += 1
    vendors = {
        surface: {
            "node_items": grouped[surface]["NODE"],
            "cell_items": grouped[surface]["CELL"],
            "occurrences": len(occurrences),
            "sha256": hashlib.sha256("\n".join(sorted(occurrences)).encode()).hexdigest(),
        }
        for surface, occurrences in lines.items()
    }
    digest = hashlib.sha256("\n".join(sorted(facts)).encode()).hexdigest()
    return {"xbrl": {"facts": len(facts), "sha256": digest}, "vendors": vendors}


def _point(line: str) -> dict[str, Any]:
    """One ``point`` report line as its named fields, numbers as decimals."""
    _, verdict, source, *fields = line.split("\t")
    named: dict[str, Any] = dict(field.split("=", 1) for field in fields)
    members = {k: Decimal(v) for k, v in (m.split("=") for m in named["members"].split(","))}
    numbers = {name: Decimal(named[name]) for name in ("vendor", "first_party", "difference")}
    named |= numbers | {"members": members, "package": int(named["package"])}
    return {"verdict": verdict, "source": source} | named


def _want_point(
    check: dict[str, Any],
    reading: dict[str, Any],
    package: int | None,
    instant: str = HEADER["instant"],
) -> dict[str, Any]:
    """A manifest point check (vendor value from the companion) as a parsed report line."""
    cid, _, dims, _ = check["key"].split("|")
    point, vendor = Decimal(check["v"]), Decimal(reading["v"])
    members = {
        m["key"].split("=")[-1].split("|")[0]: Decimal(m["lex"]) * 100 for m in check["members"]
    }
    members |= dict.fromkeys(check["zero"], Decimal(0))
    return {
        "verdict": check["verdict"],
        "source": check["vendor"],
        "key": f"{cid}:{instant}:STANDALONE:{dims}",
        "vendor": vendor,
        "first_party": point,
        "difference": vendor - point,
        "members": members,
        "package": package,
        "outcome": (check["formal"] or NONE_TEXT).split("/")[0],
        "reason": NONE_TEXT,
        "labels": ";".join(check["labels"]),
    }


def test_stage3_end_to_end(guarded: PgTestDatabase, tmp_path: Path) -> None:
    vendor = companion(MANIFEST)  # fails on a fresh clone: the retained readings are absent
    entities = {symbol: _seed(guarded, symbol) for symbol in COMPANIES}
    for symbol in sorted(HEADER["filings"]):
        assert _cli(*_recorded("ingest", SYM=symbol, tmp=str(tmp_path / "s")))[0] == 0, symbol

    problems: list[str] = []
    for run in MANIFEST["runs"]:
        symbol, entity_id = run["entity"], entities[run["entity"]]
        code, out = _cli(*_recorded("run", KEY=symbol))
        run_id = int(out.split("\n")[0].split("\t")[1])
        with guarded.runtime_pool() as pool:
            repository = EvidenceRepository(pool)
            rows = load_results(run_id, pool=pool)
            items = list(read_overlay(pool, run_id=run_id, as_of=overlay_boundary(pool)).open_items)
            tree, where = _tree(repository, entity_id, symbol, vendor)
            keyless = _keyless(pool, repository, items, where)
            packages = repository.list_packages(entity_id, FilingFamily.SHAREHOLDING, INSTANT)
            ids = sorted({v.interpretation_id for r in rows for v in r.source_values} - {None})
            readings = {r.interpretation_id: r for r in repository.get_interpretations(ids)}

        # Rows: the manifest's, with each VALUE vendor side's value from the companion.
        rich = copy.deepcopy(run)
        for key, sides in vendor["sides"][run["run"]].items():
            for name, side in sides.items():
                rich["rows"][key]["vendors"][name] |= {"v": side["v"], "iv": _printed(side)}
        found = diff(expected(rich, entity_id, MANIFEST), actual(run, rows, items))
        problems += [f"{symbol} {line.split(':', 1)[0]}" for line in found]  # row key, field only
        # Each vendor side's node and assumption labels (R10, R12).
        bound = {
            _key(row.key): {
                f"{value.source_id}/{value.surface}": {
                    "at": {"node": where[readings[value.interpretation_id].occurrence_id]},
                    "labels": _labels(readings[value.interpretation_id]),
                }
                for value in row.source_values
                if value.source_id is not None and value.interpretation_id is not None
            }
            for row in rows
        }
        want_bound = {
            key: {
                name: {field: side[field] for field in ("at", "labels")}
                for name, side in row.get("vendors", {}).items()
                if "at" in side
            }
            for key, row in run["rows"].items()
        }
        assert bound == want_bound, symbol
        assert keyless == run["keyless"], symbol
        queue = Counter(item.severity.value + "_diagnostic" * item.diagnostic for item in items)
        assert (code, dict(queue)) == (run["exit"], run["counts"]["queue"]), symbol

        # The full tree inventory against the companion (owner amendment).
        inventory = {n["id"]: n for nodes in _inventory(vendor, symbol).values() for n in nodes}
        off = sorted(n for n in tree.keys() | inventory.keys() if tree.get(n) != inventory.get(n))
        assert not off, (symbol, off)  # node ids only

        # Packages and lineage; each links one XBRL representation, so extraction is
        # NOT_APPLICABLE (R3, the rows' ext status above).
        stored = MANIFEST["packages"][symbol]
        assert [_package(package) for package in packages] == [
            (x["instance"], x["lineage"], x["links"], parse_filed_at(x["at"][2]["lex"].title()))
            for x in stored["stored"]
        ], symbol
        selected = packages[stored["selected"]].package_id

        # compare report: every R12 point check with its labels, never an error (owner amendment).
        code, out = _cli(*_recorded("report", KEY=symbol))
        assert code == 0 and f"run\t{run_id}\n" in out and f"status\t{run['status']}" in out
        printed = [_point(line) for line in out.splitlines() if line.startswith("point\t")]
        checks = MANIFEST["point_checks"][run["run"]]
        want = [
            _want_point(check, reading, selected)
            for check, reading in zip(checks, vendor["point_checks"][run["run"]], strict=True)
        ]
        order = lambda line: (line["key"], line["source"])  # noqa: E731
        off = sorted({order(x) for x in printed + want if printed.count(x) != want.count(x)})
        assert not off, (symbol, off)  # point key and source only
        queued = [line.split("\t") for line in out.splitlines() if line.startswith("queue\t")]
        unmapped = [line for line in queued if line[3] == "UNMAPPED"]
        assert len(unmapped) == sum(item.key is None for item in items) and all(
            line[6] == f"key={NONE_TEXT}" for line in unmapped
        ), symbol
    assert not problems, "\n".join(problems)
