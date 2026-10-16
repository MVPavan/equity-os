"""Ledger manifest claim checks: each claim field bound to its source lexeme (D3 D6, D4 M9)."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from decimal import Decimal
from typing import Any, cast

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
