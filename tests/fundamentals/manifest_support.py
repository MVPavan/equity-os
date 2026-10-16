"""Ledger manifest claim checks: each claim field bound to its source lexeme (D3 D6, D4 M9)."""

from __future__ import annotations

import copy
import hashlib
import json
import re
from collections.abc import Callable
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any, cast

import yaml
from lxml import etree  # type: ignore[import-untyped]
from stage4_support import CONSOLIDATED, FINANCIALS, UPSTOX, need, period_end, quarter_ends

from fundamentals.compare.run_models import RunExitStatus
from fundamentals.contracts.basis_status import BasisStatus
from fundamentals.contracts.observation import AccountingFramework
from fundamentals.contracts.onboarding import (
    ANCHOR_UNITS,
    ONBOARDING_VERSIONS,
    UNIT_SURFACES,
    OnboardingReason,
    VerificationState,
    VerificationUnit,
)

# Oracle-owned copy of the Task 0b framework rule (d6-capability.md §3); deliberately not
# imported from entity.verification, so a wrong rule in src cannot agree with itself.
ENTRY_POINT_PREFIX = "in-capmkt-ent-"
IND_AS_ENTRY_POINT = re.compile(
    rb"^http://www\.sebi\.gov\.in/xbrl/IntegratedFinance_IndAS/\d{4}-\d{2}-\d{2}"
    rb"/in-capmkt/in-capmkt-ent$"
)

CONTRACT_FIELDS = ("metric", "scope", "horizon", "unit", "constant_currency")  # plan D4 M9
MKEY_FIELDS = {  # contracts.measurement_key.MeasurementKey
    *("entity_id", "canonical_id", "period", "basis", "framework"),
    *("currency", "value_kind", "dimensions"),
}
LEDGERS = ("LEDGER1", "LEDGER2")  # ledger Stage 3 sources: imported, then corrective versions
REPORT = ("stock", "period", "kind")
MODE = ("mode", "creator")
ITEM = ("kind", "stock", "statement", "epistemic_class", "valid_from", "valid_to")
FLAGS = {"flags": "flags"}
IMPORTED_VALIDATION = {"mode": "RETROSPECTIVE", "creator": "PANEL"}  # ledger/importer.py
READER_VIEWS = ("eqos.report_status_view", "eqos.promoted_memory_view")  # migrations/0021
REFUSED_OPS = ["INSERT", "UPDATE", "DELETE"]
Mutation = Callable[[dict[str, Any]], None]
SCHEMA_REF = "{http://www.xbrl.org/2003/linkbase}schemaRef"
XLINK_HREF = "{http://www.w3.org/1999/xlink}href"


def failure_surface(failure: str) -> str:
    """An operational failure's representation (``compare/run.py`` ``_FAILURE``), or a vendor
    name, without its ``:<schema>`` surface suffix (``vendor_sides.py``)."""
    return failure.partition("\t")[0].partition(":")[0]


def expected_status(run: dict[str, Any]) -> tuple[str, int]:
    """(status, exit) as ``compare/run.py`` assigns them: INCOMPLETE iff a non-diagnostic
    operational failure is listed, else whether an open HIGH item exists."""
    vendors = run["source_vector"]["vendors"]
    diagnostic = {failure_surface(v) for v, spec in vendors.items() if spec["role"] == "DIAGNOSTIC"}
    if {failure_surface(f) for f in run.get("operational_failures", [])} - diagnostic:
        return "INCOMPLETE", RunExitStatus.INCOMPLETE
    high = run["counts"]["queue"].get("HIGH")
    return "COMPLETE", RunExitStatus.SUCCESS_WITH_OPEN_HIGH if high else RunExitStatus.SUCCESS


def xml_refs(data: bytes) -> dict[str, list[str]]:
    """An XBRL instance's ``schemaRef`` hrefs and root namespace declarations (shape xml_ref)."""
    root = etree.fromstring(data)
    hrefs = [ref.get(XLINK_HREF) for ref in root.iter(SCHEMA_REF)]
    return {"schemaRef": hrefs, "namespace": list(root.nsmap.values())}


def check_ledger_claims(manifest: dict[str, Any]) -> None:
    """Every claim's value or bounds, source SHA-256 and quote (and any other bound field) equal
    the lexemes its locators name, and each alias equals the claim (plan D6). A FIGURE's or
    CALCULATION's canonical id is a located lexeme (a mapping entry's, plus its change suffix)."""
    checked = 0
    for version in manifest["versions"]:
        for claim in version["claims"]:
            values = {"lo", "hi"} if "lo" in claim else {"v"}
            cited = {
                "FIGURE": {"source_sha256", "canonical_id"},
                "CALCULATION": {"canonical_id"},
                "SOURCE_QUOTE": {"source_sha256", "quote"},
            }
            assert values | cited.get(claim["kind"], set()) <= claim["from"].keys(), claim["key"]
            if "canonical_id" in claim["from"]:
                key = claim["mkey"]
                assert key.keys() == MKEY_FIELDS and not key["dimensions"], claim["key"]
                assert (key["currency"], key["value_kind"]) == (
                    claim["currency"],
                    claim["value_kind"],
                ), claim["key"]
            for binding in [claim["from"], *claim.get("aliases", [])]:
                for name, loc in binding.items():
                    assert loc.keys() in ({"src", "line", "lex"}, {"src", "path", "lex"}), loc
                    if name == "canonical_id":
                        parts = [loc["lex"], claim.get("change")]
                        assert claim["mkey"][name] == ".".join(filter(None, parts)), claim["key"]
                    elif name == "native_field":
                        entry = binding["canonical_id"]["path"].removesuffix(".canonical_id")
                        assert loc["path"] == f"{entry}.selector.native_field", claim["key"]
                        assert claim["concept"].partition(":")[2] == loc["lex"], claim["key"]
                    elif name in ("v", "lo", "hi"):
                        assert Decimal(claim[name]) == Decimal(loc["lex"]), (claim["key"], name)
                    else:
                        assert str(claim[name]) == loc["lex"], (claim["key"], name)
            checked += 1
    assert checked == manifest["header"]["size"]["claims"]


def check_ledger(manifest: dict[str, Any]) -> None:
    """The claim check, and for Stage 2 each quote claim's whole guidance contract bound to the
    management ledger and its capture's bytes being the cited ones (plan D4 M9)."""
    check_ledger_claims(manifest)
    if manifest["header"]["manifest"] != "ledger_stage2":
        return
    hashes = {s["label"]: s["sha256"] for s in manifest["header"]["sources"]}
    for version in manifest["versions"]:
        for claim in version["claims"]:
            bound = {name: claim["from"].get(name, {}).get("src") for name in CONTRACT_FIELDS}
            assert bound == dict.fromkeys(CONTRACT_FIELDS, "MLEDGER"), claim["key"]
            assert hashes[claim["capture"]] == claim["source_sha256"], claim["key"]


def check_ledger_stage3(manifest: dict[str, Any], value_at: Callable[[str, str], Any]) -> None:
    """Every copied expectation equals the Stage 1/2 manifest value its locator names, every
    derived one its header rule; the inventories are the Stage 2 end state's (plan D5 Task 4)."""

    def loc(src: str, path: str) -> dict[str, str]:
        return {"src": src, "path": path, "lex": str(value_at(src, path))}

    def base(entry: dict[str, Any]) -> tuple[str, str]:
        return entry["source"]["src"], entry["source"]["path"].removesuffix(".id")

    files, memory, reader = manifest["files"], manifest["memory"], manifest["reader"]
    status_map = manifest["header"]["status_map"]
    end_state = [
        (s, f"versions[{i}]") for s in LEDGERS for i in range(len(value_at(s, "versions")))
    ]
    assert sorted(map(base, files)) == sorted(end_state)
    assert manifest["header"]["size"]["files"] == len(files)
    by_base = {base(entry): entry for entry in files}
    position: dict[str, int] = {}
    for entry in files:
        src, at = base(entry)
        assert entry["source"] == loc(src, f"{at}.id")
        assert entry["report_at"] == {k: loc(src, f"{at}.report.{k}") for k in REPORT}
        assert entry["report"] == {k: entry["report_at"][k]["lex"] for k in REPORT}
        count = len(value_at(src, f"{at}.decisions"))
        assert entry["decisions_at"] == [loc(src, f"{at}.decisions[{n}]") for n in range(count)]
        assert entry["decisions"] == [d["lex"] for d in entry["decisions_at"]]
        claims = value_at(src, f"{at}.claims")
        assert entry["untrusted"] == [
            {"key": c["key"], "state": c["state"], "at": loc(src, f"{at}.claims[{j}].state")}
            for j, c in enumerate(claims)
            if c["state"] != "MATCH"
        ]
        status_at = f"{at}.status"
        if src == LEDGERS[0]:  # rules stem and imported_validation
            assert entry["decisions"][0] == "IMPORT_SEAL"
            assert entry["validation"] == IMPORTED_VALIDATION
            assert entry["derived"] == {
                "stem": "stem",
                "validation": "imported_validation",
                **FLAGS,
            }
            position[entry["stem"]] = 1
            successors = [b for b, e in by_base.items() if e.get("predecessor") == entry["stem"]]
            if successors:
                ((src, succ),) = successors
                status_at = f"{succ}.predecessor.status_after"
        else:
            assert entry["validation_at"] == {k: loc(src, f"{at}.validation.{k}") for k in MODE}
            assert entry["validation"] == {k: entry["validation_at"][k]["lex"] for k in MODE}
            assert entry["derived"] == {"stem": "stem", **FLAGS}
            assert entry["predecessor_at"] == loc(src, f"{at}.predecessor.period")
            period, kind = entry["predecessor_at"]["lex"], entry["report"]["kind"]
            (pred,) = [
                e
                for e in files
                if (e["report"]["period"], e["report"]["kind"]) == (period, kind)
                and e["source"]["src"] == LEDGERS[0]
            ]
            assert entry["predecessor"] == pred["stem"]
            position[entry["stem"]] = 2  # its predecessor is a root (n = 1)
        assert entry["status_at"] == loc(src, status_at)
        assert entry["status"] == entry["status_at"]["lex"]
    for entry in files:  # rule stem (positions), rule status_map, rule flags
        report, n = entry["report"], position[entry["stem"]]
        assert entry["stem"] == f"{report['period']}-{report['kind']}-v{n}"
        status = status_map["heads"].get(entry["decisions"][-1], status_map["no_decision"])
        later = [e for e in files if e["report"] == report and position[e["stem"]] > n]
        if status in status_map["superseded"]["from"] and any(
            set(status_map["superseded"]["by"]) & set(e["decisions"]) for e in later
        ):
            status = "SUPERSEDED"
        assert entry["status"] == status, entry["stem"]
        cited = [m for m in memory if any(s["stem"] == entry["stem"] for s in m["supports"])]
        assert entry["flags"] == [m["statement"] for m in cited if m["needs_revalidation"]]
    assert manifest["header"]["size"]["untrusted"] == sum(len(e["untrusted"]) for e in files)
    retrievals = value_at(LEDGERS[1], "retrievals")
    (promoted,) = [
        i
        for i, r in enumerate(retrievals)
        if (r["after"], r["statuses"], r["cutoff"]) == ("promote", ["PROMOTED"], None)
    ]
    item = {k: loc(LEDGERS[1], f"item.{k}") for k in ITEM}
    flag = loc(LEDGERS[1], f"retrievals[{promoted}].expect[0].needs_revalidation")
    stems = {e["source"]["lex"]: e["stem"] for e in files if e["source"]["src"] == LEDGERS[1]}
    supports = value_at(LEDGERS[1], "item.supports")
    expected = {k: value_at(LEDGERS[1], f"item.{k}") for k in ITEM} | {
        "needs_revalidation": value_at(LEDGERS[1], flag["path"]),
        "at": item | {"needs_revalidation": flag},
        "supports": [
            {
                "stem": stems[s["version"]],
                "claim": s["claim"],
                "at": {k: loc(LEDGERS[1], f"item.supports[{j}].{k}") for k in ("version", "claim")},
            }
            for j, s in enumerate(supports)
        ],
    }
    assert memory == [expected] and manifest["header"]["size"]["memory"] == len(memory)
    assert reader["report_status_view"] == [
        {
            **e["report"],
            "version": f"v{position[e['stem']]}",
            "status": e["status"],
            "mode": e["validation"]["mode"],
            "untrusted": len(e["untrusted"]),
        }
        for e in files
    ]
    assert reader["promoted_memory_view"] == [{k: m[k] for k in ITEM} for m in memory]
    names = [
        v["at"]["lex"].removeprefix("CREATE VIEW ").removesuffix(" AS") for v in reader["views"]
    ]
    assert names == [v["name"] for v in reader["views"]] == list(READER_VIEWS)
    assert reader["refused"] == [
        {"target": t, "ops": REFUSED_OPS} for t in [*READER_VIEWS, "eqos.decisions"]
    ]
    rules = manifest["header"].get("rules", {})
    assert all(rules.get(r) for e in files for r in e["derived"].values())  # named rules declared
    assert manifest["header"]["vault_in_scope"] is False and manifest["vault"] == []


def payload_sha256(content: bytes) -> str:
    """sha256 of the manifest without its one header approval line (header.notation.approval)."""
    lines = content.splitlines(keepends=True)
    (index,) = [i for i, line in enumerate(lines) if line.startswith(b"  approval:")]
    return hashlib.sha256(b"".join(lines[:index] + lines[index + 1 :])).hexdigest()


def stage3_file(manifest: dict[str, Any], stem: str) -> dict[str, Any]:
    (found,) = [f for f in manifest["files"] if f["stem"] == stem]
    return cast(dict[str, Any], found)


def drop_version(manifest: dict[str, Any]) -> None:
    """FY26_Q4 dropped from the files and, consistently, from the reader rows."""
    manifest["files"].remove(stage3_file(manifest, "FY26_Q4-EARNINGS_UPDATE-v1"))
    manifest["reader"]["report_status_view"] = [
        row for row in manifest["reader"]["report_status_view"] if row["period"] != "FY26_Q4"
    ]
    manifest["header"]["size"]["files"] -= 1


LEDGER3_MUTATIONS: dict[str, Mutation] = {
    "status-changed-locator-intact": lambda m: stage3_file(m, "FY27_Q1-EARNINGS_UPDATE-v1").update(
        status="HISTORICAL"
    ),
    "version-dropped": drop_version,
    "view-deleted-with-refusals": lambda m: [
        m["reader"][k].pop(i) for k, i in (("views", 1), ("refused", 1))
    ],
    "view-duplicated-with-refusals": lambda m: m["reader"].update(
        views=m["reader"]["views"][:1] * 2,
        refused=m["reader"]["refused"][:1] * 2 + m["reader"]["refused"][2:],
    ),
    "rules-removed": lambda m: m["header"].pop("rules"),
}


# --- Stage 4 manifest oracle (plan T5a) ------------------------------------------------------

LISTING = "nse_listing"  # header source kind of the two pinned NSE listing files
Locators = list[dict[str, Any]]


def one(values: set[Any]) -> Any:
    """The single value every located lexeme yields, else None."""
    return next(iter(values)) if len(values) == 1 else None


def framework_of_entry_point(locators: Locators) -> str | None:
    """IND_AS iff every located ``schemaRef`` file name has the pinned ``in-capmkt-ent-`` prefix
    and every located namespace is the IntegratedFinance_IndAS entry point; the file name alone
    also matches bank and NBFC filings (``entity/verification.py`` pins, Task 0b §2-3)."""
    hrefs = [loc["lex"] for loc in locators if loc["ref"] == "schemaRef"]
    spaces = [loc["lex"] for loc in locators if loc["ref"] == "namespace"]
    names = (href.rsplit("/", 1)[-1] for href in hrefs)
    held = all(name.startswith(ENTRY_POINT_PREFIX) for name in names) and all(
        IND_AS_ENTRY_POINT.match(space.encode()) for space in spaces
    )
    return AccountingFramework.IND_AS.value if hrefs and spaces and held else None


TRANSFORMS: dict[str, Callable[[Locators], Any]] = {  # the closed set
    "identity": lambda locs: one({loc["lex"] for loc in locs}),
    "month_of_date": lambda locs: one({date.fromisoformat(loc["lex"]).month for loc in locs}),
    "basis_of_inventory": lambda locs: (
        (
            BasisStatus.CONSOLIDATED_AND_STANDALONE
            if any(loc["lex"] == CONSOLIDATED for loc in locs)
            else BasisStatus.STANDALONE_ONLY
        ).value
    ),
    "framework_of_entry_point": framework_of_entry_point,
}


XBRL = "xbrl"  # header source kind of a retained filing instance
VALUE_RULES = {  # the complete inventory: name -> (transform, located field) (T5a, D5)
    "SYMBOL": ("identity", "Symbol"),
    "ISIN": ("identity", "ISIN"),
    "BSE_SCRIP": ("identity", "ScripCode"),
    "NAME": ("identity", "NameOfTheCompany"),
    "FISCAL_YEAR_END": ("month_of_date", "DateOfEndOfFinancialYear"),
    "PRESENTATION_CURRENCY": ("identity", "DescriptionOfPresentationCurrency"),
    "ROUNDING_LEVEL": ("identity", "LevelOfRounding"),
    "REPORTING_FRAMEWORK": ("framework_of_entry_point", "schemaRef namespace"),
    "BASIS_STATUS": ("basis_of_inventory", "consolidated"),
}
PDF_VERDICT = (VerificationState.UNAVAILABLE, OnboardingReason.EXCLUDED_BY_RULE)  # R-PDF
EXCLUDED_REASONS: dict[str, set[str] | None] = {  # a PARTIAL attempt's excluded vendor (D4.3)
    VerificationState.UNAVAILABLE: {OnboardingReason.NO_CANDIDATE, OnboardingReason.ACCESS_FAILED},
    VerificationState.NOT_AUTHORISED: {OnboardingReason.NOT_AUTHORISED},
    VerificationState.UNVERIFIED: None,  # any recorded reason, e.g. a basis gate's own code
}


def check_unit(name: str, unit: dict[str, Any], excluded: list[str]) -> None:
    """The unit's exact verdict: R-PDF's for ``RESULTS_PDF``; ``VERIFIED`` without a reason
    unless predicted excluded; else a non-anchor state a ``PARTIAL`` outcome permits, with a
    reason it permits."""
    state, reason = unit["state"], unit.get("reason")
    if name == VerificationUnit.RESULTS_PDF:
        need((state, reason) == PDF_VERDICT, f"{name} verdict")
    elif name not in excluded:
        need((state, reason) == (VerificationState.VERIFIED, None), f"{name} verdict")
    else:
        allowed = EXCLUDED_REASONS.get(state, set())
        permitted = (
            isinstance(reason, str) and bool(reason) and (allowed is None or reason in allowed)
        )
        need(
            name not in ANCHOR_UNITS and state in EXCLUDED_REASONS and permitted, f"{name} verdict"
        )


def check_value(
    repo: Path, manifest: dict[str, Any], node: dict[str, Any], attempt: dict[str, Any]
) -> None:
    """One onboarding value: its name's transform, every locator at its name's field, the
    filing values covering every retained filing, the symbol the current attempt's."""
    name, locators = node["name"], node["at"]
    transform, field = VALUE_RULES[name]
    need(node["transform"] == transform, f"{name} transform")
    got = TRANSFORMS[transform](locators)
    need(got is not None and str(got) == str(node["v"]), f"value {name}")
    if transform == "basis_of_inventory":
        located = {(loc["src"], loc["path"]) for loc in locators}
        as_of = date.fromisoformat(node["as_of"]["lex"])
        need(located == basis_rows(repo, manifest, as_of), "basis inventory")
        return
    filings = {s["label"] for s in manifest["header"]["sources"] if s["kind"] == XBRL}
    key = "ref" if transform == "framework_of_entry_point" else "c"
    at_field = all(loc.get(key) in field.split() for loc in locators)
    need(at_field and {loc["src"] for loc in locators} == filings != set(), f"{name} locators")
    need(name != "SYMBOL" or node["v"] == attempt["identifier"], "identifier")


def basis_rows(repo: Path, manifest: dict[str, Any], as_of: date) -> set[tuple[str, str]]:
    """(label, path) of the basis lexeme of every window row (D1.3) of both listing files."""
    listings = {
        s["label"]: s["path"] for s in manifest["header"]["sources"] if s["kind"] == LISTING
    }
    need(len(listings) == 2, "listing sources")
    window, found = quarter_ends(as_of), set()
    for label, path in listings.items():
        doc = json.loads((repo / path).read_bytes())
        rows, prefix = (doc["data"], "data") if isinstance(doc, dict) else (doc, "")
        found |= {
            (label, f"{prefix}[{i}].consolidated")
            for i, row in enumerate(rows)
            if row.get("consolidated") and period_end(row) in window
        }
    return found


def check_stage4(
    repo: Path, manifest: dict[str, Any], attempt: dict[str, Any], freeze: dict[str, Any]
) -> None:
    """The Stage 4 manifest against the current attempt's prediction, its freeze entry and
    ``ONBOARDING_VERSIONS``; each unit's exact verdict; operational failures projected to the
    non-diagnostic excluded units' surfaces; the complete value inventory, each value equal to
    its located lexemes after its name's transform. Lexemes at their locators are
    ``check_locator``'s; failures name the step only (D1.7)."""
    onboarding, prediction, (run,) = manifest["onboarding"], attempt["prediction"], manifest["runs"]
    versions = ONBOARDING_VERSIONS.model_dump(exclude_defaults=True)
    need(manifest["header"]["onboarding_versions"] == versions, "onboarding_versions")
    need(freeze["attempt"] == attempt["n"], "freeze attempt")
    need(freeze["onboarding_versions"] == versions, "freeze onboarding_versions")
    units = onboarding["units"]
    need(units.keys() == set(VerificationUnit), "units")
    excluded = sorted(u for u, unit in units.items() if unit["state"] != VerificationState.VERIFIED)
    need(excluded == sorted(onboarding["excluded_units"]), "excluded_units")
    need(excluded == sorted(prediction["excluded_units"]), "unit states")
    need(onboarding["outcome"] == prediction["outcome"], "outcome")
    need(run["status"] == prediction["run_status"], "run_status")
    for name, unit in units.items():
        check_unit(name, unit, prediction["excluded_units"])
    surfaces = {UNIT_SURFACES[VerificationUnit(u)] for u in excluded if u != UPSTOX}
    failed = {failure_surface(f) for f in run.get("operational_failures", [])}
    need(failed == surfaces, "operational failures")
    names = sorted(node["name"] for node in onboarding["values"])
    need(names == sorted(VALUE_RULES), "value inventory")
    for node in onboarding["values"]:
        check_value(repo, manifest, node, attempt)


# Synthetic Stage 4 cases over a development company (Apar), files under ``tmp_path``.
DEV_SYMBOL, DEV_ISIN = "APARINDS", "INE372A01015"  # config/identity/aparinds.yaml
ENTRY = "http://www.sebi.gov.in/xbrl/IntegratedFinance_IndAS/2026-01-31/in-capmkt/in-capmkt-ent"
HREF = "in-capmkt-ent-2026-01-31.xsd"
INSTANCE = f"""<xbrli:xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance"
 xmlns:link="http://www.xbrl.org/2003/linkbase" xmlns:xlink="http://www.w3.org/1999/xlink"
 xmlns:in-capmkt="http://www.sebi.gov.in/xbrl/2026-01-31/in-capmkt" xmlns:in-capmkt-ent="{ENTRY}">
<link:schemaRef xlink:type="simple" xlink:href="{HREF}"/>
<xbrli:context id="c1"><xbrli:period><xbrli:instant>2026-06-30</xbrli:instant></xbrli:period>
</xbrli:context>
<in-capmkt:DateOfEndOfFinancialYear contextRef="c1">2027-03-31</in-capmkt:DateOfEndOfFinancialYear>
<in-capmkt:Symbol contextRef="c1">APARINDS</in-capmkt:Symbol>
<in-capmkt:ISIN contextRef="c1">INE372A01015</in-capmkt:ISIN>
<in-capmkt:ScripCode contextRef="c1">532259</in-capmkt:ScripCode>
<in-capmkt:NameOfTheCompany contextRef="c1">APAR INDUSTRIES LIMITED</in-capmkt:NameOfTheCompany>
<in-capmkt:DescriptionOfPresentationCurrency contextRef="c1">INR\
</in-capmkt:DescriptionOfPresentationCurrency>
<in-capmkt:LevelOfRounding contextRef="c1">Crores</in-capmkt:LevelOfRounding>
</xbrli:xbrl>"""
LISTED = {"symbol": DEV_SYMBOL, "type": FINANCIALS, "broadcast_Date": "24-Jul-2026 18:34:26"}
INTEGRATED = {
    "data": [
        LISTED | {"qe_Date": "30-Jun-2026", "consolidated": CONSOLIDATED},
        LISTED | {"qe_Date": "30-Jun-2026", "consolidated": "Non-Consolidated"},
        LISTED | {"qe_Date": "30-Jun-2026", "type": "Integrated Filing- Governance"},
        LISTED | {"qe_Date": "31-Mar-2023", "consolidated": CONSOLIDATED},  # before the window
    ]
}
LEGACY = [{"symbol": DEV_SYMBOL, "toDate": "31-Mar-2026", "consolidated": "Non-Consolidated"}]
EXCLUSIONS = {  # R-PDF always excludes RESULTS_PDF
    "pdf-only": ["RESULTS_PDF"],
    "upstox-diagnostic": ["RESULTS_PDF", "UPSTOX"],
    "mixed": ["RESULTS_PDF", "TIJORI", "UPSTOX"],
}
VERDICTS = {  # an excluded unit's (state, reason)
    "RESULTS_PDF": ("UNAVAILABLE", "EXCLUDED_BY_RULE"),
    "TIJORI": ("UNAVAILABLE", "ACCESS_FAILED"),
    "UPSTOX": ("UNVERIFIED", "BASIS_UNVERIFIED"),
}
FAILURES = {
    "RESULTS_PDF": "PDF\tEXCLUDED_BY_RULE\tattempt=7",
    "TIJORI": "tijori/financials\t-\tattempt=-",
}
VERSIONS = {"dictionary": "v2", "mapping_set": "v5"}
FACT = "{src: INSTANCE, c: %s, ctx: c1, u: null, d: null, per: '2026-06-30', lex: '%s'}"
VALUES = (
    f"""
- {{name: SYMBOL, transform: identity, v: APARINDS, at: [{FACT % ("Symbol", "APARINDS")}]}}
- {{name: ISIN, transform: identity, v: INE372A01015, at: [{FACT % ("ISIN", "INE372A01015")}]}}
- {{name: BSE_SCRIP, transform: identity, v: '532259', at: [{FACT % ("ScripCode", "532259")}]}}
- {{name: NAME, transform: identity, v: APAR INDUSTRIES LIMITED,
   at: [{FACT % ("NameOfTheCompany", "APAR INDUSTRIES LIMITED")}]}}
- {{name: PRESENTATION_CURRENCY, transform: identity, v: INR,
   at: [{FACT % ("DescriptionOfPresentationCurrency", "INR")}]}}
- {{name: ROUNDING_LEVEL, transform: identity, v: Crores,
   at: [{FACT % ("LevelOfRounding", "Crores")}]}}
- {{name: FISCAL_YEAR_END, transform: month_of_date, v: 3,
   at: [{FACT % ("DateOfEndOfFinancialYear", "2027-03-31")}]}}
"""
    + """
- {name: REPORTING_FRAMEWORK, transform: framework_of_entry_point, v: IND_AS, at: [
   {src: INSTANCE, ref: schemaRef, lex: in-capmkt-ent-2026-01-31.xsd},
   {src: INSTANCE, ref: namespace, lex: '%(entry)s'}]}
- {name: BASIS_STATUS, transform: basis_of_inventory, v: CONSOLIDATED_AND_STANDALONE,
   as_of: {src: DISCOVERY, path: as_of, lex: '2026-08-01'}, at: [
   {src: INTEGRATED, path: 'data[0].consolidated', lex: Consolidated},
   {src: INTEGRATED, path: 'data[1].consolidated', lex: Non-Consolidated},
   {src: LEGACY, path: '[0].consolidated', lex: Non-Consolidated}]}
"""
)


def stage4_case(name: str, root: Path, run: dict[str, Any]) -> dict[str, Any]:
    """A synthetic Stage 4 manifest, attempt and freeze entry, consistent for the case's
    exclusion set and then mutated; its Stage 1-schema run a copy of a development run carrying
    the excluded failures; ``check`` runs ``check_stage4`` on it, ``fails`` names the checks that
    must refuse (``run`` = ``check_run``)."""
    base, mutate, fails = STAGE4_CASES[name]
    files = {
        "INSTANCE": ("instance.xml", "xbrl", INSTANCE.encode()),
        "INTEGRATED": ("integrated.json", LISTING, json.dumps(INTEGRATED).encode()),
        "LEGACY": ("legacy.json", LISTING, json.dumps(LEGACY).encode()),
        "DISCOVERY": ("discovery.json", "json", b'{"as_of": "2026-08-01"}'),
    }
    for file, _, data in files.values():
        (root / file).write_bytes(data)
    excluded = EXCLUSIONS[base]
    failures = [FAILURES[u] for u in excluded if u in FAILURES]
    values = yaml.safe_load(VALUES % {"entry": ENTRY})
    sources = [
        {"label": label, "path": str(root / file), "kind": kind}
        for label, (file, kind, _) in files.items()
    ]
    manifest = {
        "header": {"manifest": "stage4", "onboarding_versions": dict(VERSIONS), "sources": sources},
        "onboarding": {
            "outcome": "PARTIAL",
            "excluded_units": list(excluded),
            "units": {
                u: dict(zip(("state", "reason"), VERDICTS[u], strict=True))
                if u in excluded
                else {"state": "VERIFIED"}
                for u in VerificationUnit
            },
            "values": values,
        },
        "runs": [
            copy.deepcopy(run)
            | {"operational_failures": failures, "status": "INCOMPLETE", "exit": 4}
        ],
    }
    prediction = {
        "outcome": "PARTIAL",
        "excluded_units": list(excluded),
        "diagnostic_excluded": [u for u in excluded if u == UPSTOX],
        "run_status": "INCOMPLETE" if set(excluded) - {UPSTOX} else "COMPLETE",
    }
    attempt = {"n": 1, "identifier": DEV_SYMBOL, "prediction": prediction}
    freeze = {"attempt": 1, "onboarding_versions": dict(VERSIONS)}
    case = {"root": root, "manifest": manifest, "attempt": attempt, "freeze": freeze}
    mutate(case)
    return case | {"fails": fails, "check": lambda: check_stage4(root, manifest, attempt, freeze)}


def value_node(case: dict[str, Any], name: str) -> dict[str, Any]:
    """One onboarding value of a case."""
    (node,) = [n for n in values_of(case) if n["name"] == name]
    return node


def banking(case: dict[str, Any]) -> None:
    """The filing re-declared under IntegratedFinance_Banking: same xsd file name (Task 0b §2)."""
    instance = case["root"] / "instance.xml"
    instance.write_text(instance.read_text().replace("_IndAS/", "_Banking/"))
    for loc in value_node(case, "REPORTING_FRAMEWORK")["at"]:
        loc["lex"] = loc["lex"].replace("_IndAS/", "_Banking/")


def values_of(case: dict[str, Any]) -> list[dict[str, Any]]:
    """The case's onboarding values."""
    return cast(list[dict[str, Any]], case["manifest"]["onboarding"]["values"])


def unit_of(case: dict[str, Any], unit: str) -> dict[str, Any]:
    """One unit's verdict of a case."""
    return cast(dict[str, Any], case["manifest"]["onboarding"]["units"][unit])


def run_of_case(case: dict[str, Any]) -> dict[str, Any]:
    """The case's one run."""
    return cast(dict[str, Any], case["manifest"]["runs"][0])


UPSTOX_FAILURE = "upstox/income-statement:upstox-income-statement-summary-v2\t-\tattempt=-"
STAGE4_CASES: dict[str, tuple[str, Callable[[dict[str, Any]], Any], set[str]]] = {
    # name: (exclusion set, mutation, the checks that must refuse)
    **{base: (base, lambda case: None, set()) for base in EXCLUSIONS},
    "incomplete-to-complete": (
        "pdf-only",
        lambda case: run_of_case(case).update(status="COMPLETE", exit=3),
        {"run", "stage4"},
    ),
    "upstox-failure-projected": (
        "upstox-diagnostic",
        lambda case: run_of_case(case)["operational_failures"].append(UPSTOX_FAILURE),
        {"stage4"},
    ),
    "mixed-failure-dropped": (
        "mixed",
        lambda case: run_of_case(case)["operational_failures"].pop(),
        {"stage4"},
    ),
    "unit-state-wrong": (
        "pdf-only",
        lambda case: case["manifest"]["onboarding"]["units"]["TIJORI"].update(state="UNVERIFIED"),
        {"stage4"},
    ),
    "basis-wrong": (
        "pdf-only",
        lambda case: value_node(case, "BASIS_STATUS").update(v="STANDALONE_ONLY"),
        {"stage4"},
    ),
    "basis-row-unlocated": (
        "pdf-only",
        lambda case: value_node(case, "BASIS_STATUS")["at"].pop(),
        {"stage4"},
    ),
    "framework-banking-namespace": ("pdf-only", banking, {"stage4"}),
    "onboarding-versions-wrong": (
        "pdf-only",
        lambda case: case["manifest"]["header"]["onboarding_versions"].update(mapping_set="v4"),
        {"stage4"},
    ),
    "values-deleted": ("pdf-only", lambda case: values_of(case).clear(), {"stage4"}),
    "value-duplicated": (
        "pdf-only",
        lambda case: values_of(case).append(copy.deepcopy(value_node(case, "ISIN"))),
        {"stage4"},
    ),
    "framework-as-identity-of-isin": (
        "pdf-only",
        lambda case: value_node(case, "REPORTING_FRAMEWORK").update(
            transform="identity", v=DEV_ISIN, at=copy.deepcopy(value_node(case, "ISIN")["at"])
        ),
        {"stage4"},
    ),
    "currency-at-rounding-field": (
        "pdf-only",
        lambda case: value_node(case, "PRESENTATION_CURRENCY").update(
            v="Crores", at=copy.deepcopy(value_node(case, "ROUNDING_LEVEL")["at"])
        ),
        {"stage4"},
    ),
    "filing-unlocated": (
        "pdf-only",
        lambda case: case["manifest"]["header"]["sources"].append(
            {"label": "OLDER", "path": str(case["root"] / "instance.xml"), "kind": XBRL}
        ),
        {"stage4"},
    ),
    "symbol-not-the-attempts": (
        "pdf-only",
        lambda case: case["attempt"].update(identifier="ZZOTHER"),
        {"stage4"},
    ),
    "pdf-state-conflict": (
        "pdf-only",
        lambda case: unit_of(case, "RESULTS_PDF").update(state="CONFLICT"),
        {"stage4"},
    ),
    "pdf-reason-changed": (
        "pdf-only",
        lambda case: unit_of(case, "RESULTS_PDF").update(reason="ACCESS_FAILED"),
        {"stage4"},
    ),
    "vendor-reason-missing": (
        "mixed",
        lambda case: unit_of(case, "TIJORI").pop("reason"),
        {"stage4"},
    ),
    "vendor-state-conflict": (
        "mixed",
        lambda case: unit_of(case, "TIJORI").update(state="CONFLICT"),
        {"stage4"},
    ),
}
