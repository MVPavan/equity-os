"""LIVE-RUN-1 Task 4 (eqos-dna, OD-3/OD-4): ``ledger panel`` decides a submitted version as the
panel login on a verdict recorded out of band. The verdict comes only from the reviewer's own
preserved response, which must carry exactly one binding line naming the subject, its sealed
digest and the narrative's SHA-256; the verdict file says only who answered. Any mismatch or
failing gate refuses with no ``decisions`` or ``panel_reviews`` row, and a ``rehearsal`` label is
accepted only on an ``eqos_test_*`` database.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Callable
from typing import Any

import pytest
from evidence_support import ingest, policy
from prep2b_support import QUARTERS, STOCK, Pilot
from retained_support import APAR_MANIFEST, REPO_ROOT
from test_operator_cli import PILOT_STORE
from test_prep2b_run_draft import dictionary, mapping_set, pilot
from test_transcript_admission import issuer_config

import fundamentals.api.cli as cli
from fundamentals.api import operator_cli
from fundamentals.api.cli import main
from fundamentals.api.ledger_cli import DEFAULT_WATCHLIST
from fundamentals.api.screener_cli_dispatch import EXIT_OK, EXIT_REFUSED
from fundamentals.contracts.ledger import CitationKind, ClaimState, VersionStatus
from fundamentals.ledger.lifecycle import version_status
from fundamentals.store.pg_fact_store import _INSERT_STORE, _OPEN_EVENT

__all__ = ["dictionary", "ingest", "mapping_set", "pilot", "policy"]

_DIGEST = "SELECT eqos.version_sealed_digest(%s)"
_ROWS = "SELECT (SELECT count(*) FROM eqos.decisions), (SELECT count(*) FROM eqos.panel_reviews)"
_DECIDED = """SELECT d.kind, d.decider, r.provider, r.model, r.effort, r.brief_version, r.verdict,
    r.rationale FROM eqos.decisions d JOIN eqos.panel_reviews r ON r.id = d.panel_review_id
    WHERE d.id = %s"""
_BINDING = "EQOS-BINDING subject=REPORT_VERSION:{id} sealed_digest={digest} narrative_sha256={sha}"
_RESPONDER = {
    "provider": "rehearsal",
    "model": "gpt-6.1-sol",
    "effort": "high",
    "brief_version": "live-run-1-t4",
}
_STALE = "0" * 64


def _ledger(pilot: Pilot, action: str, version_id: int, *flags: str) -> int:
    """One ``ledger`` action on the version with the pilot's catalog and snapshot store."""
    command = ["ledger", action, str(version_id), *flags, "--stock", STOCK]
    command += ["--snapshot-root", str(pilot.rig.snapshots)]
    command += ["--watchlist", str(REPO_ROOT / DEFAULT_WATCHLIST)]
    command += [flag for q in QUARTERS for flag in ("--issuer-config", str(issuer_config(q)))]
    return main(command)


def _operator(pilot: Pilot, quarter: str, monkeypatch: pytest.MonkeyPatch) -> int:
    """Task 1 ``fundamentals-operator`` ``stage`` then ``run`` of the quarter's accepted config;
    the run's draft version."""
    fiscal, number = quarter.split("_")
    config = REPO_ROOT / f"config/aparinds-{fiscal.lower()}-{number.lower()}.yaml"
    store, locator = pilot.tmp_path / f"intake-{quarter}", pilot.tmp_path / f"{quarter}.json"
    store.mkdir(mode=0o700)
    stage = ["stage", "--config", str(config), "--source-admission-store", str(store)]
    assert operator_cli.main([*stage, "--out-manifest", str(locator)]) == 0
    argv = ["run", "--issuer", STOCK, "--quarter", f"{number}-{fiscal}", "--config", str(config)]
    argv += ["--source-admission-manifest", str(locator), "--source-admission-store", str(store)]
    argv += ["--snapshot-root", str(pilot.rig.snapshots)]
    argv += ["--watchlist", str(REPO_ROOT / DEFAULT_WATCHLIST)]
    argv += [flag for q in QUARTERS for flag in ("--issuer-config", str(issuer_config(q)))]
    argv += ["--compare-run", str(pilot.compare_run(quarter))]
    argv += ["--retrospective", str(APAR_MANIFEST)]
    drafts: list[int | None] = []
    run_command = cli.run_command

    def spy(*args: Any, **kwargs: Any) -> Any:
        result = run_command(*args, **kwargs)
        drafts.append(result.draft_version_id)
        return result

    with monkeypatch.context() as patch:
        patch.setattr(cli, "run_command", spy)
        assert operator_cli.main(argv) == 0
    [draft] = drafts
    assert draft is not None
    return draft


def _bound(pilot: Pilot, version_id: int) -> tuple[str, str]:
    """The version's sealed digest and the SHA-256 of its ``ledger export`` narrative."""
    out = pilot.tmp_path / f"narrative-{version_id}.md"
    assert main(["ledger", "export", str(version_id), "--out", str(out)]) == EXIT_OK
    [(digest,)] = pilot.query(_DIGEST, version_id)
    return digest, hashlib.sha256(out.read_bytes()).hexdigest()


def _line(version_id: int, digest: str, sha: str, verdict: str = "APPROVE") -> str:
    """A binding line naming the subject, digest, narrative hash and verdict."""
    return _BINDING.format(id=version_id, digest=digest, sha=sha) + f" verdict={verdict}"


def _panel(pilot: Pilot, version_id: int, response: str) -> int:
    """``ledger panel`` of the version on the rehearsal verdict file and ``response``."""
    verdict = pilot.tmp_path / "verdict.json"
    verdict.write_text(json.dumps(_RESPONDER), encoding="utf-8")
    preserved = pilot.tmp_path / "response.md"
    preserved.write_bytes(response.encode())
    flags = ("--verdict", str(verdict), "--response", str(preserved))
    return _ledger(pilot, "panel", version_id, *flags)


def _quotes_match(pilot: Pilot, version_id: int) -> None:
    """Every guidance ``SOURCE_QUOTE`` claim of the version checks ``MATCH`` (it is bound)."""
    quoted = {
        claim.claim_key
        for claim in pilot.version(version_id).claims
        if claim.citation.kind is CitationKind.SOURCE_QUOTE
    }
    states = dict(pilot.validate(version_id).claim_states)
    assert quoted and {states[key] for key in quoted} == {ClaimState.MATCH}


@pytest.mark.pg
@pytest.mark.retained
def test_panel_approval_carries_the_route_to_the_next_quarter(
    pilot: Pilot, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Operator stage + run FY26_Q2 → ``ledger submit`` → ``ledger export`` → a response binding
    that narrative → ``ledger panel`` APPROVE → operator stage + run FY26_Q3: the panel, not the
    owner, decides; the review row records who answered and the response verbatim; FY26_Q3
    builds on the approved version."""
    with pilot.pg_db.runtime_pool() as pool, pool.connection() as conn, conn.transaction():
        conn.execute(_INSERT_STORE, (PILOT_STORE,))
        conn.execute(_OPEN_EVENT, (PILOT_STORE, uuid.uuid4()))
    q2 = _operator(pilot, "FY26_Q2", monkeypatch)
    assert _ledger(pilot, "submit", q2) == EXIT_OK
    _quotes_match(pilot, q2)
    digest, sha = _bound(pilot, q2)
    response = f"Approve: every claim is grounded.\r\n\n{_line(q2, digest, sha)}\n"
    capsys.readouterr()

    assert _panel(pilot, q2, response) == EXIT_OK
    decision = int(capsys.readouterr().out.removeprefix("decision\t"))
    assert pilot.query(_DECIDED, decision) == [
        ("APPROVE", "PANEL", *_RESPONDER.values(), "APPROVE", response)
    ]
    with pilot.pg_db.runtime_pool() as pool, pool.connection() as conn:
        assert version_status(conn.cursor(), q2) is VersionStatus.APPROVED

    q3 = _operator(pilot, "FY26_Q3", monkeypatch)
    assert f"Prior: version:{q2} digest {digest}." in pilot.version(q3).sections[0].body
    _quotes_match(pilot, q3)


def _no_line(version_id: int, digest: str, sha: str) -> str:
    return "Approve.\n"


def _two_lines(version_id: int, digest: str, sha: str) -> str:
    line = _line(version_id, digest, sha)
    return f"{line}\n{_line(version_id, digest, sha, 'REJECT')}\n"


def _other_version(version_id: int, digest: str, sha: str) -> str:
    return _line(version_id + 1, digest, sha) + "\n"


def _stale_digest(version_id: int, digest: str, sha: str) -> str:
    return _line(version_id, _STALE, sha) + "\n"


def _wrong_narrative(version_id: int, digest: str, sha: str) -> str:
    return _line(version_id, digest, _STALE) + "\n"


def _bound_line(version_id: int, digest: str, sha: str) -> str:
    return _line(version_id, digest, sha) + "\n"


@pytest.mark.pg
@pytest.mark.retained
@pytest.mark.parametrize(
    ("response", "submitted", "reason"),
    [
        (_no_line, True, "exactly one EQOS-BINDING line"),
        (_two_lines, True, "exactly one EQOS-BINDING line"),
        (_other_version, True, "binds REPORT_VERSION:"),
        (_stale_digest, True, "does not bind the sealed digest"),
        (_wrong_narrative, True, "does not bind the reviewed narrative"),
        (_bound_line, False, "its head is not SUBMIT"),
    ],
    ids=["no-line", "two-lines", "other-version", "stale-digest", "wrong-narrative", "unsubmitted"],
)
def test_panel_refusals_write_nothing(
    pilot: Pilot,
    capsys: pytest.CaptureFixture[str],
    response: Callable[[int, str, str], str],
    submitted: bool,
    reason: str,
) -> None:
    """A response that does not bind exactly this subject, digest and narrative, or a version
    the panel may not decide, refuses before any ``decisions`` or ``panel_reviews`` row."""
    version_id = pilot.run("FY26_Q2").draft_version_id
    assert version_id is not None
    if submitted:
        assert _ledger(pilot, "submit", version_id) == EXIT_OK
    digest, sha = _bound(pilot, version_id)
    before = pilot.query(_ROWS)
    capsys.readouterr()

    assert _panel(pilot, version_id, response(version_id, digest, sha)) == EXIT_REFUSED
    assert reason in capsys.readouterr().err
    assert pilot.query(_ROWS) == before


@pytest.mark.parametrize(
    ("database", "allowed"), [("eqos_live", False), ("eqos", False), ("eqos_test_x", True)]
)
def test_rehearsal_label_only_on_test_databases(database: str, allowed: bool) -> None:
    """OD-4: a ``rehearsal`` verdict never decides outside an ``eqos_test_*`` database; a real
    provider is not restricted."""
    from fundamentals.ledger.recorded_reviewer import REHEARSAL_PROVIDER, rehearsal_allowed

    assert rehearsal_allowed(REHEARSAL_PROVIDER, database) is allowed
    assert rehearsal_allowed("codex", database)
