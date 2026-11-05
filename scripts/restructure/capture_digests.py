#!/usr/bin/env python3
"""Every hash-producing parser call site's digest, keyed by persisted parser_version.

Usage: capture_digests.py <fundamentals|equity_os> <out.json>. Run before and after the move; the
two files must be byte-equal.
"""

from __future__ import annotations

import csv
import hashlib
import importlib
import inspect
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT, OUT = sys.argv[1:3]
MOVED = {
    row["old"]: row["new"]
    for row in csv.DictReader((HERE / "moves.tsv").open(newline=""), delimiter="\t")
    if row["kind"] in ("module", "config")
}


def load(old: str):  # type: ignore[no-untyped-def]
    """An ingest module of the old layout, under whichever root is installed."""
    path = f"src/fundamentals/ingest/{old}.py"
    name = (path.removeprefix("src/") if ROOT == "fundamentals" else MOVED[path]).removesuffix(
        ".py"
    )
    return importlib.import_module(name.replace("/", "."))


def config(old: str) -> Path:
    """A config path of the old layout, wherever it now is."""
    return Path(old if ROOT == "fundamentals" else MOVED[old])


def source_sha(function: object) -> str:
    """The digest the call sites store: sha256 of one function's source text."""
    return hashlib.sha256(inspect.getsource(function).encode()).hexdigest()  # type: ignore[arg-type]


parse, specs_module = load("vendor_surface_parse"), load("vendor_surface_specs")
capture, market = load("vendor_surface_capture"), load("vendor_surface_market")
claims, canary = load("vendor_surface_claims"), load("vendor_surface_canary")
specs = specs_module.load_specs(
    config("config/vendor_surface/surfaces.yaml"), Path("docs/research/vendor-surface/catalog.yaml")
)
parse.register_tables(specs)
digests = {entry.version: parse.parser_sha256(entry.parse) for entry in parse.PARSERS.values()}
digests["gate.identity"] = parse.parser_sha256(capture.identity_gate)
digests["gate.topology"] = parse.parser_sha256(capture.topology_gate)
digests["tijori:company-financials.slug.v1"] = parse.parser_sha256(capture.identity_gate)
digests[market.TRAVERSAL_VERSION] = parse.parser_sha256(market.continuation)
digests[f"claims:{claims.PROMPT_VERSION}"] = source_sha(claims.extract_text)
for item in canary.CANARIES:
    digests[f"canary.{item.name}.v1"] = source_sha(item.markers)
Path(OUT).write_text(json.dumps(digests, indent=1, sort_keys=True) + "\n")
print(len(digests), "digests")
