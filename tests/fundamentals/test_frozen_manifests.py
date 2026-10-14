"""Frozen data-foundation manifests: provenance, verbatim lexemes and recorded arithmetic.

A manifest is the independent oracle the stage e2e is compared against, so this test reads the
retained bytes directly (lxml, json, pymupdf) and never imports fundamentals parsers, mappings or
engine code. Approval is asserted separately: it fails until the reviewer's verdict is recorded.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
import subprocess
from collections import Counter
from collections.abc import Callable, Iterator
from datetime import date
from decimal import ROUND_HALF_DOWN, ROUND_HALF_UP, Decimal
from fractions import Fraction
from functools import cache
from pathlib import Path
from typing import Any, cast

import pymupdf
import pytest
import yaml
from lxml import etree, html  # type: ignore[import-untyped]

REPO = Path(__file__).resolve().parents[2]
MANIFESTS = sorted((REPO / "tests/fundamentals/fixtures/data_foundation").glob("*_manifest.yaml"))
STAGE1 = REPO / "tests/fundamentals/fixtures/data_foundation/stage1_manifest.yaml"
E2E = "tests/fundamentals/test_data_{stage}_e2e.py"
XI = "{http://www.xbrl.org/2003/instance}"
DI = "{http://xbrl.org/2006/xbrldi}"
TOKEN = re.compile(r"\{[^}]*\}|\d+(?:\.\d+)?|[-+*/()]")
ROW_TOL, LABEL_TOL = 5, 7  # points, word-box centres (header.notation.pdf_locator)
SCREENER = "screener-subscriber/SCREENER_FINANCIALS"
SCREENER_SECTIONS = ("quarters", "profit-loss", "balance-sheet", "cash-flow")
TIJORI_TABLES = ("bs_c_d", "bs_c_s", "cf_c", "fr_c", "pl_c_d", "pl_c_s", "qt_c")
ISLAND = '<script id="fin_tables_data" type="application/json">'
VALUE_FIELDS = {"s", "v", "iv", "why", "tier", "expr", "lo_expr", "hi_expr"}
SHAPES = {  # locator shape -> (required, optional) fields besides VALUE_FIELDS (header.notation)
    "xbrl": ({"src", "c", "ctx", "u", "d", "lex", "per"}, {"dims", "sign"}),
    "xbrl_anchor": ({"src", "c", "ctx"}, set()),
    "pdf": ({"src", "pg", "label", "col", "lex"}, {"n", "note", "sign", "reading"}),
    "screener": ({"src", "sec", "row", "col", "lex"}, set()),
    "screener_absent": ({"src", "sec", "row", "col", "note"}, set()),
    "screener_construction_absent": ({"src", "construction", "col", "note"}, set()),
    "tijori": ({"src", "tbl", "row", "col", "island", "shown"}, set()),
    "upstox": ({"src", "block", "item", "col", "lex"}, set()),
    "screener_html": ({"src", "sec", "row", "cols"}, set()),  # vendor UNMAPPED row groups
    "tijori_island": ({"src", "tbl", "row", "cols"}, set()),
    "upstox_json": ({"src", "block", "item", "cols", "diag"}, set()),
}
GROUP_FIELDS = {
    "screener_html": ("sec", "row"),
    "tijori_island": ("tbl", "row"),
    "upstox_json": ("block", "item"),
}
Interval = tuple[Fraction, Fraction]

per_manifest = pytest.mark.parametrize(
    "path", MANIFESTS, ids=[p.name.removesuffix("_manifest.yaml") for p in MANIFESTS]
)


@cache
def load(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], yaml.safe_load(path.read_text()))


def walk(node: Any) -> Iterator[dict[str, Any]]:
    """Every mapping in the manifest, depth first."""
    if isinstance(node, dict):
        yield node
        node = list(node.values())
    if isinstance(node, list):
        for item in node:
            yield from walk(item)


def evaluate(expr: str, refs: dict[str, Interval] | None = None) -> Interval:
    """Exact interval of an arithmetic expression over decimal literals and {row key} operands."""
    tokens = TOKEN.findall(expr)
    assert "".join(tokens) == expr.replace(" ", ""), expr
    pos = 0

    def atom() -> Interval:
        nonlocal pos
        token, pos = tokens[pos], pos + 1
        if token == "-":
            lo, hi = atom()
            return -hi, -lo
        if token == "(":
            value = chain()
            assert tokens[pos : pos + 1] == [")"], expr
            pos += 1
            return value
        if token.startswith("{"):
            return (refs or {})[token[1:-1]]
        return Fraction(token), Fraction(token)

    def chain(level: int = 0) -> Interval:
        nonlocal pos
        ops = "+-" if level == 0 else "*/"
        value = chain(1) if level == 0 else atom()
        while pos < len(tokens) and tokens[pos] in ops:
            op, pos = tokens[pos], pos + 1
            (a_lo, a_hi), (b_lo, b_hi) = value, chain(1) if level == 0 else atom()
            if op == "+":
                value = a_lo + b_lo, a_hi + b_hi
            elif op == "-":
                value = a_lo - b_hi, a_hi - b_lo
            else:
                if op == "/":
                    assert b_lo > 0 or b_hi < 0, f"divisor straddles zero: {expr}"
                    b_lo, b_hi = 1 / b_hi, 1 / b_lo
                products = [a_lo * b_lo, a_lo * b_hi, a_hi * b_lo, a_hi * b_hi]
                value = min(products), max(products)
        return value

    value = chain()
    assert pos == len(tokens), expr
    return value


def interval(node: dict[str, Any]) -> Interval:
    lo, hi = node["iv"]
    return Fraction(lo), Fraction(hi)


def printed(lex: str) -> Interval:
    """A printed lexeme (grouping commas, (x) negative) and half a unit of its last digit."""
    text = lex.replace(",", "")
    sign = -1 if text.startswith("(") and text.endswith(")") else 1
    value = sign * Fraction(text.strip("()"))
    half = Fraction(1, 2 * 10 ** len(text.strip("()").partition(".")[2]))
    return value - half, value + half


def tijori_shown(island: str) -> str:
    """tijori-v4: the page's rendering of the island double; |x| > 100 Math.round (half toward
    +infinity) with en-IN grouping, else toFixed(2) (half away from zero)."""
    x = Decimal(float(island))
    if abs(x) <= 100:
        return str(x.quantize(Decimal("0.01"), ROUND_HALF_UP))
    digits = str(abs(int(x.quantize(Decimal(1), ROUND_HALF_DOWN if x < 0 else ROUND_HALF_UP))))
    head = re.sub(r"(\d)(?=(\d{2})+$)", r"\1,", digits[:-3])
    return "-" * (x < 0) + (f"{head},{digits[-3:]}" if head else digits)


def reading(loc: dict[str, Any]) -> Interval:
    """The interval a located lexeme denotes in its row's unit (header.notation.value)."""
    sign = int(loc.get("sign", 1))
    if "dash_rule" in loc:
        return Fraction(0), Fraction(0)
    if "c" in loc:
        scale = 10**7 if loc["u"] == "INR" else 1
        value = sign * Fraction(loc["lex"]) / scale
        half = Fraction(0) if loc["d"] == "INF" else Fraction(10) ** -int(loc["d"]) / 2 / scale
        return value - half, value + half
    lo, hi = printed(loc["shown"] if "island" in loc else loc["lex"])
    return (lo, hi) if sign == 1 else (-hi, -lo)


def expected_interval(node: dict[str, Any]) -> Interval | None:
    """What a VALUE node's lexemes say its interval is; None when it carries no locator."""
    if "at" in node:
        (loc,) = node["at"]
        return reading(loc)
    if "operands" in node:
        parts = [reading(op["at"][0] if "at" in op else op) for op in node["operands"]]
        return sum((p[0] for p in parts), Fraction(0)), sum((p[1] for p in parts), Fraction(0))
    if {"lex", "island"} & node.keys():
        return reading(node)
    return None


def source(manifest: dict[str, Any], label: str) -> tuple[Path, str]:
    (found,) = [s for s in manifest["header"]["sources"] if s["label"] == label]
    return REPO / str(found["path"]), str(found["kind"])


@cache
def xbrl_index(path: Path) -> dict[tuple[str, str], list[tuple[Any, str, list[str]]]]:
    """(concept, contextRef) -> [(element, effective period, dims)], FourD re-periodised."""
    root = etree.parse(str(path)).getroot()
    contexts = {}
    for ctx in root.iter(f"{XI}context"):
        instant = ctx.findtext(f".//{XI}instant")
        period = instant.strip() if instant else None
        if period is None:
            start, end = ctx.findtext(f".//{XI}startDate"), ctx.findtext(f".//{XI}endDate")
            period = f"{start.strip()}..{end.strip()}"
        dims = [
            f"{m.get('dimension').split(':')[-1]}={(m.text or '').strip().split(':')[-1]}"
            for m in ctx.iter(f"{DI}explicitMember")
        ] + [
            f"{m.get('dimension').split(':')[-1]}=typed:"
            + "".join(m.itertext()).strip().split(":")[-1]
            for m in ctx.iter(f"{DI}typedMember")
        ]
        contexts[ctx.get("id")] = (period, sorted(dims))
    facts = [el for el in root if isinstance(el.tag, str) and el.get("contextRef")]
    declared: dict[str, dict[str, str]] = {}
    for el in facts:
        name = etree.QName(el).localname
        if name in ("DateOfStartOfReportingPeriod", "DateOfEndOfReportingPeriod"):
            declared.setdefault(el.get("contextRef"), {})[name] = el.text.strip()
    index: dict[tuple[str, str], list[tuple[Any, str, list[str]]]] = {}
    for el in facts:
        ref = el.get("contextRef")
        period, dims = contexts[ref]
        dates = declared.get(ref, {})
        if ".." in period and len(dates) == 2:
            period = (
                f"{dates['DateOfStartOfReportingPeriod']}..{dates['DateOfEndOfReportingPeriod']}"
            )
        index.setdefault((etree.QName(el).localname, ref), []).append((el, period, dims))
    return index


@cache
def pdf_words(path: Path, page: int) -> list[tuple[float, float, str]]:
    """(x centre, y centre, text) of every word box on a page."""
    document: Any = pymupdf.open(path)  # type: ignore[no-untyped-call]
    with document:
        words = document[page - 1].get_text("words")
    return [((w[0] + w[2]) / 2, (w[1] + w[3]) / 2, w[4]) for w in words]


def label_rows(words: list[tuple[float, float, str]], label: str) -> list[float]:
    """y centres of the label's instances, top-down (header.notation.pdf_locator)."""
    tokens = Counter(label.split())
    first = label.split()[0]
    return sorted(
        y
        for x, y, text in words
        if text == first
        and not tokens - Counter(t for wx, wy, t in words if abs(wy - y) <= LABEL_TOL and wx >= x)
    )


def in_band(words: list[tuple[float, float, str]], x: list[float], y: list[float]) -> list[str]:
    return [t for wx, wy, t in words if x[0] <= wx <= x[1] and y[0] <= wy <= y[1]]


def check_pdf(manifest: dict[str, Any], loc: dict[str, Any]) -> None:
    """The lexeme is the whole cell where the label's row meets its header-bound column."""
    words = pdf_words(source(manifest, loc["src"])[0], loc["pg"])
    page = manifest["header"]["pdf_columns"][loc["src"]][loc["pg"]]
    column = page["cols"][loc["col"]]
    assert " ".join(in_band(words, column["x"], page["header_y"])) == column["header"], loc
    rows = label_rows(words, loc["label"])
    assert len(rows) == 1 or "n" in loc, (loc, rows)
    y = rows[loc.get("n", 1) - 1]
    assert in_band(words, column["x"], [y - ROW_TOL, y + ROW_TOL]) == (
        [loc["lex"]] if loc["lex"] else []
    ), loc


def text(node: Any) -> str:
    return " ".join(node.text_content().split())


@cache
def screener_table(path: Path, section: str) -> tuple[list[str], dict[str, list[str]]]:
    """A section's data-table: header labels and each body row's cells by label ('+' dropped)."""
    root = html.fromstring(path.read_bytes())
    (table,) = root.get_element_by_id(section).xpath(".//table[contains(@class, 'data-table')]")
    heads = [text(th) for th in table.xpath(".//thead//th")]
    rows: dict[str, list[str]] = {}
    for tr in table.xpath(".//tbody/tr"):
        cells = [text(td) for td in tr.xpath("./td")]
        if cells:
            label = cells[0].removesuffix("+").strip()
            assert label not in rows and len(cells) == len(heads), (path, section, label)
            rows[label] = cells
    return heads, rows


@cache
def tijori_island(path: Path) -> dict[str, Any]:
    body = path.read_text(encoding="utf-8")
    return cast(
        dict[str, Any], json.JSONDecoder().raw_decode(body, body.index(ISLAND) + len(ISLAND))[0]
    )


def tijori_cell(path: Path, table: str, row: str, column: str) -> str:
    body = tijori_island(path)[table]
    (values,) = [item["value"] for item in body["data"] if item["name"] == row]
    return repr(values[body["report_dates"].index(column)])


def upstox_entries(path: Path, block: str) -> list[tuple[str, list[dict[str, Any]]]]:
    key = "category" if block == "income_statement" else "particular"
    data = json.loads(path.read_text())["data"]
    return [(entry[key], entry["history"]) for entry in data[block]]


def upstox_cell(path: Path, block: str, item: str, column: str) -> str:
    (history,) = [h for name, h in upstox_entries(path, block) if name == item]
    (cell,) = [h["value"] for h in history if h["period"] == column]
    return repr(cell)


def vendor_rows(kind: str, path: Path) -> Iterator[tuple[str, str, str, list[str]]]:
    """(section / table / block, row key, label, columns) of every row a vendor capture yields
    occurrences for (header.interpretations I18); a row without values yields no column."""
    if kind == "screener_html":
        for section in SCREENER_SECTIONS:
            heads, rows = screener_table(path, section)
            yield from ((section, label, label, heads[1:]) for label in rows)
    elif kind == "tijori_island":
        island = tijori_island(path)

        def flatten(table: str, rows: list[Any], parents: str) -> Iterator[Any]:
            dates = island[table]["report_dates"]
            for row in rows:
                key, count = parents + row["name"], len(row["value"])
                assert count in (0, len(dates)) or count < len(dates) and table[:2] == "pl", key
                yield table, key, row["name"], dates if count else []
                yield from flatten(table, row.get("sub_section") or [], key + "/")

        for table in TIJORI_TABLES:
            if island.get(table):
                yield from flatten(table, island[table]["data"], "")
    else:
        for block in ("income_statement", "full_statement"):
            for name, history in upstox_entries(path, block):
                yield block, name, name, [h["period"] for h in history]


def check_locator(manifest: dict[str, Any], loc: dict[str, Any]) -> None:
    """The locator has exactly one recognised shape and its lexeme is where it says."""
    keys = loc.keys() - VALUE_FIELDS
    (shape,) = [name for name, (req, opt) in SHAPES.items() if req <= keys <= req | opt]
    path = source(manifest, loc["src"])[0]
    if shape in ("xbrl", "xbrl_anchor"):
        hits = xbrl_index(path)[(loc["c"], loc["ctx"])]
        assert len(hits) == 1, loc
        if shape == "xbrl":
            ((el, period, dims),) = hits
            found = ((el.text or "").strip(), el.get("unitRef"), el.get("decimals"), period, dims)
            wanted = (loc["lex"], loc["u"], loc["d"], loc["per"], sorted(loc.get("dims", [])))
            assert found == wanted, loc
    elif shape == "pdf":
        check_pdf(manifest, loc)
    elif shape == "screener":
        heads, rows = screener_table(path, loc["sec"])
        assert rows[loc["row"]][heads.index(loc["col"])] == loc["lex"], loc
    elif shape in ("screener_absent", "screener_construction_absent"):
        section = loc.get("sec") or loc["construction"].split(".")[1]
        assert loc["col"] not in screener_table(path, section)[0], loc
    elif shape == "tijori":
        assert tijori_cell(path, loc["tbl"], loc["row"], loc["col"]) == loc["island"], loc
        assert tijori_shown(loc["island"]) == loc["shown"], loc
    elif shape == "upstox":
        assert upstox_cell(path, loc["block"], loc["item"], loc["col"]) == loc["lex"], loc


def check_vendor_unmapped(manifest: dict[str, Any], run: dict[str, Any]) -> None:
    """Listed vendor UNMAPPED groups are exactly the rows of the run's vendor captures that no
    header.vendor_selection label selects, with all their columns (I18)."""
    selection = manifest["header"]["vendor_selection"]

    def tokens(label: str) -> list[str]:
        return re.sub(r"[^a-z0-9]+", " ", label.lower()).split()

    expected = []
    for request in run["vendor_inputs"].values():
        label = request.split()[0]
        path, kind = source(manifest, label)
        group, field = GROUP_FIELDS[kind]
        for section, key, name, cols in vendor_rows(kind, path):
            chosen = [tokens(s) for s in selection[kind].get(section, [])]
            if cols and tokens(name) not in chosen:
                entry = {"src": label, group: section, field: key, "cols": cols}
                expected.append(entry | ({"diag": True} if kind == "upstox_json" else {}))
    assert [e for e in run["unmapped"] if "cols" in e] == expected, run["run"]


def expanded_rows(run: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Every row of a run from the manifest alone: explicit rows plus named defaults."""
    rows = dict(run["rows"])
    for name, keys in run["default_rows"].items():
        assert not rows.keys() & set(keys), name
        rows |= dict.fromkeys(keys, run["defaults"][name])
    return rows


def check_numbers(row: dict[str, Any], record: dict[str, Any], a: str, b: str) -> None:
    """A comparable pair records exact b - a and the interval gap, and only a pair whose
    intervals are disjoint is a disagreement; a refused one records no numbers."""
    outcome = record["out" if "out" in record else "status"]
    if outcome == "NOT_COMPARABLE":
        assert record["diff"] is None and record["gap"] is None, record
        return

    def side(name: str) -> dict[str, Any]:
        return cast(dict[str, Any], row[name] if name in ("xbrl", "pdf") else row["vendors"][name])

    left, right = side(a), side(b)
    (a_lo, a_hi), (b_lo, b_hi) = interval(left), interval(right)
    assert Fraction(record["diff"]) == Fraction(right["v"]) - Fraction(left["v"]), record
    gap = max(a_lo - b_hi, b_lo - a_hi, Fraction(0))
    assert Fraction(record["gap"]) == gap, record
    assert (gap > 0) == (outcome in ("ANOMALY", "MISMATCH", "DISAGREE")), record


def expected_pairs(row: dict[str, Any], vector: dict[str, Any]) -> Counter[tuple[str, str, bool]]:
    """Pair endpoints the source vector implies (I9): the representative with each vendor and,
    diagnostically, the other representation and Screener-Upstox, on VALUE/INVALID sides."""
    pairs: Counter[tuple[str, str, bool]] = Counter()
    reps, vendors = vector["first_party"], row.get("vendors", {})
    if not reps:
        return pairs
    rep = row.get("rep", reps[0])
    other = next((r for r in reps if r != rep), None)

    def live(side: dict[str, Any]) -> bool:
        return side["s"] in ("VALUE", "INVALID")

    for name, side in vendors.items():
        diagnostic = vector["vendors"][name]["role"] == "DIAGNOSTIC"
        if not live(side):
            continue
        if live(row[rep]):
            pairs[(rep, name, diagnostic)] += 1
        if other and row["ext"]["status"] != "AGREE" and live(row[other]):
            pairs[(other, name, True)] += 1
        if diagnostic and SCREENER in vendors and live(vendors[SCREENER]):
            pairs[(SCREENER, name, True)] += 1
    return pairs


def routed(row: dict[str, Any], vector: dict[str, Any]) -> list[dict[str, Any]]:
    """The queue items a row's recorded outcomes route to, at their severities (spec §5, I6)."""
    ext, cor, pairs = row["ext"]["status"], row["cor"]["status"], row.get("pairs", [])
    diagnostic = {name for name, spec in vector["vendors"].items() if spec["role"] == "DIAGNOSTIC"}
    sev = {
        "DISAGREE": "HIGH",
        "NOT_COMPARABLE": "MEDIUM",
        "ONE_SIDE_XBRL": "LOW",
        "ONE_SIDE_PDF": "LOW",
    }
    items = [{"on": "extraction", "sev": sev[ext], "out": ext}] if ext in sev else []
    for pair in pairs:
        out, diag = pair["out"], bool(pair.get("diag"))
        anomaly = {"STRUCTURAL": "HIGH", "MAGNITUDE": "MEDIUM"}.get(pair.get("triage", ""))
        if out == "NOT_COMPARABLE" or (
            diag and out in ("MISMATCH", "ANOMALY") and diagnostic & {pair["a"], pair["b"]}
        ):
            level: str | None = "MEDIUM"
        else:
            level = None if diag else {"MISMATCH": "HIGH", "ANOMALY": anomaly}.get(out)
        if level:
            item = {"on": "pair", "a": pair["a"], "b": pair["b"], "sev": level, "out": out}
            items.append(item | ({"diag": True} if diag else {}))
    if (
        cor in ("VENDOR_ONLY", "NO_SOURCE")
        or cor == "NOT_COMPARABLE"
        and all(p.get("diag") for p in pairs)
    ):
        items.append({"on": "corroboration", "sev": "MEDIUM", "out": cor})
    return items


def check_run(run: dict[str, Any]) -> None:
    """Rows, pairs, queue identities, counts and exit follow from manifest declarations only."""
    rows, vector, counts = expanded_rows(run), run["source_vector"], run["counts"]
    assert (counts["rows"], counts["explicit"]) == (len(rows), len(run["rows"])), run["run"]
    assert counts["defaulted"] == len(rows) - len(run["rows"]), run["run"]
    queue = Counter("LOW" + "_diagnostic" * bool(entry.get("diag")) for entry in run["unmapped"])
    assert counts["unmapped"] == queue.total(), run["run"]
    for key, row in rows.items():
        cid, alias, dims, kind = key.split("|")
        assert all(rep in row for rep in vector["first_party"]), key
        members = {
            vendor
            for vendor, spec in vector["vendors"].items()
            if dims == "-" and cid in spec["keys"].get(alias, [])
        }
        assert set(row.get("vendors", {})) == members, key
        defaulted = row in run["defaults"].values()
        assert not defaulted or kind == "REPORTED" or row["applicability"] == "NOT_APPLICABLE", key
        for rep in vector["first_party"]:
            side = row[rep]
            if side.get("calc") == "COMPUTED":
                refs = re.findall(r"\{([^}]*)\}", side["form"])
                points = {ref: (Fraction(rows[ref][rep]["v"]),) * 2 for ref in refs}
                assert evaluate(side["form"], points) == (Fraction(side["v"]),) * 2, key
                spans = {ref: interval(rows[ref][rep]) for ref in refs}
                assert evaluate(side["form"], spans) == interval(side), key
            elif side["s"] == "VALUE":
                assert expected_interval(side) is not None, (key, rep)
        if row["ext"]["status"] in ("AGREE", "AGREE_UNQUALIFIED", "DISAGREE", "NOT_COMPARABLE"):
            check_numbers(row, row["ext"], "xbrl", "pdf")
        pairs = row.get("pairs", [])
        for pair in pairs:
            check_numbers(row, pair, pair["a"], pair["b"])
        named = Counter((p["a"], p["b"], bool(p.get("diag"))) for p in pairs)
        assert named == expected_pairs(row, vector), key
        items = row.get("queue", [])
        assert items == routed(row, vector), key
        queue.update(item["sev"] + "_diagnostic" * bool(item.get("diag")) for item in items)
    assert queue == Counter(counts["queue"]), run["run"]
    assert (run["status"], run["exit"]) == ("COMPLETE", 3 if queue["HIGH"] else 0), run["run"]


def check_inventory(manifest: dict[str, Any]) -> None:
    """Runs and fixtures are all present: declared sizes, unique run ids, total rows."""
    runs, size = manifest["runs"], manifest["header"]["size"]
    assert len(runs) == size["runs"] == len({run["run"] for run in runs})
    assert sum(len(expanded_rows(run)) for run in runs) == size["rows"]
    assert len(manifest["fixtures"]) == size["fixtures"]


def check_values(manifest: dict[str, Any]) -> None:
    """Every located value is its lexeme normalised (unit, scale, sign, precision interval)."""
    checked = 0
    for node in walk(manifest):
        expected = expected_interval(node) if "iv" in node else None
        if expected is not None:
            assert interval(node) == expected, node
            assert Fraction(node["v"]) == sum(expected) / 2, node
            checked += 1
    assert checked


def payload_sha256(content: bytes) -> str:
    """sha256 of the manifest without its one header approval line (header.notation.approval)."""
    lines = content.splitlines(keepends=True)
    (index,) = [i for i, line in enumerate(lines) if line.startswith(b"  approval:")]
    return hashlib.sha256(b"".join(lines[:index] + lines[index + 1 :])).hexdigest()


@pytest.mark.parametrize("expr", ["1 + 2) + 50", "(1 + 2", "1 2", "()", "1 +", "1 + (2 * 3"])
def test_evaluator_rejects_malformed_expressions(expr: str) -> None:
    with pytest.raises((AssertionError, IndexError, ValueError)):
        evaluate(expr)


@pytest.mark.parametrize(
    ("island", "shown"),
    [("1415.05", "1,415"), ("90.61", "90.61"), ("96.005", "96.00"), ("-100.5", "-100")],
)
def test_tijori_rendering(island: str, shown: str) -> None:
    """Rounding of the island double as the page shows it (96.005 is 96.00499... in binary)."""
    assert tijori_shown(island) == shown


@per_manifest
def test_header_records_hand_verification(path: Path) -> None:
    header = load(path)["header"]
    assert {"verifier", "date", "method"} <= header["hand_verification"].keys()
    assert all(header["hand_verification"].values())
    assert header["approval"]["reviewer"] == "gpt-6.1-sol"


@pytest.mark.retained
@per_manifest
def test_sources_match_their_hashes(path: Path) -> None:
    for source_entry in load(path)["header"]["sources"]:
        digest = hashlib.sha256((REPO / source_entry["path"]).read_bytes()).hexdigest()
        assert digest == source_entry["sha256"], source_entry["path"]


@pytest.mark.retained
@per_manifest
def test_every_lexeme_is_at_its_locator(path: Path) -> None:
    manifest = load(path)
    located = [node for node in walk(manifest) if "src" in node]
    assert located
    for loc in located:
        check_locator(manifest, loc)
    for run in manifest["runs"]:
        check_vendor_unmapped(manifest, run)


@pytest.mark.retained
@pytest.mark.parametrize(
    "change",
    [
        {"col": "FY25-I", "lex": "1.73"},
        {"lex": "1.73"},
        {"lex": "3,310.50"},
        {"label": "Other intangible assets"},
    ],
    ids=["other-row-and-column", "other-row-value", "other-column-value", "other-label"],
)
def test_pdf_locator_rejects_a_misplaced_cell(change: dict[str, str]) -> None:
    """E11's 3,364.50 is bound to Inventories x 30-Sep-2025, not merely printed on the page."""
    manifest = load(STAGE1)
    e11 = manifest["fixtures"]["E11"]["pdf"]
    check_pdf(manifest, e11)
    with pytest.raises(AssertionError):
        check_pdf(manifest, e11 | change)


def run_of(manifest: dict[str, Any], name: str) -> dict[str, Any]:
    (run,) = [run for run in manifest["runs"] if run["run"] == name]
    return cast(dict[str, Any], run)


def row_of(manifest: dict[str, Any], name: str, key: str) -> dict[str, Any]:
    return cast(dict[str, Any], run_of(manifest, name)["rows"][key])


def apar_revenue(manifest: dict[str, Any]) -> dict[str, Any]:
    return row_of(manifest, "APARINDS-Q2FY26", "revenue_from_operations|Q|-|REPORTED")


TIJORI = "tijori/financials"


def drop_routed_item(manifest: dict[str, Any]) -> None:
    """Drop a routed queue item and lower the run's total to match."""
    run = run_of(manifest, "THERMAX-Q3FY25")
    item = run["rows"]["revenue_from_operations|Q|-|REPORTED"]["queue"].pop()
    run["counts"]["queue"][item["sev"]] -= 1


Mutation = Callable[[dict[str, Any]], None]
MUTATIONS: dict[str, tuple[Mutation, Callable[[dict[str, Any]], None]]] = {
    "value-not-its-lexeme": (
        lambda m: row_of(m, "LAURUSLABS-Q3FY25", "total_income|Q|-|REPORTED")["xbrl"].update(
            v="123456", iv=["123455.5", "123456.5"]
        ),
        check_values,
    ),
    "tijori-shown-not-rendered": (
        lambda m: apar_revenue(m)["vendors"][TIJORI].update(shown="5,000"),
        lambda m: check_locator(m, apar_revenue(m)["vendors"][TIJORI]),
    ),
    "derived-operand-unbound": (
        lambda m: row_of(m, "LAURUSLABS-Q3FY25", "total_expenses|Q|-|REPORTED")["xbrl"].update(
            v="1300", iv=["1299.5", "1300.5"]
        ),
        lambda m: check_run(run_of(m, "LAURUSLABS-Q3FY25")),
    ),
    "required-pair-deleted": (
        lambda m: row_of(m, "LAURUSLABS-Q3FY25", "profit_continuing_after_tax|Q|-|REPORTED")[
            "pairs"
        ].pop(),
        lambda m: check_run(run_of(m, "LAURUSLABS-Q3FY25")),
    ),
    "pair-outcome-not-its-item": (
        lambda m: row_of(m, "THERMAX-Q3FY25", "revenue_from_operations|Q|-|REPORTED")["pairs"][
            0
        ].update(out="MISMATCH"),
        lambda m: check_run(run_of(m, "THERMAX-Q3FY25")),
    ),
    "routed-item-dropped-total-lowered": (
        drop_routed_item,
        lambda m: check_run(run_of(m, "THERMAX-Q3FY25")),
    ),
    "runs-emptied": (lambda m: m["runs"].clear(), check_inventory),
    "pdf-locator-without-page": (
        lambda m: apar_revenue(m)["pdf"].pop("pg"),
        lambda m: check_locator(m, apar_revenue(m)["pdf"]),
    ),
    "vendor-unmapped-row-dropped": (
        lambda m: run_of(m, "LAURUSLABS-Q3FY25")["unmapped"].pop(),
        lambda m: check_vendor_unmapped(m, run_of(m, "LAURUSLABS-Q3FY25")),
    ),
}


@pytest.mark.retained
@pytest.mark.parametrize("name", MUTATIONS)
def test_stage1_checks_reject_mutations(name: str) -> None:
    """Each check passes on the frozen manifest and fails once its target is altered."""
    mutate, check = MUTATIONS[name]
    manifest = copy.deepcopy(load(STAGE1))
    check(manifest)
    mutate(manifest)
    with pytest.raises((AssertionError, KeyError, ValueError)):
        check(manifest)


@per_manifest
def test_recorded_arithmetic_is_exact(path: Path) -> None:
    checked = 0
    for node in walk(load(path)):
        if "expr" in node and "v" in node:
            assert evaluate(node["expr"]) == (Fraction(node["v"]),) * 2, node["expr"]
            checked += 1
        if "lo_expr" in node:
            bounds = [evaluate(node["lo_expr"])[0], evaluate(node["hi_expr"])[1]]
            assert bounds == list(interval(node)), node["expr"]
    assert checked


@per_manifest
def test_values_follow_from_their_lexemes(path: Path) -> None:
    check_values(load(path))


@per_manifest
def test_runs_expand_from_the_manifest_alone(path: Path) -> None:
    manifest = load(path)
    check_inventory(manifest)
    for run in manifest["runs"]:
        check_run(run)


@per_manifest
def test_approved_payload_preceded_its_e2e(path: Path) -> None:
    """The e2e's first commit is a child of a commit whose manifest payload is the approved one."""
    e2e = E2E.format(stage=path.name.removesuffix("_manifest.yaml"))
    if not (REPO / e2e).exists():
        return

    def git(*args: str) -> bytes:
        return subprocess.run(["git", *args], cwd=REPO, capture_output=True, check=True).stdout

    added = git("log", "--diff-filter=A", "--format=%H", "--", e2e).split()
    assert added, f"{e2e} is not committed"
    before = git("show", f"{added[-1].decode()}^:{path.relative_to(REPO)}")
    assert payload_sha256(before) == load(path)["header"]["approval"]["payload_sha256"]


@per_manifest
def test_manifest_is_approved(path: Path) -> None:
    approval, payload = load(path)["header"]["approval"], payload_sha256(path.read_bytes())
    print(f"{path.name} payload_sha256: {payload}")
    assert approval["verdict"] == "APPROVE"
    assert isinstance(approval["date"], date), "an approval records its date (YYYY-MM-DD)"
    assert approval["payload_sha256"] == payload, "the approval covers another payload"
