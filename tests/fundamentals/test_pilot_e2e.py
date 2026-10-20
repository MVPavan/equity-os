"""PILOT-E2E (eqos-4j2.8): the pilot exit test, one cumulative PostgreSQL rehearsal.

On a disposable ``eqos_test_*`` database: the legacy store is reconciled and cut over, then Apar
PQ0 (FY26_Q2) → PQ1 → PQ2 → PQ3 (FY27_Q1) run, are compared with both vendors, reviewed and
approved; export, replay, retention, backup and restore follow. Every expected number comes from
the frozen ``pilot_manifest.yaml`` (or the ``stage1_manifest.yaml`` it pins) and every failing
assertion begins ``PILOT-n:`` (``docs/plans/PILOT-E2E.md``, PILOT checks). Verdict inputs this
test cannot supply stay external: PILOT-5's contradiction clause is waived for this pilot and
PILOT-9 is NOT MET until D8 is built (owner, 2026-10-20).
"""

from __future__ import annotations

import hashlib
import io
import sqlite3
import subprocess
from datetime import datetime
from fractions import Fraction
from pathlib import Path
from typing import Any

import psycopg
import pytest
from evidence_support import Ingest, ingest, policy
from ledger_support import CONTENT_HASH, CUTOFF
from manifest_support import approved
from pg_support import PgTestDatabase
from pilot_e2e_support import (
    MANIFEST,
    PILOT_PATH,
    Q0,
    Q1,
    Q2,
    Q3,
    QUARTERS,
    compare_run,
    fail,
    frozen_value,
    pilot1,
    pilot2,
    pilot10,
    pilot13,
    vendor_captures,
)
from pilot_manifest_check import KEYS as CLAIM_KEYS
from pilot_manifest_check import citations_allowed
from prep2b_support import COUNTS, STOCK, Pilot
from test_cutover_rollback import CUTOVER, Window
from test_frozen_manifests import REPO, load
from test_legacy_import import Rig
from test_pilot_citations import _cites_predecessor
from test_pilot_memory import _CREATED, _PROMOTED, _item, _line, _promote
from test_prep2b_run_draft import dictionary, mapping_set
from test_prep3_resume import ADMITTED_ROWS, RUN_TABLES, added, ids, interrupted
from test_prep5_rework import QOQ, Calls, _lines, _plan, calls
from test_prep6_review import (
    ACCEPTED,
    ANSWER,
    R1,
    REJECTED,
    T0,
    _claim,
    _finish,
    _review_set,
    _seeds,
    _shadow,
    _sources,
    _start,
    _ticking,
)

import fundamentals.api.cli as fundamentals_cli
import fundamentals.pg.cutover as cutover
from fundamentals.api.cli import main
from fundamentals.api.ledger_cli import _MEMORY_FILE, _NARRATIVE, _STEM, DEFAULT_IMPORT_CONFIG
from fundamentals.api.pipeline import PipelineResult
from fundamentals.canon.dictionary import CanonicalDictionary
from fundamentals.contracts.canonical import StatementFamily
from fundamentals.contracts.evidence import RunMode
from fundamentals.contracts.ledger import (
    CitationKind,
    ClaimState,
    DecisionKind,
    ReportKind,
    ReportSection,
    SubjectKind,
    VersionDraft,
)
from fundamentals.contracts.memory import MemoryStatus, SupportTarget
from fundamentals.ledger import lifecycle, review, store
from fundamentals.ledger.display import FILED, FILED_SUFFIX
from fundamentals.ledger.run_draft import GUIDANCE, recall
from fundamentals.memory.pg_store import PgMemoryStore

__all__ = ["calls", "dictionary", "ingest", "mapping_set", "policy"]

pytestmark = [pytest.mark.pg, pytest.mark.retained]

CABLES = "ledger.cables_revenue_growth.annual.consolidated"
FILED_COUNTS = {Q0: 13, Q1: 7, Q2: 7, Q3: 7}  # Evidence 2: PQ0 cites no predecessor fact
D8_EXIT = REPO / "tests/fundamentals/test_data_stage3_e2e.py"  # verify_project.sh's D8 row
WATCHLIST_HEAD = (
    "SELECT kind FROM eqos.decisions WHERE subject_kind = 'WATCHLIST' AND subject_id = %s "
    "ORDER BY id DESC LIMIT 1"
)
APPROVALS = (
    "SELECT count(*) FROM eqos.decisions WHERE subject_kind = 'REPORT_VERSION' "
    "AND subject_id = %s AND kind = 'APPROVE'"
)
CITED = (
    "SELECT source_sha256 FROM eqos.numeric_claims WHERE version_id = %s "
    "AND source_sha256 IS NOT NULL UNION SELECT c.blob_sha256 FROM eqos.numeric_claims n "
    "JOIN eqos.capture_refs c ON c.id = n.capture_ref_id WHERE n.version_id = %s"
)
CLAIM_ID = "SELECT id FROM eqos.numeric_claims WHERE version_id = %s AND claim_key = %s"
SESSIONS = (
    "SELECT extract(epoch FROM finished_at - started_at) FROM eqos.review_sessions "
    "WHERE version_id = %s"
)
EVENTS = (
    "SELECT r.claim_key, r.disposition, r.category FROM eqos.claim_reviews r "
    "JOIN eqos.review_sessions s ON s.id = r.session_id WHERE s.version_id = %s"
)
REPORT_ROWS = (
    "SELECT (SELECT count(*) FROM eqos.reports), (SELECT count(*) FROM eqos.report_versions)"
)
SEALED = (
    "SELECT sealed_digest FROM eqos.decisions WHERE subject_kind = 'REPORT_VERSION'"
    " AND subject_id = %s AND kind = 'REQUEST_CHANGES'"
)
VERSIONS = "SELECT id FROM eqos.report_versions"
IMPORT_SEALS = (
    "SELECT subject_id FROM eqos.decisions WHERE subject_kind = 'REPORT_VERSION' "
    "AND kind = 'IMPORT_SEAL'"
)
STEMS = (
    "SELECT v.id, r.period, r.kind, v.content_hash, "
    "row_number() OVER (PARTITION BY v.report_id ORDER BY v.id) FROM eqos.report_versions v "
    "JOIN eqos.reports r ON r.id = v.report_id WHERE r.entity_id = %s"
)


@pytest.fixture(scope="module", autouse=True)
def preflight() -> None:
    """PREP-7 step 0: the working manifest is the committed one, and it carries its own APPROVE
    over its own payload."""
    committed = subprocess.run(
        ["git", "show", f"HEAD:{PILOT_PATH}"], cwd=REPO, capture_output=True, check=True
    ).stdout
    assert (REPO / PILOT_PATH).read_bytes() == committed, "PILOT-0: the manifest differs from HEAD"
    approved(committed, committed)


def _version_ids(pilot: Pilot) -> list[int]:
    """Every report version id."""
    return [row[0] for row in pilot.query(VERSIONS)]


# PILOT-3, PILOT-8 ---------------------------------------------------------------------------


def _pilot3(
    pg_db: PgTestDatabase, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, ingest: Ingest
) -> Pilot:
    """PILOT-3: the legacy copy imports, reconciles and cuts over; the pilot then runs with no
    SQLite path reachable."""
    rig = Rig(pg_db, tmp_path)
    window = Window(rig)
    assert window.reconciled.equal(), "PILOT-3: the legacy copy does not reconcile"
    window.move(CUTOVER)
    pilot = Pilot(pg_db, tmp_path, monkeypatch, ingest, rig=rig, replayable=True)

    def no_sqlite(*_: object) -> Any:
        raise AssertionError("PILOT-3: the pilot reached a SQLite store")

    monkeypatch.setattr(cutover, "FactStore", no_sqlite)
    monkeypatch.setattr(sqlite3, "connect", no_sqlite)
    ((head,),) = pilot.query(WATCHLIST_HEAD, pilot.entity_id)
    assert head == DecisionKind.ADD.value, f"PILOT-8: the watchlist head is {head}, not ADD"
    return pilot


def _pilot8(pilot: Pilot, monkeypatch: pytest.MonkeyPatch) -> None:
    """PILOT-8: after the owner's ``REMOVE`` a runtime draft is refused and writes nothing."""
    monkeypatch.setattr("sys.stdin", io.StringIO("TEST: the pilot ends; remove the stock\n"))
    command = ["ledger", "decide", "WATCHLIST", str(pilot.entity_id), DecisionKind.REMOVE.value]
    assert main(command) == 0, "PILOT-8: the owner's REMOVE was refused"
    before = pilot.query(REPORT_ROWS)
    section = ReportSection(ordinal=0, section_key="thesis", body="thesis")
    try:
        with pilot.pg_db.runtime_pool() as pool, pool.connection() as conn, conn.transaction():
            cursor = conn.cursor()
            report = store.create_report(
                cursor, entity_id=pilot.entity_id, period=Q3, kind=ReportKind.BOOTSTRAP_THESIS
            )
            draft = VersionDraft(
                report_id=report,
                author="pilot-e2e",
                knowledge_cutoff=CUTOFF,
                content_hash=CONTENT_HASH,
                sections=(section,),
            )
            store.create_version(cursor, draft)
    except psycopg.Error as refused:
        assert "is not on the watchlist" in str(refused), f"PILOT-8: refused otherwise: {refused}"
    else:
        pytest.fail("PILOT-8: a runtime draft was written after REMOVE")
    assert pilot.query(REPORT_ROWS) == before, "PILOT-8: the refused draft wrote a row"


# PILOT-4 ------------------------------------------------------------------------------------


def _cited(pilot: Pilot, version_id: int | None) -> set[str]:
    """The blobs a version cites (none for no version)."""
    if version_id is None:
        return set()
    return {row[0] for row in pilot.query(CITED, version_id, version_id)}


def _pilot4(pilot: Pilot, quarter: str, result: PipelineResult, prior: int | None) -> None:
    """PILOT-4 on one run version: cutoff and designation, citations inside the package or the
    prior, the 46 frozen values, the citation routes and ``FILED`` labels, the predecessor QoQ
    priors, the export hash and an all-``MATCH`` claim check."""
    version_id = result.draft_version_id
    assert version_id is not None, f"PILOT-4: {quarter} wrote no draft"
    version, frozen = pilot.version(version_id), MANIFEST["quarters"][quarter]
    digest = frozen["retrospective"]["retrieval_manifest_sha256"]
    cutoff = datetime.fromisoformat(frozen["source_cutoff"]["v"])
    assert result.update.source_cutoff == cutoff, f"PILOT-4: {quarter} source cutoff"
    assert f"retrieval manifest sha256 {digest})" in version.sections[0].body, (
        f"PILOT-4: {quarter} is not designated retrospective on the pinned manifest"
    )
    package = {member["sha256"] for member in frozen["package"]}
    fail("PILOT-4", citations_allowed, _cited(pilot, version_id), package, _cited(pilot, prior))
    claims = {claim.claim_key: claim for claim in version.claims}
    figures = {k for k, c in claims.items() if c.citation.kind is not CitationKind.SOURCE_QUOTE}
    assert figures == CLAIM_KEYS, f"PILOT-4: {quarter} keys {sorted(figures ^ CLAIM_KEYS)}"
    for key in CLAIM_KEYS:
        got, want = Fraction(claims[key].value or 0), frozen_value(quarter, key)
        assert got == want, f"PILOT-4: {quarter} {key} {got} ≠ {want}"
    filed = {key for key, claim in claims.items() if FILED in claim.qualifiers}
    for key, claim in claims.items():
        cited = claim.citation
        if claim.section_key == GUIDANCE:
            assert cited.kind is CitationKind.SOURCE_QUOTE, f"PILOT-4: {key} is not a quote"
            continue
        routed = (
            (cited.kind is CitationKind.FIGURE and cited.fact_origin is not None)
            or (cited.kind is CitationKind.CALCULATION and cited.calculation_trace_id is not None)
            or (cited.kind is CitationKind.FIGURE and key in filed)
        )
        assert routed, f"PILOT-4: {quarter} {key} cites no fact, trace or labelled filed value"
    priors = {key for key in filed if key.startswith("cmp.") and key.endswith(".prior")}
    assert filed - priors <= {"calc.2"}, f"PILOT-4: {quarter} FILED on {sorted(filed - priors)}"
    assert len(filed) == FILED_COUNTS[quarter], f"PILOT-4: {quarter} {len(filed)} FILED claims"
    if prior is not None:
        predecessor = pilot.version(prior)
        qoq = [c for k, c in claims.items() if k.startswith("cmp.") and k.endswith(".qoq.prior")]
        assert all(_cites_predecessor(claim, predecessor) for claim in qoq), (
            f"PILOT-4: {quarter} QoQ priors do not cite the predecessor's facts"
        )
    exported = pilot.tmp_path / f"export-{version_id}.md"
    assert main(["ledger", "export", str(version_id), "--out", str(exported)]) == 0, (
        f"PILOT-4: {quarter} export failed"
    )
    body = exported.read_bytes()
    assert hashlib.sha256(body).hexdigest() == version.content_hash, f"PILOT-4: {quarter} hash"
    assert body.decode().count(FILED_SUFFIX) == len(filed), f"PILOT-4: {quarter} suffix"
    states = set(dict(pilot.validate(version_id).claim_states).values())
    assert states == {ClaimState.MATCH}, f"PILOT-4: {quarter} claim check {states}"


# PILOT-5 ------------------------------------------------------------------------------------


def _claim_id(pilot: Pilot, version_id: int, key: str) -> int:
    """A version's claim row id by key."""
    ((found,),) = pilot.query(CLAIM_ID, version_id, key)
    return int(found)


def _pilot5_line(
    pilot: Pilot, quarter: str, result: PipelineResult, memory: dict[str, int]
) -> tuple[str, datetime]:
    """PILOT-5: the run's sealed memory line: none through PQ1, A and G in PQ2, A and G′ but
    not the retired G nor B (promoted after PQ3's recall) in PQ3; A needs revalidation only
    after PQ1's failing retrospective check."""
    line, boundary = _line(pilot, result)
    listed = {name for name, item in memory.items() if f"memory:{item} " in line}
    want = {Q0: set(), Q1: set(), Q2: {"A", "G"}, Q3: {"A", "G2"}}[quarter]
    assert listed == want, f"PILOT-5: {quarter} memory line lists {sorted(listed)} ≠ {sorted(want)}"
    if "A" in want:
        flag = "yes" if quarter == Q3 else "no"
        assert f"memory:{memory['A']} (needs revalidation: {flag}; " in line, (
            f"PILOT-5: {quarter} does not flag A's revalidation {flag}"
        )
    return line, boundary


def _pilot5_late(
    pilot: Pilot, monkeypatch: pytest.MonkeyPatch, final: dict[str, int], memory: dict[str, int]
) -> None:
    """Before PQ3: a retrospective check of PQ1 fails A's support, and B (on PQ2's revenue) is
    staged, to be promoted once PQ3 has recalled and before it persists its draft."""
    validated = pilot.validate(final[Q1], RunMode.RETROSPECTIVE)
    assert validated.mode is RunMode.RETROSPECTIVE, "PILOT-5: PQ1 retrospective validation"
    draft = _item(pilot, _claim_id(pilot, final[Q2], "fact.revenue"), "PQ2's figures check MATCH")
    with pilot.pg_db.runtime_pool() as runtime:
        memory["B"] = PgMemoryStore(runtime).stage(draft)
    run_pipeline = fundamentals_cli.run_pipeline

    def promote_first(*args: Any, **kwargs: Any) -> Any:
        monkeypatch.setattr(fundamentals_cli, "run_pipeline", run_pipeline)
        _promote(pilot, memory["B"])
        return run_pipeline(*args, **kwargs)

    monkeypatch.setattr(fundamentals_cli, "run_pipeline", promote_first)


def _pilot5_promote(pilot: Pilot, quarter: str, version_id: int, memory: dict[str, int]) -> None:
    """After PQ1 the owner promotes A (a PQ1 fact) and G (PQ1's cables guidance); after PQ2,
    G′ superseding G on PQ2's cables claim."""
    drafts = {}
    if quarter == Q1:
        drafts["A"] = _item(pilot, _claim_id(pilot, version_id, "fact.revenue"), "PQ1 MATCH")
        drafts["G"] = _item(pilot, _claim_id(pilot, version_id, CABLES), "Cables guidance")
    elif quarter == Q2:
        (section,) = (s for s in pilot.version(version_id).sections if s.section_key == GUIDANCE)
        (cables,) = (line for line in section.body.splitlines() if f"{{{{c:{CABLES}|" in line)
        assert " — MODIFIED: " in cables, (
            f"PILOT-5: PQ2's cables guidance is not MODIFIED: {cables}"
        )
        item = _item(pilot, _claim_id(pilot, version_id, CABLES), "Cables guidance, restated")
        drafts["G2"] = item.model_copy(update={"supersedes_item_id": memory["G"]})
    for name, draft in drafts.items():
        with pilot.pg_db.runtime_pool() as runtime:
            memory[name] = PgMemoryStore(runtime).stage(draft)
        _promote(pilot, memory[name])


def _pilot5(
    pilot: Pilot,
    lines: list[tuple[PipelineResult, str, datetime]],
    memory: dict[str, int],
    final: dict[str, int],
) -> None:
    """PILOT-5: each line replays at its boundary, later events are excluded (B, promoted
    between PQ3's recall and its draft, is absent from PQ3's line and retrieved later), nothing
    is retrievable at a run's source cutoff, and G′'s provenance carries G and its support."""
    created = [pilot.query(_CREATED, result.draft_version_id)[0][0] for result, _, _ in lines]
    boundaries = [boundary for _, _, boundary in lines]
    for at, made, following in zip(boundaries, created, [*boundaries[1:], None], strict=True):
        assert at < made and (following is None or made < following), "PILOT-5: boundaries"
    ((promoted,),) = pilot.query(_PROMOTED, memory["B"])
    assert boundaries[-1] < promoted < created[-1], "PILOT-5: B is not a late event of PQ3"
    with pilot.pg_db.runtime_pool() as runtime:
        assert f"memory:{memory['B']} " in recall(runtime, pilot.entity_id), "PILOT-5: B"
        for result, line, at in lines:
            assert recall(runtime, pilot.entity_id, at=at) == line, f"PILOT-5: replay at {at}"
            cutoff = result.update.source_cutoff
            found = PgMemoryStore(runtime).retrieve("", stock=pilot.entity_id, cutoff=cutoff)
            assert found == (), f"PILOT-5: memory retrievable at the source cutoff {cutoff}"
        lineage = {item.id: item for item in PgMemoryStore(runtime).provenance(memory["G2"])}
    support = (
        tuple((ref.target, ref.target_id) for ref in lineage[memory["G"]].supports)
        if memory["G"] in lineage
        else ()
    )
    staged = ((SupportTarget.CLAIM, _claim_id(pilot, final[Q1], CABLES)),)
    assert support == staged, f"PILOT-5: G′'s provenance has G supported by {support} ≠ {staged}"
    assert lineage[memory["G2"]].status is MemoryStatus.PROMOTED, "PILOT-5: G′ is not promoted"


# PILOT-6, PILOT-9, PILOT-10, PILOT-13 -------------------------------------------------------


def _pilot6(pilot: Pilot, memory: dict[str, int], reviewed: list[int]) -> None:
    """PILOT-6: the read-only stock export writes exactly the five reviewed run versions and the
    imported sealed ones (the q0 thesis and each configured earnings update), each narrative at
    its content hash, and every promoted item in ``memory.md``."""
    out = pilot.tmp_path / "stock-export"
    command = ["ledger", "export", "--stock", STOCK, "--status-notes", "--memory"]
    assert main([*command, "--out", str(out)]) == 0, "PILOT-6: the stock export failed"
    imported = {row[0] for row in pilot.query(IMPORT_SEALS)}
    sealed = 1 + len(load(REPO / DEFAULT_IMPORT_CONFIG)["earnings_updates"])
    assert len(imported) == sealed and len(reviewed) == 5, "PILOT-6: the version inventory"
    stems = {row[0]: row[1:] for row in pilot.query(STEMS, pilot.entity_id)}
    expected = {
        _NARRATIVE.format(stem=_STEM.format(period=period, report_kind=kind, position=n)): digest
        for version_id, (period, kind, digest, n) in stems.items()
        if version_id in imported | set(reviewed)
    }
    names = {path.name for path in (out / STOCK).glob("*.md")} - {_MEMORY_FILE}
    narratives = {name for name in names if not name.endswith(".status.md")}
    assert narratives == set(expected), f"PILOT-6: exported {sorted(narratives ^ set(expected))}"
    for name, digest in expected.items():
        found = hashlib.sha256((out / STOCK / name).read_bytes()).hexdigest()
        assert found == digest, f"PILOT-6: {name} hash"
    exported = (out / STOCK / _MEMORY_FILE).read_text(encoding="utf-8")
    for name in ("A", "G2", "B"):
        assert f"## Memory item {memory[name]}:" in exported, f"PILOT-6: {name} not in memory.md"


def _pilot9(pilot: Pilot, dictionary: CanonicalDictionary) -> None:
    """PILOT-9: no version carries a shareholding key or section (vacuity, recorded only); the
    check stays NOT MET while D8's exit test is absent, so the verdict is CONDITIONAL."""
    shareholding = {
        r.canonical_id for r in dictionary.rows if r.family is StatementFamily.SHAREHOLDING
    }
    for version_id in _version_ids(pilot):
        version = pilot.version(version_id)
        keys = {c.measurement_key.canonical_id for c in version.claims if c.measurement_key}
        sections = {section.section_key for section in version.sections}
        assert not keys & shareholding and not any("shareholding" in s for s in sections), (
            f"PILOT-9: version {version_id} carries shareholding"
        )
    assert not D8_EXIT.exists(), "PILOT-9: D8 is built; the CONDITIONAL verdict needs review"


# PILOT-11, PILOT-12 -------------------------------------------------------------------------


def _pilot11_resume(pilot: Pilot, ingest: Ingest) -> PipelineResult:
    """PILOT-11 (i): PQ1 interrupted after its admission commits, then retried: no version or
    selection from the attempt; the retry reuses its comparison run, adds no fact or admission,
    keeps what committed, cites every trace and leaves one PQ1 draft."""
    run_id, tables = compare_run(Q1, pilot), (*RUN_TABLES, "runs")
    initial = ids(ingest, tables)
    interrupted(lambda: pilot.run(Q1), fundamentals_cli, "admit_run", after=True)
    committed = added(ingest, tables, initial)
    assert committed["fact_admissions"] and not committed["fact_selections"], "PILOT-11: (i)"
    assert not committed["report_versions"], "PILOT-11: the interrupted attempt left a version"
    result = pilot.run(Q1)
    retried = added(ingest, tables, initial)
    assert not retried["runs"], "PILOT-11: the retry did not reuse its comparison run"
    for table in ("fact_rows", "fact_admissions"):
        assert retried[table] == committed[table], f"PILOT-11: the retry added {table}"
    version = pilot.version(result.draft_version_id or 0)
    cited = {claim.citation.calculation_trace_id for claim in version.claims}
    admitted = {row[0] for row in pilot.query(ADMITTED_ROWS, run_id)}
    assert committed["fact_rows"] <= admitted, "PILOT-11: a committed fact is not admitted"
    assert retried["calculation_traces"] <= cited, "PILOT-11: an orphan trace"
    assert retried["report_versions"] == {result.draft_version_id}, "PILOT-11: PQ1 drafts"
    return result


def _pilot11_rework(pilot: Pilot, rejected: int, calls: Calls) -> PipelineResult:
    """PILOT-11 (ii): PQ2 v1, rejected on its revenue QoQ prior, reworks only the QoQ line
    into v2 on v1's digest: no fact, admission or selection, carried claims and lines intact.
    Returns the rework run."""
    found = _plan(pilot, rejected)
    assert found is not None and found.rerun == set(QOQ), "PILOT-11: the rework plan is not QOQ"
    facts = pilot.query(COUNTS)[0][:3]
    calls.clear()
    result = pilot.run(Q2)
    successor = pilot.version(result.draft_version_id or 0)
    before, after = (
        {c.claim_key: c for c in v.claims} for v in (pilot.version(rejected), successor)
    )
    digests = sorted(before[key].measurement_key.digest() for key in QOQ[1:])  # type: ignore[union-attr]
    assert sorted(calls["conclude"]) == digests, "PILOT-11: the rework computed other traces"
    assert calls["admit_run"] == [0] and calls["select_admitted"] == [], "PILOT-11: refacted"
    assert pilot.query(COUNTS)[0][:3] == facts, "PILOT-11: the rework wrote facts"
    assert all(after[key] == before[key] for key in found.carried), "PILOT-11: carried changed"
    held = {text for kept in found.lines.values() for text, keys in kept if keys <= found.carried}
    old, new = (_lines(pilot, v) for v in (rejected, result.draft_version_id or 0))
    assert [x for x in new if x in held] == [x for x in old if x in held], "PILOT-11: lines"
    with pilot.pg_db.runtime_pool() as pool, pool.connection() as conn:
        digest = store.sealed_digest(conn.cursor(), rejected)
    sealed = pilot.query(SEALED, rejected)
    assert successor.predecessor_id == rejected and sealed == [(digest,)], (
        "PILOT-11: the successor is not v(N+1) on v1's digest"
    )
    return result


def _pilot11_drill(pilot: Pilot, clean_id: int) -> None:
    """PILOT-11 (iii): the seeded shadow of PQ0 checks as the answer key and the owner's
    approval of it is refused."""
    draft = pilot.version(clean_id)
    clean = {claim.claim_key: claim for claim in draft.claims}
    with pilot.pg_db.runtime_pool() as pool:
        with pool.connection() as conn, conn.transaction(), conn.cursor() as cursor:
            shadow = _shadow(cursor, draft, pilot.entity_id, f"{Q0}_DRILL", _seeds(clean), R1)
        lifecycle.submit(pool, shadow, **pilot.sources())
    states = dict(pilot.validate(shadow).claim_states)
    assert states == {k: ANSWER.get(k, ClaimState.MATCH) for k in clean}, "PILOT-11: drill"
    try:
        with pilot.pg_db.owner_pool() as owner:
            lifecycle.decide(
                owner,
                subject_kind=SubjectKind.REPORT_VERSION,
                subject_id=shadow,
                kind=DecisionKind.APPROVE,
                ruling="TEST: approve the seeded shadow",
                **pilot.sources(),
            )
    except lifecycle.DecisionRefusedError:
        return
    pytest.fail("PILOT-11: the owner approved the seeded shadow")


def _review(
    pilot: Pilot, monkeypatch: pytest.MonkeyPatch, version_id: int, reject: str | None = None
) -> int:
    """PILOT-12: submit, then ``review start|claim|finish``: every review-set claim accepted
    and APPROVE, or ``reject`` rejected and REQUEST_CHANGES. Returns the version."""
    with pilot.pg_db.runtime_pool() as runtime:
        lifecycle.submit(runtime, version_id, **pilot.sources())
    keys, session = _review_set(pilot, version_id), pilot.tmp_path / f"review-{version_id}"
    assert _start(version_id, session) == 0, f"PILOT-12: review start {version_id}"
    for key in keys:
        status = _claim(session, key, REJECTED if key == reject else ACCEPTED)
        assert status == 0, f"PILOT-12: review claim {key} on {version_id}"
    kind, flags = (
        (DecisionKind.REQUEST_CHANGES, []) if reject else (DecisionKind.APPROVE, _sources(pilot))
    )
    assert _finish(monkeypatch, session, kind, *flags) == 0, f"PILOT-12: finish {version_id}"
    if not reject:
        ((approvals,),) = pilot.query(APPROVALS, version_id)
        assert approvals == 1, f"PILOT-4: version {version_id} has no owner APPROVE"
    return version_id


def _pilot12(pilot: Pilot, reviewed: list[int], rejected: int) -> None:
    """PILOT-12: one session per version reviewing exactly its review set: every stored claim
    of a full version, only the rejected claim of the successor (its accepted QoQ siblings
    rerun unchanged, decision 6); v1's scripted rejection; the report total is both PQ2
    sessions."""
    successor = min(v for v in reviewed if v > rejected)
    for version_id in reviewed:
        assert len(pilot.query(SESSIONS, version_id)) == 1, f"PILOT-12: {version_id} sessions"
        claims = {claim.claim_key for claim in pilot.version(version_id).claims}
        want = {QOQ[0]} if version_id == successor else claims
        events = {key for key, *_ in pilot.query(EVENTS, version_id)}
        assert events == want, f"PILOT-12: {version_id} reviewed {sorted(events ^ want)[:5]}"
    scripted = {
        (key, *(("rejected", "wording") if key == QOQ[0] else ("accepted", "none")))
        for key in (claim.claim_key for claim in pilot.version(rejected).claims)
    }
    assert set(pilot.query(EVENTS, rejected)) == scripted, "PILOT-12: v1's rejection"
    total = sum(pilot.query(SESSIONS, v)[0][0] for v in (rejected, successor))
    with pilot.pg_db.runtime_pool() as pool, pool.connection() as conn:
        found = review.summary(conn.cursor(), successor).report_wall_clock_minutes
    assert found == float(total) / 60, f"PILOT-12: report time {found} ≠ {total}s"


# The exit test ------------------------------------------------------------------------------


def test_pilot_end_to_end(
    pg_db: PgTestDatabase,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    ingest: Ingest,
    dictionary: CanonicalDictionary,
    calls: Calls,
) -> None:
    """PILOT-3, PILOT-8 ``ADD``; per quarter the run, PILOT-1, 2, 4, 5 (PQ3's late event),
    11 (i)/(ii), 12; then
    PILOT-6, 13, 10, 11 (iii), the PILOT-8 refusal and PILOT-9 (``docs/plans/PILOT-E2E.md``)."""
    pilot = _pilot3(pg_db, tmp_path, monkeypatch, ingest)
    _ticking(monkeypatch, T0)
    captures = vendor_captures(pilot)
    final: dict[str, int] = {}
    runs: list[int] = []
    memory: dict[str, int] = {}
    lines: list[tuple[PipelineResult, str, datetime]] = []
    reviewed: list[int] = []
    rejected = 0
    for index, quarter in enumerate(QUARTERS):
        prior = final.get(QUARTERS[index - 1]) if index else None
        if quarter == Q3:
            _pilot5_late(pilot, monkeypatch, final, memory)
        result = _pilot11_resume(pilot, ingest) if quarter == Q1 else pilot.run(quarter)
        version = pilot.version(result.draft_version_id or 0)
        pilot1(pilot, quarter, dictionary, version)
        runs += [compare_run(quarter, pilot), pilot2(pilot, quarter, captures, version)]
        _pilot4(pilot, quarter, result, prior)
        lines.append((result, *_pilot5_line(pilot, quarter, result, memory)))
        if quarter == Q2:
            rejected = result.draft_version_id or 0
            reviewed.append(_review(pilot, monkeypatch, rejected, reject=QOQ[0]))
            result = _pilot11_rework(pilot, rejected, calls)
            _pilot4(pilot, quarter, result, prior)
            lines.append((result, *_pilot5_line(pilot, quarter, result, memory)))
        final[quarter] = result.draft_version_id or 0
        reviewed.append(_review(pilot, monkeypatch, final[quarter]))
        _pilot5_promote(pilot, quarter, final[quarter], memory)
    _pilot5(pilot, lines, memory, final)
    _pilot12(pilot, reviewed, rejected)
    _pilot6(pilot, memory, reviewed)
    with pg_db.runtime_pool() as pool:
        pilot13(pool, runs, "live")
    pilot10(pilot, monkeypatch, runs)
    _pilot11_drill(pilot, final[Q0])
    _pilot8(pilot, monkeypatch)
    _pilot9(pilot, dictionary)
