"""Ledger manifest claim checks: each claim field bound to its source lexeme (D3 D6, D4 M9)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

CONTRACT_FIELDS = ("metric", "scope", "horizon", "unit", "constant_currency")  # plan D4 M9
MKEY_FIELDS = {  # contracts.measurement_key.MeasurementKey
    *("entity_id", "canonical_id", "period", "basis", "framework"),
    *("currency", "value_kind", "dimensions"),
}


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
