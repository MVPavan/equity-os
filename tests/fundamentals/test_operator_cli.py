"""LIVE-RUN-1 Task 1: ``fundamentals-operator`` admits a quarter's pinned originals retrospectively.

The launcher's trust anchor is installed code: the repository root, the retrieval manifest's
SHA-256 and each accepted quarter config's bytes. Another root, changed bytes or a ``run`` without
``--retrospective`` refuses before any write; below the launcher, admission still refuses a
registration past the cutoff. Every refusal leaves the facts, report versions and intake store
as they were.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from evidence_support import ingest, policy
from pg_support import PgTestDatabase
from prep2b_support import COUNTS, QUARTERS, STOCK, Pilot
from retained_support import APAR_MANIFEST, REPO_ROOT
from test_prep2b_run_draft import dictionary, mapping_set, pilot
from test_transcript_admission import issuer_config

import fundamentals.api.cli as cli
from fundamentals.api import operator_cli
from fundamentals.api.ledger_cli import DEFAULT_IMPORT_CONFIG, DEFAULT_WATCHLIST
from fundamentals.api.pipeline import PipelineResult
from fundamentals.api.source_admission import (
    RETROSPECTIVE,
    PipelineSourceRefs,
    SourceAdmissionError,
)
from fundamentals.contracts.ledger import ClaimState
from fundamentals.contracts.snapshot import INTAKE_RIGHTS
from fundamentals.contracts.source_registration import SourceRegistrationError
from fundamentals.store.pg_fact_store import _INSERT_STORE, _OPEN_EVENT
from fundamentals.store.snapshot_store import SnapshotStore

__all__ = ["dictionary", "ingest", "mapping_set", "pilot", "policy"]

pytestmark = [pytest.mark.pg, pytest.mark.retained]

QUARTER = "FY26_Q2"
ACCEPTED = "config/aparinds-fy26-q2.yaml"
MANIFEST = "data/raw/watchlist/aparinds/retrieval-manifest-v2.json"
MANIFEST_SHA256 = "c47866ce13f719521bbcc7826fc23590acc73f9904cfc1749a1ad911bb399a1b"
# The store every committed Apar config routes to (the imported legacy store, reopened).
PILOT_STORE = "sqlite-cb02b0f12a1708d0"
UNSUPPORTED_ROOT = "unsupported root"


def _intake_store(tmp_path: Path) -> Path:
    """A new protected intake store."""
    store = tmp_path / "intake"
    store.mkdir(mode=0o700)
    return store


def _listing(store: Path) -> dict[str, str | None]:
    """Every path in the store with its file's SHA-256."""
    return {
        str(path.relative_to(store)): (
            hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
        )
        for path in sorted(store.rglob("*"))
    }


def _counts(pg_db: PgTestDatabase) -> tuple[Any, ...]:
    """Rows of every fact and report-version table a run writes."""
    with pg_db.runtime_pool() as pool, pool.connection() as conn:
        row = conn.execute(COUNTS).fetchone()
    assert row is not None
    return tuple(row)


def _refuses(
    pg_db: PgTestDatabase,
    store: Path,
    error: type[Exception],
    match: str,
    command: Callable[[], object],
) -> None:
    """``command`` refuses with ``match`` and writes no fact, version or intake-store entry."""
    before = (_counts(pg_db), _listing(store))
    with pytest.raises(error, match=match):
        command()
    assert (_counts(pg_db), _listing(store)) == before


def _stage(store: Path, locator: Path, config: Path) -> list[str]:
    """``stage`` argv of one quarter config."""
    return ["stage", "--config", str(config), "--source-admission-store", str(store)] + [
        "--out-manifest",
        str(locator),
    ]


def _run(store: Path, locator: Path, config: Path = REPO_ROOT / ACCEPTED) -> list[str]:
    """The FY26_Q2 ``run`` argv over a staged locator, without ``--retrospective``."""
    argv = ["run", "--issuer", STOCK, "--quarter", "Q2-FY26", "--config", str(config)]
    return argv + [
        "--source-admission-manifest",
        str(locator),
        "--source-admission-store",
        str(store),
    ]


def _replacement(tmp_path: Path, edit: Callable[[dict[str, Any]], None]) -> Path:
    """A self-consistent copy of the installed root: the accepted config's bytes, a manifest
    edited by ``edit`` and ``config/ledger_import.yaml`` repinned to it."""
    root = tmp_path / "replacement"
    (root / "config").mkdir(parents=True)
    (root / ACCEPTED).write_bytes((REPO_ROOT / ACCEPTED).read_bytes())
    body = json.loads(APAR_MANIFEST.read_bytes())
    edit(body)
    manifest = root / MANIFEST
    manifest.parent.mkdir(parents=True)
    manifest.write_text(json.dumps(body))
    pin = hashlib.sha256(manifest.read_bytes()).hexdigest()
    imported = (REPO_ROOT / DEFAULT_IMPORT_CONFIG).read_text()
    (root / DEFAULT_IMPORT_CONFIG).write_text(imported.replace(MANIFEST_SHA256, pin))
    return root


def _entry(body: dict[str, Any], quarter: str, kind: str) -> dict[str, Any]:
    """The manifest's one entry of a quarter and kind."""
    (entry,) = [e for e in body["entries"] if (e["quarter"], e["kind"]) == (quarter, kind)]
    return entry


def _refile(body: dict[str, Any]) -> None:
    """Move the FY26_Q2 XBRL's filing time one second."""
    entry = _entry(body, QUARTER, "xbrl-consolidated")
    entry["filed_at_nse"] = entry["filed_at_nse"][:-1] + str(
        (int(entry["filed_at_nse"][-1]) + 1) % 10
    )


def _swap_xbrl(body: dict[str, Any]) -> None:
    """Pin the FY26_Q2 XBRL entry to FY26_Q3's XBRL content."""
    other = _entry(body, "FY26_Q3", "xbrl-consolidated")["sha256"]
    _entry(body, QUARTER, "xbrl-consolidated")["sha256"] = other


def test_stage_and_run_admit_registered_originals_retrospectively(
    pilot: Pilot,
    pg_db: PgTestDatabase,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``stage`` registers the three pinned originals under A05-DECISION-004 rights; ``run``
    admits each ``retrospective_registered`` and writes a draft that checks ``MATCH``."""
    with pg_db.runtime_pool() as pool, pool.connection() as conn, conn.transaction():
        conn.execute(_INSERT_STORE, (PILOT_STORE,))
        conn.execute(_OPEN_EVENT, (PILOT_STORE, uuid.uuid4()))
    store, locator = _intake_store(tmp_path), tmp_path / "locator.json"
    capsys.readouterr()
    assert operator_cli.main(_stage(store, locator, REPO_ROOT / ACCEPTED)) == 0
    refs = PipelineSourceRefs.model_validate_json(locator.read_bytes())
    printed = [line.split("\t") for line in capsys.readouterr().out.splitlines()]
    assert printed == [
        [role, getattr(refs, role).source_id, getattr(refs, role).capture_id]
        for role in ("xbrl", "results_pdf", "transcript_pdf")
    ]
    authorization = json.loads(APAR_MANIFEST.read_bytes())["authorization"]
    for role in ("xbrl", "results_pdf", "transcript_pdf"):
        ref = getattr(refs, role)
        record = SnapshotStore(store).get_capture(
            ref.source_id, ref.surface, ref.request_key, ref.capture_id
        )
        assert record.rights == INTAKE_RIGHTS
        assert record.rights.authority_refs == ("A05-DECISION-004",) != (authorization,)

    results: list[PipelineResult] = []

    def spy(*args: Any, **kwargs: Any) -> PipelineResult:
        results.append(run_command(*args, **kwargs))
        return results[-1]

    run_command = cli.run_command
    monkeypatch.setattr(cli, "run_command", spy)
    out = tmp_path / "out"
    out.mkdir()
    argv = _run(store, locator) + ["--snapshot-root", str(pilot.rig.snapshots)]
    argv += ["--watchlist", str(REPO_ROOT / DEFAULT_WATCHLIST)]
    argv += [flag for q in QUARTERS for flag in ("--issuer-config", str(issuer_config(q)))]
    argv += ["--compare-run", str(pilot.compare_run(QUARTER))]
    argv += ["--retrospective", str(APAR_MANIFEST)]
    argv += ["--out-json", str(out / "q2.json"), "--out", str(out / "q2.md")]
    assert operator_cli.main(argv) == 0

    (result,) = results
    assert [source.mode for source in result.temporal_evidence.sources] == [RETROSPECTIVE] * 3
    assert json.loads((out / "q2.json").read_bytes())["retrospective"] is True
    version_id = result.draft_version_id
    assert version_id is not None
    heading = pilot.version(version_id).sections[0].body
    assert (
        f"Retrospective workflow demonstration (retrieval manifest sha256 {MANIFEST_SHA256})"
        in (heading)
    )
    states = pilot.validate(version_id).claim_states
    assert states and {state for _, state in states} == {ClaimState.MATCH}
    assert hashlib.sha256(APAR_MANIFEST.read_bytes()).hexdigest() == MANIFEST_SHA256
    assert json.loads(APAR_MANIFEST.read_bytes())["authorization"] == authorization


def test_staged_runs_refuse_without_the_launcher_guards(
    pg_db: PgTestDatabase, tmp_path: Path
) -> None:
    """After ``stage``: the launcher refuses a run with no ``--retrospective``; admission
    itself refuses that run past the cutoff; a locator citing another quarter's registered XBRL
    refuses at the binding comparison. None writes a draft."""
    store = _intake_store(tmp_path)
    locator, other = tmp_path / "q2.json", tmp_path / "q3.json"
    assert operator_cli.main(_stage(store, locator, REPO_ROOT / ACCEPTED)) == 0
    assert operator_cli.main(_stage(store, other, REPO_ROOT / "config/aparinds-fy26-q3.yaml")) == 0
    retrospective = ["--retrospective", str(APAR_MANIFEST)]

    _refuses(
        pg_db,
        store,
        SourceRegistrationError,
        "retrospective manifest required",
        lambda: operator_cli.main(_run(store, locator)),
    )
    context = operator_cli.approved_intake(REPO_ROOT / ACCEPTED, store)
    _refuses(
        pg_db,
        store,
        SourceAdmissionError,
        "source acquisition/first-seen/registration exceeds cutoff",
        lambda: cli.main(_run(store, locator), intake_context=context),
    )
    edited = json.loads(locator.read_bytes())
    edited["xbrl"] = json.loads(other.read_bytes())["xbrl"]
    substituted = tmp_path / "substituted.json"
    substituted.write_text(json.dumps(edited))
    _refuses(
        pg_db,
        store,
        SourceAdmissionError,
        "native registered source refused",
        lambda: operator_cli.main(_run(store, substituted) + retrospective),
    )


@pytest.mark.parametrize("edit", [_refile, _swap_xbrl], ids=["filed-at", "xbrl-substitution"])
def test_a_self_consistent_replacement_root_refuses(
    pg_db: PgTestDatabase, tmp_path: Path, edit: Callable[[dict[str, Any]], None]
) -> None:
    """A copied tree with accepted config bytes, an edited manifest and a matching pin is not
    the installed root: ``stage`` and ``run`` (with the installed manifest) both refuse."""
    root, store = _replacement(tmp_path, edit), _intake_store(tmp_path)
    config, locator = root / ACCEPTED, tmp_path / "locator.json"
    _refuses(
        pg_db,
        store,
        SourceRegistrationError,
        UNSUPPORTED_ROOT,
        lambda: operator_cli.main(_stage(store, locator, config)),
    )
    run = _run(store, locator, config) + ["--retrospective", str(APAR_MANIFEST)]
    _refuses(
        pg_db, store, SourceRegistrationError, UNSUPPORTED_ROOT, lambda: operator_cli.main(run)
    )
    assert not locator.exists()


def test_changed_accepted_bytes_refuse(pg_db: PgTestDatabase, tmp_path: Path) -> None:
    """Under an accepted name, a config with one byte changed or a manifest with one filing
    time changed refuses before anything is staged."""
    root, store = _replacement(tmp_path, _refile), _intake_store(tmp_path)
    _refuses(
        pg_db,
        store,
        SourceRegistrationError,
        "manifest not accepted",
        lambda: operator_cli.approved_intake(root / ACCEPTED, store, root=root),
    )
    config = root / ACCEPTED
    config.write_bytes(config.read_bytes().replace(b"Apar", b"Apaz", 1))
    _refuses(
        pg_db,
        store,
        SourceRegistrationError,
        "config not accepted",
        lambda: operator_cli.approved_intake(config, store, root=root),
    )
