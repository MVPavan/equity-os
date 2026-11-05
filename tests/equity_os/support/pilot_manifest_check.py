"""PREP-7 pilot manifest check (docs/plans/PREP-7.md Decisions 2-7).

Binds every frozen pilot expectation to the meaning its claim key requires: the quarter's
config-pinned package member, concept, period and unit, the results-PDF cell that corroborates it,
the IST-correct cutoff and the retrospective designation. The binding tables are literal here; the
manifest cannot declare its own. Reads retained bytes only; never imports fundamentals.
"""

from __future__ import annotations

import copy
import hashlib
import re
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from fractions import Fraction
from functools import cache
from pathlib import Path
from typing import Any, cast
from zoneinfo import ZoneInfo

import pytest
from manifest_locators import shp_table, tijori_html, upstox_shp
from moved_support import recorded_path
from stage3_data_support import LISTED, P, Z, facts, number, row_key
from test_frozen_manifests import (
    REPO,
    ROW_TOL,
    check_locator,
    check_values,
    evaluate,
    in_band,
    label_rows,
    parsed,
    pdf_words,
    reading,
    source,
    walk,
    xbrl_index,
)

Node = dict[str, Any]
LEDGER_IMPORT = "config/ledger_import.yaml"
STAGE1 = "tests/fundamentals/fixtures/data_foundation/stage1_manifest.yaml"
STAGE3 = "tests/fundamentals/fixtures/data_foundation/stage3_manifest.yaml"
SHP_GENERATIONS = {"FY26_Q2": 4, "FY26_Q3": 5, "FY26_Q4": 6}  # PILOT-9 Task 1; FY27_Q1 is Stage 3's
GEN = "data/raw/shareholding/APARINDS/gen-{}"
COLUMN = {"screener_shp_html": "%b %Y", "tijori_shp_html": "%b'%y", "upstox_shp_json": "%b %Y"}
A_VR = row_key(P, "VOTING_RIGHTS", "INE372A01015", "sebi_promoter_group")  # PQ0 mutations
ASSUMED, FORMAL = "denominator assumed, not vendor-stated", "NOT_COMPARABLE/PRECISION_UNSUPPORTED"
CONFIGS = {  # Decision 5 (test_prep2b_cutoffs.py:19-24): Q4 runs from the -pg copy
    "FY26_Q2": "config/aparinds-fy26-q2.yaml",
    "FY26_Q3": "config/aparinds-fy26-q3.yaml",
    "FY26_Q4": "config/aparinds-fy26-q4-pg.yaml",
    "FY27_Q1": "config/aparinds-fy27-q1.yaml",
}
ROLES = "revenue total_income total_expenses profit_before_tax profit_for_period basic_eps".split()
ROLE_CONCEPT = {  # Decision 3; tax and associates as api/config.py:47-48 map them
    "revenue": "RevenueFromOperations",
    "total_income": "Income",
    "total_expenses": "Expenses",
    "profit_before_tax": "ProfitBeforeTax",
    "profit_for_period": "ProfitLossForPeriod",
    "basic_eps": "BasicEarningsLossPerShareFromContinuingAndDiscontinuedOperations",
    "tax": "TaxExpense",
    "share_of_associates": "ShareOfProfitLossOfAssociates"
    "AndJointVenturesAccountedForUsingEquityMethod",
}
UNIT_SCALE = {"INR": 10**7, "INRPerShare": 1}
MEMBERS = ["xbrl", "results_pdf", "transcript_pdf", "qoq", "yoy"]
CMP = {f"cmp.{r}.{k}": f"fact.{r}" for r in ROLES for k in ("qoq", "yoy")}
KEYS = {f"fact.{r}" for r in ROLES} | {f"calc.{n}" for n in range(1, 5)}
KEYS |= {f"{c}.{part}" for c in CMP for part in ("prior", "abs", "pct")}
FORMULAS = {  # derived claim -> its prescribed formula over the bound operands (Decision 3)
    **{f"{c}.abs": f"{{{f}}} - {{{c}.prior}}" for c, f in CMP.items()},
    **{f"{c}.pct": f"({{{f}}} - {{{c}.prior}}) / {{{c}.prior}} * 100" for c, f in CMP.items()},
    "calc.1": "{fact.total_income} - {fact.revenue}",
    "calc.3": "{calc.2} / {fact.profit_before_tax} * 100",
    "calc.4": "{fact.profit_before_tax} + {aux.share_of_associates}",
}
XBRL_KEYS = {"src", "c", "ctx", "u", "d", "lex", "per"}
PDF_KEYS = {"src", "pg", "label", "col", "lex"}
ZERO_MARKERS = {"-", "."}  # a lone "." is FY27_Q1's scanned dash (Task 1 ruling 2)
# Decision 2 tables, as each results PDF's text layer prints them (Task 1 ruling 1).
PDF_SCOPE = {
    "FY26_Q2": "Consolidated",
    "FY26_Q3": "Consolidated",
    "FY26_Q4": "Consolidated (Refer Note 4)",
    "FY27_Q1": "Consolidated (Refer Note 3)",
}
PDF_CURRENT = {
    "FY26_Q2": "Sep 30, 2025",
    "FY26_Q3": "Dec 31, 2025",
    "FY26_Q4": "Mar 31, 2026",
    "FY27_Q1": "Jun 30, 2026",
}
PBT = "Profit before tax & share in net profit / (loss) of associates"
ROW = {
    "revenue": "Revenue from operations (1+2)",
    "total_income": "Total income (3+4)",
    "total_expenses": "Total expenses",
    "profit_before_tax": f"{PBT} (7.8)",
    "profit_for_period": "Profit after tax",
    "basic_eps": "Basic",
    "share_of_associates": "Share in net profit / (loss) of associates",
}
PDF_ROW = {(q, role): label for q in CONFIGS for role, label in ROW.items()} | {
    ("FY26_Q2", "total_expenses"): "Total exp",
    ("FY26_Q2", "profit_before_tax"): f"{PBT} (5.6)",
    ("FY26_Q2", "profit_for_period"): "rroft after tax",
    ("FY26_Q3", "profit_before_tax"): f"{PBT} (7",
    ("FY26_Q4", "basic_eps"): "'Basic",
    ("FY27_Q1", "basic_eps"): "-Basic",
}
TAX = ["(a) Current tax", "(b) Deferred tax", "(c) Current tax in respect of earlier years"]
PDF_TAX_ROWS = {q: TAX for q in CONFIGS} | {"FY26_Q2": [TAX[0], "(b( Deferred tax", TAX[2]]}
IST = ZoneInfo("Asia/Kolkata")


@cache
def sha(rel: str) -> str:
    """The sha256 of a repo-relative file."""
    return hashlib.sha256(recorded_path(REPO, rel).read_bytes()).hexdigest()


def doc(rel: str) -> Any:
    """A repo-relative YAML or JSON file's value."""
    return parsed(recorded_path(REPO, rel))


def published(entry: Node) -> datetime:
    """The entry's NSE filing time, read as Asia/Kolkata wall time, in UTC."""
    filed = datetime.strptime(entry["filed_at_nse"], "%d-%b-%Y %H:%M:%S")
    return filed.replace(tzinfo=IST).astimezone(UTC)


def admitted(entry: Node, cutoff: datetime) -> None:
    """Contract (a): published by the cutoff; retrospective: acquired after it (Decision 6)."""
    assert published(entry) <= cutoff, "published after cutoff"
    assert datetime.fromisoformat(entry["retrieved_at"]) > cutoff, "acquired at or before cutoff"


def citations_allowed(cited: set[str], package: set[str], inherited: set[str]) -> None:
    """Every cited blob is in the quarter's package or inherited via the approved prior."""
    outside = sorted(cited - package - inherited)
    assert not outside, f"cited outside the package: {outside}"


def files(config: Node) -> dict[str, tuple[str, str, str | None]]:
    """Package role -> (config source_id, repo path, config sha256 pin) (Decision 4)."""
    raw, xbrl_id, priors = config["raw_dir"], config["xbrl"]["source_id"], config["comparators"]
    out = {"xbrl": (xbrl_id, config["xbrl"]["local_path"], None)}
    for r in ("results_pdf", "transcript_pdf"):
        out[r] = (config[r]["source_id"], f"{raw}/{config[r]['filename']}", config[r]["sha256"])
    return out | {
        k: (xbrl_id, priors[k]["local_path"], priors[k]["sha256"]) for k in ("qoq", "yoy")
    }


def binding(key: str, config: Node) -> tuple[str, str, str, str]:
    """(package member, concept, period, unit) a located claim or operand must come from."""
    kind, name, *rest = key.split(".")
    member = rest[0] if kind == "cmp" else "xbrl"
    role = {"calc": "tax", "aux": "share_of_associates"}.get(kind, name)
    span = config["quarter"] if member == "xbrl" else config["comparators"][member]
    unit = "INRPerShare" if role == "basic_eps" else "INR"
    return member, ROLE_CONCEPT[role], f"{span['period_start']}..{span['period_end']}", unit


def nodes(quarter: Node) -> dict[str, Node]:
    """A quarter's claims plus its aux operands under ``aux.<name>``."""
    return quarter["claims"] | {f"aux.{name}": node for name, node in quarter["aux"].items()}


def sha_of(m: Node, label: str) -> str:
    """The recorded sha256 of a header source."""
    (digest,) = [s["sha256"] for s in m["header"]["sources"] if s["label"] == label]
    return str(digest)


def cell_bound(m: Node, q: str, cell: Node, results_sha: str) -> bool:
    """The cell sits in this quarter's results PDF, on its consolidated page, in the
    current-quarter column: the leftmost band headed PDF_CURRENT[q] (Task 1 ruling 3)."""
    words = pdf_words(source(m, cell["src"])[0], cell["pg"])
    page = m["header"]["pdf_columns"][cell["src"]][cell["pg"]]
    column, (top, bottom), first = page["cols"][cell["col"]], page["header_y"], PDF_CURRENT[q][:3]
    leftmost = min(x for x, y, text in words if text == first and top <= y <= bottom)
    return (
        cell.keys() == PDF_KEYS
        and sha_of(m, cell["src"]) == results_sha
        and column["header"] == PDF_CURRENT[q]
        and column["x"][0] <= leftmost <= column["x"][1]
        and len(label_rows(words, PDF_SCOPE[q])) == 1
    )


def check_quarter(m: Node, q: str, labels: dict[str, str]) -> None:
    """One quarter's cutoff, designation, package, inventory, bindings and derivations."""
    quarter, config, imports = m["quarters"][q], doc(CONFIGS[q]), doc(LEDGER_IMPORT)
    assert config["quarter"]["issuer_quarter"] == q, f"config {q}"
    entries, resolved = doc(imports["retrieval_manifest"])["entries"], {}
    for role, (_, path, _) in files(config).items():
        name = Path(path).name
        (resolved[role],) = [(i, e) for i, e in enumerate(entries) if e["filename"] == name]
    index, transcript = resolved["transcript_pdf"]
    cutoff = published(transcript)
    utc, field = f"{cutoff:%Y-%m-%dT%H:%M:%SZ}", f"entries[{index}].filed_at_nse"
    loc = {
        "src": labels[imports["retrieval_manifest"]],
        "path": field,
        "lex": transcript["filed_at_nse"],
    }
    assert quarter["source_cutoff"] == {"v": utc, "at": [loc]}, f"cutoff {q}"
    assert utc == config["quarter"]["knowledge_cutoff"], f"cutoff {q}"
    pin = imports["retrieval_manifest_sha256"]
    designation = {"designated": "RETROSPECTIVE", "retrieval_manifest_sha256": pin}
    assert sha(imports["retrieval_manifest"]) == pin, "retrieval manifest pin"
    assert quarter["retrospective"] == designation, f"retrospective {q}"
    assert sorted(p["role"] for p in quarter["package"]) == sorted(MEMBERS), f"package {q}"
    package = {member["role"]: member for member in quarter["package"]}
    for role, (source_id, path, pinned) in files(config).items():
        entry = resolved[role][1]
        listed = {"quarter": entry["quarter"], "kind": entry["kind"]}
        member = {"role": role, "source_id": source_id, "entry": listed, "sha256": sha(path)}
        assert package[role] == member and entry["sha256"] == sha(path), f"package {q} {role}"
        assert pinned in (None, sha(path)), f"package {q} {role}"
        admitted(entry, cutoff)
    claims, aux = nodes(quarter), quarter["aux"].keys()
    assert quarter["claims"].keys() == KEYS and aux == {"share_of_associates"}, f"inventory {q}"
    figures = {key: node for key, node in claims.items() if key not in FORMULAS}
    columns: set[tuple[object, ...]] = set()
    for key, node in figures.items():
        kind = key.split(".")[0]
        cells = node.get("pdf_parts", [node["pdf"]] if "pdf" in node else [])
        corroborated = {"fact": {"pdf"}, "aux": {"pdf"}, "calc": {"pdf_parts"}}.get(kind, set())
        assert node.keys() == {"v", "iv", "at"} | corroborated, f"shape {q} {key}"
        (loc,) = node["at"]
        assert loc.keys() == XBRL_KEYS, f"shape {q} {key}"
        assert Fraction(node["v"]) == Fraction(loc["lex"]) / UNIT_SCALE[loc["u"]], (
            f"shape {q} {key}"
        )
        member, concept, per, unit = binding(key, config)
        found = (sha_of(m, loc["src"]), loc["c"], loc["per"], loc["u"])
        assert found == (package[member]["sha256"], concept, per, unit), f"member {q} {key}"
        rows = PDF_TAX_ROWS[q] if key == "calc.2" else [PDF_ROW[q, key.split(".")[1]]] * bool(cells)
        bound = all(cell_bound(m, q, cell, package["results_pdf"]["sha256"]) for cell in cells)
        columns |= {(cell["src"], cell["pg"], cell["col"]) for cell in cells}
        one_page = len(columns) <= 1
        assert sorted(c["label"] for c in cells) == sorted(rows) and bound and one_page, (
            f"pdf {q} {key}"
        )
    values = {key: (Fraction(node["v"]),) * 2 for key, node in figures.items()}
    for key, formula in FORMULAS.items():
        assert claims[key].keys() == {"expr", "v"}, f"shape {q} {key}"
        assert Fraction(claims[key]["v"]) == evaluate(formula, values)[0], f"derived {q} {key}"


def check_pilot(m: Node) -> None:
    """The pilot manifest's inventories, sources, quarters and pilot_checks pointers."""
    imports = doc(LEDGER_IMPORT)
    assert list(m["quarters"]) == imports["earnings_updates"] == list(CONFIGS), "quarters"
    paths = {imports["retrieval_manifest"], STAGE1}
    paths |= {path for q in CONFIGS for _, path, _ in files(doc(CONFIGS[q])).values()}
    for root in map(GEN.format, SHP_GENERATIONS.values()):  # PILOT-9 generations, every file
        paths |= {STAGE3, *(str(file.relative_to(REPO)) for file in (REPO / root).iterdir())}
    sources = m["header"]["sources"]
    labels = {s["path"]: s["label"] for s in sources}
    assert {s["path"]: s["sha256"] for s in sources} == {p: sha(p) for p in paths}, "sources"
    assert len(sources) == len(paths) == len(set(labels.values())), "sources"
    for q in CONFIGS:
        check_quarter(m, q, labels)
    checks, q0 = m["pilot_checks"], next(iter(CONFIGS))
    pilot1 = {"pbt": f"{q0} fact.profit_before_tax", "pbt_after_associates": f"{q0} calc.4"}
    fields = {"opm": "pre_registered.C7_OPM.spec_literal_2dp"}
    fields |= {name: f"pre_registered.H3.outcome.{name}" for name in ("pair", "triage", "queue")}
    located = {"opm": checks["PILOT-1"]["opm"], **checks["PILOT-2"]}
    assert checks.keys() == {"PILOT-1", "PILOT-2"}, "pilot_checks"
    assert checks["PILOT-2"].keys() == {"pair", "triage", "queue"}, "pilot_checks"
    assert checks["PILOT-1"] == pilot1 | {"opm": located["opm"]}, "pilot_checks"
    found = {k: (loc.keys(), loc["src"], loc["path"]) for k, loc in located.items()}
    wanted = {k: ({"src", "path", "lex"}, labels[STAGE1], path) for k, path in fields.items()}
    assert found == wanted, "pilot_checks"
    check_shareholding(m, labels)


def cell(m: Node, node: Node, day: date, root: str) -> str:
    """The cell a companion node locates (manifest_locators) in its quarter's generation."""
    path, kind = source(m, node["file"])
    assert path.parent == REPO / root and node["column"] == f"{day:{COLUMN[kind]}}", "column"
    if kind == "upstox_shp_json":
        found = {(name, name): periods for name, periods in upstox_shp(path)}
    elif kind == "screener_shp_html":
        heads, rows = shp_table(path, f"{node['periodicity']}-shp")
        found = {(label, str(hook)): dict(zip(heads, c, strict=True)) for label, hook, c in rows}
    else:
        heads, tree = tijori_html(path)
        found = {(c[0], myid): dict(zip(heads, c[1:], strict=True)) for _, myid, _, c in tree}
    return found[node["path"][-1], node["source_node_id"]][node["column"]]


def check_shareholding(m: Node, labels: dict[str, str]) -> None:
    """PILOT-9 Task 2: each quarter against its generation's bytes and the companion; FY27_Q1."""
    pin, quarters = m["shareholding"]["companion"], m["shareholding"]["quarters"]  # vendor readings
    assert "_vendor" in m or sha(pin["path"]) == pin["sha256"], "companion"
    stage3 = parsed(source(m, m["shareholding"]["stage3"])[0])
    readings = m.get("_vendor") or doc(pin["path"])
    header, (run3,) = stage3["header"], [r["run"] for r in stage3["runs"] if "APAR" in r["run"]]
    pinned = {"instant": header["instant"], "generation": 2, "run": run3}
    assert list(quarters) == list(CONFIGS) and quarters["FY27_Q1"] == pinned, "FY27_Q1"
    for q, gen in SHP_GENERATIONS.items():
        quarter, root = quarters[q], GEN.format(gen)
        run, day, src = quarter["run"], date.fromisoformat(quarter["instant"]), f"{root}/01.bin"
        assert (quarter["generation"], run["run"]) == (gen, f"APARINDS-SHP-{day}"), f"run {q}"
        listing, entries = doc(src), doc(f"{root}/discovery-manifest.json")["entries"]
        (i,) = [i for i, row in enumerate(listing) if row["date"] == f"{day:%d-%b-%Y}".upper()]
        (entry,) = [e for e in entries if e["url"] == listing[i]["xbrl"]]
        at = [{"src": labels[src], "path": f"[{i}].{f}", "lex": str(listing[i][f])} for f in LISTED]
        links = [field for field, value in listing[i].items() if str(value).startswith("http")]
        instance = labels[path := f"{root}/{entry['filename']}"]
        stored = {"instance": instance, "lineage": None, "links": links, "at": at}
        assert quarter["package"] == {"stored": [stored], "selected": 0}, f"package {q}"
        filed = {"filed_at_nse": listing[i]["broadcastDate"], "retrieved_at": entry["retrieved_at"]}
        admitted(filed, datetime.fromisoformat(m["quarters"][q]["source_cutoff"]["v"]))
        rows, bearing = run["rows"], set().union(*facts(path)[1].values())
        lex = {key: row["xbrl"]["at"][0]["lex"] for key, row in rows.items() if "at" in row["xbrl"]}
        located = {loc["src"] for row in rows.values() for loc in row["xbrl"].get("at", [])}
        assert lex and located == {instance}, f"xbrl {q}"
        valued = {(k, s): v for k, r in rows.items() for s, v in r["vendors"].items() if "at" in v}
        paired = {k for k, r in rows.items() if r["pairs"]} | {k for k, _ in valued}
        assert not {k for k in paired if "VOTING_RIGHTS" in k}, f"paired {q}"  # R10: TOTAL_SHARES
        checks, own = quarter["point_checks"], readings["runs"][run["run"]]
        assert sorted((c["key"], c["vendor"]) for c in checks) == sorted(valued), f"points {q}"
        assert own["nodes"].keys() == {v["at"]["node"] for v in valued.values()}, f"nodes {q}"
        for check, read in zip(checks, own["point_checks"], strict=True):
            side, (cid, _, dims, _) = valued[check["key"], check["vendor"]], check["key"].split("|")
            den, isin, cat = (d.split("=")[1] for d in dims.split(","))
            keys = {k: row_key(P, den, isin, k) for k in header["baskets"].get(cid, [0, [cat]])[1]}
            zero = [member for member, k in keys.items() if k not in lex]
            assert not {d for z in zero for d in header["descendants"][z]} & bearing, f"zero {q}"
            present = [{"key": k, "lex": lex[k]} for k in keys.values() if k in lex]
            terms = " + ".join([p["lex"] for p in present] + ["0"] * len(zero))
            want = {"at": side["at"], "members": present, "zero": zero, "expr": f"({terms}) * 100"}
            want |= {"labels": side["labels"] + [Z] * bool(zero), "formal": FORMAL}
            assert {k: check[k] for k in want} == want and side["labels"][0] == ASSUMED, q
            shown = cell(m, own["nodes"][side["at"]["node"]], day, root)
            assert [read["lex"], read["v"]] == [shown, str(number(shown))], f"point {q}"
            assert side["s"] != "VALUE" or own["sides"][check["key"]][check["vendor"]] == read, q
        assert all(valued[k, s]["s"] == "VALUE" for k, x in own["sides"].items() for s in x), q


def generic(m: Node) -> None:
    """The frozen-suite checks on a manifest dict, plus the PDF/XBRL interval overlap."""
    check_values(m)
    for node in walk(m):
        if "src" in node:
            check_locator(m, node)
        if "expr" in node:
            assert evaluate(node["expr"]) == (Fraction(node["v"]),) * 2, node["expr"]
        cells = node.get("pdf_parts", [node["pdf"]] if "pdf" in node else [])
        if cells:
            zero = (Fraction(0), Fraction(0))  # a zero marker reads as exact 0 (Decision 2)
            parts = [zero if cell["lex"] in ZERO_MARKERS else reading(cell) for cell in cells]
            lo, hi = reading(node["at"][0])
            low, high = sum(p[0] for p in parts), sum(p[1] for p in parts)
            assert lo <= high and low <= hi, f"overlap {node['at'][0]}"


def cell_at(m: Node, cell: Node) -> Node:
    """The cell re-read from the PDF: whatever genuinely sits at its label row and column."""
    words = pdf_words(source(m, cell["src"])[0], cell["pg"])
    x = m["header"]["pdf_columns"][cell["src"]][cell["pg"]]["cols"][cell["col"]]["x"]
    (y,) = label_rows(words, cell["label"])
    return cell | {"lex": " ".join(in_band(words, x, [y - ROW_TOL, y + ROW_TOL]))}


def repoint(m: Node, q: str, key: str, at: Node | None = None, pdf: Node | None = None) -> None:
    """Swap a figure's XBRL and/or PDF locator for other genuine ones, re-read their lexemes,
    reset v/iv and recompute the quarter's derivations with FORMULAS."""
    claims = nodes(m["quarters"][q])
    node = claims[key]
    if at:
        loc = node["at"][0] | at
        ((element, per, _),) = xbrl_index(source(m, loc["src"])[0])[loc["c"], loc["ctx"]]
        unit, d = element.get("unitRef"), element.get("decimals")
        loc |= {"lex": element.text.strip(), "u": unit, "d": d, "per": per}
        lo, hi = reading(loc)
        node.update(at=[loc], v=str(Fraction(loc["lex"]) / UNIT_SCALE[unit]), iv=[str(lo), str(hi)])
    if pdf:
        node["pdf"] = cell_at(m, node["pdf"] | pdf)
    values = {key: Fraction(node["v"]) for key, node in claims.items() if key not in FORMULAS}
    for key, formula in FORMULAS.items():
        expr = re.sub(r"\{([^}]*)\}", lambda ref: f"({values[ref[1]]})", formula)
        claims[key].update(expr=expr, v=str(evaluate(expr)[0]))


Q0, Q1 = "FY26_Q2", "FY26_Q3"


def claims(m: Node, q: str = Q0) -> Node:
    """A quarter's claims (PQ0 by default)."""
    return m["quarters"][q]["claims"]


def reformulate(m: Node) -> None:
    """calc.1 expr and v changed consistently to a sum: exact, but not the prescribed formula."""
    node = claims(m)["calc.1"]
    node["expr"] = node["expr"].replace(" - ", " + ")
    node["v"] = str(evaluate(node["expr"])[0])


def add_sign(m: Node) -> None:
    """A prior gains sign -1 with v and iv negated, so check_values still holds."""
    node = claims(m)["cmp.revenue.yoy.prior"]
    lo, hi = (Fraction(bound) for bound in node["iv"])
    node["at"][0]["sign"] = -1
    node.update(v=str(-Fraction(node["v"])), iv=[str(-hi), str(-lo)])


def break_tax_sum(m: Node) -> None:
    """One calc.2 component cell re-pointed at another genuine cell on its page and column."""
    parts = claims(m)["calc.2"]["pdf_parts"]
    parts[0] = cell_at(m, parts[0] | {"label": PDF_ROW[Q0, "share_of_associates"]})


def shift_cutoff(m: Node) -> None:
    """The old UTC misreading: the IST wall time recorded as UTC (+5h30)."""
    cut, form = m["quarters"][Q0]["source_cutoff"], "%Y-%m-%dT%H:%M:%SZ"
    when = datetime.strptime(cut["v"], form) + timedelta(hours=5, minutes=30)
    cut["v"] = when.strftime(form)


def package(m: Node, q: str, index: int) -> Node:
    """One package member of a quarter (MEMBERS order)."""
    return m["quarters"][q]["package"][index]


def shp(m: Node, q: str = Q0) -> Node:
    """A PILOT-9 quarter of the shareholding section (PQ0 by default)."""
    return cast(Node, m["shareholding"]["quarters"][q])


def readings_copy(m: Node) -> Node:
    """PQ0's readings in a companion copy injected into the manifest (``_vendor``)."""
    injected = m.setdefault("_vendor", copy.deepcopy(doc(m["shareholding"]["companion"]["path"])))
    return dict(injected["runs"][shp(m)["run"]["run"]])


def bump(m: Node) -> None:
    """PQ0's first point-check lexeme one unit up in its last printed decimal."""
    read = readings_copy(m)["point_checks"][0]
    step = Decimal(1).scaleb(int(Decimal(read["v"]).as_tuple().exponent))
    read["lex"] = read["lex"].replace(read["v"], str(Decimal(read["v"]) + step))


PILOT_MUTATIONS: dict[str, Callable[[Node], object]] = {
    "cutoff-utc-misreading": shift_cutoff,
    "package-sha256": lambda m: package(m, Q0, 3).update(sha256=package(m, Q1, 4)["sha256"]),
    "digest-only": lambda m: m["quarters"][Q0]["retrospective"].update(
        retrieval_manifest_sha256=sha(STAGE1)
    ),
    "designation-label": lambda m: m["quarters"][Q0]["retrospective"].update(designated="LIVE"),
    "derived-formula": reformulate,
    "pdf-outside-xbrl": lambda m: repoint(
        m, Q0, "fact.revenue", None, {"label": PDF_ROW[Q0, "total_income"]}
    ),
    "broken-tax-sum": break_tax_sum,
    "dropped-iv": lambda m: claims(m)["cmp.revenue.qoq.prior"].pop("iv"),
    "added-sign": add_sign,
    "deleted-quarter": lambda m: m["quarters"].pop("FY27_Q1"),
    "deleted-cmp-claim": lambda m: claims(m).pop("cmp.basic_eps.yoy.pct"),
    "deleted-calc.3": lambda m: claims(m, Q1).pop("calc.3"),
    "deleted-member": lambda m: m["quarters"][Q0]["package"].pop(),
    "wrong-quarter": lambda m: repoint(m, Q0, "fact.revenue", {"src": "X-FY26_Q1"}, {"col": "Q-1"}),
    "wrong-concept": lambda m: repoint(
        m,
        Q0,
        "fact.total_income",
        claims(m)["fact.revenue"]["at"][0],
        {"label": PDF_ROW[Q0, "revenue"]},
    ),
    "qoq-yoy-swap": lambda m: repoint(m, Q0, "cmp.revenue.qoq.prior", {"src": "X-FY25_Q2"}),
    "pbt-concept-swap": lambda m: repoint(
        m, Q0, "fact.profit_before_tax", {"c": "ProfitBeforeExceptionalItemsAndTax"}
    ),
    "cross-package-pdf": lambda m: repoint(
        m, Q0, "fact.revenue", None, {"src": "R-FY26_Q3", "col": "Q-1"}
    ),
    "id-only": lambda m: package(m, Q0, 1).update(source_id="aparinds-fy26-q3-results-pdf"),
    "shp-deleted-run": lambda m: shp(m, Q1).pop("run"),
    "shp-paired-denominator": lambda m: shp(m)["run"]["rows"][A_VR]["pairs"].append({"a": "xbrl"}),
    "shp-dropped-label": lambda m: shp(m)["point_checks"][1]["labels"].pop(),
    "shp-filed-zero": lambda m: shp(m)["point_checks"][6]["zero"].append("public_shareholding"),
    "shp-companion-value": bump,
    "shp-node-column": lambda m: [*readings_copy(m)["nodes"].values()][0].update(column="Jun 2025"),
    "shp-late": lambda m: shp(m)["package"]["stored"][0]["at"][2].update(lex="08-NOV-2025"),
    "shp-stage3-pin": lambda m: m["header"]["sources"][-1].update(sha256=sha(STAGE1)),
}
SEMANTIC = {  # binding probe -> the refusal check_pilot must raise once generic passes
    "wrong-quarter": f"member {Q0} fact.revenue",
    "wrong-concept": f"member {Q0} fact.total_income",
    "qoq-yoy-swap": f"member {Q0} cmp.revenue.qoq.prior",
    "pbt-concept-swap": f"member {Q0} fact.profit_before_tax",
    "cross-package-pdf": f"pdf {Q0} fact.revenue",
    "id-only": f"package {Q0} results_pdf",
}


def refuses(manifest: Node, name: str) -> None:
    """The mutated copy is refused: an ordinary mutation by generic or check_pilot; a SEMANTIC
    probe passes generic (else the probe is broken), then check_pilot raises exactly its message."""
    m = copy.deepcopy(manifest)
    PILOT_MUTATIONS[name](m)
    if name not in SEMANTIC:
        with pytest.raises((AssertionError, KeyError, ValueError)):
            generic(m)
            check_pilot(m)
        return
    generic(m)
    with pytest.raises(AssertionError, match=f"^{re.escape(SEMANTIC[name])}$"):
        check_pilot(m)
