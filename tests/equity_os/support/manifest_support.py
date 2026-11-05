"""Ledger manifest claim checks: each claim field bound to its source lexeme (D3 D6, D4 M9)."""

from __future__ import annotations

import csv
import gzip
import hashlib
import io
import json
import re
from collections.abc import Callable
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any, cast

import yaml
from lxml import etree, html  # type: ignore[import-untyped]
from moved_support import recorded_path
from stage4_filings import CONSOLIDATED, period_end, qualifying_filings, quarter_ends
from stage4_support import UPSTOX, need

from equity_os.contracts.companies.basis_status import BasisStatus
from equity_os.contracts.companies.onboarding import (
    ANCHOR_UNITS,
    ONBOARDING_VERSIONS,
    UNIT_SURFACES,
    OnboardingReason,
    VerificationState,
    VerificationUnit,
)
from equity_os.contracts.measurement.observation import AccountingFramework
from equity_os.verification.comparison.run_models import RunExitStatus

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


def approved(manifest: bytes, current: bytes) -> None:
    """``manifest`` carries its own dated APPROVE over its own payload, the ``current`` one."""
    approval = yaml.safe_load(manifest)["header"]["approval"]
    assert approval["verdict"] == "APPROVE"
    assert isinstance(approval["date"], date), "an approval records its date (YYYY-MM-DD)"
    assert approval["payload_sha256"] == payload_sha256(manifest), "approval of another payload"
    assert payload_sha256(manifest) == payload_sha256(current), "the payload changed since"


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


def normalise_name(name: str) -> str:
    """The D4.3 pinned name normalisation, restated: casefold, drop ``.`` and ``,``, collapse
    whitespace, trailing ``ltd`` -> ``limited``."""
    folded = " ".join(name.casefold().replace(".", "").replace(",", "").split())
    return re.sub(r"\bltd$", "limited", folded)


TRANSFORMS: dict[str, Callable[[Locators], Any]] = {  # the closed set
    "identity": lambda locs: one({str(loc["lex"]) for loc in locs}),
    "normalised_name": lambda locs: one({normalise_name(loc["lex"]) for loc in locs}),
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
FILINGS = 2  # D4.2 step 3: the latest two qualifying consolidated instances
SETTINGS = ("FISCAL_YEAR_END", "PRESENTATION_CURRENCY", "ROUNDING_LEVEL", "REPORTING_FRAMEWORK")
VALUE_RULES = {  # the complete inventory: name -> (transform, located filing field) (T5a, D5)
    "SYMBOL": ("identity", "Symbol"),
    "ISIN": ("identity", "ISIN"),
    "BSE_SCRIP": ("identity", "ScripCode"),
    "NAME": ("normalised_name", "NameOfTheCompany"),
    "FISCAL_YEAR_END": ("month_of_date", "DateOfEndOfFinancialYear"),
    "PRESENTATION_CURRENCY": ("identity", "DescriptionOfPresentationCurrency"),
    "ROUNDING_LEVEL": ("identity", "LevelOfRounding"),
    "REPORTING_FRAMEWORK": ("framework_of_entry_point", "schemaRef namespace"),
    "BASIS_STATUS": ("basis_of_inventory", "consolidated"),
    "DOCUMENT_URL": ("identity", "url"),  # DOCUMENT_LOCATION of the ingested instance
    "DOCUMENT_SHA256": ("identity", "sha256"),
    "SCREENER_COMPANY_ID": ("identity", ""),  # vendor-own ids: binding locators only
    "SCREENER_WAREHOUSE_ID": ("identity", ""),
    "TIJORI_SLUG": ("identity", ""),
    "TIJORI_COMPANY_ID": ("identity", ""),
}
SURFACE_UNITS = {  # discovery surfaces of the identity bindings and their units (D4.2)
    "EQUITY_L": "EXCHANGE",
    "PEER_SMART_SEARCH": "EXCHANGE",
    "SCREENER_SEARCH": "SCREENER",
    "SCREENER_FINANCIALS": "SCREENER",
    "company_search": "TIJORI",
    "financials": "TIJORI",
    "instruments": "UPSTOX",
}
BINDINGS = {  # binding locator ``fld`` -> (surface, value its ``key`` must be, value it locates)
    "master_isin": ("EQUITY_L", "SYMBOL", "ISIN"),
    "master_name": ("EQUITY_L", "SYMBOL", "NAME"),
    "peer_scrip": ("PEER_SMART_SEARCH", "ISIN", "BSE_SCRIP"),
    "screener_search_id": ("SCREENER_SEARCH", "SYMBOL", "SCREENER_COMPANY_ID"),
    "screener_page_id": ("SCREENER_FINANCIALS", None, "SCREENER_COMPANY_ID"),
    "screener_warehouse_id": ("SCREENER_FINANCIALS", None, "SCREENER_WAREHOUSE_ID"),
    "screener_nse": ("SCREENER_FINANCIALS", None, "SYMBOL"),
    "screener_bse": ("SCREENER_FINANCIALS", None, "BSE_SCRIP"),
    "tijori_search_slug": ("company_search", None, "TIJORI_SLUG"),
    "tijori_page_slug": ("financials", None, "TIJORI_SLUG"),
    "tijori_company_id": ("financials", None, "TIJORI_COMPANY_ID"),
    "tijori_symbol": ("financials", None, "SYMBOL"),
    "upstox_nse_symbol": ("instruments", "ISIN", "SYMBOL"),
    "upstox_bse_token": ("instruments", "ISIN", "BSE_SCRIP"),
}
DISCOVERY = "discovery_manifest"  # header source kind of the discovery generation's manifest
XBRL_SURFACE = "NSE_XBRL_INSTANCE"  # contracts.source_catalog.NSE_XBRL_INSTANCE
PDF_VERDICT = (VerificationState.UNAVAILABLE, OnboardingReason.EXCLUDED_BY_RULE)  # R-PDF
EXCLUDED_REASONS: dict[str, set[str] | None] = {  # a PARTIAL attempt's excluded vendor (D4.3)
    VerificationState.UNAVAILABLE: {OnboardingReason.NO_CANDIDATE, OnboardingReason.ACCESS_FAILED},
    VerificationState.NOT_AUTHORISED: {OnboardingReason.NOT_AUTHORISED},
    VerificationState.UNVERIFIED: None,  # any recorded reason, e.g. a basis gate's own code
}
COMPANY_DETAILS = re.compile(
    rb'<script id="company_details" type="application/json">(.*?)</script>', re.S
)
TIJORI_DETAILS = {"tijori_page_slug": "slug", "tijori_company_id": "company_id"}
SCREENER_IDS = {"screener_page_id": "company", "screener_warehouse_id": "warehouse"}


def read_binding(path: Path, fld: str, key: str | None) -> str:
    """The identity value a binding locator names in its retained bytes, by the D4.3 rule
    restated here: exactly one record (for ``key``), else the unpacking fails."""
    raw = path.read_bytes()
    if fld.startswith("master_"):
        reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
        rows = [{k.strip(): (v or "").strip() for k, v in r.items() if k} for r in reader]
        (row,) = [r for r in rows if r.get("SYMBOL") == key and r.get("SERIES") == "EQ"]
        return row["ISIN NUMBER" if fld == "master_isin" else "NAME OF COMPANY"]
    if fld == "peer_scrip":
        items = re.findall(r"<li\b.*?</li>", json.loads(raw), re.S)
        (item,) = [li for li in items if f"<strong>{key}</strong>" in li]
        (scrip,) = re.findall(r"</strong>(?:&nbsp;|\s)*(\d+)", item)
        return str(scrip)
    if fld == "screener_search_id":
        urls = {f"/company/{key}/", f"/company/{key}/consolidated/"}
        (found,) = [
            i["id"] for i in json.loads(raw) if i.get("id") is not None and i["url"] in urls
        ]
        return str(found)
    if fld == "tijori_search_slug":
        (slug,) = [item["slug"] for item in json.loads(raw) if item.get("type") == "companies"]
        return str(slug)
    if fld.startswith("upstox_"):
        segment, column = {
            "upstox_nse_symbol": ("NSE_EQ", "trading_symbol"),
            "upstox_bse_token": ("BSE_EQ", "exchange_token"),
        }[fld]
        rows = json.loads(gzip.decompress(raw))
        (row,) = [r for r in rows if r.get("isin") == key and r.get("segment") == segment]
        return str(row[column])
    if fld.startswith("tijori_"):
        (island,) = COMPANY_DETAILS.findall(raw)
        return str(json.loads(island)[TIJORI_DETAILS.get(fld, "symbol")])
    root = html.fromstring(raw)
    if fld in SCREENER_IDS:
        (value,) = set(root.xpath(f"//@data-{SCREENER_IDS[fld]}-id"))
        return str(value)
    spans = " ".join(span.text_content() for span in root.xpath("//*[@id='top']//span"))
    exchange = "NSE" if fld == "screener_nse" else "BSE"
    (code,) = {v for ex, v in re.findall(r"\b(BSE|NSE):\s*(\S+)", spans) if ex == exchange}
    return str(code)


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


class Retained:
    """The manifest's retained sources, its discovery entries and its two filings' periods: the
    latest two the D1.3 filing-window rule selects over both listings at discovery's ``as_of``."""

    def __init__(self, repo: Path, manifest: dict[str, Any]) -> None:
        sources = manifest["header"]["sources"]
        self.paths = {s["label"]: recorded_path(repo, s["path"]) for s in sources}
        found = [s["label"] for s in sources if s["kind"] == DISCOVERY]
        need(len(found) == 1, "discovery source")
        self.discovery = found[0]
        document = json.loads(self.paths[self.discovery].read_bytes())
        self.entries = document["entries"]
        rows = [
            row
            for s in sources
            if s["kind"] == LISTING
            for row in listing_items(json.loads(self.paths[s["label"]].read_bytes()))[0]
        ]
        window = qualifying_filings(rows, date.fromisoformat(document["as_of"])) or {}
        selected = {url: end for end, url in sorted(window.items())[-FILINGS:] if url}
        instances = {e["sha256"]: e["url"] for e in self.ok(XBRL_SURFACE)}
        filings = {s["label"]: self.sha(s["label"]) for s in sources if s["kind"] == XBRL}
        need(len(instances) == len(filings) == len(selected) == FILINGS, "filings")
        need(sorted(filings.values()) == sorted(instances), "filings")
        need(sorted(instances.values()) == sorted(selected), "filing window")
        self.periods = {label: selected[instances[sha]] for label, sha in filings.items()}

    def ok(self, surface: str) -> list[dict[str, Any]]:
        """The generation's successful entries of one surface."""
        return [e for e in self.entries if e["surface"] == surface and e["outcome"] == "OK"]

    def sha(self, label: str) -> str:
        """Hex SHA-256 of one source's bytes."""
        return hashlib.sha256(self.paths[label].read_bytes()).hexdigest()


def check_value(
    repo: Path,
    manifest: dict[str, Any],
    node: dict[str, Any],
    retained: Retained,
    verified: set[str],
    values: dict[str, Any],
) -> None:
    """One onboarding value: its name's transform; its filing locators at its name's field,
    covering every filing (a setting: its own filings, valid from the earliest); a binding
    locator for each identity field of every verified unit, on a successful discovery capture
    and keyed by this issuer's identity."""
    name, locators = node["name"], node["at"]
    transform, field = VALUE_RULES[name]
    need(node["transform"] == transform, f"{name} transform")
    got = TRANSFORMS[transform](locators)
    want = normalise_name(str(node["v"])) if transform == "normalised_name" else str(node["v"])
    need(got is not None and str(got) == want, f"value {name}")
    if transform == "basis_of_inventory":
        located = {(loc["src"], loc["path"]) for loc in locators}
        as_of = date.fromisoformat(node["as_of"]["lex"])
        need(located == basis_rows(repo, manifest, as_of), "basis inventory")
        return
    if name.startswith("DOCUMENT_"):
        check_document(retained, field, locators)
        return
    bound = [loc for loc in locators if "fld" in loc]
    wanted = [f for f, (s, _, n) in BINDINGS.items() if n == name and SURFACE_UNITS[s] in verified]
    need(sorted(loc["fld"] for loc in bound) == sorted(wanted), f"{name} bindings")
    for loc in bound:
        surface, key, _ = BINDINGS[loc["fld"]]
        captured = {e["sha256"] for e in retained.ok(surface)}
        need(retained.sha(loc["src"]) in captured, f"{name} capture")
        need(loc.get("key") == (key and str(values[key])), f"{name} key")
    filed = [loc for loc in locators if "fld" not in loc]
    srcs = {loc["src"] for loc in filed}
    key = "ref" if transform == "framework_of_entry_point" else "c"
    at_field = all(loc.get(key) in field.split() for loc in filed)
    need(at_field and srcs <= retained.periods.keys() and bool(srcs) == bool(field), f"{name} at")
    if name in SETTINGS:
        start = min(retained.periods[src] for src in srcs)
        need(str(node.get("valid_from")) == start.isoformat(), f"{name} valid_from")
    elif field:
        need(srcs == retained.periods.keys(), f"{name} locators")
    need(name != "SYMBOL" or node["v"] == values["SYMBOL"], "identifier")


def check_document(retained: Retained, field: str, locators: Locators) -> None:
    """D5 DOCUMENT_LOCATION: the field of the discovery-manifest entry of the ingested instance,
    the filing of the latest listed period."""
    latest = retained.sha(max(retained.periods, key=retained.periods.__getitem__))
    instances = retained.ok(XBRL_SURFACE)
    (index,) = [
        i for i, e in enumerate(retained.entries) if e in instances and e["sha256"] == latest
    ]
    at = f"entries[{index}].{field}"
    need(
        [(loc["src"], loc["path"]) for loc in locators] == [(retained.discovery, at)],
        "document locator",
    )


def listing_items(doc: Any) -> tuple[list[dict[str, Any]], str]:
    """A listing file's rows and their path prefix (integrated ``data``, legacy a list)."""
    return (doc["data"], "data") if isinstance(doc, dict) else (doc, "")


def basis_rows(repo: Path, manifest: dict[str, Any], as_of: date) -> set[tuple[str, str]]:
    """(label, path) of the basis lexeme of every window row (D1.3) of both listing files."""
    listings = {
        s["label"]: s["path"] for s in manifest["header"]["sources"] if s["kind"] == LISTING
    }
    need(len(listings) == 2, "listing sources")
    window, found = quarter_ends(as_of), set()
    for label, path in listings.items():
        rows, prefix = listing_items(json.loads((repo / path).read_bytes()))
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
    non-diagnostic excluded units' surfaces; the complete value inventory over both filings and
    every verified unit's identity bindings, each value equal to its located lexemes after its
    name's transform. Lexemes at their locators are
    ``check_locator``'s; failures name the step only (D1.7)."""
    onboarding, prediction, (run,) = manifest["onboarding"], attempt["prediction"], manifest["runs"]
    versions = ONBOARDING_VERSIONS.model_dump(exclude_defaults=True)
    need(manifest["header"]["onboarding_versions"] == versions, "onboarding_versions")
    need(freeze["attempt"] == attempt["n"], "freeze attempt")
    frozen_versions = type(ONBOARDING_VERSIONS).model_validate(freeze["onboarding_versions"])
    need(frozen_versions == ONBOARDING_VERSIONS, "freeze onboarding_versions")
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
    verified = {u for u, unit in units.items() if unit["state"] == VerificationState.VERIFIED}
    check_values(repo, manifest, attempt, verified)


def check_values(
    repo: Path, manifest: dict[str, Any], attempt: dict[str, Any], verified: set[str]
) -> None:
    """The complete value inventory (each verified unit's identity ids too), one node per name
    but one per setting value; each setting's nodes partition the two filings; every node
    equal to its located lexemes after its name's transform."""
    retained, nodes = Retained(repo, manifest), manifest["onboarding"]["values"]
    names = [node["name"] for node in nodes]
    required = {n for n, (_, field) in VALUE_RULES.items() if field} | {
        n for s, _, n in BINDINGS.values() if SURFACE_UNITS[s] in verified
    }
    single = all(names.count(n) == 1 for n in names if n not in SETTINGS)
    need(set(names) == required and single, "value inventory")
    latest = max(retained.periods.values())
    need(str(manifest["onboarding"]["period_end"]) == latest.isoformat(), "period end")
    values = {node["name"]: node["v"] for node in nodes} | {"SYMBOL": attempt["identifier"]}
    for node in nodes:
        check_value(repo, manifest, node, retained, verified, values)
    for name in SETTINGS:
        group = [node for node in nodes if node["name"] == name]
        filed = [{loc["src"] for loc in node["at"]} for node in group]
        covered = sum(map(len, filed)) == len(retained.periods) == len(set().union(*filed))
        need(covered and len({str(node["v"]) for node in group}) == len(group), f"{name} periods")
