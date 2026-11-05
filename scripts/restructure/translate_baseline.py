#!/usr/bin/env python3
"""Write the moved tree's baseline from the kept original, so the same gate command stays the route.

Usage: translate_baseline.py <original.json> <out.json> [additions.txt]
Replaces only the exact mapped path before ``::``, keeps test names, applies the reviewed
param_ids.tsv, and appends the enumerated new ids (one per line in additions.txt).
"""

import csv
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def read_rows(name: str) -> list[dict[str, str]]:
    """One data file beside this script, by header."""
    with (HERE / name).open(newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t", quoting=csv.QUOTE_NONE))


def main() -> None:
    """Translate, check the translation inverts exactly, write."""
    original, out = Path(sys.argv[1]), Path(sys.argv[2])
    additions = Path(sys.argv[3]).read_text().split("\n") if len(sys.argv) > 3 else []
    paths = {row["old"]: row["new"] for row in read_rows("moves.tsv") if row["kind"] == "test"}
    params = {row["old_nodeid"]: row["new_nodeid"] for row in read_rows("param_ids.tsv")}
    baseline = json.loads(original.read_text())
    tests: list[str] = baseline["tests"]

    def translate(nodeid: str) -> str:
        if nodeid in params:
            return params[nodeid]
        path, separator, rest = nodeid.partition("::")
        return paths[path] + separator + rest

    forward = {nodeid: translate(nodeid) for nodeid in tests}
    assert len(set(forward.values())) == len(tests), "the translation is not injective"
    inverse = {new: old for old, new in forward.items()}
    assert sorted(inverse[new] for new in forward.values()) == sorted(tests), "no exact inverse"
    added = [line for line in additions if line.strip()]
    assert not set(added) & set(forward.values()), "an addition repeats a translated id"
    translated = sorted([*forward.values(), *added])
    baseline["tests"] = translated
    baseline["passed"] = len(translated)
    baseline["translated_from_sha256"] = hashlib.sha256(original.read_bytes()).hexdigest()
    out.write_text(json.dumps(baseline, indent=2) + "\n")
    print(f"translated {len(tests)} ids, added {len(added)}, wrote {out}")


if __name__ == "__main__":
    main()
