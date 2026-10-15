"""Amendment records bind exact scope to a real independent approval report."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from datetime import date
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
AMENDMENTS = ROOT / "docs/blueprint/amendments"
LEDGER_RECORD = AMENDMENTS / "2026-10-12-report-ledger.md"
LEDGER_E2E = ROOT / "tests/fundamentals/test_ledger_stage1_e2e.py"
RECORDS = {
    "data_layer": (
        AMENDMENTS / "2026-10-11-data-layer-postgresql.md",
        "financial-data-layer",
        "docs/specs/2026-10-11-canonical-financial-data-and-cross-source-comparison.md",
        {"postgresql-financial-data", "indian-market-data-target"},
    ),
    "ledger_stage1": (
        LEDGER_RECORD,
        "report-ledger-and-memory",
        "docs/specs/2026-10-12-report-ledger-memory-and-data-lifecycle.md",
        {
            "narrative-authority-postgresql",
            "postgresql-ledger-memory",
            "memory-deletion-retirement",
            "promotion-approval-roles",
        },
    ),
}
MODEL_NAME = re.compile(r"gpt|claude|opus|sonnet|fable|astra|\bsol\b|gemini|llama", re.IGNORECASE)


@pytest.mark.parametrize(("record", "scope", "spec", "ids"), RECORDS.values(), ids=RECORDS.keys())
def test_amendment_records(record: Path, scope: str, spec: str, ids: set[str]) -> None:
    """Only exactly scoped amendments with a real approval report pass the governance gate."""
    body = record.read_text(encoding="utf-8")
    header = re.match(r"\A---\n(.*?)\n---\n", body, re.DOTALL)
    assert header is not None, "amendment record needs structured scope and approval evidence"
    metadata = yaml.safe_load(header.group(1))
    assert metadata["scope"] == scope
    items = metadata["amendments"]
    assert {item["id"] for item in items} == ids
    assert len(items) == len(ids)
    assert all(item["scope"] == scope for item in items)
    digest = hashlib.sha256(
        json.dumps(items, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    assert metadata["subject_sha256"] == digest
    assert metadata["spec"] == spec
    assert (
        metadata["register"]
        == "docs/blueprint/funda-blueprint-implementation-decision-register-v2.md"
    )
    for name in (metadata["spec"], metadata["register"]):
        assert (ROOT / name).is_file()
    for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", body):
        if "://" not in target:
            assert (record.parent / target.split("#", 1)[0]).resolve().is_file(), target
    assert metadata["status"] == "approved"
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


def _first_commit(path: Path) -> str:
    """Return the commit that first added ``path``."""
    log = subprocess.run(
        ["git", "log", "--diff-filter=A", "--format=%H", "--", str(path)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()
    assert log, f"{path.name} is not committed"
    return log[-1]


def test_ledger_stage1_record_follows_e2e() -> None:
    """Amendment 3 is recorded only after the Stage 1 end-to-end test exists."""
    e2e, record = _first_commit(LEDGER_E2E), _first_commit(LEDGER_RECORD)
    ancestry = ["git", "merge-base", "--is-ancestor", e2e, record]
    assert subprocess.run(ancestry, cwd=ROOT).returncode == 0


def _entry(text: str, term: str) -> str:
    """Return the body of one bold-term entry in a Markdown glossary or list."""
    match = re.search(rf"\*\*{re.escape(term)}\*\*:?\n?(.*?)(?=\n\n|\n\d+\. |\Z)", text, re.S)
    assert match is not None, term
    return term + match.group(1)


def test_context_glossary() -> None:
    """Glossary and invariant 11 name decision roles, never models (amendments 3 and 8)."""
    context = (ROOT / "CONTEXT.md").read_text(encoding="utf-8")
    promotion = _entry(context, "Memory promotion")
    roles = _entry(context, "Approval panel / owner role / runtime role")
    truth = _entry(context, "Source-of-truth hierarchy")
    invariant = _entry(
        (ROOT / ".claude/project/invariants.md").read_text(encoding="utf-8"),
        "Memory promotion is a separate, approved action",
    )
    assert (
        "a separate decision by the approval panel or the owner role (override kept)" in promotion
    )
    assert all(role in roles.lower() for role in ("approval panel", "owner role", "runtime role"))
    assert "PostgreSQL rows for the approved narrative" in truth
    assert "approval panel or the owner role" in " ".join(invariant.split())
    for entry in (promotion, roles, truth, invariant):
        assert not MODEL_NAME.search(entry), entry
