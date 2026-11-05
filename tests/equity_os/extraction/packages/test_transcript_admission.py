"""D4 Task 3b: first-party transcript admission (amendment T1), O1's gate.

On the ledger Stage 1 rig after ``ledger import``, each quarter's transcript PDF is admitted as a
diagnostic first-party capture through product code under its issuer config's source id, the
ledger CLI's catalog classifies it first-party, and the imported quote claim cited to it resolves
its quote. Comparison and ``ledger check`` are unchanged by the admission and the new flag.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import yaml
from pg_support import PgTestDatabase
from retained_support import apar_intake, apar_store, manifest_entry
from stage1_e2e_support import RUNS, Outcome, Stage, manifest_lines
from test_frozen_manifests import REPO
from test_ledger_import import CONFIG as IMPORT_CONFIG
from test_legacy_import import Rig

from equity_os.contracts.measurement.canonical import Basis, Representation
from equity_os.contracts.publication.ledger import CitationKind, InputTime
from equity_os.extraction.packages.capture_intake import (
    TRANSCRIPT_SURFACE,
    IntakeError,
    RetainedIntake,
)
from equity_os.extraction.packages.first_party_ingest import IngestError, admit_transcript
from equity_os.interface.commands.publication.ledger_cli import DEFAULT_WATCHLIST, ledger_catalog
from equity_os.interface.commands.sourcing.screener_cli_dispatch import EXIT_OK
from equity_os.interface.entry.cli import main
from equity_os.interface.entry.watchlist_config import load_watchlist_config, stock_catalog
from equity_os.publication.checking.citations import resolve_citation
from equity_os.storage.raw_files.snapshot_store import SnapshotStore
from equity_os.storage.records import store
from equity_os.storage.records.repository import EvidenceRepository
from equity_os.verification.comparison.run import request_for
from equity_os.verification.comparison.run_models import FIRST_PARTY_SOURCES

TRANSCRIPTS = {
    "FY26_Q3": "66df508c06619698e5eb2122ae9564b6ec938dac696cddd84aed2d2133a89d02",
    "FY27_Q1": "78a312c86f58ea515f3eea3763e02a1e977104f282256e774e428d2a898304e5",
}
_TRANSCRIPT_ROWS = "SELECT id, source_id, blob_sha256 FROM eqos.capture_refs WHERE surface = %s"
_VERSION = (
    "SELECT v.id FROM eqos.reports r JOIN eqos.report_versions v ON v.report_id = r.id "
    "WHERE r.period = %s"
)


def issuer_config(quarter: str) -> Path:
    """The committed issuer config of one quarter."""
    return REPO / f"config/runs/aparinds-{quarter.lower().replace('_', '-')}.yaml"


def transcript_intake(tmp_path: Path, quarter: str, config: Path | None = None) -> RetainedIntake:
    """The quarter's transcript intake, pinned by its (or the given) issuer config."""
    return apar_intake(
        tmp_path,
        quarter,
        {Representation.PDF: "transcript"},
        issuer_config=config or issuer_config(quarter),
        pdf_declaration="transcript_pdf",
    )


def check_states(capsys: pytest.CaptureFixture[str], version_id: int, *extra: str) -> list[str]:
    """``ledger check`` of one version: its printed claim and version states (no validation id)."""
    command = ["ledger", "check", "--version", str(version_id), "--stock", "APARINDS"]
    assert main([*command, *extra]) == EXIT_OK
    return capsys.readouterr().out.splitlines()[2:]


@pytest.mark.pg
@pytest.mark.retained
def test_transcripts_are_admitted_as_cited_first_party_captures(
    pg_db: PgTestDatabase,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # The ledger Stage 1 rig: Stage 1 captures and run, the legacy import, ``ledger import``.
    rig = Rig(pg_db, tmp_path)
    rig.register()
    rig.run(*rig.pair())
    for name, value in pg_db.cli_env().items():
        monkeypatch.setenv(name, value)
    configs = [issuer_config(quarter) for quarter in TRANSCRIPTS]
    catalog = ledger_catalog(DEFAULT_WATCHLIST, "APARINDS", configs)
    snapshots = SnapshotStore(rig.snapshots)
    with pg_db.runtime_pool() as pool:
        stage = Stage(pg_db, pool, tmp_path, RUNS["APARINDS-Q2FY26"])
        stage.first_party()
        stage.execute(vendors=[])
        command = ["ledger", "import", "--config", str(IMPORT_CONFIG), "--repo", str(REPO)]
        assert main([*command, "--snapshot-root", str(rig.snapshots)]) == EXIT_OK
        capsys.readouterr()
        repository = EvidenceRepository(pool)

        # 3 (before). The frozen Stage 1 run at a fixed cutoff after every admission below.
        assert FIRST_PARTY_SOURCES == ("NSE_RESULTS_PDF", "NSE_XBRL_INSTANCE")
        stage.vendors()
        cutoff = repository.store_clock() + timedelta(hours=1)
        before = Outcome(stage, cutoff)
        assert manifest_lines(before) == []

        # 2. Refusals write no capture row.
        wrong = tmp_path / "wrong-transcript-pin.yaml"
        raw = yaml.safe_load(issuer_config("FY26_Q3").read_bytes())
        raw["transcript_pdf"]["sha256"] = "0" * 64
        wrong.write_text(yaml.safe_dump(raw))
        with pytest.raises(IntakeError):
            transcript_intake(tmp_path, "FY26_Q3", wrong)
        stock = stock_catalog(load_watchlist_config(DEFAULT_WATCHLIST).stock("APARINDS"))
        with pytest.raises(IngestError):
            admit_transcript(
                repository,
                apar_store(tmp_path),
                transcript_intake(tmp_path, "FY26_Q3"),
                catalog=stock,
            )
        assert rig.query(_TRANSCRIPT_ROWS, TRANSCRIPT_SURFACE) == []

        # 1. Admission, first-seen and the quote, per quarter; a second admission is the same row.
        for quarter, sha256 in TRANSCRIPTS.items():
            declared = yaml.safe_load(issuer_config(quarter).read_bytes())["transcript_pdf"]
            intake = transcript_intake(tmp_path, quarter)
            ref = admit_transcript(repository, apar_store(tmp_path), intake, catalog=catalog)
            again = admit_transcript(repository, apar_store(tmp_path), intake, catalog=catalog)
            assert (again.capture_ref_id, again.capture_id) == (ref.capture_ref_id, ref.capture_id)
            assert (ref.capture_ref_id, declared["source_id"], sha256) in rig.query(
                _TRANSCRIPT_ROWS, TRANSCRIPT_SURFACE
            )
            first_seen = datetime.fromisoformat(
                manifest_entry(quarter, "transcript")["retrieved_at"]
            )
            assert first_seen < datetime(2026, 9, 7, 18, 30, tzinfo=UTC)
            ((version_id,),) = rig.query(_VERSION, quarter)
            with pool.connection() as conn:
                claims = [
                    claim
                    for claim in store.read_version(conn.cursor(), version_id).claims
                    if claim.citation.kind is CitationKind.SOURCE_QUOTE
                    and claim.citation.source_sha256 == sha256
                ]
                assert claims, quarter
                for claim in claims:
                    cited = claim.model_copy(
                        update={
                            "citation": claim.citation.model_copy(
                                update={"capture_ref_id": ref.capture_ref_id}
                            ),
                            "unresolved": False,
                        }
                    )
                    resolved = resolve_citation(
                        conn.cursor(),
                        cited,
                        entity_id=stage.entity_id,
                        overlay_position=cutoff,
                        catalog=catalog,
                        snapshots=snapshots,
                    )
                    assert resolved is not None, claim.claim_key
                    assert resolved.times == ((InputTime.FIRST_SEEN, first_seen),)
                    assert resolved.quote_text == claim.citation.quote

        # 3 (after). Same run identity, still the frozen run; the surface is not requestable.
        after = Outcome(stage, cutoff)
        identity = before.record.manifest.identity_hash()
        assert after.record.manifest.identity_hash() == identity
        assert manifest_lines(after) == []
        with pytest.raises(ValueError, match=TRANSCRIPT_SURFACE):
            request_for(
                stage.entity_id,
                stage.end,
                Basis.CONSOLIDATED,
                cutoff=cutoff,
                config_root=stage.config_root,
                code_version="test-commit",
                database_identity=stage.request().database_identity,
                sources=(TRANSCRIPT_SURFACE,),
                versions=stage.versions,
            )

    # 4. ``ledger check`` with both issuer configs prints the same claim states as without.
    ((version_id,),) = rig.query(_VERSION, "FY26_Q3")
    root = ["--snapshot-root", str(rig.snapshots)]
    flags = [arg for config in configs for arg in ("--issuer-config", str(config))]
    assert check_states(capsys, version_id, *root, *flags) == check_states(
        capsys, version_id, *root
    )
