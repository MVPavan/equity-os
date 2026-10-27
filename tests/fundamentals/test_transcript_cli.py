"""LIVE-RUN-1 Task 2: ``evidence transcript`` and A05 rights on retained-intake captures.

A transcript and a comparator XBRL registered through the CLI must carry the source-use
authority (A05-DECISION-004), never the manifest's retrieval attestation, and a transcript
registers once under the pin its quarter config declares.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from evidence_support import Ingest, dictionary, ingest, mapping_set, policy
from retained_support import APAR_MANIFEST, REPO_ROOT, apar_intake

from fundamentals.api.cli import main
from fundamentals.api.screener_cli_dispatch import EXIT_OK, EXIT_REFUSED
from fundamentals.contracts.canonical import Representation
from fundamentals.contracts.snapshot import INTAKE_RIGHTS, SnapshotRights
from fundamentals.evidence.capture_intake import SURFACE_OF, TRANSCRIPT_SURFACE
from fundamentals.store.snapshot_store import SnapshotStore

__all__ = ["dictionary", "ingest", "mapping_set", "policy"]

QUARTER = "FY26_Q3"
CONFIG = REPO_ROOT / "config"
_ROWS = (
    "SELECT id, source_id, surface, request_key, capture_id FROM eqos.capture_refs "
    "WHERE surface = %s"
)


def _config(quarter: str) -> Path:
    """The committed issuer config of one quarter."""
    return CONFIG / f"aparinds-{quarter.lower().replace('_', '-')}.yaml"


def _rows(ingest: Ingest, surface: str) -> list[tuple[int, str, str, str, str]]:
    """The ``capture_refs`` rows on one surface."""
    with ingest.pg_db.runtime_pool() as pool, pool.connection() as conn:
        return conn.execute(_ROWS, (surface,)).fetchall()


def _rights(ingest: Ingest, row: tuple[int, str, str, str, str]) -> SnapshotRights:
    """The rights sealed in one registered capture's record."""
    return SnapshotStore(ingest.tmp_path / "store").get_capture(*row[1:]).rights


def _transcript(ingest: Ingest, monkeypatch: pytest.MonkeyPatch, config: Path) -> list[str]:
    """Stage the quarter's transcript inputs and return its ``evidence transcript`` argv."""
    for key, value in ingest.pg_db.cli_env().items():
        monkeypatch.setenv(key, value)
    apar_intake(
        ingest.tmp_path,
        QUARTER,
        {Representation.PDF: "transcript"},
        issuer_config=_config(QUARTER),
        pdf_declaration="transcript_pdf",
    )
    return [
        "evidence",
        "transcript",
        "--retrieval-manifest",
        str(APAR_MANIFEST),
        "--issuer",
        "APARINDS",
        "--quarter",
        QUARTER,
        "--raw-root",
        str(ingest.tmp_path / "inputs"),
        "--snapshot-root",
        str(ingest.tmp_path / "store"),
        "--issuer-config",
        str(config),
    ]


@pytest.mark.pg
@pytest.mark.retained
def test_transcript_registers_once_under_intake_rights(
    ingest: Ingest, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A repeat prints the same id and adds no row; rights are A05, not the attestation."""
    argv = _transcript(ingest, monkeypatch, _config(QUARTER))
    assert main(argv) == EXIT_OK
    first = capsys.readouterr().out
    assert main(argv) == EXIT_OK
    assert capsys.readouterr().out == first
    (row,) = _rows(ingest, TRANSCRIPT_SURFACE)
    assert first == f"capture_ref\t{row[0]}\n"
    assert _rights(ingest, row) == INTAKE_RIGHTS
    assert INTAKE_RIGHTS.authority_refs == ("A05-DECISION-004",)


@pytest.mark.pg
@pytest.mark.retained
def test_transcript_pin_mismatch_refuses_without_a_row(
    ingest: Ingest, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Another quarter's config pins another transcript: refused before any write."""
    argv = _transcript(ingest, monkeypatch, _config("FY27_Q1"))
    assert main(argv) == EXIT_REFUSED
    assert "issuer config pins the PDF" in capsys.readouterr().err
    assert _rows(ingest, TRANSCRIPT_SURFACE) == []


@pytest.mark.pg
@pytest.mark.retained
def test_comparator_ingest_stores_intake_rights(
    ingest: Ingest, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A comparator ``evidence ingest`` capture carries A05 rights, not the attestation."""
    for key, value in ingest.pg_db.cli_env().items():
        monkeypatch.setenv(key, value)
    ingest.intake({Representation.XBRL: "xbrl-consolidated-comparator"}, "FY25_Q2")
    argv = [
        "evidence",
        "ingest",
        "--retrieval-manifest",
        str(APAR_MANIFEST),
        "--issuer",
        "APARINDS",
        "--quarter",
        "FY25_Q2",
        "--period-end",
        "2024-09-30",
        "--basis",
        "consolidated",
        "--raw-root",
        str(ingest.tmp_path / "inputs"),
        "--snapshot-root",
        str(ingest.tmp_path / "store"),
        "--member",
        "xbrl=xbrl-consolidated-comparator",
        "--config-root",
        str(CONFIG),
    ]
    assert main(argv) == EXIT_OK
    (row,) = _rows(ingest, SURFACE_OF[Representation.XBRL])
    assert _rights(ingest, row) == INTAKE_RIGHTS
