"""D5.1 acceptance: ``ledger export --stock`` writes each version's narrative, its status note and
the stock's promoted memory (ledger spec §3, P2; plan D5, D3).

Status never alters narrative bytes: the narrative file hashes to the version's content hash
before and after a later decision and a status-note export. A note derives status, decisions,
the latest validation, its untrusted (non-``MATCH``) claims and the promoted items flagged for
revalidation that cite the version. Stored free-text periods that are not a safe filename
component, and any existing destination (a link included), are refused before anything is
written. A stock with promoted memory and no report version exports its memory alone.
"""

from __future__ import annotations

import hashlib
from datetime import date
from pathlib import Path

import pytest
from ledger_support import SECTION, Ledger, claim, ledger
from memory_support import Memory, memory, promote
from pg_evidence_schema_support import runtime, seeded
from pg_support import PgTestDatabase

from fundamentals.api.cli import main
from fundamentals.api.screener_cli_dispatch import EXIT_OK, EXIT_REFUSED
from fundamentals.contracts.evidence import RunMode
from fundamentals.contracts.guidance_claim import EpistemicClass
from fundamentals.contracts.ledger import ClaimState, DecisionKind, ReportKind
from fundamentals.contracts.memory import MemoryItemDraft, MemoryKind, SupportDraft, SupportTarget
from fundamentals.ledger import store
from fundamentals.ledger.display import content_hash, narrative
from fundamentals.memory.pg_store import PgMemoryStore
from fundamentals.pg.settings import PgRole

__all__ = ["ledger", "memory", "runtime", "seeded"]
pytestmark = pytest.mark.pg

STOCK = "FIXTURE"
OWNER = PgRole.OWNER


@pytest.fixture
def cli(pg_db: PgTestDatabase, monkeypatch: pytest.MonkeyPatch) -> None:
    """Point the CLI at the test database."""
    for name, value in pg_db.cli_env().items():
        monkeypatch.setenv(name, value)


def _export(out: Path, *flags: str) -> dict[str, bytes]:
    """One ``ledger export --stock`` run through the CLI; every file it wrote, by name."""
    assert main(["ledger", "export", "--stock", STOCK, "--out", str(out), *flags]) == EXIT_OK
    return {path.name: path.read_bytes() for path in sorted((out / STOCK).iterdir())}


def _file(version: str) -> str:
    """The narrative file name of the root version of the fixture's ``version`` period."""
    return f"{version}-{ReportKind.EARNINGS_UPDATE}-v1.md"


def test_export_writes_narratives_status_notes_and_promoted_memory(
    memory: Memory, cli: None, tmp_path: Path
) -> None:
    """Notes show status, decisions, latest validation and untrusted claims; a withdrawn
    support's promoted item is flagged in its note and ``memory.md``; candidates and retired
    items stay out; narrative bytes hash to the content hash before and after a decision."""
    ledger = memory.ledger
    hashed = content_hash((SECTION,), (claim(ledger.trace_id),))
    good = memory.approved(content_hash=hashed)
    untrusted = memory.approved()
    ledger.validate(untrusted, mode=RunMode.RETROSPECTIVE, state=ClaimState.VALUE_MISMATCH)
    good_support = (SupportDraft(target=SupportTarget.VERSION, target_id=good),)
    flagged, kept = memory.stage(), memory.stage(statement="Held", supports=good_support)
    candidate = memory.stage(statement="Never promoted")
    retired = memory.stage(statement="Later retired")
    for item in (flagged, kept, retired):
        memory.decide(OWNER, item, DecisionKind.PROMOTE)
    memory.decide(OWNER, retired, DecisionKind.RETIRE)
    ledger.decide(OWNER, memory.version_id, DecisionKind.WITHDRAW)

    files = _export(tmp_path, "--status-notes", "--memory")
    periods = ("FY27_Q1", "FY27_Q2", "FY27_Q3")
    stems = [_file(period).removesuffix(".md") for period in periods]
    assert sorted(files) == sorted(
        ["memory.md", *(f"{stem}.md" for stem in stems), *(f"{stem}.status.md" for stem in stems)]
    )
    assert hashlib.sha256(files[_file("FY27_Q2")]).hexdigest() == hashed
    withdrawn, approved, mismatched = (files[f"{stem}.status.md"].decode() for stem in stems)
    with ledger.pools[PgRole.RUNTIME].connection() as conn:
        good_check = store.latest_validation(conn.cursor(), good)
        bad_check = store.latest_validation(conn.cursor(), untrusted)
    assert good_check is not None and bad_check is not None

    assert "- status: APPROVED" in approved
    assert "1. SUBMIT by RUNTIME" in approved and "2. APPROVE by OWNER" in approved
    assert f"- id: {good_check.id}\n- mode: AS_KNOWN\n- creator: OWNER" in approved
    assert "## Untrusted claims\n\nnone" in approved
    assert "## Revalidation flags\n\nnone" in approved
    assert f"- id: {bad_check.id}\n- mode: RETROSPECTIVE\n- creator: RUNTIME" in mismatched
    assert "## Untrusted claims\n\n- calc.1: VALUE_MISMATCH" in mismatched
    assert "- status: WITHDRAWN" in withdrawn and "3. WITHDRAW by OWNER" in withdrawn
    assert f"## Revalidation flags\n\n- memory item {flagged}:" in withdrawn

    shown = files["memory.md"].decode()
    assert f"## Memory item {flagged}" in shown and f"## Memory item {kept}" in shown
    assert f"## Memory item {candidate}" not in shown and f"## Memory item {retired}" not in shown
    flagged_section, kept_section = shown.split(f"## Memory item {kept}")
    assert "- needs revalidation: yes" in flagged_section
    assert "- needs revalidation: no" in kept_section
    assert f"- FY27_Q2 {ReportKind.EARNINGS_UPDATE} (version {good})" in kept_section

    ledger.decide(OWNER, good, DecisionKind.WITHDRAW)
    again = _export(tmp_path / "again", "--status-notes")
    assert again[_file("FY27_Q2")] == files[_file("FY27_Q2")]
    assert hashlib.sha256(again[_file("FY27_Q2")]).hexdigest() == hashed
    assert "- status: WITHDRAWN" in again[f"{stems[1]}.status.md"].decode()


def test_export_refuses_an_unsafe_period_before_writing(
    ledger: Ledger, cli: None, tmp_path: Path
) -> None:
    """A stored period ``../escaped`` is refused and nothing is written, inside or outside
    ``<dir>``."""
    with ledger._cursor(PgRole.RUNTIME) as cursor:
        escaped = store.create_report(
            cursor, entity_id=ledger.entity_id, period="../escaped", kind=ReportKind.EARNINGS_UPDATE
        )
    ledger.draft(ledger.report())
    ledger.draft(escaped)
    out = tmp_path / "out"
    assert main(["ledger", "export", "--stock", STOCK, "--out", str(out)]) == EXIT_REFUSED
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("link", ["symlink", "hardlink"])
def test_export_refuses_linked_destinations_before_writing(
    ledger: Ledger, cli: None, tmp_path: Path, link: str
) -> None:
    """A status note pre-linked to its narrative, or a narrative hard-linked to a file outside
    ``<dir>``, is refused before any write: the narrative, the outside file and ``<dir>`` are
    unchanged (writing through either link would replace narrative or outside bytes)."""
    ledger.draft(ledger.report())
    folder = tmp_path / "out" / STOCK
    folder.mkdir(parents=True)
    narrative_path, outside = folder / _file("FY27_Q1"), tmp_path / "outside.md"
    outside.write_bytes(b"outside")
    if link == "symlink":
        (folder / _file("FY27_Q1").replace(".md", ".status.md")).symlink_to(narrative_path)
    else:
        narrative_path.hardlink_to(outside)
    before = sorted(folder.iterdir())
    command = ["ledger", "export", "--stock", STOCK, "--out", str(tmp_path / "out")]
    assert main([*command, "--status-notes"]) == EXIT_REFUSED
    assert sorted(folder.iterdir()) == before
    assert outside.read_bytes() == b"outside"
    if link == "hardlink":
        assert narrative_path.read_bytes() == b"outside"
    else:
        assert not narrative_path.exists()


def test_export_writes_memory_of_a_stock_without_versions(
    ledger: Ledger, seeded: dict[str, int], cli: None, tmp_path: Path
) -> None:
    """A known stock's owner-promoted, capture-supported source quirk exports as ``memory.md``
    with no narratives although the stock has no report version; an unknown stock is refused."""
    quirk = MemoryItemDraft(
        entity_id=ledger.entity_id,
        kind=MemoryKind.SOURCE_QUIRK,
        statement="Transcript pagination restarts each section",
        epistemic_class=EpistemicClass.OBSERVED,
        valid_from=date(2026, 4, 1),
        valid_to=None,
        supersedes_item_id=None,
        supports=(SupportDraft(target=SupportTarget.CAPTURE, target_id=seeded["capture_refs"]),),
    )
    item = PgMemoryStore(ledger.pools[PgRole.RUNTIME]).stage(quirk)
    with ledger._cursor(OWNER) as cursor:
        promote(cursor, item)
    files = _export(tmp_path, "--status-notes", "--memory")
    assert list(files) == ["memory.md"]
    assert f"## Memory item {item}: {MemoryKind.SOURCE_QUIRK}" in files["memory.md"].decode()
    unknown = tmp_path / "unknown"
    command = ["ledger", "export", "--stock", "UNKNOWN", "--out", str(unknown), "--memory"]
    assert main(command) == EXIT_REFUSED
    assert not unknown.exists()


def test_export_forms_are_mutually_exclusive(ledger: Ledger, cli: None, tmp_path: Path) -> None:
    """``--stock`` with a version id is refused; ``--stock`` needs ``--out``; the notes and
    memory flags need ``--stock``; the version form still writes the narrative."""
    version = ledger.draft(ledger.report())
    with pytest.raises(SystemExit):
        main(["ledger", "export", str(version), "--stock", STOCK, "--out", str(tmp_path)])
    assert main(["ledger", "export", "--stock", STOCK]) == EXIT_REFUSED
    assert main(["ledger", "export", str(version), "--memory"]) == EXIT_REFUSED
    out = tmp_path / "one.md"
    assert main(["ledger", "export", str(version), "--out", str(out)]) == EXIT_OK
    with ledger.pools[PgRole.RUNTIME].connection() as conn:
        draft = store.read_version(conn.cursor(), version)
    assert out.read_bytes() == narrative(draft.sections, draft.claims)
