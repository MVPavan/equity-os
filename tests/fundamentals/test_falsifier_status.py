"""RESEARCH-1 Tasks 2-3: a run draft's falsifier status binds to the thesis approved at its cutoff.

A ``THESIS_CLAIM`` resolves only through an approval recorded on the cited thesis version's
sealed digest, at the approval's time; the schema keeps its columns to that kind. The binder
selects the newest bootstrap thesis version ``APPROVED`` as of a time and refuses one whose twin
cannot be read. Each case seeds imported versions holding the Q0 thesis bytes (or a successor
re-registering F5) on its own ``eqos_test_*`` database. A rework refuses a rejected threshold
claim or a version written before the falsifier sections (on the retained pilot). RESEARCH-3 S1
Task 1: a probe limit imports typed by its metric suffix, a measure of another kind refuses and
a stale measure is ``NOT_ASSESSED``.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import psycopg
import pytest
from evidence_support import ingest, policy
from ledger_support import CUTOFF, Ledger, claim, ledger
from pg_evidence_schema_support import runtime, seeded
from prep2b_support import Pilot
from psycopg import errors
from test_prep2b_run_draft import dictionary, mapping_set
from test_prep5_rework import _plan, _request_changes, _rerun, _successor, submitted_q2

from fundamentals.contracts.canonical import ValueKind
from fundamentals.contracts.evidence import RunMode
from fundamentals.contracts.ledger import (
    Citation,
    CitationKind,
    ClaimState,
    DecisionKind,
    NumericClaim,
    ReportKind,
)
from fundamentals.contracts.source_catalog import SourceCatalog
from fundamentals.ledger import lifecycle, store
from fundamentals.ledger.citations import resolve_citation
from fundamentals.ledger.claim_check import PERCENT, check_claim
from fundamentals.ledger.display import content_hash
from fundamentals.ledger.falsifier_status import (
    DERIVED,
    FALSIFIER_STATUS,
    NO_THESIS,
    NO_VALUE,
    SUPERSEDED,
    THESIS_IMPACT,
    BoundThesis,
    approved_thesis,
    derived,
    evaluate,
)
from fundamentals.ledger.import_mapping import LosslessError, map_q0
from fundamentals.ledger.run_traces import CALCS, MARGIN_KEY, MARGIN_LABEL, Line, RunDraftError
from fundamentals.pg.settings import PgRole
from fundamentals.verify.thesis_predicates import (
    Disposition,
    FalsifierPredicate,
    PredicateOp,
    parse_thesis,
)

__all__ = [
    "dictionary",
    "ingest",
    "ledger",
    "mapping_set",
    "policy",
    "runtime",
    "seeded",
    "submitted_q2",
]

pytestmark = pytest.mark.pg

REPO = Path(__file__).resolve().parents[2]
Q0_MD = REPO / "docs/evidence/phase-0.5/q0-approved-thesis.md"
Q0_YAML = REPO / "docs/evidence/phase-0.5/q0-approved-thesis.yaml"
SYMBOL = "APARINDS"
Q0_ETR, FILED_ETR = b"effective_tax_rate_pct", b"filed_effective_tax_rate_pct"
CLAIM_ID = "SELECT id FROM eqos.numeric_claims WHERE version_id = %s AND claim_key = %s"
NOW = "SELECT eqos.store_now()"


def _files(successor: bool = False) -> tuple[bytes, bytes]:
    """The Q0 thesis Markdown and twin; a successor re-registers F5 on the filed tax rate."""
    md, twin = Q0_MD.read_bytes(), Q0_YAML.read_bytes()
    return (
        (md.replace(Q0_ETR, FILED_ETR), twin.replace(Q0_ETR, FILED_ETR))
        if successor
        else (md, twin)
    )


def thesis(
    ledger: Ledger,
    report: int,
    predecessor: int | None = None,
    *,
    approve: bool = True,
    successor: bool = False,
    sources: tuple[tuple[str, bytes], ...] | None = None,
    extra: tuple[NumericClaim, ...] = (),
) -> int:
    """An imported thesis version of ``report`` holding the (successor) thesis bytes and any
    ``extra`` claims."""
    from fundamentals.ledger.falsifier_status import KINDS

    md, twin = _files(successor)
    mapped = map_q0(md, twin, cutoff=date(2025, 11, 6), metrics=KINDS)
    files = (("thesis.md", md), ("thesis.yaml", twin)) if sources is None else sources
    return ledger.imported(
        report,
        predecessor,
        approve=approve,
        sections=mapped.sections,
        claims=(*mapped.claims, *extra),
        import_sources=files,
    )


def _report(ledger: Ledger) -> int:
    """The stock's thesis report."""
    with ledger.pools[PgRole.RUNTIME].connection() as conn, conn.transaction():
        return store.create_report(
            conn.cursor(),
            entity_id=ledger.entity_id,
            period="FY26_Q2",
            kind=ReportKind.BOOTSTRAP_THESIS,
        )


def _bound(ledger: Ledger, as_of: datetime | None = None, symbol: str = SYMBOL) -> Any:
    """``approved_thesis`` as of ``as_of`` (default: now), read as the runtime role."""
    with ledger.pools[PgRole.RUNTIME].connection() as conn, conn.transaction():
        cursor = conn.cursor()
        return approved_thesis(cursor, ledger.entity_id, symbol, as_of or datetime.now(UTC))


def _now(ledger: Ledger) -> datetime:
    """The store clock."""
    with ledger.pools[PgRole.RUNTIME].connection() as conn:
        row = conn.execute(NOW).fetchone()
    assert row is not None
    at: datetime = row[0]
    return at


def _claim_id(ledger: Ledger, version: int, key: str) -> int:
    with ledger.pools[PgRole.RUNTIME].connection() as conn:
        row = conn.execute(CLAIM_ID, (version, key)).fetchone()
    assert row is not None
    return int(row[0])


def _cite(ledger: Ledger, version: int, key: str = "falsifier.F1", **citation: Any) -> NumericClaim:
    """A run claim citing ``version``'s ``key`` as a ``THESIS_CLAIM`` at its sealed digest."""
    with ledger.pools[PgRole.RUNTIME].connection() as conn:
        digest = store.sealed_digest(conn.cursor(), version)
        cited = next(
            c for c in store.read_version(conn.cursor(), version).claims if c.claim_key == key
        )
    pinned = {"cited_claim_id": _claim_id(ledger, version, key), "cited_sealed_digest": digest}
    return cited.model_copy(
        update={
            "claim_key": "thesis.F1",
            "section_key": FALSIFIER_STATUS,
            "citation": Citation(kind=CitationKind.THESIS_CLAIM, **(pinned | citation)),
        }
    )


def _state(ledger: Ledger, cited: NumericClaim, cutoff: datetime) -> ClaimState:
    """The ``AS_KNOWN`` check of ``cited`` on the stock's report at ``cutoff``."""
    with ledger.pools[PgRole.RUNTIME].connection() as conn:
        resolved = resolve_citation(
            conn.cursor(),
            cited,
            entity_id=ledger.entity_id,
            overlay_position=datetime.now(UTC),
            catalog=SourceCatalog.of(),
            snapshots=ledger.snapshots,
        )
    return check_claim(cited, resolved, mode=RunMode.AS_KNOWN, cutoff=cutoff, imported=False)


# Task 2: the citation -------------------------------------------------------------------------


@pytest.mark.parametrize("case", ["approved", "digest", "unapproved", "not-falsifier", "late"])
def test_a_thesis_claim_resolves_only_through_an_approval_of_its_digest(
    ledger: Ledger, case: str
) -> None:
    """``MATCH`` on an approved thesis's falsifier threshold at its sealed digest; another
    digest, an unapproved version or a non-falsifier claim are ``UNRESOLVED``; an approval
    recorded after the cutoff is ``POST_CUTOFF``."""
    from fundamentals.ledger.falsifier_status import KINDS

    md, twin = _files()
    (first, *_) = map_q0(md, twin, cutoff=date(2025, 11, 6), metrics=KINDS).claims
    extra = (first.model_copy(update={"claim_key": "threshold.F1"}),)
    version = thesis(ledger, _report(ledger), approve=case != "unapproved", extra=extra)
    cited = _cite(ledger, version)
    if case == "digest":
        cited = _cite(ledger, version, cited_sealed_digest="0" * 64)
    elif case == "not-falsifier":
        cited = _cite(ledger, version, "threshold.F1")
    want = {"approved": ClaimState.MATCH, "late": ClaimState.POST_CUTOFF}
    cutoff = CUTOFF if case == "late" else _now(ledger)
    assert _state(ledger, cited, cutoff) is want.get(case, ClaimState.UNRESOLVED)


def test_the_schema_keeps_the_cited_columns_to_their_kind(ledger: Ledger) -> None:
    """A ``THESIS_CLAIM`` row may set no other citation column, and no other kind may set the
    cited claim or digest."""
    version = thesis(ledger, _report(ledger))
    cited = _cite(ledger, version)
    stray = cited.citation.model_copy(update={"source_sha256": "a" * 64})
    pinned = Citation(
        kind=CitationKind.CALCULATION,
        calculation_trace_id=ledger.trace_id,
        cited_claim_id=cited.citation.cited_claim_id,
    )
    rows = (
        (cited.model_copy(update={"citation": stray}), "numeric_claims_thesis_claim_check"),
        (claim(ledger.trace_id).model_copy(update={"citation": pinned}), "thesis_columns_check"),
    )
    for row, constraint in rows:
        with pytest.raises(errors.CheckViolation, match=constraint):
            ledger.draft(
                ledger.report(), claims=(row.model_copy(update={"section_key": "preamble"}),)
            )


def test_the_sealed_digest_covers_the_cited_claim(ledger: Ledger, pg_db: Any) -> None:
    """Pointing a stored ``THESIS_CLAIM`` at another thesis claim changes its version's sealed
    digest (admin only, triggers bypassed, rolled back)."""
    version = thesis(ledger, _report(ledger))
    cited = _cite(ledger, version).model_copy(update={"section_key": "preamble"})
    draft = ledger.draft(ledger.report(), claims=(cited,))
    other = _claim_id(ledger, version, "falsifier.F2")
    with psycopg.connect(pg_db.conninfo(PgRole.ADMIN)) as conn:
        digest = "SELECT eqos.version_sealed_digest(%s)"
        before = conn.execute(digest, (draft,)).fetchone()
        conn.execute("SET LOCAL session_replication_role = replica")
        conn.execute(
            "UPDATE eqos.numeric_claims SET cited_claim_id = %s WHERE version_id = %s",
            (other, draft),
        )
        after = conn.execute(digest, (draft,)).fetchone()
        conn.rollback()
    assert before is not None and after is not None and before != after


# Task 3: the predicate rule, the binder and the evaluation ------------------------------------


@pytest.mark.parametrize(
    ("op", "value", "holds"),
    [
        (PredicateOp.LT, "5", False),
        (PredicateOp.LT, "4.99", True),
        (PredicateOp.LTE, "5", True),
        (PredicateOp.GT, "5", False),
        (PredicateOp.GT, "5.01", True),
        (PredicateOp.GTE, "5", True),
        (PredicateOp.OUTSIDE_BAND, "1", False),
        (PredicateOp.OUTSIDE_BAND, "5", False),
        (PredicateOp.OUTSIDE_BAND, "0.99", True),
        (PredicateOp.OUTSIDE_BAND, "5.01", True),
    ],
)
def test_a_predicate_is_strict_only_where_its_operator_says(
    op: PredicateOp, value: str, holds: bool
) -> None:
    """A falsifier triggers past its threshold: equality triggers ``LTE``/``GTE`` only, and a
    band's edges are inside it."""
    band = op is PredicateOp.OUTSIDE_BAND
    predicate = FalsifierPredicate(
        metric_id="m_pct",
        op=op,
        threshold=None if band else Decimal(5),
        band=(Decimal(1), Decimal(5)) if band else None,
    )
    assert predicate.holds(Decimal(value)) is holds


def test_the_newest_thesis_approved_as_of_the_cutoff_is_bound(ledger: Ledger) -> None:
    """An approved successor is selected over Q0, but not as of a time before its approval
    (recorded before the call), and an unapproved successor never is."""
    report = _report(ledger)
    q0 = thesis(ledger, report)
    unapproved = thesis(ledger, report, q0, approve=False)
    assert _bound(ledger).version_id == q0
    before = _now(ledger)
    approved = thesis(ledger, report, unapproved, successor=True)
    assert _bound(ledger).version_id == approved
    assert _bound(ledger, before).version_id == q0
    bound = _bound(ledger)
    with ledger.pools[PgRole.RUNTIME].connection() as conn:
        assert bound.sealed_digest == store.sealed_digest(conn.cursor(), approved)
    assert bound.thresholds["F5"][0] == _claim_id(ledger, approved, "falsifier.F5")


@pytest.mark.parametrize("case", ["never", "withdrawn"])
def test_no_approved_thesis_derives_the_unresolved_sections(ledger: Ledger, case: str) -> None:
    """A never-approved or withdrawn thesis binds nothing; both sections then say so."""
    version = thesis(ledger, _report(ledger), approve=case == "withdrawn")
    if case == "withdrawn":
        ledger.decide(PgRole.OWNER, version, DecisionKind.WITHDRAW)
    assert _bound(ledger) is None
    sections, thresholds = derived(None, ())
    assert [key for key, _ in sections] == [THESIS_IMPACT, FALSIFIER_STATUS]
    assert {key for key, _ in sections} == DERIVED and thresholds == ()
    assert all(body == f"## {key}\n\n{NO_THESIS}\n\n" for key, body in sections)


@pytest.mark.parametrize("case", ["symbol", "no-twin", "malformed"])
def test_an_unreadable_approved_thesis_refuses(ledger: Ledger, case: str) -> None:
    """An approved thesis of another symbol, with no YAML twin, or whose twin does not parse
    refuses rather than being dropped."""
    md, _ = _files()
    sources = {
        "symbol": None,
        "no-twin": (("thesis.md", md),),
        "malformed": (("thesis.md", md), ("thesis.yaml", b"symbol: [")),
    }[case]
    thesis(ledger, _report(ledger), sources=sources)
    with pytest.raises(RunDraftError, match="approved thesis version"):
        _bound(ledger, symbol="OTHER" if case == "symbol" else SYMBOL)


def test_an_unmeasured_or_superseded_falsifier_is_unresolved(ledger: Ledger) -> None:
    """Q0's F5 (PBT − PAT definition) is superseded; with no claims and a claimless margin line
    every other falsifier lacks its value; none emits a threshold claim."""
    thesis(ledger, _report(ledger))
    bound: BoundThesis = _bound(ledger)
    rows = evaluate(bound, {}, (Line(section=CALCS, label=MARGIN_LABEL),))
    reasons = {row.falsifier_id: (row.disposition, row.reason) for row in rows}
    unresolved = Disposition.UNRESOLVED
    assert reasons == {
        **{fid: (unresolved, NO_VALUE) for fid in ("F1", "F2", "F3", "F4")},
        "F5": (unresolved, SUPERSEDED),
    }
    sections, thresholds = derived(bound, rows)
    assert thresholds == ()
    assert "UNRESOLVED F1, F2, F3, F4, F5." in sections[0][1]


# RESEARCH-3 S1 Task 1: typed probe limits ------------------------------------------------------

DAYS_METRICS = {
    "probe_receivable_days": "probe.R1",
    "probe_inventory_materials_days": "probe.R2",
    "probe_payable_materials_days": "probe.R3",
}
# F5 (``effective_tax_rate_pct GT 26.78``) re-registered on a probe metric: above the limit
# breaches, as days or leverage do.
F5_METRIC = b"effective_tax_rate_pct"
BREACH, WITHIN = Decimal("30.00"), Decimal("20.00")


def _renamed(*pairs: tuple[bytes, bytes]) -> tuple[bytes, bytes]:
    """The Q0 thesis Markdown and twin with each metric id renamed in both."""
    md, twin = _files()
    for old, new in pairs:
        md, twin = md.replace(old, new), twin.replace(old, new)
    return md, twin


def _probe_bound(metric: str) -> tuple[BoundThesis, NumericClaim]:
    """Q0 with F5 on ``metric``, mapped and bound without a store, and F5's threshold claim."""
    from fundamentals.ledger.falsifier_status import KINDS

    md, twin = _renamed((F5_METRIC, metric.encode()))
    mapped = map_q0(md, twin, cutoff=date(2025, 11, 6), metrics=KINDS)
    thresholds = {
        c.claim_key.removeprefix("falsifier."): (row, c) for row, c in enumerate(mapped.claims, 1)
    }
    bound = BoundThesis(
        version_id=1, sealed_digest="0" * 64, thesis=parse_thesis(twin), thresholds=thresholds
    )
    return bound, thresholds["F5"][1]


def _f5(rows: tuple[Any, ...]) -> Any:
    """F5's row."""
    (row,) = (row for row in rows if row.falsifier_id == "F5")
    return row


def test_a_probe_limit_imports_typed_by_its_suffix() -> None:
    """A ``_days`` limit is a unitless day count and a ``_ratio`` limit a unitless ratio, so
    each compares with its probe claim at its own kind; ``_pct`` stays a percentage."""
    from fundamentals.ledger.falsifier_status import KINDS

    renames = (
        (b"revenue_yoy_pct", b"probe_receivable_days"),
        (b"pbt_margin_pct", b"probe_inventory_materials_days"),
        (b"pat_yoy_pct", b"probe_payable_materials_days"),
        (b"eps_yoy_pct", b"probe_borrowings_to_equity_ratio"),
    )
    md, twin = _renamed(*renames)
    mapped = map_q0(md, twin, cutoff=date(2025, 11, 6), metrics=KINDS)
    typed = {c.claim_key: (c.value_kind, c.unit, c.currency, c.scale) for c in mapped.claims}
    unitless = (None, None, None)
    assert typed == {
        **{f"falsifier.F{n}": (ValueKind.DAYS, *unitless) for n in (1, 2, 3)},
        "falsifier.F4": (ValueKind.RATIO, *unitless),
        "falsifier.F5": (ValueKind.PERCENTAGE, PERCENT, None, None),
    }


@pytest.mark.parametrize("case", ["unknown-suffix", "registered-kind"])
def test_an_unknown_or_mismatched_probe_limit_refuses(case: str) -> None:
    """A suffix with no kind, or a registered metric whose kind is not its suffix's, cannot be
    compared with its claim, so the thesis does not import."""
    from fundamentals.ledger.falsifier_status import KINDS

    metric = b"revenue_yoy_bps" if case == "unknown-suffix" else b"probe_receivable_days"
    md, twin = _renamed((b"revenue_yoy_pct", metric))
    metrics = dict(KINDS)
    if case == "registered-kind":
        map_q0(md, twin, cutoff=date(2025, 11, 6), metrics=KINDS)  # imports at its own kind
        metrics[metric.decode()] = ValueKind.PERCENTAGE
    with pytest.raises(LosslessError):
        map_q0(md, twin, cutoff=date(2025, 11, 6), metrics=metrics)


def test_a_probe_measure_of_another_kind_refuses() -> None:
    """A days limit tested on a percentage claim would compare unlike numbers: a structural
    fault, not an unresolved falsifier."""
    bound, threshold = _probe_bound("probe_receivable_days")
    measured = threshold.model_copy(
        update={"claim_key": "probe.R1", "value_kind": ValueKind.PERCENTAGE, "unit": PERCENT}
    )
    with pytest.raises(RunDraftError):
        evaluate(bound, {"probe.R1": measured}, ())


@pytest.mark.parametrize("metric", sorted(DAYS_METRICS))
def test_a_days_limit_weakens_on_breach(metric: str) -> None:
    """Each days limit weakens the thesis when its probe measure crosses it, and holds when
    it does not; the row names the measuring claim."""
    bound, threshold = _probe_bound(metric)
    key = DAYS_METRICS[metric]
    for value, disposition in ((BREACH, Disposition.WEAKENED), (WITHIN, Disposition.HELD)):
        measured = threshold.model_copy(update={"claim_key": key, "value": value})
        row = _f5(evaluate(bound, {key: measured}, ()))
        assert (row.disposition, row.claim_key) == (disposition, key)


def test_a_stale_measure_is_not_assessed() -> None:
    """A measure read from an earlier statement is not this period's: even past the limit it
    is ``NOT_ASSESSED``, so a breach is reported once, in the run that owns the statement."""
    from fundamentals.ledger.falsifier_status import STALE

    bound, threshold = _probe_bound("probe_receivable_days")
    measured = threshold.model_copy(update={"claim_key": "probe.R1", "value": BREACH})
    rows = evaluate(bound, {"probe.R1": measured}, (), stale=frozenset({"probe.R1"}))
    row = _f5(rows)
    assert (row.disposition, row.reason) == (Disposition.NOT_ASSESSED, STALE)


def _pre_slice(pilot: Pilot, version: int) -> int:
    """A successor of ``version`` as written before RESEARCH-1 (no margin line or claim, no
    derived sections or threshold claims), submitted."""
    draft = pilot.version(version)
    sections = tuple(
        section.model_copy(
            update={
                "body": "".join(
                    line
                    for line in section.body.splitlines(True)
                    if f"{{{{c:{MARGIN_KEY}|" not in line
                )
            }
        )
        for section in draft.sections
        if section.section_key not in DERIVED
    )
    claims = tuple(
        c for c in draft.claims if c.section_key not in DERIVED and c.claim_key != MARGIN_KEY
    )
    old = draft.model_copy(
        update={
            "predecessor_id": version,
            "sections": sections,
            "claims": claims,
            "content_hash": content_hash(sections, claims),
        }
    )
    with pilot.pg_db.runtime_pool() as pool:
        with pool.connection() as conn, conn.transaction(), conn.cursor() as cursor:
            pre_slice = store.create_version(cursor, old)
        lifecycle.submit(pool, pre_slice, **pilot.sources())
    return pre_slice


@pytest.mark.retained
def test_a_derived_claim_or_a_pre_slice_version_refuses_a_rework(
    submitted_q2: tuple[Pilot, int],
) -> None:
    """A threshold claim is re-derived from the approved thesis, so rejecting it refuses; a
    version written before the falsifier sections refuses an ordinary rework, which a
    ``--full-successor`` upgrades."""
    pilot, version = submitted_q2
    _request_changes(pilot, version, "thesis.F1")
    with pytest.raises(RunDraftError, match="re-derived from the approved thesis"):
        _plan(pilot, version)
    pre_slice = _pre_slice(pilot, version)
    _request_changes(pilot, pre_slice, "fact.revenue")
    with pytest.raises(RunDraftError, match="predates the falsifier sections"):
        _rerun(pilot)
    successor = _rerun(pilot, "--full-successor").draft_version_id
    assert successor is not None and _successor(pilot, pre_slice) == successor
    upgraded = pilot.version(successor)
    assert MARGIN_KEY in {c.claim_key for c in upgraded.claims}
    assert DERIVED <= {s.section_key for s in upgraded.sections}
