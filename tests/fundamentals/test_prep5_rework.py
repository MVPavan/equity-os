"""PREP-5 acceptance: a rejected claim reworks only its affected claims into v(N+1).

Task 1: a ``REQUEST_CHANGES`` records the claims it rejects, each a distinct claim key of the
version under review, in an immutable column; a stored trace's operand set cannot grow.
Task 2: a rejected version's package inputs and rerun set are derived from its verified rows.
Task 3: a rework run derives only the rerun lines and refuses any other movement before writing;
``--full-successor`` reruns the version whole; the head is re-checked before and at the write.
Task 4 (PILOT-11): a corrected comparator filing reworks its dependent claims into an approved
v(N+1); a correction reaching a carried claim, or a source outside the cutoff or the package,
refuses before any write.
"""

from __future__ import annotations

import dataclasses
import hashlib
import io
import json
import sqlite3
from collections import defaultdict
from collections.abc import Callable
from datetime import date
from decimal import ROUND_HALF_EVEN, Decimal
from fractions import Fraction
from functools import partial
from pathlib import Path
from typing import Any

import psycopg
import pytest
import yaml
from evidence_support import Ingest, ingest, policy
from ledger_support import RULING, SELF_CITED, Ledger, claim, ledger
from pg_evidence_schema_support import _insert, _trace, runtime, seeded
from pg_support import PgTestDatabase
from prep2b_support import COMPARATOR_KIND, STOCK, Pilot
from psycopg import errors
from retained_support import (
    APAR_MANIFEST,
    INPUTS_DIR,
    STORE_DIR,
    XBRL_DIR,
    apar_original,
    manifest_entry,
)
from test_prep2b_run_draft import dictionary, mapping_set

from fundamentals.api import cli
from fundamentals.api.cli import _build_parser, main, run_command
from fundamentals.api.ledger_cli import DEFAULT_IMPORT_CONFIG
from fundamentals.api.pipeline import PipelineResult
from fundamentals.canon.formula import CalculationTrace, TraceOperand
from fundamentals.contracts.canonical import Representation
from fundamentals.contracts.ledger import (
    Citation,
    CitationKind,
    DecisionKind,
    NumericClaim,
    SubjectKind,
    VersionStatus,
)
from fundamentals.evidence.capture_intake import retained_intake_from_manifest
from fundamentals.evidence.repository import EvidenceRepository
from fundamentals.evidence.repository_calc import StoredTrace
from fundamentals.evidence.xbrl_adapter import parse_instance
from fundamentals.extract.xbrl_parser import RawXbrlFact
from fundamentals.ledger import lifecycle, rework, run_draft, run_traces, store
from fundamentals.ledger.run_traces import CHANGES, RunDraftError, _Binder
from fundamentals.pg.settings import PgRole
from fundamentals.store.pg_fact_store import PgFactStore

__all__ = ["dictionary", "ingest", "ledger", "mapping_set", "policy", "runtime", "seeded"]

pytestmark = [pytest.mark.pg, pytest.mark.retained]

V = SubjectKind.REPORT_VERSION
CLAIM = "calc.1"
OTHER_CLAIM = "calc.2"
EXIT_REFUSED = 2


@pytest.fixture
def under_review(ledger: Ledger) -> int:
    """An ``IN_REVIEW`` version holding ``CLAIM``, beside another report's version holding
    ``OTHER_CLAIM``."""
    version = ledger.draft(ledger.report())
    ledger.submit(version)
    ledger.draft(ledger.report(), claims=(claim(ledger.trace_id, OTHER_CLAIM),))
    return version


@pytest.mark.parametrize(
    ("kind", "keys", "via_cli"),
    [
        (DecisionKind.REQUEST_CHANGES, ("fact.unknown",), True),
        (DecisionKind.REQUEST_CHANGES, (CLAIM, CLAIM), True),
        (DecisionKind.REJECT, (CLAIM,), False),
        (DecisionKind.REQUEST_CHANGES, (OTHER_CLAIM,), False),
    ],
    ids=["unknown", "duplicate", "reject", "other-version"],
)
def test_a_rejection_names_only_distinct_claims_of_the_version_under_review(
    ledger: Ledger,
    under_review: int,
    pg_db: PgTestDatabase,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    kind: DecisionKind,
    keys: tuple[str, ...],
    via_cli: bool,
) -> None:
    """The rejected set must name claims of the version being reviewed, each once, and only on
    a ``REQUEST_CHANGES``: a later rework reruns exactly what it names. Each refusal is the
    schema's (23514), never the role's privileges, and writes no decision."""
    version = under_review
    before = ledger.head(version)
    if via_cli:
        for name, value in pg_db.cli_env().items():
            monkeypatch.setenv(name, value)
        monkeypatch.setattr("sys.stdin", io.StringIO(RULING))
        flags = [arg for key in keys for arg in ("--claim", key)]
        command = ["ledger", "decide", V.value, str(version), kind.value, *flags]
        assert main(command) == EXIT_REFUSED
        captured = capsys.readouterr()
        assert "are not distinct claims of version" in captured.out + captured.err
    else:
        with pytest.raises(errors.CheckViolation) as refused:
            ledger.decide(PgRole.OWNER, version, kind, rejected_claims=keys)
        assert refused.value.sqlstate == "23514"
    assert ledger.head(version) == before


def test_a_recorded_rejection_is_immutable(
    ledger: Ledger, under_review: int, pg_db: PgTestDatabase
) -> None:
    """The decision keeps the keys it rejected; not even the migrator can rewrite them."""
    version = under_review
    record = lifecycle.decide(
        ledger.pools[PgRole.OWNER],
        subject_kind=V,
        subject_id=version,
        kind=DecisionKind.REQUEST_CHANGES,
        ruling=RULING,
        claims=(CLAIM,),
    )
    assert record.rejected_claims == (CLAIM,)
    with pg_db.migrator_connection() as migrator, pytest.raises(psycopg.Error, match="immutable"):
        migrator.execute(
            "UPDATE eqos.decisions SET rejected_claims = %s WHERE id = %s",
            ([OTHER_CLAIM], record.id),
        )


def _operand(interpretation_id: int, ordinal: int) -> TraceOperand:
    """A selected leaf operand."""
    return TraceOperand.model_validate(
        {
            "name": f"x{ordinal}",
            "key_digest": f"key-{ordinal}",
            "temporal_role": "DURATION",
            "interpretation_id": interpretation_id,
            "operand_trace_id": None,
            "alignment_proof_id": None,
            "mapping_entry_id": None,
            "qualification_ref": None,
            "scoped_tier": "EQUIVALENCE_UNPROVEN",
            "selection_source": "PACKAGE_AS_REPORTED",
            "source_state": "VALUE",
            "value": Decimal(1),
            "lower": Decimal(1),
            "upper": Decimal(1),
            "exact_value": Fraction(1),
            "exact_interval": {"lower": Fraction(1), "upper": Fraction(1)},
        }
    )


def _two_operand_trace(first: int, second: int) -> CalculationTrace:
    """A computed trace over two leaf operands, of interpretations ``first`` and ``second``."""
    return CalculationTrace.model_validate(
        {
            **_trace(),
            "operands": (_operand(first, 0), _operand(second, 1)),
            "exact_value": Fraction(617, 50),
            "exact_interval": {"lower": Fraction(1233, 100), "upper": Fraction(247, 20)},
        }
    )


@pytest.mark.parametrize(
    ("ordinal", "closed", "sqlstate"),
    [(2, False, "23514"), (0, False, "23505"), (0, True, "23514")],
    ids=["past-count", "taken", "pre-0039"],
)
def test_a_stored_trace_takes_no_further_operand(
    pg_db: PgTestDatabase,
    seeded: dict[str, int],
    runtime: psycopg.Connection,
    ordinal: int,
    closed: bool,
    sqlstate: str,
) -> None:
    """A cited trace must not gain an operand, now or after a restore: the writer records the
    count it stores, every slot below it is taken, and a row without a count (pre-0039) admits
    none. The refusal reaches the trace writer's own role."""
    trace = _two_operand_trace(seeded["interpretations"], seeded["interpretations"])
    with pg_db.runtime_pool() as pool:
        trace_id = EvidenceRepository(pool).put_calculation_trace(trace)
    count = runtime.execute(
        "SELECT operand_count FROM eqos.calculation_traces WHERE id = %s", (trace_id,)
    ).fetchone()
    assert count == (2,)
    if closed:
        with pg_db.migrator_connection() as migrator:
            trace_id = _insert(migrator, "calculation_traces", _trace("a" * 64) | _NO_COUNT)
    row: dict[str, Any] = {"calculation_trace_id": trace_id, "ordinal": ordinal} | _LATE_OPERAND
    with pytest.raises(psycopg.Error) as refused:
        _insert(runtime, "calculation_trace_operands", row)
    assert refused.value.sqlstate == sqlstate


_NO_COUNT: dict[str, Any] = {"operand_count": None}
_LATE_OPERAND: dict[str, Any] = {
    "operand_name": "late",
    "key_digest": "k",
    "temporal_role": "DURATION",
    "scoped_tier": "EQUIVALENCE_UNPROVEN",
    "selection_source": "PACKAGE_AS_REPORTED",
    "source_state": "VALUE",
}


def test_tombstoning_cannot_change_an_operand_count(
    seeded: dict[str, int], pg_db: PgTestDatabase
) -> None:
    """The retention purge clears a trace's values but never its operand count."""
    clear = "UPDATE eqos.calculation_traces SET value = NULL{extra} WHERE id = %s"
    trace_id = (seeded["calculation_traces"],)
    tombstone = "SELECT set_config('eqos.tombstone', 'purge', true)"
    with pg_db.migrator_connection() as migrator:
        with migrator.transaction():
            migrator.execute(tombstone)
            migrator.execute(clear.format(extra=""), trace_id)
        with pytest.raises(psycopg.Error, match="immutable"), migrator.transaction():
            migrator.execute(tombstone)
            migrator.execute(clear.format(extra=", operand_count = 11"), trace_id)


_NESTED = {"interpretation_id": None, "operand_trace_id": 9}
_NEITHER = {"interpretation_id": None}


@pytest.mark.parametrize(
    "shape",
    ["nested", "neither", "comparison", "policy", "unresolved"],
)
def test_inputs_refuse_a_claim_whose_inputs_cannot_all_be_named(shape: str) -> None:
    """A dropped operand or record would shrink the rerun set and carry a stale claim, so any
    shape a run draft does not emit refuses before grouping."""
    trace = _two_operand_trace(1, 2)
    calculation = claim(7)
    if shape in ("nested", "neither"):
        second = trace.operands[1].model_copy(update=_NESTED if shape == "nested" else _NEITHER)
        trace = trace.model_copy(update={"operands": (trace.operands[0], second)})
    claims = {
        "nested": calculation,
        "neither": calculation,
        "comparison": calculation.model_copy(
            update={"citation": Citation(kind=CitationKind.COMPARISON, pair_outcome_id=3)}
        ),
        "policy": SELF_CITED,
        "unresolved": calculation.model_copy(update={"unresolved": True}),
    }
    stored = {7: StoredTrace(trace_id=7, trace=trace, children=())}
    with pytest.raises(RunDraftError, match="no reworkable inputs"):
        rework.inputs({"c": claims[shape]}, stored, {1: "a", 2: "b"}, {})


def test_a_calculation_rests_on_every_operand() -> None:
    """Each operand is an input: its interpretation's capture blob under its own key."""
    stored = {7: StoredTrace(trace_id=7, trace=_two_operand_trace(1, 2), children=())}
    atoms = rework.inputs({"c": claim(7)}, stored, {1: "a", 2: "b"}, {})
    assert atoms == {"c": frozenset({("a", "key-0"), ("b", "key-1")})}


def test_a_gate_refuses_a_claim_given_twice_for_one_placeholder() -> None:
    """Two claims behind one placeholder would write a claim no text shows, so a line's claim
    keys must equal its placeholders as a multiset, not as a set."""
    held = rework.Rework(
        head=1,
        claims={},
        atoms={},
        lines={},
        rerun=frozenset({CLAIM}),
        carried=frozenset(),
        blobs=frozenset(),
        scaffolds={},
    )
    gate = held.gate(lambda _section, lines: "".join(lines), lambda _blobs: None)
    with pytest.raises(RunDraftError, match="moved"):
        gate.line("results", f"{{{{c:{CLAIM}|}}}}", (claim(7), claim(7)))


@pytest.fixture
def submitted_q2(
    pg_db: PgTestDatabase, tmp_path: Any, monkeypatch: pytest.MonkeyPatch, ingest: Any
) -> tuple[Pilot, int]:
    """The pilot with FY26_Q2's run draft submitted (``IN_REVIEW``)."""
    pilot = Pilot(pg_db, tmp_path, monkeypatch, ingest)
    version = pilot.run("FY26_Q2").draft_version_id
    assert version is not None
    with pg_db.runtime_pool() as runtime:
        lifecycle.submit(runtime, version, **pilot.sources())
    return pilot, version


def _request_changes(pilot: Pilot, version: int, *keys: str) -> None:
    """The owner requests changes to ``version``, rejecting ``keys``."""
    with pilot.pg_db.owner_pool() as owner:
        record = lifecycle.decide(
            owner, subject_kind=V, subject_id=version, kind=REQUEST, ruling=RULING, claims=keys
        )
    assert (record.rejected_claims or ()) == keys


def _plan(pilot: Pilot, version: int) -> rework.Rework | None:
    """The version's rework, read as the runtime role."""
    with pilot.pg_db.runtime_pool() as pool, pool.connection() as conn:
        return rework.plan(conn.cursor(), EvidenceRepository(pool), version)


REQUEST = DecisionKind.REQUEST_CHANGES
QOQ = tuple(f"cmp.revenue.qoq.{part}" for part in ("prior", "abs", "pct"))
YOY = tuple(f"cmp.revenue.yoy.{part}" for part in ("prior", "abs", "pct"))
GAP = "calc.1"  # the income − revenue gap
CABLES = "ledger.cables_revenue_growth.annual.consolidated"


@pytest.mark.parametrize(
    ("rejected", "rerun"),
    [
        ("cmp.revenue.qoq.prior", set(QOQ)),
        ("fact.revenue", {"fact.revenue", *QOQ, *YOY, GAP}),
        (CABLES, {CABLES}),
    ],
    ids=["comparator-prior", "current-fact", "guidance"],
)
def test_a_rejection_reruns_the_lines_sharing_its_inputs(
    submitted_q2: tuple[Pilot, int], rejected: str, rerun: set[str]
) -> None:
    """Affected = the rejected claim and every claim sharing one of its inputs (one hop), closed
    over the lines they sit on: a comparator prior reruns its own changes line, the current
    revenue fact every revenue change and the income gap (with the line-mate priors), a
    guidance quote only itself. Everything else is carried untouched."""
    pilot, version = submitted_q2
    assert _plan(pilot, version) is None
    _request_changes(pilot, version, rejected)
    found = _plan(pilot, version)
    assert found is not None
    assert found.rerun == rerun
    assert found.carried == {c.claim_key for c in pilot.version(version).claims} - rerun
    for section in pilot.version(version).sections[1:]:
        body, lines = section.body.splitlines(), found.lines[section.section_key]
        assert len(found.scaffolds[section.section_key].splitlines()) + len(lines) == len(body)


def test_a_rejected_package_cannot_expand(
    submitted_q2: tuple[Pilot, int], runtime: psycopg.Connection
) -> None:
    """N's package must not expand under an unchanged seal: an operand added to one of its
    cited traces is refused, and its inputs and rerun set read back unchanged."""
    pilot, version = submitted_q2
    _request_changes(pilot, version, "fact.revenue")
    before = _plan(pilot, version)
    assert before is not None
    trace_id = before.claims[GAP].citation.calculation_trace_id
    assert trace_id is not None
    with pilot.pg_db.runtime_pool() as pool:
        traces = EvidenceRepository(pool).get_calculation_traces([trace_id])
    row: dict[str, Any] = {"calculation_trace_id": trace_id, "ordinal": 2} | _LATE_OPERAND
    with pytest.raises(errors.CheckViolation):
        _insert(runtime, "calculation_trace_operands", row)
    assert _plan(pilot, version) == before
    with pilot.pg_db.runtime_pool() as pool:
        assert EvidenceRepository(pool).get_calculation_traces([trace_id]) == traces


GAP_INPUTS = ("fact.revenue", "cmp.revenue.qoq.prior", "cmp.revenue.yoy.prior", "fact.total_income")
WRITES = ("put_calculation_trace", "put", "select_canonical")
TABLES = (
    "fact_rows",
    "fact_selections",
    "calculation_traces",
    "calculation_trace_operands",
    "report_versions",
    "numeric_claims",
)
CONDUCTOR = "ledger.conductor_ebitda_per_mt.medium_term.consolidated"
PBT = "fact.profit_before_tax"
Calls = dict[str, list[Any]]


@pytest.fixture
def calls(monkeypatch: pytest.MonkeyPatch) -> Calls:
    """Every operand lookup (its key), trace computation (its output key), trace store, fact
    store and canonical selection (each fact's role family) the run makes."""
    found: Calls = defaultdict(list)

    def spy(owner: Any, name: str, record: Callable[..., Any]) -> None:
        real = getattr(owner, name)

        def wrapper(*args: Any, **kwargs: Any) -> Any:
            result = real(*args, **kwargs)
            found[name].append(record(result, *args))
            return result

        monkeypatch.setattr(owner, name, wrapper)

    spy(_Binder, "operand", lambda _, _self, _name, _source, key, *__: key.digest())
    spy(run_traces, "conclude", lambda _, _kind, output, *__: output.digest())
    spy(EvidenceRepository, "put_calculation_trace", lambda trace_id, *_: trace_id)
    spy(PgFactStore, "put", lambda revision, *_: revision.fact.revision_family)
    spy(PgFactStore, "select_canonical", lambda revision, *_: revision.fact.revision_family)
    return found


def _rerun(
    pilot: Pilot,
    *flags: str,
    edit: Callable[[dict[str, Any]], None] | None = None,
    manifest: Path = APAR_MANIFEST,
) -> PipelineResult:
    """FY26_Q2 run again on ``manifest``; ``edit`` corrects its config first (a new approved
    config, A3)."""
    context, argv = pilot.registered("FY26_Q2")
    if edit is not None:
        path = Path(argv[argv.index("--config") + 1])
        body = yaml.safe_load(path.read_text(encoding="utf-8"))
        edit(body)
        path.write_text(yaml.safe_dump(body, allow_unicode=True), encoding="utf-8")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        context = dataclasses.replace(context, approved_config_sha256=digest)
    args = _build_parser().parse_args([*argv, "--retrospective", str(manifest), *flags])
    return run_command(args, intake_context=context)


def _rules(body: dict[str, Any]) -> list[dict[str, Any]]:
    """The config's guidance rules."""
    rules: list[dict[str, Any]] = body["guidance"]["rules"]
    return rules


def _relabel(body: dict[str, Any]) -> None:
    """The cables guidance shown under a corrected label."""
    for rule in _rules(body):
        if rule["metric"] == "cables_revenue_growth":
            rule["label"] = "Cables revenue growth guidance (corrected)"


def _add_metric(body: dict[str, Any]) -> None:
    """A copy of the cables rule under a new metric."""
    cables = next(r for r in _rules(body) if r["metric"] == "cables_revenue_growth")
    _rules(body).append(cables | {"metric": "cables_growth_copy"})


def _repeat(metric: str, body: dict[str, Any]) -> None:
    """The ``metric`` guidance rule configured twice."""
    _rules(body).append(next(r for r in _rules(body) if r["metric"] == metric))


def _cables_label(label: str, body: dict[str, Any]) -> None:
    """The cables guidance shown under ``label``."""
    for rule in _rules(body):
        if rule["metric"] == "cables_revenue_growth":
            rule["label"] = label


def _reorder(body: dict[str, Any]) -> None:
    """The guidance rules in reverse order."""
    _rules(body).reverse()


def _counts(pilot: Pilot) -> tuple[int, ...]:
    """Rows of every table a run writes."""
    found = pilot.query(f"SELECT {', '.join(f'(SELECT count(*) FROM eqos.{t})' for t in TABLES)}")
    return tuple(found[0])


def _successor(pilot: Pilot, version: int) -> int:
    """The draft written on ``version``."""
    rows = pilot.query("SELECT id FROM eqos.report_versions WHERE predecessor_id = %s", version)
    ((found,),) = rows
    return int(found)


def _lines(pilot: Pilot, version: int) -> list[str]:
    """Every line of the version's sections after the heading, in order."""
    return [line for s in pilot.version(version).sections[1:] for line in s.body.splitlines()]


def test_a_rework_reruns_only_the_rejected_lines(
    submitted_q2: tuple[Pilot, int], calls: Calls
) -> None:
    """Rejecting the revenue fact with no correction looks up, computes and stores exactly the
    revenue lines' inputs and traces and writes only the revenue fact (the unaffected
    calculations never execute, not merely deduplicate); every carried claim is N's row, cited
    and resolved, on N's line, although the run built it unbound (Sol r2 1)."""
    pilot, version = submitted_q2
    _request_changes(pilot, version, "fact.revenue")
    found = _plan(pilot, version)
    assert found is not None
    new = _rerun(pilot).draft_version_id
    assert new is not None and _successor(pilot, version) == new
    before = {c.claim_key: c for c in pilot.version(version).claims}
    digest = {
        key: claim.measurement_key.digest()
        for key, claim in before.items()
        if claim.measurement_key
    }
    traced = (*QOQ[1:], *YOY[1:], GAP)
    assert sorted(calls["conclude"]) == sorted(digest[key] for key in traced)
    assert len(calls["put_calculation_trace"]) == len(traced)
    assert set(calls["operand"]) == {digest[key] for key in GAP_INPUTS}
    assert set(calls["put"]) == {"FY26_Q2:revenue"}
    assert set(calls["select_canonical"]) <= {"FY26_Q2:revenue"}
    after = {c.claim_key: c for c in pilot.version(new).claims}
    assert set(after) == set(before)
    for key in found.carried:
        assert after[key] == before[key] and not after[key].unresolved
    carried = {
        text for held in found.lines.values() for text, keys in held if keys <= found.carried
    }
    assert [line for line in _lines(pilot, new) if line in carried] == [
        line for line in _lines(pilot, version) if line in carried
    ]
    assert carried <= set(_lines(pilot, new))


def test_a_guidance_rework_binds_and_writes_nothing(
    submitted_q2: tuple[Pilot, int], calls: Calls
) -> None:
    """No rerun line of a guidance rejection holds a computed or fact claim, so nothing may be
    looked up, computed or stored."""
    pilot, version = submitted_q2
    _request_changes(pilot, version, CABLES)
    assert _rerun(pilot).draft_version_id is not None
    for name in ("operand", "conclude", *WRITES):
        assert calls[name] == [], name


@pytest.mark.parametrize(
    ("rejected", "edit", "intro", "named"),
    [
        ((PBT,), _relabel, None, CABLES),
        ((CONDUCTOR,), _add_metric, None, "ledger.cables_growth_copy"),
        ((CONDUCTOR,), None, "(prior − current)", "changes section"),
        ((PBT,), partial(_repeat, "conductor_ebitda_per_mt"), None, CONDUCTOR),
        ((PBT, CABLES), partial(_repeat, "cables_revenue_growth"), None, CABLES),
        ((PBT, CABLES), partial(_cables_label, f"{{{{c:{CONDUCTOR}|}}}}"), None, CONDUCTOR),
        ((PBT, CABLES), partial(_cables_label, "{{c:ledger.unknown|}}"), None, "ledger.unknown"),
        ((PBT, CABLES), partial(_cables_label, f"{{{{c:{CABLES}|bogus}}}}"), None, "bogus"),
        ((PBT,), _reorder, None, "reorders carried"),
    ],
    ids=[
        "carried-label",
        "unexplained-addition",
        "changes-intro",
        "repeated-carried-rule",
        "repeated-rerun-rule",
        "carried-key-in-rerun-label",
        "unknown-key-in-rerun-label",
        "invalid-style-in-rerun-label",
        "reordered-carried-rules",
    ],
)
def test_a_rework_refuses_movement_outside_its_rerun_lines_before_writing(
    submitted_q2: tuple[Pilot, int],
    calls: Calls,
    monkeypatch: pytest.MonkeyPatch,
    rejected: tuple[str, ...],
    edit: Callable[[dict[str, Any]], None] | None,
    intro: str | None,
    named: str,
) -> None:
    """Presentation drift on a carried line (with a fact role rerun, so a write would follow),
    an unexplained new claim, a changed intro (it defines every carried change's sign; Sol
    r2 4), a claim shown twice, a placeholder that is not its line's claim (a carried or unknown
    key in a rerun label) or does not render (an invalid style) and carried lines out of order
    each refuse inside the hook: a refusal after writes would leave a canonical selection and
    traces no version cites."""
    pilot, version = submitted_q2
    _request_changes(pilot, version, *rejected)
    if intro is not None:
        monkeypatch.setitem(run_draft.INTROS, CHANGES, f"Prior figures and changes {intro}:")
    before = _counts(pilot)
    with pytest.raises(RunDraftError, match=named):
        _rerun(pilot, edit=edit)
    for name in WRITES:
        assert calls[name] == [], name
    assert _counts(pilot) == before


def test_a_relabelled_guidance_rework_changes_only_its_claim(
    submitted_q2: tuple[Pilot, int],
) -> None:
    """The rejected guidance claim takes its corrected label; nothing else moves."""
    pilot, version = submitted_q2
    _request_changes(pilot, version, CABLES)
    new = _rerun(pilot, edit=_relabel).draft_version_id
    assert new is not None
    before = {c.claim_key: c for c in pilot.version(version).claims}
    after = {c.claim_key: c for c in pilot.version(new).claims}
    assert after[CABLES].metric_label == "Cables revenue growth guidance (corrected)"
    assert (
        after[CABLES].model_copy(update={"metric_label": before[CABLES].metric_label})
        == before[CABLES]
    )
    assert {key: c for key, c in after.items() if key != CABLES} == {
        key: c for key, c in before.items() if key != CABLES
    }
    moved = [
        pair
        for pair in zip(_lines(pilot, new), _lines(pilot, version), strict=True)
        if len(set(pair)) > 1
    ]
    assert len(moved) == 1 and all(CABLES in line for line in moved[0])


def test_a_refused_rework_recovers_as_a_full_successor(
    submitted_q2: tuple[Pilot, int], calls: Calls
) -> None:
    """A correction moving a carried line refuses selectively; ``--full-successor`` reruns
    the version whole under a heading naming it and its rejections, validates, submits and is
    approved, while N stays as it was."""
    pilot, version = submitted_q2
    _request_changes(pilot, version, PBT)
    with pilot.pg_db.runtime_pool() as pool, pool.connection() as conn:
        digest = store.sealed_digest(conn.cursor(), version)
    with pytest.raises(RunDraftError, match=CABLES):
        _rerun(pilot, edit=_relabel)
    new = _rerun(pilot, "--full-successor", edit=_relabel).draft_version_id
    assert new is not None and _successor(pilot, version) == new
    heading = pilot.version(new).sections[0].body
    assert f"Full successor of version:{version} (full rework requested; rejected {PBT})" in heading
    claims = {c.claim_key: c for c in pilot.version(new).claims}
    assert claims[CABLES].metric_label == "Cables revenue growth guidance (corrected)"
    computed = [c for c in claims.values() if c.citation.kind is CitationKind.CALCULATION]
    assert len(calls["conclude"]) == len(computed)
    pilot.approve(new)
    with pilot.pg_db.runtime_pool() as pool, pool.connection() as conn:
        cursor = conn.cursor()
        assert lifecycle.version_status(cursor, new) is VersionStatus.APPROVED
        assert lifecycle.version_status(cursor, version) is VersionStatus.CHANGES_REQUESTED
        assert store.sealed_digest(cursor, version) == digest


@pytest.mark.parametrize("sqlite", [False, True], ids=["no-rejections", "sqlite"])
def test_a_full_successor_needs_claim_rejections_and_postgres(
    submitted_q2: tuple[Pilot, int], monkeypatch: pytest.MonkeyPatch, sqlite: bool
) -> None:
    """``--full-successor`` reruns only a head with claim rejections; on a SQLite store, which
    has no ledger to check, it refuses before the pipeline runs."""
    pilot, version = submitted_q2
    _request_changes(pilot, version)
    ran: list[object] = []
    monkeypatch.setattr(cli, "run_pipeline", lambda **_: ran.append(_))
    database = pilot.tmp_path / "facts.db"

    def to_sqlite(body: dict[str, Any]) -> None:
        del body["fact_store_id"]
        body["store_db"] = str(database)

    before = _counts(pilot)
    with pytest.raises(RunDraftError, match="PostgreSQL" if sqlite else "no claim rejections"):
        _rerun(pilot, "--full-successor", edit=to_sqlite if sqlite else None)
    assert ran == [] and _counts(pilot) == before
    if sqlite:
        with sqlite3.connect(database) as facts:
            assert facts.execute("SELECT count(*) FROM facts").fetchone() == (0,)


def _compete(pilot: Pilot, version: int) -> None:
    """A successor of ``version``, closed (submitted, changes requested), as another writer's."""
    draft = pilot.version(version).model_copy(update={"predecessor_id": version})
    with pilot.pg_db.runtime_pool() as pool:
        with pool.connection() as conn, conn.transaction(), conn.cursor() as cursor:
            competitor = store.create_version(cursor, draft)
        lifecycle.submit(pool, competitor, **pilot.sources())
    _request_changes(pilot, competitor)


@pytest.mark.parametrize("full", [False, True], ids=["rework", "full-successor"])
@pytest.mark.parametrize("late", [False, True], ids=["before-hook", "after-check"])
def test_a_rework_refuses_a_head_that_moved(
    submitted_q2: tuple[Pilot, int],
    calls: Calls,
    monkeypatch: pytest.MonkeyPatch,
    full: bool,
    late: bool,
) -> None:
    """A successor closed after preflight would otherwise become the predecessor, under a
    heading naming N (Sol r3). Committed before the hook, the pre-write check refuses with
    nothing written; committed after it, the draft write refuses with no version or claim
    written (closing r2 ruling A: only the rerun's writes remain)."""
    pilot, version = submitted_q2
    _request_changes(pilot, version, "fact.revenue")
    counts: list[tuple[int, ...]] = []

    def compete() -> None:
        _compete(pilot, version)
        counts.append(_counts(pilot))

    if late:
        put = EvidenceRepository.put_calculation_trace

        def racing(self: EvidenceRepository, trace: CalculationTrace) -> int:
            if not counts:
                compete()
            return put(self, trace)

        monkeypatch.setattr(EvidenceRepository, "put_calculation_trace", racing)
    else:
        real = cli.preflight

        def stale(*args: Any, **kwargs: Any) -> run_draft.Prior:
            prior = real(*args, **kwargs)
            compete()
            return prior

        monkeypatch.setattr(cli, "preflight", stale)
    with pytest.raises(RunDraftError, match=f"not the reworked {version}"):
        _rerun(pilot, *(["--full-successor"] if full else []))
    (before,) = counts
    after = _counts(pilot)
    if late:
        assert calls["put_calculation_trace"]
        assert after[-2:] == before[-2:]  # report_versions, numeric_claims
    else:
        for name in WRITES:
            assert calls[name] == [], name
        assert after == before


Q1 = "FY26_Q1"
CORRECTED_KIND = "xbrl-consolidated-comparator-corrected"
# FY26_Q1's consolidated revenue from operations as its comparator filing states it, in ₹.
Q1_REVENUE = 51_041_600_000
REVENUE_FACT = b'<in-capmkt:RevenueFromOperations contextRef="OneD" decimals="-5" unitRef="INR">%d<'
CRORE = 10**7
LATE = "01-Dec-2025 10:00:00"  # after FY26_Q2's source cutoff
_CAPTURE_BLOB = """SELECT c.blob_sha256 FROM eqos.interpretations i
JOIN eqos.capture_refs c ON c.id = i.capture_ref_id WHERE i.id = %s"""
_TRACE_BLOBS = """SELECT DISTINCT c.blob_sha256 FROM eqos.calculation_trace_operands o
JOIN eqos.interpretations i ON i.id = o.interpretation_id
JOIN eqos.capture_refs c ON c.id = i.capture_ref_id WHERE o.calculation_trace_id = %s"""


def _facts(body: bytes, ingest: Ingest) -> tuple[RawXbrlFact, ...]:
    """Every fact of an instance as evidence ingest reads it."""
    return parse_instance(body, mapping_set=ingest.mapping_set).facts


def _correct(
    pilot: Pilot, ingest: Ingest, *, filed_at: str | None = None, original: bool = True
) -> tuple[str, Callable[[], PipelineResult]]:
    """FY26_Q1's comparator restated with revenue ₹100 crore higher, published (by default) when
    the original was, entered in a copy of the retrieval manifest the run is pinned to and
    evidence-ingested; returns its digest and the FY26_Q2 rerun pointing ``comparators.qoq`` at
    it. ``original=False`` drops the original filing from the manifest copy."""
    entry = manifest_entry(Q1, COMPARATOR_KIND)
    body = apar_original(Q1, COMPARATOR_KIND).read_bytes()
    assert body.count(REVENUE_FACT % Q1_REVENUE) == 1
    corrected = body.replace(REVENUE_FACT % Q1_REVENUE, REVENUE_FACT % (Q1_REVENUE + 100 * CRORE))
    pairs = zip(_facts(body, ingest), _facts(corrected, ingest), strict=True)
    changed = [new for old, new in pairs if old != new]
    assert [fact.raw_text for fact in changed] == [str(Q1_REVENUE + 100 * CRORE)]
    path = pilot.tmp_path / INPUTS_DIR / XBRL_DIR / f"corrected-{entry['filename']}"
    path.write_bytes(corrected)
    sha = hashlib.sha256(corrected).hexdigest()
    manifest = json.loads(APAR_MANIFEST.read_text(encoding="utf-8"))
    if not original:
        manifest["entries"] = [e for e in manifest["entries"] if e["sha256"] != entry["sha256"]]
    manifest["entries"].append(
        entry
        | {"kind": CORRECTED_KIND, "filename": path.name, "sha256": sha, "bytes": len(corrected)}
        | {"filed_at_nse": filed_at or entry["filed_at_nse"]}
    )
    copy = pilot.tmp_path / "retrieval-manifest-corrected.json"
    copy.write_text(json.dumps(manifest), encoding="utf-8")
    pin = pilot.tmp_path / DEFAULT_IMPORT_CONFIG
    text = pin.read_text(encoding="utf-8")
    pinned = hashlib.sha256(APAR_MANIFEST.read_bytes()).hexdigest()
    assert text.count(pinned) == 1
    pin.write_text(text.replace(pinned, hashlib.sha256(copy.read_bytes()).hexdigest()))
    intake = retained_intake_from_manifest(
        copy,
        issuer=STOCK,
        quarter=Q1,
        kinds={Representation.XBRL: CORRECTED_KIND},
        store_root=(pilot.tmp_path / STORE_DIR).absolute(),
        input_root=(pilot.tmp_path / INPUTS_DIR).absolute(),
        issuer_config=None,
    )
    ingest.run(intake, date(2025, 6, 30))

    def point(config: dict[str, Any]) -> None:
        config["comparators"]["qoq"] |= {"local_path": str(path), "sha256": sha}

    return sha, partial(_rerun, pilot, edit=point, manifest=copy)


def _blob(pilot: Pilot, claim: NumericClaim) -> str:
    """The capture blob of the interpretation a figure cites."""
    ((found,),) = pilot.query(_CAPTURE_BLOB, claim.citation.interpretation_id)
    return str(found)


def _sealed(pilot: Pilot, version: int) -> tuple[VersionStatus, str, str, rework.Rework | None]:
    """The version's status, sealed digest, content hash and rework (package inputs, rerun set)."""
    with pilot.pg_db.runtime_pool() as pool, pool.connection() as conn:
        cursor = conn.cursor()
        status = lifecycle.version_status(cursor, version)
        digest = store.sealed_digest(cursor, version)
    return status, digest, pilot.version(version).content_hash, _plan(pilot, version)


def test_corrected_filing_reworks_only_dependent_claims(
    submitted_q2: tuple[Pilot, int],
    ingest: Ingest,
    calls: Calls,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """PILOT-11: a restated QoQ comparator moves only the rejected prior's changes line. v(N+1)
    carries the values recomputed from the new filing; every other claim keeps N's citation,
    the other QoQ priors the old filing's (finding 4); only the two dependent calculations run,
    nothing is written as a fact; v(N+1) is approved and N's package is as it was."""
    pilot, version = submitted_q2
    monkeypatch.setattr("sys.stdin", io.StringIO(RULING))
    command = ["ledger", "decide", V.value, str(version), REQUEST.value, "--claim", QOQ[0]]
    assert main(command) == 0
    with pilot.pg_db.runtime_pool() as pool, pool.connection() as conn:
        assert rework.rejected(conn.cursor(), version) == (QOQ[0],)
    baseline = _sealed(pilot, version)
    assert baseline[3] is not None and baseline[3].rerun == set(QOQ)
    sha, rerun = _correct(pilot, ingest)
    new = rerun().draft_version_id
    assert new is not None and _successor(pilot, version) == new
    numbers = pilot.query("SELECT eqos.version_number(%s), eqos.version_number(%s)", version, new)
    assert numbers[0][1] == numbers[0][0] + 1
    old = {c.claim_key: c for c in pilot.version(version).claims}
    claims = {c.claim_key: c for c in pilot.version(new).claims}
    current, prior = old["fact.revenue"].value, old[QOQ[0]].value
    assert current is not None and prior is not None
    prior += 100  # a run states amounts in ₹ crore
    pct = ((current - prior) / prior * 100).quantize(Decimal(1).scaleb(-2), ROUND_HALF_EVEN)
    expected = dict(zip(QOQ, (prior, current - prior, pct), strict=True))
    assert {key: claims[key].value for key in QOQ} == expected
    assert all(old[key].value != value for key, value in expected.items())
    assert _blob(pilot, claims[QOQ[0]]) == sha
    for key in QOQ[1:]:
        trace = claims[key].citation.calculation_trace_id
        assert trace != old[key].citation.calculation_trace_id
        assert sha in {row[0] for row in pilot.query(_TRACE_BLOBS, trace)}
    digest = {key: c.measurement_key.digest() for key, c in old.items() if c.measurement_key}
    assert sorted(calls["conclude"]) == sorted(digest[key] for key in QOQ[1:])
    assert len(calls["put_calculation_trace"]) == 2
    assert set(calls["operand"]) == {digest["fact.revenue"], digest[QOQ[0]]}
    assert calls["put"] == calls["select_canonical"] == []
    unchanged = {key: c for key, c in claims.items() if key not in QOQ}
    assert unchanged == {key: c for key, c in old.items() if key not in QOQ}
    assert _lines(pilot, new) == _lines(pilot, version)
    original = manifest_entry(Q1, COMPARATOR_KIND)["sha256"]
    priors = [key for key in unchanged if key.endswith(".qoq.prior")]
    assert priors and {_blob(pilot, claims[key]) for key in priors} == {original}
    pilot.approve(new)
    assert _sealed(pilot, new)[0] is VersionStatus.APPROVED
    assert _sealed(pilot, version) == baseline
    assert baseline[0] is VersionStatus.CHANGES_REQUESTED


def test_a_corrected_filing_reaching_a_carried_claim_refuses_before_writing(
    submitted_q2: tuple[Pilot, int], ingest: Ingest, calls: Calls
) -> None:
    """With PBT rejected, the restated comparator moves the carried revenue QoQ line: carrying
    N's value would publish a stale one, taking the new one would bypass review."""
    pilot, version = submitted_q2
    _request_changes(pilot, version, PBT)
    _, rerun = _correct(pilot, ingest)
    before = _counts(pilot)
    with pytest.raises(RunDraftError, match=QOQ[0]):
        rerun()
    for name in WRITES:
        assert calls[name] == [], name
    assert _counts(pilot) == before


@pytest.mark.parametrize("case", ["late", "outside", "omitted"])
def test_a_rework_source_outside_its_package_refuses_before_writing(
    submitted_q2: tuple[Pilot, int],
    ingest: Ingest,
    calls: Calls,
    monkeypatch: pytest.MonkeyPatch,
    case: str,
) -> None:
    """The corrected filing published after the cutoff, a capture outside the run's package,
    and the original filing that carried claims still cite missing from the manifest each
    refuse before the rerun's traces are stored (closing r2 3, r3 1): at the draft write they
    would follow it."""
    pilot, version = submitted_q2
    _request_changes(pilot, version, QOQ[0])
    original = manifest_entry(Q1, COMPARATOR_KIND)["sha256"]
    sha, rerun = _correct(
        pilot, ingest, filed_at=LATE if case == "late" else None, original=case != "omitted"
    )
    if case == "outside":
        check = cli.check_blobs

        def narrowed(*args: Any, allowed: set[str], **kwargs: Any) -> None:
            check(*args, allowed=allowed - {sha}, **kwargs)

        monkeypatch.setattr(cli, "check_blobs", narrowed)
    named = {
        "late": f"past the source cutoff .*{sha[:12]}",
        "outside": f"not in the run's package: {sha[:12]}",
        "omitted": f"past the source cutoff .*{original[:12]}",
    }[case]
    before = _counts(pilot)
    with pytest.raises(RunDraftError, match=named):
        rerun()
    for name in WRITES:
        assert calls[name] == [], name
    assert _counts(pilot) == before
