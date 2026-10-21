"""Data Stage 3 (plan D8 Task 7): the committed manifest and its private vendor companion against
the retained shareholding bytes. Imports no fundamentals code (R9): every section is rebuilt from
the bytes, the header's rulings and the shipped contracts' states (header.notation)."""

from __future__ import annotations

import copy
import hashlib
import json
from collections import Counter
from collections.abc import Callable
from decimal import Decimal
from fractions import Fraction
from functools import cache
from pathlib import Path
from typing import Any

import pymupdf
import yaml
from lxml import etree  # type: ignore[import-untyped]
from manifest_locators import shp_bucket, shp_table, tijori_html, upstox_shp

REPO = Path(__file__).resolve().parents[2]
RAW = REPO / "data/raw/shareholding"
XI, DI = "{http://www.xbrl.org/2003/instance}", "{http://xbrl.org/2006/xbrldi}"
SCR, UPX = "screener-subscriber/SCREENER_SHAREHOLDING", "upstox/share-holdings"
VENDORS = {"screener": SCR, "tijori": "tijori/shareholding", "upstox": UPX}
INVESTORS = "screener-subscriber/SCREENER_INVESTORS"
LISTED = ("recordId", "date", "broadcastDate", "submissionDate", "xbrl", "revisedData", "isin")
NC = {"out": "NOT_COMPARABLE", "why": "PRECISION_UNSUPPORTED", "diff": None, "gap": None}
REFUSED, QUEUED = {"s": "INVALID", "why": "PRECISION_UNSUPPORTED"}, ("a", "b", "out", "diag")
MED = {"sev": "MEDIUM"}
Z, P = "absent category taken as zero", "shp_holding_pct"
Doc = dict[str, Any]


def sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


@cache
def _read(path: str) -> tuple[str, Doc]:
    data = (REPO / path).read_bytes()
    return hashlib.sha256(data).hexdigest(), yaml.safe_load(data)


def companion(manifest: Doc) -> Doc:
    """The private vendor readings: a mutation's injected copy, else the file at its SHA-256."""
    digest, found = _read(manifest["header"]["companion"]["path"])
    assert "_vendor" in manifest or digest == manifest["header"]["companion"]["sha256"]
    return dict(manifest.get("_vendor", found))


@cache
def entries(sym: str) -> list[Doc]:
    return list(json.loads((RAW / sym / "gen-2/discovery-manifest.json").read_text())["entries"])


@cache
def facts(path: str) -> tuple[dict[tuple[str, str], tuple[str, ...]], dict[str, set[str]], Doc]:
    """(concept, ctx) -> (lex, unit, decimals); ctx -> its explicit members; typed ctx -> axis."""
    root = etree.parse(str(REPO / path)).getroot()
    members, typed, found = {}, {}, {}
    for ctx in root.iter(f"{XI}context"):
        explicit = ctx.iter(f"{DI}explicitMember")
        members[ctx.get("id")] = {(m.text or "").strip().split(":")[-1] for m in explicit}
        for m in ctx.iter(f"{DI}typedMember"):
            typed[ctx.get("id")] = m.get("dimension").split(":")[-1]
    for el in (el for el in root if isinstance(el.tag, str) and el.get("contextRef")):
        key = (etree.QName(el).localname, el.get("contextRef"))
        assert key not in found, key
        found[key] = ((el.text or "").strip(), el.get("unitRef"), el.get("decimals"))
    return found, members, typed


@cache
def tree(sym: str) -> dict[str, list[Doc]]:
    """Every vendor node of the gen-2 capture (R11), document order: each Screener tab's rows,
    each followed by its drill-down holders; the Tijori tree; the Upstox categories."""
    files = {e["surface"]: RAW / sym / "gen-2" / e["filename"] for e in entries(sym)}
    drill = [e for e in entries(sym) if e["surface"] == "SCREENER_INVESTORS"]
    buckets = {
        tuple(e["url"].split("/")[-3:-1]): RAW / sym / "gen-2" / e["filename"] for e in drill
    }
    nodes: dict[str, list[Doc]] = {name: [] for name in VENDORS}

    def add(vendor: str, file: Path, how: str, path: list[str], native: Any, cells: Any) -> None:
        node = {"id": f"{sym}/{vendor}/{len(nodes[vendor])}", "file": file.name, "periodicity": how}
        node |= {"depth": len(path), "label": path[-1], "parent": ([None] + path)[-2], "path": path}
        nodes[vendor].append(node | {"source_node_id": native, "periods": dict(cells)})

    page, used = files["SCREENER_SHAREHOLDING"], []
    for how in ("quarterly", "yearly"):
        heads, rows = shp_table(page, f"{how}-shp")
        for label, bucket, cells in rows:
            add("screener", page, how, [label], bucket, zip(heads, cells, strict=True))
            if bucket:
                used.append(file := buckets[bucket, how])
                for holder, periods in shp_bucket(file).items():
                    add("screener", file, how, [label, holder], holder, periods)
    assert sorted(used) == sorted(buckets.values()), sym
    heads, tijori = tijori_html(files["shareholding"])
    paths: dict[str, list[str]] = {"1": []}
    for level, myid, parent, (label, *cells) in tijori:
        paths[myid] = [*paths[parent], label]
        assert len(paths[myid]) == level, (sym, myid)
        cells_at = zip(heads, cells, strict=True)
        add("tijori", files["shareholding"], "quarterly", paths[myid], myid, cells_at)
    for category, periods in upstox_shp(files["share-holdings"]):
        add("upstox", files["share-holdings"], "quarterly", [category], category, periods)
    return nodes


def number(lex: str) -> Decimal | None:
    """A printed vendor percentage ('%' and grouping dropped); None for a marker such as a dash."""
    text = lex.replace(",", "").removesuffix("%")
    return Decimal(text) if text.replace(".", "", 1).isdigit() else None


def counts(nodes: list[Doc], vendor: str, class_named: list[str]) -> dict[str, int]:
    cells = [v for node in nodes for v in node["periods"].values()]
    deep = {"screener": 2, "tijori": 3}.get(vendor)
    holders = [n for n in nodes if n["depth"] == deep and n["label"] not in class_named]
    found = {"nodes": len(nodes), "holders": len(holders), "cells": len(cells)}
    markers = [number(v) for v in cells].count(None)
    return found | {"markers": markers, "depth": max(len(n["path"]) for n in nodes)}


def row_key(cid: str, den: str, isin: str, member: str, kind: str = "REPORTED") -> str:
    return f"{cid}|I|denominator={den},share_class={isin},shareholding_category={member}|{kind}"


def package(header: Doc, sym: str) -> Doc:
    """The listing rows at the shareholding date, bound by URL to their instances; one selected."""
    gen = f"data/raw/shareholding/{sym}/gen-2"
    labels = {s["path"]: s["label"] for s in header["sources"]}
    urls = {e["url"]: labels[f"{gen}/{e['filename']}"] for e in entries(sym)}
    src = labels[f"{gen}/01.bin"]
    stored = []
    for i, row in enumerate(json.loads((REPO / gen / "01.bin").read_bytes())):
        at = [{"src": src, "path": f"[{i}].{field}", "lex": str(row[field])} for field in LISTED]
        links = [field for field, value in row.items() if str(value).startswith("http")]
        if row["date"] == header["listing_date"]:
            stored += [{"instance": urls[row["xbrl"]], "lineage": None, "links": links, "at": at}]
    assert len(stored) == 1, sym  # one original submission each: no selection rule is exercised
    return {"stored": stored, "selected": 0}


def expected(header: Doc, vendor: Doc, sym: str) -> tuple[Doc, ...]:
    """One company as the shipped contracts emit it (header.notation): its package, run, holder
    lists, R12 point checks and the companion's VALUE-side and point-check readings."""
    selected, nodes, instant = package(header, sym), vendor["tree"][sym], header["instant"]
    label = selected["stored"][selected["selected"]]["instance"]
    (path,) = [s["path"] for s in header["sources"] if s["label"] == label]
    found, members, typed = facts(path)
    (isin,) = [lex for (concept, _), (lex, *_) in found.items() if concept == "ISIN"]
    rows: dict[str, Doc] = {}
    for (concept, ctx), (lex, unit, decimals) in sorted(found.items()):
        (member,) = members[ctx] if len(members[ctx]) == 1 and ctx not in typed else [None]
        category, *dens = header["members"].get(member, [None])
        if (den := header["denominators"].get(concept)) in dens:
            loc = {"src": label, "c": concept, "ctx": ctx, "u": unit, "d": decimals, "lex": lex}
            loc |= {"per": instant, "dims": [f"CategoryOfShareholdersAxis={member}"]}
            rows[row_key(P, den, isin, category)] = {"xbrl": REFUSED | {"at": [loc]}}
    for den in sorted({key.split(",")[0].split("=")[1] for key in rows}):
        for cid, (out, operands) in header["baskets"].items():
            filed = [k for m in operands if (k := row_key(P, den, isin, m)) in rows]
            assert filed, (cid, den)  # a basket with no filed operand would be OPERAND_MISSING
            calc = REFUSED | {"calc": "OPERAND_INVALID", "operands": filed}
            rows[row_key(cid, den, isin, out, "DERIVED")] = {"xbrl": calc}
    rows |= {f"{cid}|I|-|REPORTED": {"xbrl": {"s": "NO_VALUE"}} for cid in header["scalars"]}
    ruled: dict[tuple[str, str], Doc] = {}
    for name, listed in nodes.items():
        for node in (x for x in listed if x["key"] != "UNMAPPED"):
            assert (node["key"], VENDORS[name]) not in ruled, node["id"]
            lex = node["periods"].get(vendor["instant_columns"][name], "")
            ruled[node["key"], VENDORS[name]] = node | {"lex": lex}
    sides: Doc = {}
    for key, row in rows.items():
        vendors = {}
        for name in header["tables"].get(key.split("|")[0], []):
            node = ruled.get((key, name), {"lex": ""})
            value = number(node["lex"])
            state = "NO_VALUE" if value is None else "VALUE" if name != UPX else "INVALID"
            bound = {"at": {"node": node["id"]}, "labels": node["labels"]} if "id" in node else {}
            vendors[name] = (REFUSED if state == "INVALID" else {"s": state}) | bound
            if state == "VALUE":
                sides.setdefault(key, {})[name] = {"lex": node["lex"], "v": str(value)}
        valued = [name for name, side in vendors.items() if side["s"] != "NO_VALUE"]
        ends = [("xbrl", b) for b in valued if row["xbrl"]["s"] != "NO_VALUE"]
        ends += [(SCR, UPX)] * ({SCR, UPX} <= {*valued})
        pairs = [{"a": a, "b": b} | NC | ({"diag": True} if b == UPX else {}) for a, b in ends]
        queue = [{"on": "pair"} | MED | {k: p[k] for k in QUEUED if k in p} for p in pairs]
        invalid = row["xbrl"]["s"] == "INVALID"
        cor = {"status": "NOT_COMPARABLE", "why": NC["why"]} if invalid else {"status": "NO_SOURCE"}
        # a corroboration route, unless a pair already carries its NOT_COMPARABLE
        queue += [{"on": "corroboration", "out": cor["status"]} | MED] * (not (invalid and pairs))
        row |= {"vendors": vendors, "pairs": pairs, "queue": queue}
        row |= {"ext": {"status": "NOT_APPLICABLE"}, "cor": cor}
    lines, readings = [], []
    for (key, name), node in ruled.items():
        if (printed := number(node["lex"])) is None:
            continue
        cid, _, dims, _ = key.split("|")
        den, _, category = (d.split("=")[1] for d in dims.split(","))
        operands = header["baskets"].get(cid, [0, [category]])[1]
        keys = [row_key(P, den, isin, m) for m in operands]
        present = [{"key": k, "lex": rows[k]["xbrl"]["at"][0]["lex"]} for k in keys if k in rows]
        zero = [m for m, k in zip(operands, keys, strict=True) if k not in rows]
        borne = {d for m in zero for d in header["descendants"][m]} & set().union(*members.values())
        assert not borne, (node["id"], "a zero member is filed")
        lexes = [p["lex"] for p in present] + ["0"] * len(zero)
        point = sum(map(Fraction, lexes), Fraction(0)) * 100
        exact = Decimal(point.numerator) / point.denominator
        equal = round(exact, -int(printed.as_tuple().exponent)) == printed
        verdict = "POINT_EQUAL" if equal else "POINT_CHECK"
        line = {"key": key, "vendor": name, "at": {"node": node["id"]}, "members": present}
        line |= {"zero": zero, "expr": f"({' + '.join(lexes)}) * 100"}
        line |= {"v": f"{exact.normalize():f}", "verdict": verdict}
        formal = "NOT_COMPARABLE/PRECISION_UNSUPPORTED" if key in rows else None
        lines.append(line | {"labels": node["labels"] + [Z] * bool(zero), "formal": formal})
        readings.append({"lex": node["lex"], "v": str(printed)})
    located = {(at["c"], at["ctx"]) for r in rows.values() for at in r["xbrl"].get("at", [])}
    rest = sorted(f"{c}|{x}" for c, x in found.keys() - located)
    keyless: Doc = {"xbrl": {"facts": len(rest), "sha256": sha("\n".join(rest))}, "vendors": {}}
    groups: dict[str, list[str]] = {surface: [] for surface in [INVESTORS, *VENDORS.values()]}
    for name, listed in nodes.items():
        for n in listed:  # a node occurrence never maps, nor does an UNMAPPED node's cell
            cells = [f"CELL|{n['id']}|{p}" for p in n["periods"]] * (n["key"] == "UNMAPPED")
            surface = INVESTORS if name == "screener" and n["depth"] == 2 else VENDORS[name]
            groups[surface] += [f"NODE|{n['id']}", *cells]
    queue = Counter({"LOW": len(rest)})
    for surface, occurrences in groups.items():
        items = Counter(o.split("|")[0] for o in {"|".join(o.split("|")[:2]) for o in occurrences})
        entry = {"node_items": items["NODE"], "cell_items": items["CELL"]}
        entry |= {"occurrences": len(occurrences), "sha256": sha("\n".join(sorted(occurrences)))}
        keyless["vendors"][surface] = entry
        queue["LOW" + "_diagnostic" * (surface == UPX)] += items.total()
    queue.update(
        q["sev"] + "_diagnostic" * ("diag" in q) for r in rows.values() for q in r["queue"]
    )
    exclusions = header["exclusions"] + [
        f"{P} {category} at {den}: no such percentage fact in the filing"
        for category, *dens in header["members"].values()
        for den in dens
        if row_key(P, den, isin, category) not in rows
    ]
    run = {"run": f"{sym}-SHP-{instant}", "entity": sym, "instant": instant}
    run |= {"keys": {"I": {"instant": instant}}, "source_vector": header["source_vector"]}
    run |= {"defaults": {}, "default_rows": {}, "rows": rows, "keyless": keyless}
    run |= {"exclusions": exclusions, "counts": {"queue": dict(+queue)}}
    run |= {"status": "COMPLETE", "exit": 0}
    rules, filing, screener, tijori = header["holder_rules"], [], [], []
    names = {ctx for concept, ctx in found if concept == "NameOfTheShareholder"}
    for axis in sorted({*typed.values()}):
        held = sum(typed[ctx] == axis for ctx in names & typed.keys())
        kind = rules["filing"].get(axis, "OTHER")
        filing.append({"axis": axis, "holders": held} | rules["classes"][kind])
    for page in (n for n in nodes["screener"] if n["depth"] == 1 and n["source_node_id"]):
        url = f"/{page['source_node_id']}/{page['periodicity']}/"
        (file,) = [e["filename"] for e in entries(sym) if e["url"].endswith(url)]
        kids = [n for n in nodes["screener"] if n["file"] == file]
        over = all((number(v) or 0) > 1 for k in kids for v in k["periods"].values())
        entry = {"node": page["id"], "file": file, "holders": len(kids)}
        screener.append(entry | rules["classes"]["SCREENER_OVER_1" if over else "SCREENER_UNMET"])
    for parent in (n for n in nodes["tijori"] if n["depth"] == 2):
        kids = [n for n in nodes["tijori"] if n["path"][:2] == parent["path"] and n["depth"] == 3]
        if kids := [n for n in kids if n["label"] not in vendor["class_named"]]:
            tijori.append({"node": parent["id"], "holders": len(kids)} | rules["classes"]["TIJORI"])
    holders = {"filing": filing, "screener": screener, "tijori": tijori}
    return selected, run, holders, lines, sides, readings


def sections(header: Doc, vendor: Doc) -> Doc:
    """Every company's expected sections, keyed as the manifest (readings: the companion) keys."""
    out: Doc = {name: {} for name in ("packages", "holders", "point_checks", "sides", "readings")}
    out["runs"] = []
    for sym in sorted(header["filings"]):
        selected, run, holders, lines, sides, readings = expected(header, vendor, sym)
        out["runs"].append(run)
        out["packages"][sym], out["holders"][sym] = selected, holders
        out["point_checks"][run["run"]], out["sides"][run["run"]] = lines, sides
        out["readings"][run["run"]] = readings
    return out


def check_classes(manifest: Doc, texts: Doc) -> None:
    """Each holder class (R4): THRESHOLDED with the tuple its located text states, UNKNOWN with
    null thresholds and a reason, or NOT_A_HOLDER_LIST; any locator resolves."""
    for found in manifest["header"]["holder_rules"]["classes"].values():
        cut = found.get("threshold_pct"), found.get("threshold_denominator")
        assert found["reason"] and (cut == (None, None)) == (found["completeness"] != "THRESHOLDED")
        if (at := found.get("at")) is None:
            assert found["completeness"] != "THRESHOLDED", found  # a threshold is located
            continue
        source = at.get("doc") or at["vtext"]
        (path,) = [REPO / s["path"] for s in manifest["header"]["sources"] if s["label"] == source]
        if "doc" in at:
            with pymupdf.open(path) as document:  # type: ignore[no-untyped-call]
                assert (text := at["phrase"]) in " ".join(document[at["pg"] - 1].get_text().split())
        else:
            assert (text := texts[source]) in path.read_text().split("\n")[at["line"] - 1], at
        if cut != (None, None):
            assert f"{cut[0]}% " in text and ("or more" in text) == found["inclusive"], found
            assert cut[1] == "TOTAL_SHARES" and "shares" in text, found


def check_tree(manifest: Doc, vendor: Doc) -> None:
    """The companion tree is the bytes' tree plus rulings; committed counts and rulings follow."""
    assert sorted(manifest["tree"]) == sorted(manifest["header"]["filings"]), "tree inventory"
    for sym, vendors in manifest["tree"].items():
        for name, summary in vendors.items():
            listed, ruled = vendor["tree"][sym][name], {}
            assert len(listed) == len(tree(sym)[name]), (sym, name)
            for node, read in zip(listed, tree(sym)[name], strict=True):
                assert node | read == node and node["key"], node["id"]
                ruled |= {node["id"]: {"key": node["key"], "labels": node["labels"]}}
            assert summary["counts"] == counts(listed, name, vendor["class_named"]), (sym, name)
            assert summary["ruled"] == {i: r for i, r in ruled.items() if r["key"] != "UNMAPPED"}


def check_data_stage3(manifest: Doc) -> None:
    """The plan D8 Task 7 checks over the committed manifest and its companion."""
    header, vendor = manifest["header"], companion(manifest)
    check_tree(manifest, vendor)
    for key, row in ((k, r) for run in manifest["runs"] for k, r in run["rows"].items()):
        alone = all(side["s"] == "NO_VALUE" for side in row.get("vendors", {}).values())
        assert "VOTING_RIGHTS" not in key or (alone and not row.get("pairs")), ("paired", key)
    want = sections(header, vendor)
    for name in ("packages", "runs", "holders", "point_checks"):
        assert manifest[name] == want[name], name
    assert (vendor["sides"], vendor["point_checks"]) == (want["sides"], want["readings"])
    check_classes(manifest, vendor["texts"])
    links = {s: [x["links"] for x in p["stored"]] for s, p in manifest["packages"].items()}
    reps = {sym: [[link.upper() for link in x] for x in rows] for sym, rows in links.items()}
    single = all(len(x) == 1 for rows in links.values() for x in rows)  # R3 extraction table
    assert header["extraction"]["representations"] == reps
    assert header["extraction"]["status"] == ("NOT_APPLICABLE" if single else "PAIRED")
    sides = sum(len(x) for run in vendor["sides"].values() for x in run.values())
    nodes = sum(len(nodes) for t in vendor["tree"].values() for nodes in t.values())
    lines = sum(map(len, vendor["point_checks"].values()))
    assert header["companion"]["rows"] == {"sides": sides, "point_checks": lines, "tree": nodes}


def _rows(sym: str, edit: Callable[[Doc], Any]) -> Callable[[Doc], None]:
    return lambda m: edit(next(r["rows"] for r in m["runs"] if r["entity"] == sym))


def _tree(sym: str, vendor: str, edit: Callable[[list[Doc]], Any]) -> Callable[[Doc], None]:
    """Edit a vendor's nodes in a companion copy injected into the manifest (``_vendor``)."""

    def mutate(manifest: Doc) -> None:
        injected = manifest.setdefault("_vendor", copy.deepcopy(companion(manifest)))
        edit(injected["tree"][sym][vendor])

    return mutate


def _move(source: tuple[str, str], target: tuple[str, str]) -> Callable[[Doc], None]:
    def move(rows: Doc) -> None:
        (a,), (b,) = ([k for k in rows if all(w in k for w in want)] for want in (source, target))
        rows[b] |= {field: rows[a].pop(field) for field in ("vendors", "pairs", "queue")}

    return _rows("APARINDS", move)


def _listed(manifest: Doc) -> Doc:
    """APARINDS's first THRESHOLDED Screener holder list."""
    return next(e for e in manifest["holders"]["APARINDS"]["screener"] if "inclusive" in e)


TS, A, APAR = "TOTAL_SHARES", "=sebi_promoter_group|", "APARINDS"
DATA3_MUTATIONS: dict[str, Callable[[Doc], None]] = {
    "paired-denominator": _move((TS, A), ("VOTING_RIGHTS", A)),
    "public-at-non-ruled-key": _move((TS, "=non_institutions|"), (TS, "=public_shareholding|")),
    "deleted-row": _rows("TITAN", lambda rows: rows.popitem()),
    "added-row": _rows("ETERNAL", lambda rows: rows.update(x={})),
    "deleted-tree-node": _tree("TITAN", "tijori", lambda nodes: nodes.pop(5)),
    "changed-node-parent-path": _tree(
        "ETERNAL", "tijori", lambda nodes: nodes[3].update(parent="")
    ),
    "removed-period-value": _tree("TITAN", "upstox", lambda nodes: nodes[0]["periods"].popitem()),
    "deleted-run": lambda m: m["runs"].pop(),
    "incomplete-run": lambda m: m["runs"][0].update(status="INCOMPLETE", exit=1),
    "emptied-queue-counts": lambda m: m["runs"][0]["counts"].update(queue={}),
    "cleared-exclusions": lambda m: m["runs"][0].update(exclusions=[]),
    "invalid-package-selection": lambda m: m["packages"][APAR].update(selected=999),
    "false-threshold": lambda m: _listed(m).update(threshold_pct=99, inclusive=True),
    "unlocated-threshold": lambda m: _listed(m).pop("at"),
    "changed-holder-count": lambda m: _listed(m).update(holders=999),
    "deleted-filing-list": lambda m: m["holders"][APAR]["filing"].pop(0),
}
