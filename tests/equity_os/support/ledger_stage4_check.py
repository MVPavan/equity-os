"""Structure of the frozen ledger Stage 4 manifest (D7 Task 5 as amended by D7-screen-export
Task 6). Reads the manifest alone; its lexemes are ``check_locator``'s."""

from __future__ import annotations

import re
from typing import Any, cast

from manifest_support import PDF_VERDICT, Mutation, failure_surface
from stage4_support import UPSTOX

from equity_os.contracts.companies.onboarding import (
    ANCHOR_UNITS,
    ONBOARDING_VERSIONS,
    UNIT_SURFACES,
    VerificationState,
    VerificationUnit,
)
from equity_os.verification.comparison.run_models import RunExitStatus

AUTOMATED_EXPORT = "AUTOMATED_EXPORT"  # header.export_provenance (D7-screen-export S6)
SCREENER_ID = "screener-subscriber/SCREENER_FINANCIALS"
SCREEN_FIXTURES = ("screener-page.html", "screener.csv", "tijori-results.json")
CAPTURES = [("SCREENER", "definition"), ("SCREENER", "results"), ("TIJORI", "results")]
SHA256 = re.compile(r"[0-9a-f]{64}")
PAGE_COUNT = re.compile(r"([0-9]+) results? found")
WATCHLIST_EXPECT = ["REFUSED", "ACCEPTED", "REFUSED", "REFUSED", "ACCEPTED", "ACCEPTED"]
WATCHLIST_EXPECT += ["REFUSED", "REFUSED"]  # D7 Task 6 steps 1-8 (R3, R6, R7)
GATES = {  # unit -> (identity binding flds, authenticated lexemes, basis/table lexemes)
    "SCREENER": (
        {"screener_search_id", "screener_page_id", "screener_warehouse_id"},
        ['href="/user/account/"', 'action="/logout/"'],
        ("basis_marker", ["Consolidated", "Figures"]),
    ),
    "TIJORI": (
        {"tijori_symbol", "tijori_company_id", "tijori_search_slug"},
        ['<script id="is_auth" type="application/json">true</script>'],
        ("consolidated_table", ['"qt_c": {"report_dates": [']),
    ),
}


def bound_members(screen: dict[str, Any]) -> dict[str, str]:
    """symbol -> ISIN of the members bound to the same NSE_EQ listing on both runs, each row's
    located codes agreeing with its registry reads; review items only when one is not."""
    sides: list[dict[str, str]] = []
    for name, index, first in (("screener", "row", 1), ("tijori", "data_index", 0)):
        rows = screen[name]
        assert [r[index] for r in rows] == list(range(first, first + len(rows))), name
        found = {}
        for row in rows:
            isin, at = row["expect"]["listing"]["isin"], row["at"]
            bse = at["registry_bse"]["lex"]
            assert at["registry_nse"]["key"] == at["registry_bse"]["key"] == isin, row["symbol"]
            assert at["registry_nse"]["lex"] == row["symbol"], row["symbol"]
            codes = f'"scripcode":{bse},"nse symbol":"{row["symbol"]}"'
            wanted = f"{bse},{row['symbol']},{isin}" if name == "screener" else codes
            assert wanted in at["codes"]["lex"], row["symbol"]
            if row["expect"]["reason"] is None and row["expect"]["listing"]["segment"] == "NSE_EQ":
                found[row["symbol"]] = isin
        sides.append(found)
    both = {s: i for s, i in sides[0].items() if sides[1].get(s) == i}
    total = {r["symbol"] for name in ("screener", "tijori") for r in screen[name]}
    assert (screen["review_items"] == []) == (set(both) == total), "review_items"
    return both


def check_member4(member: dict[str, Any], isin: str, hashes: dict[str, str]) -> None:
    """Outcome, unit states, run pins and inputs, gates and per-source comparison inventory."""
    symbol, units, run = member["symbol"], member["units"], member["run"]
    assert units.keys() == set(VerificationUnit), symbol
    excluded = sorted(u for u, unit in units.items() if unit["state"] != VerificationState.VERIFIED)
    assert excluded == sorted(member["excluded_units"]) and member["isin"] == isin, symbol
    pdf = units[VerificationUnit.RESULTS_PDF]
    assert (pdf["state"], pdf.get("reason")) == PDF_VERDICT, symbol
    anchors = all(units[u]["state"] == VerificationState.VERIFIED for u in ANCHOR_UNITS)
    assert member["outcome"] == ("PARTIAL" if anchors and excluded else "ONBOARDED"), symbol
    surfaces = {UNIT_SURFACES[VerificationUnit(u)] for u in excluded if u != UPSTOX}
    failed = {failure_surface(f) for f in run.get("operational_failures", [])}
    assert failed == surfaces, symbol
    status = "INCOMPLETE" if surfaces else "COMPLETE"
    assert run["status"] == status and (
        status != "INCOMPLETE" or run["exit"] == RunExitStatus.INCOMPLETE
    )
    assert (run["entity"], run["basis"]) == (symbol, "CONSOLIDATED"), symbol
    assert run["config"] == ONBOARDING_VERSIONS.model_dump(exclude_defaults=True), symbol
    assert member["bindings"]["isin"]["lex"] == isin, symbol
    inputs: dict[str, Any] = {"xbrl": [hashes[f"{symbol}-X1"], hashes[f"{symbol}-X2"]]}
    inputs |= {SCREENER_ID: hashes[f"{symbol}-SCR"], "tijori/financials": hashes[f"{symbol}-TIJ"]}
    assert run["inputs"] == inputs | {"upstox/income-statement": hashes[f"{symbol}-UPS"]}, symbol
    for unit, (flds, authenticated, (field, lexes)) in GATES.items():
        gate = member.get("gates", {}).get(unit)
        assert (units[unit]["state"] == VerificationState.VERIFIED) == bool(gate), (symbol, unit)
        ids = {loc["fld"]: loc["lex"] for loc in gate["identity"]}
        assert ids.keys() == flds and ids.get("tijori_symbol", symbol) == symbol, (symbol, unit)
        assert ids.get("screener_page_id") == ids.get("screener_search_id"), (symbol, unit)
        assert [loc["lex"] for loc in gate["authenticated"]] == authenticated, (symbol, unit)
        assert [loc["lex"] for loc in gate[field]] == lexes, (symbol, unit)
    comparison, end = run["comparison"], str(run["period_end"])
    keys, sources = comparison["keys"], comparison["sources"]
    assert keys["Q"].endswith(f"..{end}") and str(keys["I"]) == end, symbol
    assert {s.partition(":")[0] for s in sources} == inputs.keys() | {"upstox/income-statement"}
    for name, source in sources.items():
        sides = source.get("sides", source["value"])
        assert sides and (name == "xbrl") == ("sides" not in source), (symbol, name)
        assert source["value"] or name != "xbrl", (symbol, name)
        assert (sides.keys() | source["value"].keys()) <= keys.keys(), (symbol, name)
        assert all(set(ids) <= set(sides[a]) for a, ids in source["value"].items()), (symbol, name)
        sizes = {k: sum(map(len, source[k].values())) for k in ("sides", "value") if k in source}
        assert source["counts"] == sizes, (symbol, name)


def check_ledger_stage4(manifest: dict[str, Any]) -> None:
    """The ledger Stage 4 manifest's structure: automated-export provenance and its derived
    fixture, both screen runs' bindings, the batch as a subset of bound members with the others
    the remainder, each member (``check_member4``), the registry loads and the watchlist steps."""
    header, batch, registry = manifest["header"], manifest["batch"], manifest["registry"]
    assert header["export_provenance"] == AUTOMATED_EXPORT and "csv_provenance" not in header
    derived = header["derived_fixture"]
    captures = [(c["vendor"], c["role"]) for c in derived["source_captures"]]
    digests = [c["sha256"] for c in derived["source_captures"]]
    assert captures == CAPTURES and all(SHA256.fullmatch(d) for d in digests), "source_captures"
    assert derived["rule"], "derived_fixture.rule"
    paths = {s["path"].rsplit("/", 1)[-1]: s["sha256"] for s in header["sources"]}
    assert derived["fixture_sha256"] == {name: paths[name] for name in SCREEN_FIXTURES}
    stated = derived["counts_stated"]
    page = PAGE_COUNT.match(stated["screener_page_info"])
    originals = {"SCREENER": page and int(page.group(1)), "TIJORI": stated["tijori_total_results"]}
    assert derived["rows_kept"].keys() == originals.keys(), "rows_kept"
    for vendor, kept in derived["rows_kept"].items():
        assert kept["of"] == originals[vendor], vendor
        assert kept["kept"] == len(manifest["screen"][vendor.lower()]) <= kept["of"], vendor
    bound = bound_members(manifest["screen"])
    declared, others = batch["declared"], batch["others"]
    assert set(declared) <= bound.keys() and sorted(bound.keys() - set(declared)) == sorted(others)
    assert [m["symbol"] for m in batch["members"]] == declared and batch["completed"] is True
    expect = batch["others_expect"]
    assert expect.keys() == set(others) and not any(v for e in expect.values() for v in e.values())
    hashes = {s["label"]: s["sha256"] for s in header["sources"]}
    for member in batch["members"]:
        check_member4(member, bound[member["symbol"]], hashes)
    counts, (first, replay, later) = registry["counts"], registry["loads"]
    assert counts["listings"] == counts["NSE_EQ"] + counts["BSE_EQ"] == first["new_listings"]
    assert (replay["created"], replay["new_listings"], replay["candidate_events"]) == (False, 0, 0)
    assert later["new_listings"] == 0 and len(later["candidate_events"]) == 1, "registry loads"
    for spot in registry["spot_rows"]:
        for listing in spot["listings"]:
            key = listing["key"]
            assert key.endswith(f"|{spot['isin']}") and listing["at"]["key"]["lex"] == key, key
    assert [w["expect"] for w in manifest["watchlist"]] == WATCHLIST_EXPECT, "watchlist"


def member4(manifest: dict[str, Any], index: int = 0) -> dict[str, Any]:
    return cast(dict[str, Any], manifest["batch"]["members"][index])


def source4(manifest: dict[str, Any], name: str) -> dict[str, Any]:
    return cast(dict[str, Any], member4(manifest)["run"]["comparison"]["sources"][name])


LEDGER4_MUTATIONS: dict[str, Mutation] = {
    "provenance-owner-export": lambda m: m["header"].update(export_provenance="OWNER_EXPORT"),
    "provenance-synthetic": lambda m: m["header"].update(export_provenance="SYNTHETIC-FORMAT"),
    "derived-fixture-removed": lambda m: m["header"].pop("derived_fixture"),
    "fixture-sha256": lambda m: m["header"]["derived_fixture"]["fixture_sha256"].update(
        {"screener.csv": "0" * 64}
    ),
    "rows-kept": lambda m: m["header"]["derived_fixture"]["rows_kept"]["TIJORI"].update(kept=4),
    "rows-kept-emptied": lambda m: m["header"]["derived_fixture"].update(rows_kept={}),
    "rows-kept-false-original": lambda m: m["header"]["derived_fixture"]["rows_kept"][
        "TIJORI"
    ].update(of=375),
    "source-capture-not-hex": lambda m: m["header"]["derived_fixture"]["source_captures"][0].update(
        sha256="z" * 64
    ),
    "tijori-listing-isin": lambda m: m["screen"]["tijori"][0]["expect"]["listing"].update(
        isin="INE280A01028"
    ),
    "tijori-data-index-1-based": lambda m: m["screen"].update(
        tijori=[r | {"data_index": r["data_index"] + 1} for r in m["screen"]["tijori"]]
    ),
    "review-item-added": lambda m: m["screen"]["review_items"].append({"kind": "ABSENT"}),
    "others-incomplete": lambda m: m["batch"].update(others=["THERMAX"]),
    "outcome-onboarded": lambda m: member4(m).update(outcome="ONBOARDED"),
    "unit-unverified": lambda m: member4(m)["units"]["SCREENER"].update(state="UNVERIFIED"),
    "run-status-complete": lambda m: member4(m)["run"].update(status="COMPLETE"),
    "run-entity-swapped": lambda m: member4(m)["run"].update(entity="TITAN"),
    "run-input-sha256": lambda m: member4(m)["run"]["inputs"].update(
        {"tijori/financials": "0" * 64}
    ),
    "inventory-source-dropped": lambda m: member4(m)["run"]["comparison"]["sources"].pop(
        "tijori/financials"
    ),
    "inventory-xbrl-emptied": lambda m: source4(m, "xbrl").update(value={}),
    "inventory-count": lambda m: source4(m, "xbrl")["counts"].update(value=1),
    "inventory-value-outside-sides": lambda m: source4(m, "tijori/financials")["value"]["Q"].append(
        "total_income"
    ),
    "gate-removed": lambda m: member4(m)["gates"].pop("TIJORI"),
    "gate-page-id": lambda m: member4(m)["gates"]["SCREENER"]["identity"][1].update(lex="1"),
    "watchlist-expect": lambda m: m["watchlist"][0].update(expect="ACCEPTED"),
    "registry-replay-created": lambda m: m["registry"]["loads"][1].update(created=True),
}
