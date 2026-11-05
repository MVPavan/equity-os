"""Promotion classifications agree with the actual endpoint contracts."""

import runpy
from urllib.parse import parse_qs, urlsplit


def test_specific_endpoint_and_schedule_basis():
    promote = runpy.run_path("scripts/vendor_crawl/promote_kinds.py")
    patterns = list(promote["catalog_patterns"]("tijori"))
    assert (
        next(
            name
            for name, pattern in patterns
            if pattern.fullmatch("/api/v1/ind/chartdata/129/median-pe/")
        )
        == "chartdata-median-pe-api"
    )
    import json
    from pathlib import Path

    rows = json.loads(Path("docs/research/vendor-surface/kinds-index.json").read_text())
    schedules = [
        r
        for r in rows
        if r["id"] == "schedules-api"
        and "consolidated" in parse_qs(urlsplit(r["url"]).query, keep_blank_values=True)
    ]
    assert schedules and all(r["basis"] == "consolidated" for r in schedules)
