"""RESEARCH-3 S1 Task 4: the risk probe at its binding boundary, and PILOT-4's probe checks.

On the retained pilot's FY26_Q2 run, reading the store only through ``_Binder``: a probe operand
missing at the flow window leaves the other checks assessed; two mapped interpretations of one
operand are a store fault; no balance sheet, or a statement with no evaluable row, renders one
paragraph; a child-sum leaf from outside the package or past the cutoff refuses the draft
(``_OPERAND_BLOBS`` recurses through child traces); a selective rework re-derives the probe on
the head's own traces (P11). ``check_probe`` is PILOT-4's probe assertion over the four pilot
quarters; ``trace_closure`` is every trace reachable from cited ones (P12). Production names that
do not exist before S1 are imported inside the function that needs them.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable, Mapping
from datetime import UTC, date, datetime
from fractions import Fraction
from typing import Any, LiteralString

import pytest
from evidence_support import ingest, policy
from prep2b_support import Pilot
from test_prep2b_run_draft import dictionary, mapping_set, pilot
from test_prep5_rework import CABLES, Calls, _request_changes, _rerun, calls, submitted_q2

from equity_os.analysis.calculations.run_traces import NOT_PERFORMED, RunDraftError, _Binder
from equity_os.analysis.lenses.thesis_tests.falsifier_status import FALSIFIER_STATUS
from equity_os.contracts.measurement.canonical import Representation, ValueKind
from equity_os.contracts.measurement.evidence import CaptureReference, Interpretation
from equity_os.contracts.measurement.measurement_key import PeriodInterval
from equity_os.contracts.measurement.provenance import Provenance, SourceAnchorType
from equity_os.contracts.publication.ledger import (
    CitationKind,
    ClaimState,
    NumericClaim,
    VersionDraft,
)
from equity_os.contracts.verification.comparison import SelectionSource
from equity_os.extraction.packages.capture_intake import SURFACE_OF
from equity_os.publication.checking.citations import resolve_citation
from equity_os.publication.drafting import run_draft
from equity_os.publication.drafting.display import FILED
from equity_os.storage.records.repository import EvidenceRepository

__all__ = ["calls", "dictionary", "ingest", "mapping_set", "pilot", "policy", "submitted_q2"]

pytestmark = [pytest.mark.pg, pytest.mark.retained]

SECTION, PROBE = "risk_probe", "probe."
FORENSIC = (
    "- forensic checks beyond the risk probe's ratio checks (see `risk_probe` for the sources "
    "it does not assess)"
)
NO_SHEET = "NOT_ASSESSED: no filed balance sheet in the run's package"
NO_WINDOW = "no half-year or annual flow window in the statement"
STATUSES = ("NOT_ASSESSED", "FLAGGED", "PASSED", "COMPUTED")
SOURCES = (
    "related parties",
    "pledges",
    "contingent liabilities",
    "auditor opinion",
    "capitalised intangibles",
    "rating remarks",
    "disclosure lapses",
)
VERSIONS = "SELECT count(*) FROM eqos.report_versions"
CAPTURE_OF = (
    "SELECT c.blob_sha256 FROM eqos.interpretations i "
    "JOIN eqos.capture_refs c ON c.id = i.capture_ref_id WHERE i.id = %s"
)
SOURCE_OF = (
    "SELECT source_id FROM eqos.capture_refs WHERE blob_sha256 = %s AND surface = %s ORDER BY id"
)
# ``run_draft._OPERAND_BLOBS`` before S1 (direct operands only), copied: the draft must refuse
# a blob this query cannot see.
FLAT_BLOBS: LiteralString = """SELECT DISTINCT c.blob_sha256
FROM eqos.calculation_trace_operands o
JOIN eqos.interpretations i ON i.id = o.interpretation_id
JOIN eqos.capture_refs c ON c.id = i.capture_ref_id
WHERE o.calculation_trace_id = ANY(%s)"""
M = ("cost_of_materials_consumed", "purchases_of_stock_in_trade", "changes_in_inventories")
# Each check's raw filed amounts (spec §2) and the trend arrow (+1 up is adverse, −1 down).
OPERANDS = {
    "R1": ("trade_receivables_current", "revenue_from_operations"),
    "R2": ("inventories", *M),
    "R3": ("trade_payables_current", *M),
    "R4": ("cfo", "profit_for_period"),
    "R5": ("cf_capex_ppe", "revenue_from_operations"),
    "R6": ("borrowings_current", "borrowings_noncurrent", "total_equity"),
}
ARROWS = {"R1": 1, "R2": 1, "R4": -1, "R6": 1}
FY26_Q2 = "90baae0babfa7724e652def20f613efbf33bdadbbbe545e97ff77617d467d799"
FY25_Q2 = "c44ac3766fedbf697bb91551d55c59015a3253bac99ec95ff03f1bc7795b9d60"
FY26_Q4 = "be8ef6514df9d4ba25265ace74b85eb476d1f0a7891356a8319458d99f73bf01"
FY25_Q4 = "943873742981759927022eb5963d1ed0a4e1d2fe2aac8d9feda0fcf3c64f4cc2"
# The filed consolidated figures (INR, canonical sign: capex is an outflow, so negative) at each
# statement's balance date and flow window, and R1–R6 half-even at the rounding policy's stored
# scale (days and percentages two places, R6 six). Computed once by an independent stdlib reader
# of the pinned XBRL instances (non-dimensional facts, declared reporting periods;
# scratchpad/research3-s1/tests-round/filed.py), in Fraction, not by the probe: R1 = receivables /
# revenue × D; R2, R3 = inventories, payables / M × D with M = materials + purchases + change in
# inventories; R4 = cfo / profit × 100; R5 = −capex / revenue × 100;
# R6 = (current + non-current borrowings) / equity. E.g. FY26_Q2 R1 = 45845600000 /
# 108195800000 × 183 = 41948724/540979 ≈ 77.5422 → 77.54.
STATEMENTS: dict[str, dict[str, Any]] = {
    FY26_Q2: {
        "balance": date(2025, 9, 30),
        "window": (date(2025, 4, 1), date(2025, 9, 30)),  # D = 183
        "raw": {
            "trade_receivables_current": 45845600000,
            "inventories": 33645000000,
            "trade_payables_current": 52938200000,
            "borrowings_current": 3290100000,
            "borrowings_noncurrent": 2619100000,
            "total_equity": 48525100000,
            "revenue_from_operations": 108195800000,
            "cost_of_materials_consumed": 85375100000,
            "purchases_of_stock_in_trade": 555200000,
            "changes_in_inventories": -888400000,
            "cfo": 1688400000,
            "profit_for_period": 5146100000,
            "cf_capex_ppe": -4068300000,
        },
        "ratios": {
            "R1": "77.54",  # 41948724/540979
            "R2": "72.40",  # 6841150/94491
            "R3": "113.92",  # 32292302/283473
            "R4": "32.81",  # 1688400/51461
            "R5": "3.76",  # 2034150/540979
            "R6": "0.121776",  # 59092/485251
        },
    },
    FY25_Q2: {
        "balance": date(2024, 9, 30),
        "window": (date(2024, 4, 1), date(2024, 9, 30)),  # D = 183
        "ratios": {
            "R1": "85.23",  # 73765287/865502
            "R2": "82.46",  # 11361006/137773
            "R4": "102.88",  # 4078400/39641
            "R6": "0.114791",  # 47150/410747
        },
    },
    FY26_Q4: {
        "balance": date(2026, 3, 31),
        "window": (date(2025, 4, 1), date(2026, 3, 31)),  # D = 365
        "raw": {
            "trade_receivables_current": 53340900000,
            "inventories": 41527900000,
            "trade_payables_current": 68558900000,
            "borrowings_current": 4077300000,
            "borrowings_noncurrent": 4327800000,
            "total_equity": 53933800000,
            "revenue_from_operations": 229021200000,
            "cost_of_materials_consumed": 186942500000,
            "purchases_of_stock_in_trade": 1034200000,
            "changes_in_inventories": -7068200000,
            "cfo": 9676700000,
            "profit_for_period": 9769300000,
            "cf_capex_ppe": -7366600000,
        },
        "ratios": {
            "R1": "85.01",  # 64898095/763404
            "R2": "83.79",  # 30315367/361817
            "R3": "138.32",  # 50047997/361817
            "R4": "99.05",  # 20900/211
            "R5": "3.22",  # 1841650/572553
            "R6": "0.155841",  # 84051/539338
        },
    },
    FY25_Q4: {
        "balance": date(2025, 3, 31),
        "window": (date(2024, 4, 1), date(2025, 3, 31)),  # D = 365
        "ratios": {
            "R1": "80.11",  # 148853205/1858121
            "R2": "81.98",  # 60416625/736967
            "R4": "157.13",  # 12905600/82131
            "R6": "0.104393",  # 23507/225177
        },
    },
}
# Each pilot quarter's selected statement, its matching prior (T0-2) and whether it is stale.
QUARTERS = {
    "FY26_Q2": (FY26_Q2, FY25_Q2, False),
    "FY26_Q3": (FY26_Q2, None, True),
    "FY26_Q4": (FY26_Q4, FY25_Q4, False),
    "FY27_Q1": (FY26_Q4, None, True),
}
H1 = PeriodInterval.duration(*STATEMENTS[FY26_Q2]["window"])
CRORE = 10**7
Edit = Callable[[CaptureReference, tuple[Interpretation, ...]], tuple[Interpretation, ...]]


def trace_closure(pilot: Pilot, trace_ids: Iterable[int | None]) -> frozenset[int]:
    """Every trace the given ones reach through operand traces (``citations.TRACES``)."""
    from equity_os.publication.checking.citations import TRACES

    query: LiteralString = "WITH RECURSIVE " + TRACES + " SELECT id FROM traces"
    ids = [trace_id for trace_id in trace_ids if trace_id is not None]
    with pilot.pg_db.runtime_pool() as pool, pool.connection() as conn:
        return frozenset(row[0] for row in conn.execute(query, {"traces": ids}).fetchall())


def probe_keys(quarter: str) -> set[str]:
    """The probe claim keys PILOT-4 expects on a quarter's run."""
    _, prior, _ = QUARTERS[quarter]
    keys = {f"{PROBE}{c}" for c in OPERANDS} | {
        f"{PROBE}{c}.{operand}" for c, operands in OPERANDS.items() for operand in operands
    }
    return keys | ({f"{PROBE}{c}.prior" for c in ARROWS} if prior else set())


def _body(version: VersionDraft, key: str = SECTION) -> str:
    """A section's body."""
    (body,) = (s.body for s in version.sections if s.section_key == key)
    return body


def _paragraphs(body: str) -> list[str]:
    """A section's paragraphs after its heading."""
    return [p for p in re.split(r"\n[ \t]*\n", body) if p.strip() and not p.startswith("## ")]


def _row(body: str, check_id: str) -> str:
    """The check's row: the first line naming its label."""
    from equity_os.analysis.lenses.risk.risk_probe import CHECKS

    return next(line for line in body.splitlines() if CHECKS[check_id].label in line)


def _probe_claims(version: VersionDraft) -> dict[str, NumericClaim]:
    """The version's probe claims by key."""
    return {c.claim_key: c for c in version.claims if c.claim_key.startswith(PROBE)}


def _status(check_id: str, raw: Mapping[str, int], now: Fraction, then: Fraction | None) -> str:
    """The status the filed figures imply: S (cash below profit) and T (a strict move in the
    arrow's direction) fire; an evaluated rule that holds passes; otherwise computed."""
    fired = check_id == "R4" and raw["cfo"] < raw["profit_for_period"]
    trended = then is not None and check_id in ARROWS
    fired = fired or (trended and (now - then) * ARROWS[check_id] > 0)
    return "FLAGGED" if fired else "PASSED" if trended or check_id == "R4" else "COMPUTED"


def check_probe(pilot: Pilot, version_ids: Mapping[str, int]) -> None:
    """PILOT-4's probe checks on each quarter's version: the section follows the falsifier
    status; R1–R6, the raw amounts and the priors equal the filed-figure constants; every row
    shows its balance date and flow window and the status those figures imply; raw amounts are
    ``FILED`` figures on the selected capture's interpretations; a comparator's statement is
    marked stale; the forensic disclosure is qualified."""
    for quarter, version_id in version_ids.items():
        version = pilot.version(version_id)
        selected, prior, stale = QUARTERS[quarter]
        statement = STATEMENTS[selected]
        keys = [s.section_key for s in version.sections]
        assert keys[keys.index(FALSIFIER_STATUS) + 1] == SECTION, f"PILOT-4: {quarter} {keys}"
        body, claims = _body(version), _probe_claims(version)
        assert ("stale" in body.lower()) is stale, f"PILOT-4: {quarter} staleness"
        assert FORENSIC in _body(version, NOT_PERFORMED).splitlines(), f"PILOT-4: {quarter} P9"
        dates = (statement["balance"], *statement["window"])
        for check_id, operands in OPERANDS.items():
            ratio = claims[f"{PROBE}{check_id}"]
            now = Fraction(statement["ratios"][check_id])
            assert Fraction(ratio.value or 0) == now, f"PILOT-4: {quarter} {check_id}"
            assert ratio.citation.kind is CitationKind.CALCULATION, f"PILOT-4: {check_id} route"
            then = None
            if prior is not None and check_id in ARROWS:
                then = Fraction(STATEMENTS[prior]["ratios"][check_id])
                held = claims[f"{PROBE}{check_id}.prior"]
                assert Fraction(held.value or 0) == then, f"PILOT-4: {quarter} {check_id} prior"
            for operand in operands:
                raw = claims[f"{PROBE}{check_id}.{operand}"]
                want = Fraction(statement["raw"][operand], CRORE)
                assert Fraction(raw.value or 0) == want, f"PILOT-4: {quarter} {raw.claim_key}"
                cited = raw.citation
                assert cited.kind is CitationKind.FIGURE and FILED in raw.qualifiers
                assert cited.interpretation_id is not None, f"PILOT-4: {raw.claim_key} route"
                ((blob,),) = pilot.query(CAPTURE_OF, cited.interpretation_id)
                assert blob == selected, f"PILOT-4: {quarter} {raw.claim_key} capture"
            row = _row(body, check_id)
            assert all(day.isoformat() in row for day in dates), f"PILOT-4: {quarter} {row}"
            want_status = _status(check_id, statement["raw"], now, then)
            shown = {status for status in STATUSES if status in row}
            assert shown == {want_status}, f"PILOT-4: {quarter} {check_id} {shown}"
        assert Fraction(claims[f"{PROBE}R5"].value or 0) > 0, f"PILOT-4: {quarter} R5 sign"


# Binding boundary (q) -------------------------------------------------------------------------


def _edit(monkeypatch: pytest.MonkeyPatch, edit: Edit) -> None:
    """Every store read of a capture's interpretations passes through ``edit``."""
    real = _Binder._interpretations

    def read(self: _Binder, capture: CaptureReference | None) -> tuple[Interpretation, ...]:
        found = real(self, capture)
        return found if capture is None else edit(capture, found)

    monkeypatch.setattr(_Binder, "_interpretations", read)


def _is(item: Interpretation, canonical_id: str | None, period: PeriodInterval | None) -> bool:
    """Whether a keyed interpretation is of ``canonical_id`` (any) at ``period`` (any)."""
    key = item.key
    return (
        key is not None
        and canonical_id in (None, key.canonical_id)
        and period in (None, key.period)
    )


def _instant(item: Interpretation) -> bool:
    """Whether a keyed interpretation is at an instant."""
    return item.key is not None and item.key.period.instant is not None


def _no_revenue_window(capture: CaptureReference, found: tuple[Interpretation, ...]) -> Any:
    return tuple(i for i in found if not _is(i, "revenue_from_operations", H1))


def _ambiguous_cfo(capture: CaptureReference, found: tuple[Interpretation, ...]) -> Any:
    doubled = (
        i.model_copy(update={"interpretation_id": (i.interpretation_id or 0) + 10**9})
        for i in found
        if _is(i, "cfo", None)
    )
    return (*found, *doubled)


def _no_balance_sheet(capture: CaptureReference, found: tuple[Interpretation, ...]) -> Any:
    return tuple(i for i in found if not _instant(i))


def _no_evaluable_row(capture: CaptureReference, found: tuple[Interpretation, ...]) -> Any:
    if capture.blob_sha256 != FY26_Q2:
        return found
    equity = PeriodInterval.at(STATEMENTS[FY26_Q2]["balance"])
    return tuple(i for i in found if not (_is(i, None, H1) or _is(i, "total_equity", equity)))


def _only_other_balances(capture: CaptureReference, found: tuple[Interpretation, ...]) -> Any:
    if capture.blob_sha256 != FY26_Q2:
        return found
    at = PeriodInterval.at(STATEMENTS[FY26_Q2]["balance"])
    assert any(_is(i, "total_assets", at) for i in found), "fixture gap: no other balance"
    lines = {i for c in ("R1", "R2", "R3", "R6") for i in OPERANDS[c] if i not in M}
    lines -= {"revenue_from_operations"}
    return tuple(i for i in found if not any(_is(i, line, at) for line in lines))


@pytest.mark.parametrize(
    "edit",
    [
        _no_revenue_window,
        _ambiguous_cfo,
        _no_balance_sheet,
        _no_evaluable_row,
        _only_other_balances,
    ],
    ids=[
        "missing-revenue-window",
        "ambiguous-cfo",
        "no-balance-sheet",
        "no-evaluable-row",
        "only-other-balances",
    ],
)
def test_probe_lookup_failures(pilot: Pilot, monkeypatch: pytest.MonkeyPatch, edit: Edit) -> None:
    """A missing input fails its own rows, not the report; an ambiguous one is a store fault.
    Revenue missing at the half-year leaves R2–R4 and R6 assessed on the same window (the window
    is not read from revenue); two mapped cfo interpretations refuse with nothing written; no
    balance sheet, or no row evaluable on the selected statement, is one labelled paragraph
    naming every source the probe does not assess, beside an otherwise complete draft. A current
    statement holding other balances but none of the probe's is still the current statement, not
    a stale substitute: its balance rows report the missing lines and its flow rows are assessed."""
    _edit(monkeypatch, edit)
    before = pilot.query(VERSIONS)
    if edit is _ambiguous_cfo:
        with pytest.raises(RunDraftError, match="cfo"):
            pilot.run("FY26_Q2")
        assert pilot.query(VERSIONS) == before
        return
    version_id = pilot.run("FY26_Q2").draft_version_id
    assert version_id is not None
    version = pilot.version(version_id)
    body, claims = _body(version), _probe_claims(version)
    keys = [s.section_key for s in version.sections]
    assert keys[keys.index(FALSIFIER_STATUS) + 1] == SECTION
    assert set(dict(pilot.validate(version_id).claim_states).values()) == {ClaimState.MATCH}
    if edit is _no_revenue_window:
        assert {f"{PROBE}{c}" for c in ("R2", "R3", "R4", "R6")} <= claims.keys()
        assert not {f"{PROBE}R1", f"{PROBE}R5"} & claims.keys()
        for check_id in ("R1", "R5"):
            row = _row(body, check_id)
            assert "NOT_ASSESSED" in row and "revenue_from_operations" in row, row
        window = _row(body, "R2")
        assert all(day.isoformat() in window for day in STATEMENTS[FY26_Q2]["window"]), window
        return
    if edit is _only_other_balances:
        assert "stale" not in body.lower(), body
        assert {f"{PROBE}R4", f"{PROBE}R5"} <= claims.keys()
        for check_id, line in (("R1", "trade_receivables_current"), ("R6", "total_equity")):
            row = _row(body, check_id)
            assert STATEMENTS[FY26_Q2]["balance"].isoformat() in row, row
            assert "NOT_ASSESSED" in row and line in row, row
        return
    (paragraph,) = _paragraphs(body)
    assert not claims and "{{e:computed}}" in paragraph
    for source in SOURCES:
        assert f"NOT_ASSESSED: {source} not assessed by this probe" in paragraph
    if edit is _no_balance_sheet:
        assert NO_SHEET in paragraph
    else:
        assert STATEMENTS[FY26_Q2]["balance"].isoformat() in paragraph
        assert NO_WINDOW in paragraph and "total_equity" in paragraph
        assert all(re.search(rf"\b{c}\b", paragraph) for c in OPERANDS), paragraph


# Filed-figure exception (invariant 7, OD-2) ------------------------------------------------------


def _resolved(pilot: Pilot, version: VersionDraft, claim: NumericClaim) -> Any:
    """What the claim's citation resolves to under the version's pins."""
    with pilot.pg_db.runtime_pool() as pool, pool.connection() as conn:
        return resolve_citation(
            conn.cursor(),
            claim,
            entity_id=pilot.entity_id,
            overlay_position=datetime.now(UTC),
            run_ids=version.pinned_run_ids,
            **pilot.sources(),
        )


def test_only_the_probes_own_operands_may_cite_a_filed_value(pilot: Pilot) -> None:
    """OD-2 widened invariant 7 to the amounts the probe uses, not to anything probe-shaped: an
    unknown check, an operand that is not that check's, a key naming another line and a key of
    another amount kind all fail to resolve, while the stored raw claim resolves."""
    version_id = pilot.run("FY26_Q2").draft_version_id
    assert version_id is not None
    version = pilot.version(version_id)
    raw = _probe_claims(version)[f"{PROBE}R1.revenue_from_operations"]
    assert raw.measurement_key is not None
    assert _resolved(pilot, version, raw) is not None
    renamed = raw.measurement_key.model_copy(update={"canonical_id": "total_income"})
    per_share = raw.measurement_key.model_copy(update={"value_kind": ValueKind.PER_SHARE_AMOUNT})
    for update in (
        {"claim_key": f"{PROBE}R9.revenue_from_operations"},
        {"claim_key": f"{PROBE}R1.total_income"},
        {"claim_key": f"{PROBE}R6.revenue_from_operations"},
        {"claim_key": f"{PROBE}R1.total_income", "measurement_key": renamed},
        {"measurement_key": renamed},
        {"measurement_key": per_share},
    ):
        claim = raw.model_copy(update=update)
        assert _resolved(pilot, version, claim) is None, update


# Binding boundary (r) -------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("foreign", "end", "admitted", "message"),
    [
        (FY25_Q4, date(2025, 3, 31), False, "captures not in the run's package"),
        (FY26_Q4, date(2026, 3, 31), True, "captures past the source cutoff"),
    ],
    ids=["outside-package", "past-cutoff"],
)
def test_a_nested_probe_operand_outside_the_package_or_cutoff_refuses(
    pilot: Pilot,
    monkeypatch: pytest.MonkeyPatch,
    foreign: str,
    end: date,
    admitted: bool,
    message: str,
) -> None:
    """R6's borrowings sum is a child trace, so its leaves reach the draft only through it. A
    leaf from another registered capture, outside the package or published after the cutoff,
    must refuse the draft even though every citation and every top-level operand is in the
    package (the pre-S1 operand query cannot see it)."""
    surface = SURFACE_OF[Representation.XBRL].value
    ((source_id, *_), *_) = pilot.query(SOURCE_OF, foreign, surface)
    with pilot.pg_db.runtime_pool() as pool:
        assert EvidenceRepository(pool).find_capture_ref(source_id, surface, foreign) is not None
    source = Provenance(
        source_id=source_id,
        file_sha256=foreign,
        anchor_type=SourceAnchorType.XBRL_CONTEXT,
        context_ref="OneI",
        retrieved_at=datetime.now(UTC),
    )
    swapped: list[int | None] = []
    real_child = _Binder.child

    def child(self: _Binder, name: str, formula: str, output: Any, operands: Any) -> Any:
        if any(value.key.canonical_id == "borrowings_current" for _, value in operands):
            replaced = []
            for label, value in operands:
                if value.key.canonical_id == "borrowings_current":
                    key = value.key.model_copy(update={"period": PeriodInterval.at(end)})
                    found = self.filed(source, key, SelectionSource.HISTORICAL_PACKAGE)
                    assert found is not None, "fixture gap: no foreign borrowings instant"
                    swapped.append(found[1].interpretation_id)
                    value = found[1]
                replaced.append((label, value))
            operands = tuple(replaced)
        return real_child(self, name, formula, output, operands)

    monkeypatch.setattr(_Binder, "child", child)
    seen: dict[str, Any] = {}
    real_check = run_draft._check_sources

    def check(cursor: Any, claims: Any, run: Any, prior: Any, catalog: Any) -> None:
        traces = [c.citation.calculation_trace_id for c in claims]
        seen["direct"] = {c.citation.source_sha256 for c in claims}
        rows = cursor.execute(FLAT_BLOBS, ([t for t in traces if t],)).fetchall()
        seen["flat"] = {row[0] for row in rows}
        seen["allowed"] = run_draft.allowed_captures(prior, run.xbrl, run.pdfs)
        seen["published"] = run.retrospective.published.get(foreign)
        seen["cutoff"] = run.update.source_cutoff
        real_check(cursor, claims, run, prior, catalog)

    monkeypatch.setattr(run_draft, "_check_sources", check)
    if admitted:
        real_allowed = run_draft.allowed_captures
        monkeypatch.setattr(
            run_draft, "allowed_captures", lambda *args: real_allowed(*args) | {foreign}
        )
    before = pilot.query(VERSIONS)
    with pytest.raises(RunDraftError, match=message):
        pilot.run("FY26_Q2")
    assert swapped and None not in swapped, "the child sum was not intercepted"
    assert (foreign in seen["allowed"]) is admitted, "fixture gap: package membership"
    assert seen["published"] is not None, "fixture gap: not in the retrieval manifest"
    assert (seen["published"] > seen["cutoff"]) is admitted, "fixture gap: publication"
    assert foreign not in seen["direct"] | seen["flat"], "the pre-S1 check would see the leaf"
    assert pilot.query(VERSIONS) == before


# Rework (s) -----------------------------------------------------------------------------------


@pytest.mark.parametrize("rejected", ["fact.revenue", CABLES], ids=["run-lines", "guidance"])
def test_a_selective_rework_rederives_the_probe_on_the_heads_traces(
    submitted_q2: tuple[Pilot, int], calls: Calls, rejected: str
) -> None:
    """``risk_probe`` is derived, so every run re-derives it, a selective rework included: the
    successor's probe claims are the head's, on the same content-addressed traces, and each
    probe trace (children included) is computed and stored exactly once. The run lines'
    rework guarantee stays with the PREP-5 tests (``calls["conclude"]``)."""
    pilot, head = submitted_q2
    before = _probe_claims(pilot.version(head))
    assert before, "the head carries no probe claims"
    _request_changes(pilot, head, rejected)
    new = _rerun(pilot).draft_version_id
    assert new is not None
    assert _probe_claims(pilot.version(new)) == before
    closure = trace_closure(pilot, (c.citation.calculation_trace_id for c in before.values()))
    with pilot.pg_db.runtime_pool() as pool:
        traces = EvidenceRepository(pool).get_calculation_traces(sorted(closure))
    assert sorted(calls["probe"]) == sorted(t.trace.key_digest for t in traces)
    assert set(calls["probe_put"]) == closure


@pytest.mark.parametrize(
    "rejected",
    [f"{PROBE}R1.trade_receivables_current", f"{PROBE}R1"],
    ids=["raw-figure", "calculation"],
)
def test_a_rejected_probe_claim_routes_to_diagnosis_and_a_full_successor(
    submitted_q2: tuple[Pilot, int], rejected: str
) -> None:
    """A probe amount comes from the filed interpretation, not the thesis, so superseding the
    thesis could never fix it: the refusal names the route that does, and that route runs."""
    pilot, head = submitted_q2
    _request_changes(pilot, head, rejected)
    with pytest.raises(RunDraftError, match="diagnose.*--full-successor") as refused:
        _rerun(pilot)
    assert rejected in str(refused.value) and "thesis" not in str(refused.value)
    assert _rerun(pilot, "--full-successor").draft_version_id is not None


def test_an_unusable_qoq_comparison_keeps_the_stale_fallback(
    pilot: Pilot, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FY26_Q3 files no statement of its own, so its probe reads its declared QoQ capture (stale)
    even when no comparison could use that capture (eqos-7d3a)."""
    import yaml

    from equity_os.extraction.xbrl.xbrl_parser import FactSelectionError
    from equity_os.interface.workflows import run_comparatives

    pilot.approve(pilot.run("FY26_Q2").draft_version_id or 0)
    _, argv = pilot.registered("FY26_Q3")
    config = yaml.safe_load(open(argv[argv.index("--config") + 1], encoding="utf-8"))
    qoq, select = config["comparators"]["qoq"]["sha256"], run_comparatives._select_prior

    def unusable(observations: Any, concept: str, instance: Any) -> Any:
        if instance.sha256 == qoq:
            raise FactSelectionError("synthetic")
        return select(observations, concept, instance)

    monkeypatch.setattr(run_comparatives, "_select_prior", unusable)
    result = pilot.run("FY26_Q3")
    assert all(item.qoq.prior_source is None for item in result.update.comparatives)
    assert result.draft_version_id is not None
    check_probe(pilot, {"FY26_Q3": result.draft_version_id})
