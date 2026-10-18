"""PREP-3 proving tests: each step of an Apar quarter's PostgreSQL workflow, interrupted at a
commit boundary and re-run, reuses what committed and ends where an uninterrupted attempt ends.

An interruption raises ``Interrupted`` (a ``BaseException``, so no ``except Exception`` swallows
it) from a wrapper installed in its own ``MonkeyPatch.context()``; the fixture's monkeypatch
(the test database's env) is never undone. Each uninterrupted baseline runs the step once on its
own clone of the template database and keeps only id-free values.

The ingest orphan (plan decision 6): an interruption between a capture's publication and its
``capture_refs`` row leaves ``<store>/<source>/<surface>/<request_key>/<capture_id>/`` with no
row. It is not a record: leave it, or remove that directory (never the blob) before a purge,
which otherwise reports it as ``UNREGISTERED`` or ``UNKNOWN_LINK``. Register-sources'
install-without-receipt recovery is ``test_source_intake_store.py:263``.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest
from evidence_support import Ingest, ingest, policy
from pg_support import cloned_database
from prep2b_support import STOCK, Pilot
from psycopg import sql
from retained_support import APAR_MANIFEST, apar_store
from test_prep2b_run_draft import dictionary, mapping_set

import fundamentals.api.cli as cli
import fundamentals.api.ledger_cli as ledger_cli
from fundamentals.api.cli import main
from fundamentals.api.source_admission import load_source_manifest
from fundamentals.contracts.canonical import Representation
from fundamentals.contracts.ledger import ClaimState, DecisionKind, VersionDraft, VersionStatus
from fundamentals.contracts.source_registration import SourceRegistrationError, SourceRole
from fundamentals.evidence.capture_retention import Registration
from fundamentals.evidence.first_party_ingest import IngestReport
from fundamentals.evidence.repository import EvidenceRepository
from fundamentals.ledger import lifecycle, run_draft, store
from fundamentals.ledger.export import stock_entity, stock_versions
from fundamentals.ledger.lifecycle import DecisionRefusedError, version_status
from fundamentals.ledger.run_traces import RunDraftError
from fundamentals.store.pg_fact_store import PgFactStore
from fundamentals.store.snapshot_store import SnapshotStore
from fundamentals.store.source_intake_store import SourceIntakeStore

__all__ = ["dictionary", "ingest", "mapping_set", "policy"]

pytestmark = [pytest.mark.pg, pytest.mark.retained]

Q2 = "FY26_Q2"
INGEST_TABLES = ("capture_refs", "occurrences", "interpretations", "filing_packages")
RUN_TABLES = ("calculation_traces", "fact_rows", "fact_selections", "report_versions")
KEYS = {"fact_rows": "handle", "fact_selections": "handle"}  # one store: handle is the row id


class Interrupted(BaseException):
    """The simulated crash."""


def interrupt(
    patch: pytest.MonkeyPatch, owner: object, name: str, *, after: bool, nth: int = 1
) -> list[int]:
    """Wrap ``owner.name`` on ``patch`` to raise before or after its ``nth`` call; the returned
    list records the firing."""
    original = getattr(owner, name)
    calls: list[int] = []
    fired: list[int] = []

    def wrapper(*args: Any, **kwargs: Any) -> Any:
        calls.append(1)
        if len(calls) == nth and not after:
            fired.append(nth)
            raise Interrupted(name)
        result = original(*args, **kwargs)
        if len(calls) == nth:
            fired.append(nth)
            raise Interrupted(name)
        return result

    patch.setattr(owner, name, wrapper)
    return fired


def interrupted(
    call: Callable[[], object], owner: object, name: str, *, after: bool, nth: int = 1
) -> None:
    """``call`` dies at the boundary, which must have been reached."""
    with pytest.MonkeyPatch.context() as patch:
        fired = interrupt(patch, owner, name, after=after, nth=nth)
        with pytest.raises(Interrupted):
            call()
    assert fired == [nth], f"boundary {name} #{nth} not reached"


def delta(before: dict[str, int], after: dict[str, int]) -> dict[str, int]:
    """Per-table row-count change."""
    return {table: after[table] - before[table] for table in after if after[table] != before[table]}


def ids(ingest: Ingest, tables: tuple[str, ...]) -> dict[str, set[int]]:
    """Every row id of each table."""
    with ingest.pg_db.runtime_pool() as pool, pool.connection() as conn:
        return {
            table: {
                row[0]
                for row in conn.execute(
                    sql.SQL("SELECT {} FROM eqos.{}").format(
                        sql.Identifier(KEYS.get(table, "id")), sql.Identifier(table)
                    )
                )
            }
            for table in tables
        }


def added(
    ingest: Ingest, tables: tuple[str, ...], since: dict[str, set[int]]
) -> dict[str, set[int]]:
    """Row ids each table gained since ``since``."""
    return {table: found - since[table] for table, found in ids(ingest, tables).items()}


@contextmanager
def fresh_ingest(request: pytest.FixtureRequest) -> Iterator[Ingest]:
    """An ``Ingest`` on its own clone of the template database and its own directories."""
    template = request.getfixturevalue("pg_template")
    tmp = request.getfixturevalue("tmp_path_factory").mktemp("baseline")
    pins = (request.getfixturevalue(name) for name in ("dictionary", "mapping_set", "policy"))
    with cloned_database(template) as database, database.runtime_pool() as pool:
        yield Ingest(database, EvidenceRepository(pool), tmp, *pins)


def summary(report: IngestReport) -> tuple[Any, ...]:
    """An ingest report's id-free content."""
    attempts = sorted(
        (a.representation, a.stage, a.statement_family or "", a.outcome) for a in report.attempts
    )
    counts = dict(report.interpretation_counts)
    return report.package_id is not None, report.occurrence_count, counts, attempts


def claims(version: VersionDraft) -> list[tuple[Any, ...]]:
    """A version's claims without record ids."""
    return sorted(
        (c.claim_key, c.value, c.lower_bound, c.upper_bound, c.citation.kind)
        for c in version.claims
    )


@pytest.fixture
def pilot(pg_db: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, ingest: Ingest) -> Pilot:
    """The pilot database, ready for PostgreSQL runs."""
    return Pilot(pg_db, tmp_path, monkeypatch, ingest)


@pytest.fixture
def ingest_baseline(request: pytest.FixtureRequest) -> tuple[dict[str, int], tuple[Any, ...]]:
    """An uninterrupted FY26_Q2 ingest: its row-count delta and report."""
    with fresh_ingest(request) as other:
        start = other.table_counts()
        report = other.run(other.intake())
        return delta(start, other.table_counts()), summary(report)


@pytest.fixture
def run_baseline(request: pytest.FixtureRequest) -> tuple[dict[str, int], list[tuple[Any, ...]]]:
    """An uninterrupted FY26_Q2 pilot run: its row-count delta and draft claims."""
    with pytest.MonkeyPatch.context() as patch, fresh_ingest(request) as other:
        baseline = Pilot(other.pg_db, other.tmp_path, patch, other)
        baseline.registered(Q2)
        start = other.table_counts()
        version_id = baseline.run(Q2).draft_version_id
        assert version_id is not None
        return delta(start, other.table_counts()), claims(baseline.version(version_id))


def receipts(pilot: Pilot) -> dict[str, bytes]:
    """Every register-sources receipt's bytes, by binding."""
    found = (pilot.retained / ".source-intake").glob("*/registration.json")
    return {path.parent.name: path.read_bytes() for path in found}


@pytest.mark.parametrize(
    ("owner", "name", "nth", "kept"),
    [
        pytest.param(SourceIntakeStore, "register_capture", 1, 1, id="between-originals"),
        pytest.param(SourceIntakeStore, "register_capture", 3, 3, id="before-locator"),
        pytest.param(cli, "register_sources", 1, 3, id="after-locator"),
    ],
)
def test_register_sources_resumes(
    pilot: Pilot, owner: object, name: str, nth: int, kept: int
) -> None:
    """S1 retried with the same originals, context and argv: earlier receipts come back
    byte-identical and the rest are added; after the locator is published the retry refuses to
    overwrite it, and completion is the locator holding the submitted refs, each resolving."""
    context, register, _ = pilot.prepared(Q2)
    manifest, locator = (
        Path(register[register.index(flag) + 1])
        for flag in (
            "--source-admission-manifest",
            "--out-manifest",
        )
    )
    interrupted(lambda: main(register, intake_context=context), owner, name, after=True, nth=nth)
    before = receipts(pilot)
    assert len(before) == kept
    if owner is cli:
        with pytest.raises(SourceRegistrationError, match="refusing to overwrite locator"):
            main(register, intake_context=context)
    else:
        assert not locator.exists()
        assert main(register, intake_context=context) == 0
    after = receipts(pilot)
    assert len(after) == len(SourceRole) and before.items() <= after.items()
    refs = load_source_manifest(locator)
    assert refs == load_source_manifest(manifest)
    intake = SourceIntakeStore(SnapshotStore(pilot.retained), approved_intake=context)
    for role in SourceRole:
        intake.get_registration(role=role, **getattr(refs, role.value).model_dump())


@pytest.mark.parametrize(
    ("owner", "name", "after"),
    [
        pytest.param(Registration, "insert", False, id="capture-row"),
        pytest.param(EvidenceRepository, "put_generation", True, id="generation"),
        pytest.param(EvidenceRepository, "put_interpretations", True, id="interpretations"),
        pytest.param(EvidenceRepository, "put_package", True, id="package"),
        pytest.param(EvidenceRepository, "put_segment_members", True, id="segment-members"),
        # No ``put_attempts`` case: the default XBRL + PDF intake locates every present PDF
        # family and stages every member, so it writes no package-owned or acquisition attempt.
    ],
)
def test_ingest_resumes(
    ingest: Ingest,
    ingest_baseline: tuple[dict[str, int], tuple[Any, ...]],
    owner: object,
    name: str,
    after: bool,
) -> None:
    """S2 interrupted after the first call at each boundary, then retried: the resumed package
    uses every row the interrupted attempt committed, the attempt plus retry add exactly the
    baseline's rows (so the retry adds only the remainder) and report the same, and a further
    run adds nothing. The capture-row case leaves one orphan capture (decision 6)."""
    start, initial = ingest.table_counts(), ids(ingest, INGEST_TABLES)
    intake = ingest.intake()
    interrupted(lambda: ingest.run(intake), owner, name, after=after)
    committed = added(ingest, INGEST_TABLES, initial)
    report = ingest.run(intake)
    package = ingest.package(report)
    used = {
        "capture_refs": {ingest.capture_id(report, r) for r in package.members},
        "occurrences": set(ingest.occurrences(report)),
        "interpretations": {i.interpretation_id for i in ingest.interpretations(report)},
        "filing_packages": {report.package_id},
    }
    for table, rows in committed.items():
        assert rows <= used[table], table
    assert (delta(start, ingest.table_counts()), summary(report)) == ingest_baseline
    stable = ingest.table_counts()
    ingest.run(intake)
    assert ingest.table_counts() == stable
    if owner is Registration:
        capture = package.members[Representation.XBRL].capture
        route = (capture.source_id, capture.surface, capture.request_key)
        records = apar_store(ingest.tmp_path).list_captures(*route)
        (orphan,) = [r for r in records if r.capture_id != capture.capture_id]
        assert len(records) == 2, f"orphan {orphan.capture_id}"
        with ingest.pg_db.runtime_pool() as pool, pool.connection() as conn:
            (count,) = conn.execute(
                "SELECT count(*) FROM eqos.capture_refs "
                "WHERE source_id = %s AND surface = %s AND request_key = %s",
                route,
            ).fetchone() or (0,)
        assert count == 1, f"orphan {orphan.capture_id} registered"
        assert capture.registered_at > orphan.retrieved_at


def run_resumes(
    pilot: Pilot,
    ingest: Ingest,
    baseline: tuple[dict[str, int], list[tuple[Any, ...]]],
    boundary: tuple[object, str, bool, int],
) -> None:
    """The FY26_Q2 run interrupted at ``boundary``, then retried: persistence runs traces →
    facts and selections → draft, so the interruption leaves no version; the retry's draft
    cites every committed trace and stores every committed fact row; the attempt plus retry
    add exactly the baseline's rows (the retry only the remainder), the same claims, all MATCH,
    and one DRAFT head, which makes a further run refuse."""
    owner, name, after, nth = boundary
    pilot.registered(Q2)
    start, initial = ingest.table_counts(), ids(ingest, RUN_TABLES)
    interrupted(lambda: pilot.run(Q2), owner, name, after=after, nth=nth)
    committed = added(ingest, RUN_TABLES, initial)
    assert not committed["report_versions"]
    traces = len(committed["calculation_traces"])
    if name == "put_calculation_trace":
        assert traces == 1 and not committed["fact_rows"] and not committed["fact_selections"]
    else:
        assert traces == baseline[0]["calculation_traces"]
    result = pilot.run(Q2)
    assert result.draft_version_id is not None
    version = pilot.version(result.draft_version_id)
    assert committed["fact_rows"] <= {r.row_id for r in result.stored_revisions}
    cited = {c.citation.calculation_trace_id for c in version.claims}
    assert committed["calculation_traces"] <= cited
    assert (delta(start, ingest.table_counts()), claims(version)) == baseline
    states = {state for _, state in pilot.validate(result.draft_version_id).claim_states}
    assert states == {ClaimState.MATCH}
    with pilot.pg_db.runtime_pool() as pool, pool.connection() as conn:
        assert version_status(conn.cursor(), head(pilot)) is VersionStatus.DRAFT
    stable = ingest.table_counts()
    with pytest.raises(RunDraftError, match="is open"):
        pilot.run(Q2)
    assert ingest.table_counts() == stable


def head(pilot: Pilot) -> int:
    """FY26_Q2's latest earnings-update version."""
    ((found,),) = pilot.query(
        "SELECT max(v.id) FROM eqos.report_versions v JOIN eqos.reports r ON r.id = v.report_id "
        "WHERE r.period = %s AND r.kind = 'EARNINGS_UPDATE'",
        Q2,
    )
    return int(found)


@pytest.mark.parametrize(
    "boundary",
    [
        pytest.param((PgFactStore, "put", True, 2), id="fact-row"),
        pytest.param((PgFactStore, "select_canonical", True, 1), id="selection"),
    ],
)
def test_run_resumes_after_interrupted_fact_writes(
    pilot: Pilot,
    ingest: Ingest,
    run_baseline: tuple[dict[str, int], list[tuple[Any, ...]]],
    boundary: tuple[object, str, bool, int],
) -> None:
    """PILOT-11's first clause: a run interrupted during its fact writes (after all its traces)
    resumes without duplication."""
    run_resumes(pilot, ingest, run_baseline, boundary)


@pytest.mark.parametrize(
    "boundary",
    [
        pytest.param((EvidenceRepository, "put_calculation_trace", True, 1), id="trace"),
        # The in-transaction AS_KNOWN check runs after the version insert.
        pytest.param((run_draft, "check_version", False, 1), id="draft"),
    ],
)
def test_run_resumes_after_interrupted_trace_or_draft(
    pilot: Pilot,
    ingest: Ingest,
    run_baseline: tuple[dict[str, int], list[tuple[Any, ...]]],
    boundary: tuple[object, str, bool, int],
) -> None:
    """A run interrupted after its first trace, or inside its draft transaction, resumes
    without duplication."""
    run_resumes(pilot, ingest, run_baseline, boundary)


@pytest.mark.parametrize("after", [False, True], ids=["before-json", "between-files"])
def test_run_interrupted_after_its_draft_recovers_by_export(
    pilot: Pilot, ingest: Ingest, tmp_path: Path, after: bool
) -> None:
    """S3f: the draft committed, then the emit died before the JSON or between the files. The
    re-run refuses before the pipeline and writes nothing; the DRAFT head is submitted,
    approved and exported, its narrative hashing to the stored content hash (decision 2)."""
    context, argv = pilot.registered(Q2)
    dump, markdown = tmp_path / "run.json", tmp_path / "run.md"
    command = [*argv, "--retrospective", str(APAR_MANIFEST)]
    command += ["--out-json", str(dump), "--out", str(markdown)]
    emit = cli.write_bytes_no_clobber.__name__
    interrupted(lambda: main(command, intake_context=context), cli, emit, after=after)
    assert dump.exists() is after and not markdown.exists()
    stable = ingest.table_counts()
    with pytest.raises(RunDraftError, match="is open"):
        main(command, intake_context=context)
    assert ingest.table_counts() == stable
    version_id = head(pilot)
    with pilot.pg_db.runtime_pool() as pool, pool.connection() as conn:
        assert version_status(conn.cursor(), version_id) is VersionStatus.DRAFT
    pilot.approve(version_id)
    exported = tmp_path / "export.md"
    assert main(["ledger", "export", str(version_id), "--out", str(exported)]) == 0
    digest = hashlib.sha256(exported.read_bytes()).hexdigest()
    assert digest == pilot.version(version_id).content_hash


@pytest.mark.parametrize("kind", [DecisionKind.SUBMIT, DecisionKind.APPROVE])
def test_decision_resumes(pilot: Pilot, ingest: Ingest, kind: DecisionKind) -> None:
    """S4/S5 interrupted inside the transaction leave no row and the retry records exactly one
    decision (and the approval's validation); a repeat after the commit refuses and adds no
    row; the state reads IN_REVIEW / APPROVED."""
    version_id = pilot.run(Q2).draft_version_id
    assert version_id is not None

    def submit() -> None:
        with pilot.pg_db.runtime_pool() as runtime:
            lifecycle.submit(runtime, version_id, **pilot.sources())

    decide = submit
    expected = {"decisions": 1}
    if kind is DecisionKind.APPROVE:
        submit()
        claim_count = len(pilot.version(version_id).claims)
        expected |= {"validations": 1, "validation_claim_states": claim_count}

        def decide() -> None:
            pilot.approve(version_id, submit=False)

    start = ingest.table_counts()
    interrupted(decide, store, "insert_decision", after=True)
    assert ingest.table_counts() == start
    decide()
    assert delta(start, ingest.table_counts()) == expected
    stable = ingest.table_counts()
    with pytest.raises(DecisionRefusedError):
        decide()
    assert ingest.table_counts() == stable
    status = VersionStatus.APPROVED if kind is DecisionKind.APPROVE else VersionStatus.IN_REVIEW
    with pilot.pg_db.runtime_pool() as pool, pool.connection() as conn:
        assert version_status(conn.cursor(), version_id) is status


def test_stock_export_resumes_into_a_fresh_directory(
    pilot: Pilot, ingest: Ingest, tmp_path: Path
) -> None:
    """S6 interrupted before its second file leaves the database untouched; a retry into the
    same directory refuses and writes nothing, one into a fresh directory writes every sealed
    version's narrative, each hashing to its content hash."""
    start = ingest.table_counts()

    def export(out: Path) -> int:
        return main(["ledger", "export", "--stock", STOCK, "--out", str(out)])

    first, fresh = tmp_path / "first", tmp_path / "fresh"
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(ledger_cli, "open", open, raising=False)
        fired = interrupt(patch, ledger_cli, "open", after=False, nth=2)
        with pytest.raises(Interrupted):
            export(first)
    assert fired == [2]
    partial = {path: path.read_bytes() for path in (first / STOCK).iterdir()}
    assert export(first) == ledger_cli.EXIT_REFUSED  # FileExistsError, before any write
    assert {path: path.read_bytes() for path in (first / STOCK).iterdir()} == partial
    assert export(fresh) == 0
    with pilot.pg_db.runtime_pool() as pool, pool.connection() as conn:
        cursor = conn.cursor()
        hashes = sorted(v.content_hash for v in stock_versions(cursor, stock_entity(cursor, STOCK)))
    written = sorted(hashlib.sha256(f.read_bytes()).hexdigest() for f in (fresh / STOCK).iterdir())
    assert written == hashes and len(hashes) > 1
    assert ingest.table_counts() == start
