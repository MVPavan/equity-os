"""PREP-5 acceptance: a rejected claim reworks only its affected claims into v(N+1).

Task 1: a ``REQUEST_CHANGES`` records the claims it rejects, each a distinct claim key of the
version under review, in an immutable column; a stored trace's operand set cannot grow.
Task 2: a rejected version's package inputs and rerun set are derived from its verified rows.
"""

from __future__ import annotations

import io
from decimal import Decimal
from fractions import Fraction
from typing import Any

import psycopg
import pytest
from evidence_support import ingest, policy
from ledger_support import RULING, SELF_CITED, Ledger, claim, ledger
from pg_evidence_schema_support import _insert, _trace, runtime, seeded
from pg_support import PgTestDatabase
from prep2b_support import Pilot
from psycopg import errors
from test_prep2b_run_draft import dictionary, mapping_set

from fundamentals.api.cli import main
from fundamentals.canon.formula import CalculationTrace, TraceOperand
from fundamentals.contracts.ledger import Citation, CitationKind, DecisionKind, SubjectKind
from fundamentals.evidence.repository import EvidenceRepository
from fundamentals.evidence.repository_calc import StoredTrace
from fundamentals.ledger import lifecycle, rework
from fundamentals.ledger.run_traces import RunDraftError
from fundamentals.pg.settings import PgRole

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
    assert record.rejected_claims == keys


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
