"""D8 Task 2c aid. Standard library only; never imports `fundamentals`. Reuses Task 2's aid
(aid.py beside this file, stdlib only) for the filing reader and the table-4 method.

Writes tree_aid_output.md and tree_aid_holders.md (T1h) into OUT, which must be private and
gitignored: both carry vendor readings (d8-probe.md §13.4):
  T1 every vendor node per company (gen-2): printed label, printed parent label, ordered label path
     (a JSON list), depth, periodicity, source node id and parent id, and each offered period's value
     or printed marker; wholly empty nodes included;
  T2 the aid-table-4 method over gen-2 for each node §13 rules (and its gen-1 alternatives);
  T3 Jun 2026 vendor page values, gen-1 against gen-2.

    python3 -I docs/workstreams/data-foundation/aids/tree_aid.py data/raw/shareholding OUT
"""

import html
import json
import re
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import aid  # noqa: E402

COMPANIES = aid.COMPANIES
aid.ROWS |= {
    "A1": "IndianMember",
    "A2": "ForeignMember",
    "R2L": "ResidentIndividualShareholdersHoldingNominalShareCapitalUpToRsTwoLakhMember",
    "IEPF": "InvestorEducationAndProtectionFundMember",
    "NRI": "NonResidentIndiansMember",
}
TIJORI_CATEGORY_LIKE = {"Individual<2lac", "InvestorEducationandProtectionFund(IEPF)", "LLP"}  # myids; §12.2: a class, not an entity
GEN1 = {"screener": "03.bin", "tijori": "04.bin", "upstox": "05.bin"}
NON_INST = ("Public Shareholding", "Non-Institutions")
# ruled node (vendor, printed label path) -> candidate baskets; the first is the ruling's basket
RULED = {
    ("screener", ("Promoters",)): ["A"],
    ("screener", ("FIIs",)): ["B2", "FPI1+FPI2"],
    ("screener", ("DIIs",)): ["B1", "B1-SWF"],
    ("screener", ("Government",)): ["SWF", "B3", "SWF+B3"],
    ("screener", ("Public",)): ["B4", "B4+B3", "B4+C2", "B4+C"],
    ("screener", ("Others",)): ["C2", "C"],
    ("tijori", ("Promoter",)): ["A"],
    ("tijori", ("Promoter", "Indian Promoters")): ["A1"],
    ("tijori", ("Promoter", "Foreign Promoters")): ["A2"],
    ("tijori", ("Public Shareholding",)): ["B+C2", "B", "B+C"],
    ("tijori", ("Public Shareholding", "Institutions")): ["B1+B2", "B1+B2+B3"],
    ("tijori", NON_INST): ["B4+C2", "B4", "B4+B3+C2"],
    ("tijori", (*NON_INST, "Individual < 2 lac")): ["R2L", "R2L+NRI"],
    ("tijori", (*NON_INST, "Investor Education and Protection Fund (IEPF)")): ["IEPF"],
    ("upstox", ("promoters",)): ["A"],
    ("upstox", ("fii",)): ["B2", "FPI1+FPI2"],
    ("upstox", ("mutual_funds",)): ["MF"],
    ("upstox", ("other_dii",)): ["B1-MF"],
    ("upstox", ("retail_and_other",)): ["B4+C2", "B4", "B4+C", "B3+B4+C"],
}


def clean(cell: str) -> str:
    """Visible text of an HTML cell."""
    return re.sub(r"\s+", " ", html.unescape(re.sub("<[^>]+>", "", cell))).strip()


def gen2_files(folder: Path) -> dict:
    """Manifest entries of a gen-2 folder by surface, in order."""
    out: dict = {}
    for e in json.loads((folder / "discovery-manifest.json").read_text())["entries"]:
        out.setdefault(e["surface"], []).append(e)
    return out


def screener_nodes(folder: Path, files: dict) -> list[dict]:
    """Page rows of quarterly-shp and yearly-shp (depth 1), then each hook's holders (depth 2)."""
    page = (folder / files["SCREENER_SHAREHOLDING"][0]["filename"]).read_text()
    bodies = {}
    for e in files["SCREENER_INVESTORS"]:
        bucket, periodicity = e["url"].rstrip("/").split("/")[-2:]
        bodies[bucket, periodicity] = (e["filename"], json.loads((folder / e["filename"]).read_bytes()))
    nodes = []
    for periodicity in ("quarterly", "yearly"):
        section = page[page.find(f'<div id="{periodicity}-shp"'):]
        table = section[: section.find("</table>")]
        header = [clean(h) for h in re.findall(r"<th[^>]*>(.*?)</th>", table, re.S)][1:]
        for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", table, re.S)[1:]:
            cells = [clean(c) for c in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
            label = cells[0].removesuffix("+").strip()
            hook = re.search(r"showShareholders\('(\w+)', '(\w+)'", tr)
            bucket = hook.group(1) if hook else None
            name, body = bodies.get((bucket, periodicity), (None, None))
            node = {"label": label, "parent": None, "parent_id": None, "path": (label,), "depth": 1, "periodicity": periodicity,
                    "id": bucket or "(no hook)", "values": list(zip(header, cells[1:])),
                    "note": "no drill-down hook" if hook is None else f"{name}: {len(body)} children" + (" (body {})" if body == {} else "")}
            nodes.append(node)
            for holder, series in (body or {}).items():
                offered = [(k, v) for k, v in series.items() if k != "setAttributes"]
                nodes.append({"label": holder, "parent": label, "parent_id": bucket, "path": (label, holder), "depth": 2,
                              "periodicity": periodicity, "id": holder, "values": offered,
                              "note": f"holder; {name}; columns not offered: {len([h for h in header if h not in series])}"})
    return nodes


def tijori_nodes(body: str) -> list[dict]:
    """Every company_detailed row with its data-parent chain."""
    start = body.find('id="company_detailed"')
    rows = re.findall(r"<tr([^>]*)>(.*?)</tr>", body[start: body.find("</table>", start)], re.S)
    header = [clean(c) for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", rows[0][1], re.S)][1:]
    nodes, path_of = [], {}
    for attrs, tr in rows[1:]:
        get = lambda key: html.unescape((re.search(rf'\s{key}="([^"]*)"', attrs) or [None, ""])[1])
        myid, dparent, level = get("myid"), get("data-parent"), int(get("class").removeprefix("row"))
        cells = [clean(c) for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S)]
        parent_id = None if dparent == "1" else dparent
        path = (*path_of.get(parent_id, ()), cells[0])
        path_of[myid] = path
        nodes.append({"label": cells[0], "parent": path[-2] if parent_id else None, "parent_id": parent_id, "path": path, "depth": level, "periodicity": "quarterly (column labels)",
                      "id": myid, "values": list(zip(header, cells[1:])),
                      "note": ("holder; " if level == 3 and myid not in TIJORI_CATEGORY_LIKE else "")
                      + ("should_hide=yes" if get("should_hide") == "yes" else "") + (" all —" if all(c == "—" for c in cells[1:]) else "")})
    return nodes


def upstox_nodes(body: bytes) -> list[dict]:
    """Each data[] category (depth 1)."""
    return [{"label": c["category"], "parent": None, "parent_id": None, "path": (c["category"],), "depth": 1, "periodicity": "history (undeclared)",
             "id": c["category"], "values": [(h["period"], str(h["value"])) for h in c["history"]], "note": ""}
            for c in json.loads(body)["data"]]


def cell(text: str) -> str:
    """A markdown-safe table cell (holder names carry newlines and may carry pipes)."""
    return text.replace("|", "\\|").replace("\r", "").replace("\n", " ↵ ")


def label_path(path: tuple) -> str:
    """The ordered printed-label path as a JSON list."""
    return json.dumps(list(path), ensure_ascii=False)


def row(i: int, n: dict) -> str:
    """One inventory row."""
    values = "; ".join(f"{p}={v}" for p, v in n["values"]) or "(none)"
    return (f"| {i} | {n['periodicity']} | {n['depth']} | {cell(n['label'])} | {cell(n['parent'] or '—')} "
            f"| {cell(label_path(n['path']))} | {cell(n['id'])} | {cell(n['parent_id'] or '—')} "
            f"| {n['note'].strip() or '—'} | {cell(values)} |")


def jun(nodes: list[dict], path: tuple, periodicity_prefix: str = "") -> Decimal | str:
    """Jun 2026 value of the node at ``path`` (Screener: quarterly table), else why there is none."""
    for n in nodes:
        if n["path"] == path and n["depth"] <= 3 and n["periodicity"].startswith(periodicity_prefix):
            raw = dict(n["values"]).get("Jun 2026", dict(n["values"]).get("Jun'26"))
            try:
                return Decimal(raw.rstrip("%").replace(",", "")) if raw else "period not offered"
            except ArithmeticError:
                return f"printed {raw}"
    return "no node"


def main(root: Path, out_dir: Path) -> None:
    out, trees, filings = [], {}, {}
    for sym in COMPANIES:
        folder = root / sym / "gen-2"
        files = gen2_files(folder)
        trees[sym] = {
            "screener": screener_nodes(folder, files),
            "tijori": tijori_nodes((folder / files["shareholding"][0]["filename"]).read_text()),
            "upstox": upstox_nodes((folder / files["share-holdings"][0]["filename"]).read_bytes()),
        }
        filings[sym] = aid.filing(folder / "02.bin")["rows"]
    head = ["| # | Periodicity | Depth | Label | Parent label | Label path | Node id | Parent id | Note | Offered periods: value |",
            "|---|---|---|---|---|---|---|---|---|---|"]
    holders = ["# D8 probe appendix — Tree aid T1h: every Screener drill-down holder, gen-2\n",
               "Generated by `scratchpad/d8-resume/tree_aid.py` (`tree_aid_holders.md`, copied verbatim); never "
               "edited by hand. Companion to d8-probe.md §13 T1; # is the node's T1 index. Holders are listed, never "
               "mapped. Node id = drill-down key; parent id = drill-down bucket. Values as printed; a period not "
               "listed is not offered, never zero.\n"]
    out.append("## Tree aid T1 — vendor tree inventory, gen-2: every non-holder node, every Tijori and Upstox node, "
               "and a summary per Screener holder list (its holders are in T1h). Values as printed; a period not listed is not offered\n")
    for vendor in ("screener", "tijori", "upstox"):
        for sym in COMPANIES:
            nodes = trees[sym][vendor]
            out.append(f"### {vendor} {sym}: {len(nodes)} nodes, max depth {max(n['depth'] for n in nodes)}, "
                       f"holders {sum(n['note'].startswith('holder') for n in nodes)}\n")
            out.extend(head)
            for i, n in enumerate(nodes):
                if vendor == "screener" and n["depth"] == 2:
                    continue
                out.append(row(i, n))
                if vendor == "screener":
                    kids = [(j, k) for j, k in enumerate(nodes) if k["depth"] == 2 and k["path"][0] == n["label"] and k["periodicity"] == n["periodicity"]]
                    if kids:
                        holders.append(f"### screener {sym} {n['periodicity']} {n['label']} ({n['note']})\n")
                        holders.extend(head)
                        holders.extend(row(j, k) for j, k in kids)
                        holders.append("")
                        with_jun = [k for _, k in kids if "Jun 2026" in dict(k["values"])]
                        out.append(f"| ↳ | {n['periodicity']} | 2 | (holders) | {cell(n['label'])} | {cell(label_path((n['label'], '…')))} | — "
                                   f"| {n['id']} | {len(kids)} holders (T1h); "
                                   f"{len(with_jun)} offer Jun 2026, {len(kids) - len(with_jun)} do not | — |")
            out.append("")
    (out_dir / "tree_aid_holders.md").write_text("\n".join(holders) + "\n")
    out.append(f"## Tree aid T2 — ruled nodes at Jun 2026 against candidate baskets, gen-2 filings, exact counts, TOL = {aid.TOL} pp "
               "(first basket = the §13 basket; aid-table-4 method)\n")
    out.append("| Vendor | Label path | Company | Vendor value | Candidate | Not filed | TS % | TS diff | TS verdict | VR % | VR diff | VR verdict |")
    out.append("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for (vendor, path), candidates in RULED.items():
        for sym in COMPANIES:
            published = jun(trees[sym][vendor], path, "quarterly" if vendor == "screener" else "")
            for expr in candidates:
                cells = []
                for count in (aid.SHARES, aid.VOTES):
                    value, absent = aid.basket(filings[sym], expr, count)
                    if isinstance(published, str):
                        cells.append(f"{value:.4f} | — | NO VENDOR VALUE")
                    else:
                        gap = published - value
                        cells.append(f"{value:.4f} | {gap:+.4f} | {'REFUTED' if abs(gap) > aid.TOL else 'CONSISTENT'}")
                shown = str(published)
                out.append(f"| {vendor} | {cell(label_path(path))} | {sym} | {shown} | {expr} | {','.join(absent) or '—'} | {' | '.join(cells)} |")
    out.append("\n## Tree aid T3 — Jun 2026 vendor values, gen-1 page against gen-2 page (level 1–2 nodes the gen-1 aid reads)\n")
    out.append("| Vendor | Company | Node | gen-1 | gen-2 | Equal |")
    out.append("|---|---|---|---|---|---|")
    for sym in COMPANIES:
        g1 = root / sym / "gen-1"
        old = {"screener": aid.screener((g1 / GEN1["screener"]).read_text()),
               "tijori": aid.tijori((g1 / GEN1["tijori"]).read_text()),
               "upstox": aid.upstox((g1 / GEN1["upstox"]).read_bytes())}
        for vendor, values in old.items():
            for label, before in values.items():
                node = next(n for n in trees[sym][vendor] if (n["label"] if vendor == "screener" else n["id"]) == label
                            and n["depth"] <= 2 and not n["periodicity"].startswith("yearly"))
                after = dict(node["values"]).get("Jun 2026", dict(node["values"]).get("Jun'26", "absent"))
                out.append(f"| {vendor} | {sym} | {label} | {before} | {after} | {'yes' if before == after else '**no**'} |")
    (out_dir / "tree_aid_output.md").write_text("\n".join(out) + "\n")


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
