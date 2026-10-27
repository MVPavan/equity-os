"""LIVE-RUN-1 Task 3 (eqos-4j2.21): ``ledger submit`` seals a run draft for review as the runtime
role, so the panel has an ``IN_REVIEW`` head to decide; a repeat refuses with nothing written.
"""

from __future__ import annotations

import pytest
from evidence_support import ingest, policy
from prep2b_support import QUARTERS, STOCK, Pilot
from retained_support import REPO_ROOT
from test_prep2b_run_draft import dictionary, mapping_set, pilot
from test_transcript_admission import issuer_config

from fundamentals.api.cli import main
from fundamentals.api.ledger_cli import DEFAULT_WATCHLIST
from fundamentals.api.screener_cli_dispatch import EXIT_OK, EXIT_REFUSED
from fundamentals.contracts.ledger import VersionStatus
from fundamentals.ledger.lifecycle import version_status

__all__ = ["dictionary", "ingest", "mapping_set", "pilot", "policy"]

pytestmark = [pytest.mark.pg, pytest.mark.retained]

_DIGEST = "SELECT eqos.version_sealed_digest(%s)"
_DECISIONS = "SELECT count(*) FROM eqos.decisions"


def _submit(pilot: Pilot, version_id: int) -> int:
    """``ledger submit`` of the version with the pilot's catalog and snapshot store."""
    command = ["ledger", "submit", str(version_id), "--stock", STOCK]
    command += ["--snapshot-root", str(pilot.rig.snapshots)]
    command += ["--watchlist", str(REPO_ROOT / DEFAULT_WATCHLIST)]
    command += [flag for q in QUARTERS for flag in ("--issuer-config", str(issuer_config(q)))]
    return main(command)


def test_submit_seals_the_draft_once(pilot: Pilot, capsys: pytest.CaptureFixture[str]) -> None:
    """A run draft goes ``IN_REVIEW`` and the printed digest is the one the panel must bind; a
    second submit is an illegal transition that refuses without a decision row."""
    version_id = pilot.run("FY26_Q2").draft_version_id
    assert version_id is not None
    capsys.readouterr()

    assert _submit(pilot, version_id) == EXIT_OK
    lines = dict(line.split("\t") for line in capsys.readouterr().out.splitlines())
    [(digest,)] = pilot.query(_DIGEST, version_id)
    assert lines["sealed_digest"] == digest
    with pilot.pg_db.runtime_pool() as pool, pool.connection() as conn:
        assert version_status(conn.cursor(), version_id) is VersionStatus.IN_REVIEW
        decision = conn.execute(
            "SELECT kind FROM eqos.decisions WHERE id = %s", (int(lines["decision"]),)
        ).fetchone()
    assert decision == ("SUBMIT",)

    [(before,)] = pilot.query(_DECISIONS)
    assert _submit(pilot, version_id) == EXIT_REFUSED
    assert "illegal decision: SUBMIT by RUNTIME" in capsys.readouterr().err
    assert pilot.query(_DECISIONS) == [(before,)]
