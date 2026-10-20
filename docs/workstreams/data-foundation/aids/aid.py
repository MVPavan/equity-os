"""D8 Task 2 consistency aid. Standard library only; never imports `fundamentals`.

Helper imported by `tree_aid.py`: filing reader and the aid-table-4 method (no CLI; output is
private, see `tree_aid.py`). A candidate is REFUTED when |vendor - basket| > TOL (percentage points);
otherwise it is CONSISTENT, which never establishes a ruling (R5).
"""

import html
import json
import re
import xml.etree.ElementTree as ET
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

TOL = Decimal("0.03")
COMPANIES = ("APARINDS", "ETERNAL", "TITAN")
XI, DI = "{http://www.xbrl.org/2003/instance}", "{http://xbrl.org/2006/xbrldi}"
AXIS = "CategoryOfShareholdersAxis"
ROWS = {  # SEBI row -> filed CategoryOfShareholdersAxis member
    "T": "ShareholdingPatternMember",
    "A": "ShareholdingOfPromoterAndPromoterGroupMember",
    "B": "PublicShareholdingMember",
    "B1": "InstitutionsDomesticMember",
    "B2": "InstitutionsForeignMember",
    "B3": "GovernmentsMember",
    "B4": "NonInstitutionsMember",
    "C": "SharesHeldByNonPromoterNonPublicShareholdersMember",
    "C2": "EmployeeBenefitsTrustsMember",
    "MF": "MutualFundsOrUTIMember",
    "SWF": "SovereignWealthFundsDomesticMember",
    "FPI1": "InstitutionsForeignPortfolioInvestorCategoryOneMember",
    "FPI2": "InstitutionsForeignPortfolioInvestorCategoryTwoMember",
}
PCT, VR, SHARES, VOTES = (
    "ShareholdingAsAPercentageOfTotalNumberOfShares",
    "PercentageOfTotalVotingRights",
    "NumberOfShares",
    "NumberOfVotingRights",
)
# vendor label -> candidate baskets (sums of ROWS keys; "-" subtracts)
CANDIDATES = {
    ("screener", "Promoters"): ["A"],
    ("screener", "FIIs"): ["B2", "FPI1+FPI2"],
    ("screener", "DIIs"): ["B1", "B1-SWF"],
    ("screener", "Government"): ["B3", "SWF", "SWF+B3"],
    ("screener", "Public"): ["B4", "B4+B3", "B4+C2", "B4+C"],
    ("screener", "Others"): ["C2", "C"],
    ("tijori", "Promoter"): ["A"],
    ("tijori", "PublicShareholding"): ["B", "B+C2", "B+C"],
    ("tijori", "Institutions"): ["B1+B2", "B1+B2+B3"],
    ("tijori", "Non-Institutions"): ["B4", "B4+C2", "B4+B3+C2"],
    ("upstox", "promoters"): ["A"],
    ("upstox", "fii"): ["B2", "FPI1+FPI2"],
    ("upstox", "mutual_funds"): ["MF"],
    ("upstox", "mutual_funds+other_dii"): ["B1", "B1+B3"],
    ("upstox", "retail_and_other"): ["B4", "B4+C2", "B4+C", "B3+B4+C"],
}


def q2(value: Decimal) -> Decimal:
    """Round to two decimals, half up."""
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def filing(path: Path) -> dict:
    """Category member -> {shares, pct, vr} as filed (pct/vr are fractions); holder lists."""
    root = ET.parse(path).getroot()
    dims = {}
    for ctx in root.iter(XI + "context"):
        members = [(m.get("dimension").split(":")[1], m.text.split(":")[1]) for m in ctx.iter(DI + "explicitMember")]
        typed = [(m.get("dimension").split(":")[1], m.get("dimension")) for m in ctx.iter(DI + "typedMember")]
        dims[ctx.get("id")] = members + typed
    rows, holders = {}, {}
    for el in root:
        name, ctx = el.tag.split("}")[-1], el.get("contextRef")
        if ctx is None or name not in (PCT, VR, SHARES, VOTES):
            continue
        d = dims[ctx]
        if len(d) == 1 and d[0][0] == AXIS:
            rows.setdefault(d[0][1], {})[name] = Decimal(el.text)
        elif len(d) == 1 and name == PCT:
            holders.setdefault(d[0][0], []).append(Decimal(el.text))
    return {"rows": rows, "holders": holders}


def exact(rows: dict, key: str, count: str = SHARES) -> Decimal | None:
    """Share-count (or voting-rights-count) percentage of a ROWS key; None when not filed."""
    member = rows.get(ROWS[key])
    if member is None:
        return None
    return Decimal(100) * member[count] / rows[ROWS["T"]][count]


def basket(rows: dict, expr: str, count: str = SHARES) -> tuple[Decimal, list[str]]:
    """Percentage of a basket expression over ``count``; absent members count 0 and are listed."""
    total, absent = Decimal(0), []
    for sign, key in re.findall(r"([+-]?)([A-Z0-9]+)", expr):
        value = exact(rows, key, count)
        if value is None:
            absent.append(key)
            value = Decimal(0)
        total += -value if sign == "-" else value
    return total, absent


def screener(body: str) -> dict:
    """Jun 2026 column of the first quarterly-shp table."""
    section = body[body.find('id="quarterly-shp"'):]
    table = section[: section.find("</table>")]
    clean = lambda c: re.sub(r"\s+", " ", html.unescape(re.sub("<[^>]+>", "", c))).strip()
    header = [clean(h) for h in re.findall(r"<th[^>]*>(.*?)</th>", table, re.S)]
    col = header.index("Jun 2026")
    out = {}
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", table, re.S)[1:]:
        cells = [clean(c) for c in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
        out[cells[0].rstrip(" +").strip()] = cells[col]
    return out


def tijori(body: str) -> dict:
    """Jun'26 column of company_detailed, keyed by row myid."""
    start = body.find('id="company_detailed"')
    table = body[start: body.find("</table>", start)]
    clean = lambda c: re.sub(r"\s+", " ", html.unescape(re.sub("<[^>]+>", "", c))).strip()
    rows = re.findall(r"<tr([^>]*)>(.*?)</tr>", table, re.S)
    header = [clean(c) for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", rows[0][1], re.S)]
    col = header.index("Jun'26")
    out = {}
    for attrs, tr in rows[1:]:
        myid = re.search(r'myid="([^"]*)"', attrs)
        cells = [clean(c) for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S)]
        if myid and re.search(r'class="row1"|class="row2"', attrs):
            out[myid.group(1)] = cells[col]
    return out


def upstox(body: bytes) -> dict:
    """Jun 2026 value of each category."""
    data = json.loads(body)["data"]
    return {c["category"]: next((str(h["value"]) for h in c["history"] if h["period"] == "Jun 2026"), "absent") for c in data}


def vendor_value(source: str, label: str, values: dict) -> Decimal | None:
    """The published Jun 2026 value of a vendor label (sums only for the Upstox DII construction)."""
    parts = label.split("+") if source == "upstox" else [label]
    total = Decimal(0)
    for part in parts:
        raw = values.get(part)
        if raw is None or raw in ("—", "absent", ""):
            return None
        total += Decimal(raw.rstrip("%").replace(",", ""))
    return total
