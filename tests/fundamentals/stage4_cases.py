"""Synthetic Stage 4 manifest cases (plan D6 T5a) over a development company (Apar), files under
``tmp_path``: two filings and every identity binding, consistent for an exclusion set, then
mutated. Synthetic values only; the held-out record and manifest are never read here."""

from __future__ import annotations

import copy
import gzip
import hashlib
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

from manifest_support import (
    BINDINGS,
    DISCOVERY,
    LISTING,
    SURFACE_UNITS,
    XBRL,
    XBRL_SURFACE,
    check_stage4,
)
from stage4_support import CONSOLIDATED, FINANCIALS, UPSTOX

from fundamentals.contracts.onboarding import ONBOARDING_VERSIONS, VerificationUnit

DEV_SYMBOL, DEV_ISIN, DEV_SCRIP = "APARINDS", "INE372A01015", "532259"  # aparinds.yaml
NAME, MASTER_NAME, SLUG = "APAR INDUSTRIES LIMITED", "Apar Industries Limited", "apar-industries"
ENTRY = "http://www.sebi.gov.in/xbrl/IntegratedFinance_IndAS/2026-01-31/in-capmkt/in-capmkt-ent"
HREF = "in-capmkt-ent-2026-01-31.xsd"
FILED = {"INSTANCE": "2026-06-30", "OLDER": "2023-03-31"}  # each filing's listed period end


def instance(period: str, year_end: str, name: str, entry: str = ENTRY) -> bytes:
    """A filing declaring the identity facts and settings at one instant context."""
    facts = {
        "DateOfEndOfFinancialYear": year_end,
        "Symbol": DEV_SYMBOL,
        "ISIN": DEV_ISIN,
        "ScripCode": DEV_SCRIP,
        "NameOfTheCompany": name,
        "DescriptionOfPresentationCurrency": "INR",
        "LevelOfRounding": "Crores",
    }
    body = "".join(f'<c:{k} contextRef="c1">{v}</c:{k}>\n' for k, v in facts.items())
    return f"""<xbrli:xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance"
 xmlns:link="http://www.xbrl.org/2003/linkbase" xmlns:xlink="http://www.w3.org/1999/xlink"
 xmlns:c="http://www.sebi.gov.in/xbrl/2026-01-31/in-capmkt" xmlns:in-capmkt-ent="{entry}">
<link:schemaRef xlink:type="simple" xlink:href="{HREF}"/>
<xbrli:context id="c1"><xbrli:period><xbrli:instant>{period}</xbrli:instant></xbrli:period>
</xbrli:context>
{body}</xbrli:xbrl>""".encode()


LISTED = {"symbol": DEV_SYMBOL, "type": FINANCIALS, "broadcast_Date": "24-Jul-2026 18:34:26"}
XBRL_URL = "https://nsearchives.nseindia.com/corporate/xbrl/APAR_JUN.xml"
OLD_URL = "https://nsearchives.nseindia.com/corporate/xbrl/APAR_OLD.xml"
INTEGRATED = {
    "data": [
        LISTED | {"qe_Date": "30-Jun-2026", "consolidated": CONSOLIDATED, "xbrl": XBRL_URL},
        LISTED | {"qe_Date": "30-Jun-2026", "consolidated": "Non-Consolidated"},
        LISTED | {"qe_Date": "30-Jun-2026", "type": "Integrated Filing- Governance"},
        LISTED | {"qe_Date": "31-Mar-2023", "consolidated": CONSOLIDATED, "xbrl": OLD_URL},
    ]
}
LEGACY = [{"symbol": DEV_SYMBOL, "toDate": "31-Mar-2026", "consolidated": "Non-Consolidated"}]
MASTER = (
    "SYMBOL,NAME OF COMPANY, SERIES, DATE OF LISTING, ISIN NUMBER\n"
    f"{DEV_SYMBOL},{MASTER_NAME},EQ,12-JUL-2004,{DEV_ISIN}\n"
)
PEER = f"<li><a>APAR<br /><span>{DEV_SYMBOL}&nbsp;<strong>{DEV_ISIN}</strong>&nbsp;{DEV_SCRIP}"
SCREENER_PAGE = (
    '<html><body><div id="top" data-company-id="211" data-warehouse-id="6594631">'
    f"<span>BSE:\n {DEV_SCRIP}</span><span>NSE: {DEV_SYMBOL}</span></div></body></html>"
)
TIJORI_DETAILS = {"company_id": 4290, "symbol": DEV_SYMBOL, "slug": SLUG}
TIJORI_PAGE = '<html><script id="company_details" type="application/json">{}</script></html>'


def instruments(isin: str, symbol: str, scrip: str) -> bytes:
    """Upstox's compressed instrument file: one row per venue."""
    rows = [
        {"isin": isin, "segment": "NSE_EQ", "trading_symbol": symbol, "exchange_token": "1"},
        {"isin": isin, "segment": "BSE_EQ", "trading_symbol": symbol, "exchange_token": scrip},
    ]
    return gzip.compress(json.dumps(rows).encode(), mtime=0)


FILES: dict[str, tuple[str, str, str | None]] = {  # label -> (file, kind, discovery surface)
    "INSTANCE": ("instance.xml", XBRL, XBRL_SURFACE),
    "OLDER": ("older.xml", XBRL, XBRL_SURFACE),
    "INTEGRATED": ("integrated.json", LISTING, None),
    "LEGACY": ("legacy.json", LISTING, None),
    "MASTER": ("master.csv", "csv", "EQUITY_L"),
    "PEER": ("peer.json", "json", "PEER_SMART_SEARCH"),
    "SCREENER_SEARCH": ("screener_search.json", "json", "SCREENER_SEARCH"),
    "SCREENER_PAGE": ("screener.html", "html", "SCREENER_FINANCIALS"),
    "TIJORI_SEARCH": ("tijori_search.json", "json", "company_search"),
    "TIJORI_PAGE": ("tijori.html", "html", "financials"),
    "INSTRUMENTS": ("instruments.json.gz", "json", "instruments"),
    "DISCOVERY": ("discovery.json", DISCOVERY, None),
}
URLS = {"INSTANCE": XBRL_URL, "OLDER": OLD_URL}


def initial_bytes() -> dict[str, bytes]:
    """Every source's bytes but the discovery manifest's."""
    return {
        "INSTANCE": instance(FILED["INSTANCE"], "2027-03-31", NAME),
        "OLDER": instance(FILED["OLDER"], "2023-03-31", NAME),
        "INTEGRATED": json.dumps(INTEGRATED).encode(),
        "LEGACY": json.dumps(LEGACY).encode(),
        "MASTER": MASTER.encode(),
        "PEER": json.dumps(PEER + "</span></a></li>").encode(),
        "SCREENER_SEARCH": json.dumps(
            [{"id": 211, "url": f"/company/{DEV_SYMBOL}/consolidated/"}, {"id": None, "url": "/"}]
        ).encode(),
        "SCREENER_PAGE": SCREENER_PAGE.encode(),
        "TIJORI_SEARCH": json.dumps([{"slug": SLUG, "type": "companies"}]).encode(),
        "TIJORI_PAGE": TIJORI_PAGE.replace("{}", json.dumps(TIJORI_DETAILS)).encode(),
        "INSTRUMENTS": instruments(DEV_ISIN, DEV_SYMBOL, DEV_SCRIP),
    }


def materialise(case: dict[str, Any]) -> None:
    """Write every source, the discovery manifest listing each captured one as an OK entry."""
    entries = []
    for label, data in case["bytes"].items():
        file, _, surface = FILES[label]
        (case["root"] / file).write_bytes(data)
        if surface is not None:
            sha = hashlib.sha256(data).hexdigest()
            entry = {"surface": surface, "outcome": "OK", "sha256": sha}
            entries.append(entry | ({"url": URLS[label]} if label in URLS else {}))
    document = {"as_of": "2026-08-01", "entries": entries}
    (case["root"] / FILES["DISCOVERY"][0]).write_text(json.dumps(document))


def fact(label: str, field: str, lex: str) -> dict[str, Any]:
    """An XBRL locator of one filing's fact."""
    return {"src": label, "c": field, "ctx": "c1", "u": None, "d": None, "per": FILED[label]} | {
        "lex": lex
    }


def filed(field: str, lex: str) -> list[dict[str, Any]]:
    """The fact in both filings."""
    return [fact(label, field, lex) for label in FILED]


def bind(fld: str, src: str, lex: str, key: str | None = None) -> dict[str, Any]:
    """A binding locator."""
    return {"src": src, "fld": fld, "lex": lex} | ({"key": key} if key else {})


def node(name: str, transform: str, v: Any, at: list[Any], **extra: Any) -> dict[str, Any]:
    """One onboarding value."""
    return {"name": name, "transform": transform, "v": v, "at": at, **extra}


def values(sha: str) -> list[dict[str, Any]]:
    """Every onboarding value of the consistent case (all units verified)."""
    start = {"valid_from": FILED["OLDER"]}
    frameworks = [
        {"src": label, "ref": ref, "lex": lex}
        for label in FILED
        for ref, lex in (("schemaRef", HREF), ("namespace", ENTRY))
    ]
    discovery = "DISCOVERY"
    return [
        node(
            "SYMBOL",
            "identity",
            DEV_SYMBOL,
            filed("Symbol", DEV_SYMBOL)
            + [
                bind("screener_nse", "SCREENER_PAGE", DEV_SYMBOL),
                bind("tijori_symbol", "TIJORI_PAGE", DEV_SYMBOL),
                bind("upstox_nse_symbol", "INSTRUMENTS", DEV_SYMBOL, DEV_ISIN),
            ],
        ),
        node(
            "ISIN",
            "identity",
            DEV_ISIN,
            filed("ISIN", DEV_ISIN) + [bind("master_isin", "MASTER", DEV_ISIN, DEV_SYMBOL)],
        ),
        node(
            "BSE_SCRIP",
            "identity",
            DEV_SCRIP,
            filed("ScripCode", DEV_SCRIP)
            + [
                bind("peer_scrip", "PEER", DEV_SCRIP, DEV_ISIN),
                bind("screener_bse", "SCREENER_PAGE", DEV_SCRIP),
                bind("upstox_bse_token", "INSTRUMENTS", DEV_SCRIP, DEV_ISIN),
            ],
        ),
        node(
            "NAME",
            "normalised_name",
            NAME,
            filed("NameOfTheCompany", NAME)
            + [bind("master_name", "MASTER", MASTER_NAME, DEV_SYMBOL)],
        ),
        node(
            "PRESENTATION_CURRENCY",
            "identity",
            "INR",
            filed("DescriptionOfPresentationCurrency", "INR"),
            **start,
        ),
        node("ROUNDING_LEVEL", "identity", "Crores", filed("LevelOfRounding", "Crores"), **start),
        node(
            "FISCAL_YEAR_END",
            "month_of_date",
            3,
            [
                fact("INSTANCE", "DateOfEndOfFinancialYear", "2027-03-31"),
                fact("OLDER", "DateOfEndOfFinancialYear", "2023-03-31"),
            ],
            **start,
        ),
        node("REPORTING_FRAMEWORK", "framework_of_entry_point", "IND_AS", frameworks, **start),
        node(
            "DOCUMENT_URL",
            "identity",
            XBRL_URL,
            [{"src": discovery, "path": "entries[0].url", "lex": XBRL_URL}],
        ),
        node(
            "DOCUMENT_SHA256",
            "identity",
            sha,
            [{"src": discovery, "path": "entries[0].sha256", "lex": sha}],
        ),
        node(
            "BASIS_STATUS",
            "basis_of_inventory",
            "CONSOLIDATED_AND_STANDALONE",
            [
                {"src": "INTEGRATED", "path": "data[0].consolidated", "lex": CONSOLIDATED},
                {"src": "INTEGRATED", "path": "data[1].consolidated", "lex": "Non-Consolidated"},
                {"src": "LEGACY", "path": "[0].consolidated", "lex": "Non-Consolidated"},
            ],
            as_of={"src": discovery, "path": "as_of", "lex": "2026-08-01"},
        ),
        node(
            "SCREENER_COMPANY_ID",
            "identity",
            211,
            [
                bind("screener_search_id", "SCREENER_SEARCH", "211", DEV_SYMBOL),
                bind("screener_page_id", "SCREENER_PAGE", "211"),
            ],
        ),
        node(
            "SCREENER_WAREHOUSE_ID",
            "identity",
            "6594631",
            [bind("screener_warehouse_id", "SCREENER_PAGE", "6594631")],
        ),
        node(
            "TIJORI_SLUG",
            "identity",
            SLUG,
            [
                bind("tijori_search_slug", "TIJORI_SEARCH", SLUG),
                bind("tijori_page_slug", "TIJORI_PAGE", SLUG),
            ],
        ),
        node(
            "TIJORI_COMPANY_ID",
            "identity",
            4290,
            [bind("tijori_company_id", "TIJORI_PAGE", "4290")],
        ),
    ]


def unbound(nodes: list[dict[str, Any]], excluded: set[str]) -> list[dict[str, Any]]:
    """The values without the excluded units' bindings (and their vendor-own ids)."""
    kept = []
    for item in nodes:
        at = [
            loc
            for loc in item["at"]
            if "fld" not in loc or SURFACE_UNITS[BINDINGS[loc["fld"]][0]] not in excluded
        ]
        if at:
            kept.append(item | {"at": at})
    return kept


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
FULL_VERSIONS = ONBOARDING_VERSIONS.model_dump(mode="json")  # the freeze's seven-field form
INSTRUMENT_ISIN = {"src": "INSTRUMENTS", "path": "[0].isin", "lex": DEV_ISIN, "gz": True}


def stage4_case(name: str, root: Path, run: dict[str, Any]) -> dict[str, Any]:
    """A synthetic Stage 4 manifest, attempt and freeze entry, consistent for the case's
    exclusion set and then mutated; its Stage 1-schema run a copy of a development run carrying
    the excluded failures; ``check`` runs ``check_stage4`` on it, ``fails`` names the checks that
    must refuse (``run`` = ``check_run``)."""
    base, mutate, fails = STAGE4_CASES[name]
    excluded = EXCLUSIONS[base]
    failures = [FAILURES[u] for u in excluded if u in FAILURES]
    data = initial_bytes()
    sources = [
        {"label": label, "path": str(root / file), "kind": kind}
        for label, (file, kind, _) in FILES.items()
    ]
    sha = hashlib.sha256(data["INSTANCE"]).hexdigest()
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
            "values": unbound(values(sha), set(excluded)),
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
    case = {"root": root, "manifest": manifest, "attempt": attempt, "freeze": freeze, "bytes": data}
    unit_of(case, UPSTOX)["at"] = [dict(INSTRUMENT_ISIN)]  # a compressed ``field`` locator (T5a)
    materialise(case)
    mutate(case)
    return case | {"fails": fails, "check": lambda: check_stage4(root, manifest, attempt, freeze)}


def value_node(case: dict[str, Any], name: str) -> dict[str, Any]:
    """One onboarding value of a case."""
    (found,) = [n for n in values_of(case) if n["name"] == name]
    return found


def values_of(case: dict[str, Any]) -> list[dict[str, Any]]:
    """The case's onboarding values."""
    return cast(list[dict[str, Any]], case["manifest"]["onboarding"]["values"])


def unit_of(case: dict[str, Any], unit: str) -> dict[str, Any]:
    """One unit's verdict of a case."""
    return cast(dict[str, Any], case["manifest"]["onboarding"]["units"][unit])


def run_of_case(case: dict[str, Any]) -> dict[str, Any]:
    """The case's one run."""
    return cast(dict[str, Any], case["manifest"]["runs"][0])


def locator(case: dict[str, Any], name: str, src: str) -> dict[str, Any]:
    """A value's one locator on ``src``."""
    (found,) = [loc for loc in value_node(case, name)["at"] if loc["src"] == src]
    return cast(dict[str, Any], found)


def older(case: dict[str, Any], year_end: str = "2023-03-31", name: str = NAME) -> None:
    """SYNTHETIC: the older filing re-declared, its locators following (still captured)."""
    case["bytes"]["OLDER"] = instance(FILED["OLDER"], year_end, name)
    materialise(case)
    locator(case, "FISCAL_YEAR_END", "OLDER")["lex"] = year_end
    locator(case, "NAME", "OLDER")["lex"] = name


def year_end_change(case: dict[str, Any], split: bool = True) -> None:
    """A December year end in the older filing, a March one in the latest: one node per value,
    each valid from its earliest filing (D5), unless ``split`` is off."""
    older(case, year_end="2022-12-31")
    if split:
        node_ = value_node(case, "FISCAL_YEAR_END")
        values_of(case).remove(node_)
        for label, month in (("OLDER", 12), ("INSTANCE", 3)):
            at = [loc for loc in node_["at"] if loc["src"] == label]
            values_of(case).append(node_ | {"v": month, "at": at, "valid_from": FILED[label]})


def drop_older(case: dict[str, Any]) -> None:
    """The second instance's source and every locator on it deleted (still in discovery)."""
    sources = case["manifest"]["header"]["sources"]
    sources[:] = [s for s in sources if s["label"] != "OLDER"]
    for item in values_of(case):
        item["at"] = [loc for loc in item["at"] if loc["src"] != "OLDER"]


def drop_screener(case: dict[str, Any]) -> None:
    """Every Screener binding and id deleted, the unit still VERIFIED."""
    for item in values_of(case):
        item["at"] = [loc for loc in item["at"] if not loc.get("fld", "").startswith("screener")]
    values_of(case)[:] = [item for item in values_of(case) if item["at"]]


def upstox_other_company(case: dict[str, Any]) -> None:
    """Another company's instrument rows, captured; every locator on them agrees with them."""
    other_isin = "INZZ00000010"
    case["bytes"]["INSTRUMENTS"] = instruments(other_isin, "ZZOTHER", "999001")
    materialise(case)
    unit_of(case, UPSTOX).pop("at")
    for name, lex in (("SYMBOL", "ZZOTHER"), ("BSE_SCRIP", "999001")):
        locator(case, name, "INSTRUMENTS").update(lex=lex, key=other_isin)


def uncaptured_page(case: dict[str, Any]) -> None:
    """The Screener page's bytes differ from its discovery capture (locators still hold)."""
    page = case["root"] / FILES["SCREENER_PAGE"][0]
    page.write_bytes(page.read_bytes() + b"<!-- zz -->")


def document_sha_wrong(case: dict[str, Any]) -> None:
    """The entry, value and lexeme agree on a hash that is no retained filing's bytes."""
    path = case["root"] / FILES["DISCOVERY"][0]
    document = json.loads(path.read_text())
    document["entries"][0]["sha256"] = "f" * 64
    path.write_text(json.dumps(document))
    found = value_node(case, "DOCUMENT_SHA256")
    found["v"] = found["at"][0]["lex"] = "f" * 64


def banking(case: dict[str, Any]) -> None:
    """The older filing re-declared under IntegratedFinance_Banking: same xsd file name
    (Task 0b §2)."""
    banked = ENTRY.replace("_IndAS/", "_Banking/")
    case["bytes"]["OLDER"] = instance(FILED["OLDER"], "2023-03-31", NAME, banked)
    materialise(case)
    for loc in value_node(case, "REPORTING_FRAMEWORK")["at"]:
        if loc["src"] == "OLDER":
            loc["lex"] = loc["lex"].replace("_IndAS/", "_Banking/")


UPSTOX_FAILURE = "upstox/income-statement:upstox-income-statement-summary-v2\t-\tattempt=-"
STAGE4_CASES: dict[str, tuple[str, Callable[[dict[str, Any]], Any], set[str]]] = {
    # name: (exclusion set, mutation, the checks that must refuse)
    **{base: (base, lambda case: None, set()) for base in EXCLUSIONS},
    "year-end-change-valid-from-each-filing": ("pdf-only", year_end_change, set()),
    "name-equal-under-normalisation": (
        "pdf-only",
        lambda c: older(c, name="Apar Industries Ltd."),
        set(),
    ),
    "year-end-change-as-one-value": (
        "pdf-only",
        lambda case: year_end_change(case, split=False),
        {"stage4"},
    ),
    "setting-valid-from-wrong": (
        "pdf-only",
        lambda case: value_node(case, "ROUNDING_LEVEL").update(valid_from=FILED["INSTANCE"]),
        {"stage4"},
    ),
    "name-differs-beyond-normalisation": (
        "pdf-only",
        lambda case: older(case, name="Apar Cables Limited"),
        {"stage4"},
    ),
    "second-instance-deleted": ("pdf-only", drop_older, {"stage4"}),
    "screener-evidence-deleted": ("pdf-only", drop_screener, {"stage4"}),
    "binding-deleted": (
        "pdf-only",
        lambda case: value_node(case, "TIJORI_SLUG")["at"].pop(),
        {"stage4"},
    ),
    "upstox-rows-of-another-company": ("pdf-only", upstox_other_company, {"stage4"}),
    "screener-page-not-the-capture": ("pdf-only", uncaptured_page, {"stage4"}),
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
    "freeze-versions-seven-fields": (
        "pdf-only",
        lambda case: case["freeze"].update(onboarding_versions=dict(FULL_VERSIONS)),
        set(),
    ),
    "freeze-default-version-changed": (
        "pdf-only",
        lambda case: case["freeze"].update(
            onboarding_versions=FULL_VERSIONS | {"rounding_policy": "v2"}
        ),
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
            {"label": "THIRD", "path": str(case["root"] / "instance.xml"), "kind": XBRL}
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
    "document-location-omitted": (
        "pdf-only",
        lambda case: values_of(case).remove(value_node(case, "DOCUMENT_SHA256")),
        {"stage4"},
    ),
    "document-url-of-an-older-instance": (
        "pdf-only",
        lambda case: value_node(case, "DOCUMENT_URL").update(
            v=OLD_URL, at=[{"src": "DISCOVERY", "path": "entries[1].url", "lex": OLD_URL}]
        ),
        {"stage4"},
    ),
    "document-url-wrong": (
        "pdf-only",
        lambda case: value_node(case, "DOCUMENT_URL").update(v=OLD_URL),
        {"stage4"},
    ),
    "document-sha-not-the-retained-bytes": ("pdf-only", document_sha_wrong, {"stage4"}),
    "vendor-state-conflict": (
        "mixed",
        lambda case: unit_of(case, "TIJORI").update(state="CONFLICT"),
        {"stage4"},
    ),
}
