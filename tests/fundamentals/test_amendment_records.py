"""Amendment records bind exact scope to a real independent approval report."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
DATA_LAYER_RECORD = ROOT / "docs/blueprint/amendments/2026-10-11-data-layer-postgresql.md"


@pytest.mark.parametrize("record", [DATA_LAYER_RECORD], ids=["data_layer"])
def test_amendment_records(record: Path) -> None:
    """Only the two approved financial-data amendments pass the shared governance gate."""
    body = record.read_text(encoding="utf-8")
    header = re.match(r"\A---\n(.*?)\n---\n", body, re.DOTALL)
    assert header is not None, "amendment record needs structured scope and approval evidence"
    metadata = yaml.safe_load(header.group(1))
    assert metadata["status"] == "approved"
    assert metadata["scope"] == "financial-data-layer"
    items = metadata["amendments"]
    assert {item["id"] for item in items} == {
        "postgresql-financial-data",
        "indian-market-data-target",
    }
    assert len(items) == 2
    assert all(item["scope"] == "financial-data-layer" for item in items)
    digest = hashlib.sha256(
        json.dumps(items, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    for item in items:
        approval = metadata["approvals"][item["id"]]
        assert approval["verdict"] == "APPROVE"
        assert approval["reviewer"].strip()
        assert approval["subject_sha256"] == digest
        date.fromisoformat(str(approval["date"]))
        report = ROOT / approval["report"]
        text = report.read_text(encoding="utf-8")
        assert digest in text and "VERDICT: APPROVE" in text
        assert item["id"] in text
    assert (
        metadata["spec"]
        == "docs/specs/2026-10-11-canonical-financial-data-and-cross-source-comparison.md"
    )
    assert (
        metadata["register"]
        == "docs/blueprint/funda-blueprint-implementation-decision-register-v2.md"
    )
    for name in (metadata["spec"], metadata["register"]):
        assert (ROOT / name).is_file()
    for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", body):
        if "://" not in target:
            assert (record.parent / target.split("#", 1)[0]).resolve().is_file(), target
