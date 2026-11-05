"""Audit F03: submit and validation enforce the prose capture's issuer and cutoff."""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from equity_os.contracts.measurement.evidence import RunMode
from equity_os.contracts.publication.ledger import ReportSection, VersionDraft, VersionState
from equity_os.contracts.sourcing.source_catalog import BUILTIN_SOURCES
from equity_os.publication.approval import lifecycle
from equity_os.publication.checking import citations
from equity_os.publication.drafting.display import content_hash
from equity_os.storage.raw_files.snapshot_store import SnapshotStore

CUTOFF = datetime(2026, 7, 31, tzinfo=UTC)


@pytest.mark.parametrize("operation", ["submit", "validate"])
@pytest.mark.parametrize("ineligible", ["future", "other_issuer"])
def test_ineligible_prose_capture_is_refused(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, operation: str, ineligible: str
) -> None:
    section = ReportSection(
        ordinal=0, section_key="narrative", body="{{e:observed}} Demand held {{s:7|p1.b0.0:10}}."
    )
    draft = VersionDraft(
        report_id=1,
        author="audit",
        knowledge_cutoff=CUTOFF,
        content_hash=content_hash((section,), ()),
        sections=(section,),
    )
    cursor, own, pool = MagicMock(), MagicMock(), MagicMock()
    cursor.execute.return_value.fetchone.return_value = (1,)
    cursor.connection.cursor.return_value.__enter__.return_value = own
    own.execute.return_value.fetchone.return_value = None if ineligible == "other_issuer" else (1,)
    conn = pool.connection.return_value.__enter__.return_value
    conn.cursor.return_value.__enter__.return_value = cursor
    capture = {"first_seen": CUTOFF + timedelta(seconds=ineligible == "future")}
    monkeypatch.setattr(citations, "_first_party_capture", lambda *args: capture)
    monkeypatch.setattr(citations, "_span", lambda *args: "Demand held")
    monkeypatch.setattr(lifecycle.store, "read_version", lambda *args: draft)
    monkeypatch.setattr(lifecycle.store, "sealed_digest", lambda *args: "a" * 64)
    monkeypatch.setattr(lifecycle, "append_decision", lambda *args: None)
    paths = {"catalog": BUILTIN_SOURCES, "snapshots": SnapshotStore(tmp_path)}
    if operation == "submit":
        with pytest.raises(lifecycle.DecisionRefusedError, match="UNCITED_PROSE"):
            lifecycle.submit(pool, 1, **paths)
    else:
        result = lifecycle.check_version(
            cursor, 1, mode=RunMode.AS_KNOWN, boundary=CUTOFF + timedelta(days=1), **paths
        )
        assert result.version_states == (VersionState.UNCITED_PROSE,)
