"""RESEARCH-3 S2 Task 3: management credibility at the run, on the retained pilot.

Real ``_Binder``, ``check_claim`` and CLI over the retained Apar originals; interpretations a filing
lacks are stored through the real repository (``seed``). A chain costs minutes, so a test walks one
chain through several related assertions. Seams fixed for the implementer: ``cli.load_targets``,
``cli.preflight``, ``cli.write_run_draft`` are ``cli`` globals; ``credibility.ACTUALS`` is a plain
dict; ``prepare`` calls ``derive_window`` as a ``credibility`` global. Real runs cannot score Apar's
undated quotes (C-8), so ``_score`` patches exactly those two seams.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from fractions import Fraction
from pathlib import Path
from typing import Any

import pytest
import yaml
from credibility_support import (
    claim,
    cred_module,
    entry,
    event_of,
    gt_module,
    measure,
    outcomes,
    record_lines,
    registry,
    row,
    same_statement,
    write_targets,
)
from evidence_support import ingest, policy
from prep2b_support import Pilot
from prep5_support import _rerun
from retained_support import APAR_MANIFEST, REPO_ROOT
from test_prep2b_run_draft import dictionary, mapping_set, pilot
from test_prep5_rework import CABLES, _request_changes

from fundamentals.api import cli
from fundamentals.api.cli import PILOT_VERSIONS, _build_parser, run_command
from fundamentals.api.ledger_cli import DEFAULT_IMPORT_CONFIG
from fundamentals.canon.interval import Interval
from fundamentals.contracts.canonical import Basis, Representation
from fundamentals.contracts.evidence import InterpretationStatus, RunMode
from fundamentals.contracts.ledger import ClaimState, NumericClaim
from fundamentals.contracts.measurement_key import PeriodInterval
from fundamentals.evidence.capture_intake import SURFACE_OF
from fundamentals.evidence.repository import EvidenceRepository
from fundamentals.ledger import lifecycle, run_draft
from fundamentals.ledger.citations import resolve_citation
from fundamentals.ledger.claim_check import check_claim
from fundamentals.ledger.display import render_section
from fundamentals.ledger.run_traces import RunDraftError

__all__ = ["dictionary", "ingest", "mapping_set", "pilot", "policy"]

pytestmark = [pytest.mark.pg, pytest.mark.retained]

SECTION, PROBE_SECTION, GUIDANCE = "management_credibility", "risk_probe", "management_ledger"
REVENUE = "revenue_from_operations"
FY26_Q2 = "90baae0babfa7724e652def20f613efbf33bdadbbbe545e97ff77617d467d799"
FY25_Q2 = "c44ac3766fedbf697bb91551d55c59015a3253bac99ec95ff03f1bc7795b9d60"
FY26_Q4 = "be8ef6514df9d4ba25265ace74b85eb476d1f0a7891356a8319458d99f73bf01"
# Apar's consolidated revenue growth, computed once with Fraction from the filed figures (never by
# the probe or this code): H1 108195800000 on 86550200000; annual 229021200000 on 185812100000.
H1_GROWTH, H1_DIGITS = Fraction(10822800, 432751), "25.009300"
ANNUAL_GROWTH, ANNUAL_DIGITS = Fraction(43209100, 1858121), "23.254190"
FY25, FY24 = (date(2024, 4, 1), date(2025, 3, 31)), (date(2023, 4, 1), date(2024, 3, 31))
FY26 = (date(2025, 4, 1), date(2026, 3, 31))
H1_26, H1_25 = (date(2025, 4, 1), date(2025, 9, 30)), (date(2024, 4, 1), date(2024, 9, 30))
ALONE: dict[str, Any] = {"basis": Basis.STANDALONE}
QUARTERS = ("FY26_Q2", "FY26_Q3", "FY26_Q4", "FY27_Q1")

CONDUCTOR = "conductor_ebitda_per_mt.consolidated.AMBIGUOUS.conductor-ebitda-FY26_Q2"
GROWTH_Q2 = "cables_revenue_growth.consolidated.AMBIGUOUS.cables-growth-FY26_Q2"
CAGR_Q3 = "cables_revenue_growth.consolidated.DESCRIPTIVE.cables-growth-FY26_Q3"
MARGIN = "cables_ebitda_margin.consolidated.AMBIGUOUS.cables-margin-FY26_Q3"
VOLUME = "conductor_volume_growth.consolidated.AMBIGUOUS.conductor-volume-FY26_Q4"
GROWTH_Q4 = "cables_revenue_growth.consolidated.MULTI_YEAR.cables-growth-FY26_Q4"
# PROVISIONAL with the mapping file: Sol's freeze review may change these literals.
EPISODES = {
    "FY26_Q2": (CONDUCTOR, GROWTH_Q2),
    "FY26_Q3": (CONDUCTOR, GROWTH_Q2, CAGR_Q3, MARGIN),
    "FY26_Q4": (CONDUCTOR, GROWTH_Q2, CAGR_Q3, MARGIN, VOLUME, GROWTH_Q4),
    "FY27_Q1": (CONDUCTOR, GROWTH_Q2, CAGR_Q3, MARGIN, VOLUME, GROWTH_Q4),
}
EVENTS = {
    "conductor-ebitda-FY26_Q2": ("FY26_Q2", "OPENED"),
    "cables-growth-FY26_Q2": ("FY26_Q2", "OPENED"),
    "cables-growth-FY26_Q3": ("FY26_Q3", "DESCRIBED"),
    "cables-margin-FY26_Q3": ("FY26_Q3", "OPENED"),
    "conductor-ebitda-FY26_Q4": ("FY26_Q4", "REVISED_UP"),
    "conductor-volume-FY26_Q4": ("FY26_Q4", "OPENED"),
    "cables-growth-FY26_Q4": ("FY26_Q4", "OPENED"),
    "cables-margin-FY27_Q1": ("FY27_Q1", "REVISED_UP"),
}
LATEST_MOVES = {"FY26_Q4": {CONDUCTOR}, "FY27_Q1": {MARGIN}}
UNDATED = ("window not established", "no filed measure")
ROW_REASONS = {
    CONDUCTOR: UNDATED,
    GROWTH_Q2: UNDATED,
    MARGIN: UNDATED,
    VOLUME: UNDATED,
    GROWTH_Q4: ("window not single-year", "no filed measure"),
}
ROUTE = r"diagnose.*supersedes.*--full-successor"
SCORED, ABSENT = "cables-growth-FY26_Q2", "absent-statement"
SCORED_KEY = "cred.cables_revenue_growth.consolidated.FY25"
SCORED_EPISODE = "cables_revenue_growth.consolidated.FY25"


def _apar() -> list[dict[str, Any]]:
    path = REPO_ROOT / "config" / "guidance_targets" / "aparinds.yaml"
    entries: list[dict[str, Any]] = yaml.safe_load(path.read_text("utf-8"))["entries"]
    return entries


def _use(monkeypatch: pytest.MonkeyPatch, pilot: Pilot, entries: list[dict[str, Any]]) -> None:
    """The run's mapping file becomes ``entries`` (a new reviewed file, not a mock of its load)."""
    root = pilot.tmp_path / "targets"
    write_targets(root, *entries)
    load = gt_module().load_targets
    monkeypatch.setattr(cli, "load_targets", lambda symbol, *_a, **_k: load("TEST", root))


def _edited(id_: str, **change: Any) -> list[dict[str, Any]]:
    return [{**held, **change} if held["id"] == id_ else held for held in _apar()]


def _deleted(id_: str) -> list[dict[str, Any]]:
    return [held for held in _apar() if held["id"] != id_]


def _superseded(id_: str, entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The mapping plus a correction reading the entry's quote as descriptive."""
    old = next(item for item in entries if item["id"] == id_)
    return [*entries, {**old, "id": f"{id_}-fix", "supersedes": id_, "reading": "DESCRIPTIVE"}]


def _submit(pilot: Pilot, version: int) -> None:
    with pilot.pg_db.runtime_pool() as pool:
        lifecycle.submit(pool, version, **pilot.sources())


def _run_approved(pilot: Pilot, *quarters: str) -> dict[str, Any]:
    results = {}
    for quarter in quarters:
        results[quarter] = pilot.run(quarter)
        pilot.approve(results[quarter].draft_version_id)
    return results


def _score(monkeypatch: pytest.MonkeyPatch, pilot: Pilot) -> None:
    """Apar's FY26_Q2 cables quote scored against FY25 in real runs: the two seams C-8 forces (a
    registered measure, the window rule reading FY25 for one quote), and a file declaring it."""
    cred = cred_module()
    monkeypatch.setitem(
        cred.ACTUALS,
        ("cables_revenue_growth", "consolidated"),
        measure(REVENUE, "cables_revenue_growth", interim=False),
    )
    quote = next(held["quote"] for held in _apar() if held["id"] == SCORED)
    real = cred.derive_window

    def selective(text: str, *args: Any) -> str:
        return "FY25" if text == quote else real(text, *args)

    monkeypatch.setattr(cred, "derive_window", selective)
    _use(monkeypatch, pilot, _edited(SCORED, window="FY25"))


def seed(
    pilot: Pilot,
    blob: str,
    period: tuple[date, date],
    value: str,
    *,
    basis: Basis = Basis.CONSOLIDATED,
    canonical: str = REVENUE,
    interval: Interval | None = None,
) -> int:
    """A mapped interpretation stored on the registered capture through the real repository, as a
    template copy; its id."""
    surface = SURFACE_OF[Representation.XBRL].value
    with pilot.pg_db.runtime_pool() as pool:
        repo = EvidenceRepository(pool)
        ((source_id,), *_) = pilot.query(
            "SELECT source_id FROM eqos.capture_refs WHERE blob_sha256 = %s AND surface = %s "
            "ORDER BY id",
            blob,
            surface,
        )
        capture = repo.find_capture_ref(source_id, surface, blob)
        template = next(
            item
            for item in repo.list_capture_interpretations(capture.capture_ref_id)
            if item.status is InterpretationStatus.MAPPED
            and item.key is not None
            and item.key.canonical_id == REVENUE
        )
        span = PeriodInterval.duration(*period)
        key = template.key.model_copy(
            update={"basis": basis, "period": span, "canonical_id": canonical}
        )
        (new_id,) = repo.reserve_interpretation_ids(1)
        label = f"{blob}{period}{basis}{canonical}{value}".encode()
        repo.put_interpretations(
            [
                template.model_copy(
                    update={
                        "interpretation_id": new_id,
                        "basis": basis,
                        "period": span,
                        "canonical_id": canonical,
                        "key": key,
                        "value": Decimal(value),
                        "interval": interval or Interval.exact(Decimal(value)),
                        "input_digest": hashlib.sha256(label).hexdigest(),
                        "recorded_at": repo.store_clock() + timedelta(microseconds=1),
                    }
                )
            ]
        )
    return int(new_id)


def _stated(
    metric: str, window: str, scope: str, page: int = 1
) -> tuple[NumericClaim, dict[str, Any]]:
    held = claim(metric, scope=scope, quote=f"growth of 10% in {window}", page=page)
    return held, entry(f"{metric}-{scope}-{window}", held, window)


def direct(
    pilot: Pilot,
    update: Any,
    statements: Any,
    measures: Mapping[Any, Any],
    period: str,
    prior_actuals: tuple[NumericClaim, ...] = (),
) -> tuple[Any, Any]:
    """``prepare``, the real ``bind_credibility`` on the store, and ``build``."""
    cred = cred_module()
    prep = cred.prepare(
        tuple(held for held, _ in statements),
        cred.Record(),
        cred.Record(),
        write_targets(pilot.tmp_path / "direct", *(mapped for _, mapped in statements)),
        period=period,
        period_end=update.period_end,
        month=3,
        filed_at={},
        actual_blobs=frozenset(),
    )
    with pilot.pg_db.runtime_pool() as pool:
        inputs = cred.bind_credibility(
            EvidenceRepository(pool),
            update,
            prep,
            prior_actuals,
            entity_id=pilot.entity_id,
            versions=PILOT_VERSIONS,
            registry=measures,
        )
    section = cred.build(
        prep,
        actuals=inputs.actuals,
        exact=inputs.exact,
        unavailable=inputs.unavailable,
        registry=measures,
    )
    return inputs, section


def citation_state(pilot: Pilot, held: NumericClaim) -> ClaimState:
    with pilot.pg_db.runtime_pool() as pool, pool.connection() as conn:
        resolved = resolve_citation(
            conn.cursor(),
            held,
            entity_id=pilot.entity_id,
            overlay_position=datetime.now(UTC),
            run_ids=(),
            **pilot.sources(),
        )
    at = datetime.now(UTC) + timedelta(days=1)
    return check_claim(held, resolved, mode=RunMode.AS_KNOWN, cutoff=at, imported=False)


def all_counts(pilot: Pilot) -> dict[str, int]:
    """Every ``eqos`` table's row count: a refusal must leave all of them unchanged."""
    tables = pilot.query("SELECT tablename FROM pg_tables WHERE schemaname = 'eqos'")
    return {name: int(pilot.query(f"SELECT count(*) FROM eqos.{name}")[0][0]) for (name,) in tables}


def operand_ids(pilot: Pilot, held: NumericClaim) -> set[int]:
    rows = pilot.query(
        "SELECT interpretation_id FROM eqos.calculation_trace_operands "
        "WHERE calculation_trace_id = %s",
        held.citation.calculation_trace_id,
    )
    return {int(found) for (found,) in rows}


def traces_reading(pilot: Pilot, *ids: int) -> int:
    rows = pilot.query(
        "SELECT count(*) FROM eqos.calculation_trace_operands WHERE interpretation_id = ANY(%s)",
        list(ids),
    )
    return int(rows[0][0])


def _body(pilot: Pilot, version: int) -> str:
    sections = pilot.version(version).sections
    return next(s.body for s in sections if s.section_key == SECTION)


def _all_match(pilot: Pilot, version: int) -> bool:
    return set(dict(pilot.validate(version).claim_states).values()) == {ClaimState.MATCH}


def check_credibility(pilot: Pilot, version_ids: Mapping[str, int]) -> None:
    """PILOT-4's credibility checks on each quarter's version. Apar's quotes name no single year,
    so the record is events and reasons only: any outcome or ``cred.*`` here is a false verdict.
    ``.original`` never moves across the chain; ``.latest`` moves only on a restatement, and then
    it is that quarter's guidance claim."""
    gt, cred = gt_module(), cred_module()
    mapping = gt.load_targets("APARINDS")
    for quarter, version_id in version_ids.items():
        version = pilot.version(version_id)
        keys = [section.section_key for section in version.sections]
        assert keys[keys.index(PROBE_SECTION) + 1] == SECTION, f"PILOT-4: {quarter} {keys}"
        claims = {held.claim_key: held for held in version.claims}
        guidance = [held for held in version.claims if held.section_key == GUIDANCE]
        assert all(held.claim_key.startswith("ledger.") for held in guidance), quarter
        assert not [key for key in claims if key.startswith("cred.")], f"PILOT-4: {quarter} cred"
        want = {f"episode.{n}.{role}" for n in EPISODES[quarter] for role in ("original", "latest")}
        found = {held.claim_key for held in version.claims if held.section_key == SECTION}
        assert found == want, f"PILOT-4: {quarter} episodes"
        body = _body(pilot, version_id)
        lines = record_lines(body)
        due = {
            id_ for id_, (at, _) in EVENTS.items() if at in QUARTERS[: 1 + QUARTERS.index(quarter)]
        }
        assert set(lines) == due, f"PILOT-4: {quarter} statements"
        for id_ in due:
            assert lines[id_]["stated"] == EVENTS[id_][0], f"PILOT-4: {quarter} {id_} period"
            assert event_of(body, id_) == (EVENTS[id_][1], None), f"PILOT-4: {quarter} {id_} event"
        for episode in EPISODES[quarter]:
            line = row(body, episode)
            assert set(outcomes(line)) == {"UNRESOLVED"}, f"PILOT-4: {quarter} {episode}"
            reasons = ROW_REASONS.get(episode, (cred.REASON_DESCRIPTIVE,))
            assert all(reason in line for reason in reasons), f"PILOT-4: {quarter} {episode}"
        record = cred.read_record(body, version.claims)
        assert record.pins == {id_: mapping.entries[id_].digest for id_ in due}, quarter
        previous = run_draft._predecessor(quarter)
        with pilot.pg_db.runtime_pool() as pool, pool.connection() as conn:
            head = run_draft._head(conn.cursor(), pilot.entity_id, previous)
        if head is not None:
            before = {held.claim_key: held for held in pilot.version(head).claims}
            for name in EPISODES.get(previous, ()):
                original, latest = f"episode.{name}.original", f"episode.{name}.latest"
                assert claims[original] == before[original], f"PILOT-4: {quarter} {name} original"
                moved = claims[latest] != before[latest]
                assert moved is (name in LATEST_MOVES.get(quarter, ())), (
                    f"PILOT-4: {quarter} {name}"
                )
                if moved:
                    assert any(same_statement(claims[latest], held) for held in guidance), quarter
        assert _all_match(pilot, version_id), f"PILOT-4: {quarter} claim check"


def test_filed_actuals_on_retained_statements_and_every_admitted_capture(pilot: Pilot) -> None:
    """A12, A14, F5: a verdict's actual is Apar's real filed growth, cited. Half-year FY26 (interim)
    and annual FY26 equal independently computed constants, exactly and at six cut digits; another
    formula or window could not. A target first mapped after its year ended has its figures on an
    earlier filing: every admitted capture is searched, so a filed figure does not read "not yet
    filed", and two captures that disagree are not silently resolved."""
    runs = _run_approved(pilot, "FY26_Q2", "FY26_Q3", "FY26_Q4")
    pair = _stated("revenue_growth", "FY26", "consolidated")
    key = "cred.revenue_growth.consolidated.FY26"
    for quarter, want_key, exact, digits, outcome in (
        ("FY26_Q2", f"{key}.ytd", H1_GROWTH, H1_DIGITS, "ON_TRACK"),
        ("FY26_Q4", key, ANNUAL_GROWTH, ANNUAL_DIGITS, "ACHIEVED"),
    ):
        inputs, section = direct(pilot, runs[quarter].update, (pair,), registry(), quarter)
        (actual,) = inputs.actuals
        assert actual.claim_key == want_key and inputs.exact[want_key] == exact
        assert str(actual.value) == digits and actual.precision == cred_module().EXACT_PLACES
        assert citation_state(pilot, actual) is ClaimState.MATCH
        (stored,) = pilot.query(
            "SELECT count(*) FROM eqos.calculation_traces WHERE id = %s AND formula_id = %s",
            actual.citation.calculation_trace_id,
            "run.change_pct",
        )
        assert stored == (1,)
        assert outcomes(row(section.body, "revenue_growth.consolidated.FY26")) == [outcome]

    _, argv = pilot.registered("FY27_Q1")
    config = yaml.safe_load(Path(argv[argv.index("--config") + 1]).read_text("utf-8"))
    own, qoq = (
        hashlib.sha256(Path(held["local_path"]).read_bytes()).hexdigest()
        for held in (config["xbrl"], config["comparators"]["qoq"])
    )
    assert qoq == FY26_Q4
    only_qoq = {seed(pilot, qoq, FY26, "1100", **ALONE), seed(pilot, qoq, FY25, "1000", **ALONE)}
    same, differ = "profit_before_tax", "profit_for_period"
    own_ids = {
        seed(pilot, own, FY26, "1200", canonical=same, **ALONE),
        seed(pilot, own, FY25, "1000", canonical=same, **ALONE),
    }
    seed(pilot, qoq, FY26, "1200", canonical=same, **ALONE)
    seed(pilot, qoq, FY25, "1000", canonical=same, **ALONE)
    differing = {
        seed(pilot, own, FY26, "1300", canonical=differ, **ALONE),
        seed(pilot, qoq, FY26, "1350", canonical=differ, **ALONE),
        seed(pilot, own, FY25, "1000", canonical=differ, **ALONE),
    }
    update = pilot.run("FY27_Q1").update
    names = {"m_qoq": REVENUE, "m_same": same, "m_differ": differ, "m_none": "cfo"}
    statements = [_stated(name, "FY26", "standalone", page) for page, name in enumerate(names, 1)]
    measures = {(name, "standalone"): measure(num, name) for name, num in names.items()}
    inputs, section = direct(pilot, update, statements, measures, "FY27_Q1")
    found = {held.claim_key: held for held in inputs.actuals}
    assert set(found) == {f"cred.{n}.standalone.FY26" for n in ("m_qoq", "m_same")}
    held = found["cred.m_qoq.standalone.FY26"]
    assert operand_ids(pilot, held) == only_qoq and citation_state(pilot, held) is ClaimState.MATCH
    assert inputs.exact[held.claim_key] == Fraction(10)
    assert operand_ids(pilot, found["cred.m_same.standalone.FY26"]) == own_ids
    assert traces_reading(pilot, *differing) == 0
    reason = "filed value differs across admitted captures"
    assert reason in row(section.body, "m_differ.standalone")
    assert "actual not yet filed" in row(section.body, "m_none.standalone")
    assert "actual not yet filed" not in row(section.body, "m_qoq.standalone")


def test_a_carried_actual_keeps_its_citation_and_captures(
    pilot: Pilot, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The next quarter's package does not hold the capture behind a carried actual, so its blobs
    must be admitted, or the figure's evidence is outside what the version pinned."""
    _score(monkeypatch, pilot)
    pilot.registered("FY26_Q2")
    seed(pilot, FY25_Q2, FY25, "1100000000")
    seed(pilot, FY25_Q2, FY24, "1000000000")
    first = pilot.run("FY26_Q2").draft_version_id
    pilot.approve(first)
    carried = {c.claim_key: c for c in pilot.version(first).claims}[SCORED_KEY]
    real = cli.preflight

    def unadmitted(*args: Any, **kwargs: Any) -> Any:
        return real(*args, **kwargs).model_copy(update={"actual_blobs": frozenset()})

    monkeypatch.setattr(cli, "preflight", unadmitted)
    with pytest.raises(RunDraftError, match="captures not in the run's package"):
        pilot.run("FY26_Q3")
    monkeypatch.setattr(cli, "preflight", real)
    before = traces_reading(pilot, *operand_ids(pilot, carried))
    second = pilot.run("FY26_Q3").draft_version_id
    held = {c.claim_key: c for c in pilot.version(second).claims}[SCORED_KEY]
    assert held.citation == carried.citation
    assert traces_reading(pilot, *operand_ids(pilot, carried)) == before
    assert _all_match(pilot, second)


def test_a_mapping_fault_refuses_before_any_write(
    pilot: Pilot, monkeypatch: pytest.MonkeyPatch
) -> None:
    """F1, A10, on one chain. A run is refused before its first write: the same run on a valid file
    then adds traces and facts, which proves the refused run had writes to make and made none. Next
    quarter, editing or deleting a used entry would rewrite sealed history, so it refuses naming the
    entry. A carried statement's transcript published after the cutoff fails ``check_blobs`` on the
    real manifest route; nothing here touches the call order."""
    pilot.registered("FY26_Q2")
    before = all_counts(pilot)
    quote = next(e["quote"] for e in _apar() if e["id"] == SCORED)
    later = next(e for e in _apar() if e["id"] == "conductor-ebitda-FY26_Q4")
    absent = {k: v for k, v in later.items() if k != "same_as"} | {
        "id": ABSENT,
        "anchor": "p1.b1.0:1",
    }
    for entries, named in (
        (_edited(SCORED, quote=f"{quote} or"), SCORED),
        (_edited(SCORED, window="FY26"), SCORED),
        ([absent, *_edited("conductor-ebitda-FY26_Q2", same_as=ABSENT)], ABSENT),
    ):
        _use(monkeypatch, pilot, entries)
        with pytest.raises(RunDraftError, match=named):
            pilot.run("FY26_Q2")
        assert all_counts(pilot) == before
    _use(monkeypatch, pilot, _apar())
    _run_approved(pilot, "FY26_Q2")
    after = all_counts(pilot)
    assert after["calculation_traces"] > before["calculation_traces"]
    assert after["fact_admissions"] > before["fact_admissions"]

    context, argv = pilot.registered("FY26_Q3")
    before = all_counts(pilot)
    for entries in (_edited(SCORED, definition="edited"), _deleted(SCORED)):
        _use(monkeypatch, pilot, entries)
        with pytest.raises(RunDraftError, match=SCORED):
            pilot.run("FY26_Q3")
        assert all_counts(pilot) == before

    _use(monkeypatch, pilot, _apar())
    manifest = json.loads(APAR_MANIFEST.read_text("utf-8"))
    (late,) = [
        item
        for item in manifest["entries"]
        if item["sha256"] == next(e["source_sha256"] for e in _apar() if e["id"] == SCORED)
    ]
    late["filed_at_nse"] = "01-Dec-2030 10:00:00"
    copy = pilot.tmp_path / "retrieval-manifest-late.json"
    copy.write_text(json.dumps(manifest), encoding="utf-8")
    pin = pilot.tmp_path / DEFAULT_IMPORT_CONFIG
    original = pin.read_text("utf-8")
    pinned = hashlib.sha256(APAR_MANIFEST.read_bytes()).hexdigest()
    assert original.count(pinned) == 1
    pin.write_text(original.replace(pinned, hashlib.sha256(copy.read_bytes()).hexdigest()))
    args = _build_parser().parse_args([*argv, "--retrospective", str(copy)])
    with pytest.raises(RunDraftError, match="captures past the source cutoff"):
        run_command(args, intake_context=context)
    assert all_counts(pilot) == before
    pin.write_text(original)
    pilot.run("FY26_Q3")
    assert all_counts(pilot)["calculation_traces"] > before["calculation_traces"]


def test_a_rejected_episode_or_actual_routes_to_a_mapping_correction(
    pilot: Pilot, monkeypatch: pytest.MonkeyPatch
) -> None:
    """P10: a rework reruns lines, but these claims come from the mapping: an ordinary rerun could
    never change them. Each rejection refuses naming the real route, even with the correction in the
    file, because only ``--full-successor`` rebuilds; it must not send the reader to the thesis."""
    _score(monkeypatch, pilot)
    pilot.registered("FY26_Q2")
    seed(pilot, FY25_Q2, FY25, "1100000000")
    seed(pilot, FY25_Q2, FY24, "1000000000")
    scored = _edited(SCORED, window="FY25")
    fixed = _superseded(SCORED, scored)
    version = pilot.run("FY26_Q2").draft_version_id
    for key, mapping in ((SCORED_KEY, scored), (f"episode.{SCORED_EPISODE}.original", fixed)):
        _submit(pilot, version)
        _request_changes(pilot, version, key)
        before = all_counts(pilot)
        for attempt in (scored, fixed):
            _use(monkeypatch, pilot, attempt)
            with pytest.raises(RunDraftError, match=ROUTE) as refused:
                _rerun(pilot)
            assert "thesis" not in str(refused.value).lower()
            assert all_counts(pilot) == before
        _use(monkeypatch, pilot, mapping)
        version = _rerun(pilot, "--full-successor").draft_version_id
    body = _body(pilot, version)
    assert record_lines(body)[f"{SCORED}-fix"]["event"] == "DESCRIBED"
    assert "mapping corrected" in row(body, SCORED_EPISODE)


@pytest.mark.parametrize("head", ["rejected", "approved"])
def test_a_same_quarter_rerun_holds_that_quarters_pins(
    pilot: Pilot, monkeypatch: pytest.MonkeyPatch, head: str
) -> None:
    """R1: the bootstrap quarter has no previous-quarter head, so only its own head remembers the
    pins. Otherwise an edit just before a rerun would rewrite the version it replaces. A stale view
    of that head refuses under lock, so no rerun overwrites a head it did not read."""
    _use(monkeypatch, pilot, _apar())
    version = pilot.run("FY26_Q2").draft_version_id
    if head == "approved":
        pilot.approve(version)
        flags: tuple[str, ...] = ()
    else:
        _submit(pilot, version)
        _request_changes(pilot, version, CABLES)
        flags = ("--full-successor",)
    before = all_counts(pilot)
    for held in (_edited(SCORED, definition="edited"), _deleted(SCORED)):
        _use(monkeypatch, pilot, held)
        with pytest.raises(RunDraftError, match=SCORED):
            _rerun(pilot, *flags)
        assert all_counts(pilot) == before
    _use(monkeypatch, pilot, _apar())
    real, write, wrote = cli.preflight, cli.write_run_draft, []

    def spy(*args: Any, **kwargs: Any) -> Any:
        wrote.append(args)
        return write(*args, **kwargs)

    monkeypatch.setattr(cli, "write_run_draft", spy)
    for stale in ({"same_period_digest": "0" * 64}, {"same_period_id": None}):
        monkeypatch.setattr(
            cli, "preflight", lambda *a, _s=stale, **k: real(*a, **k).model_copy(update=_s)
        )
        versions, seen = all_counts(pilot)["report_versions"], len(wrote)
        with pytest.raises(RunDraftError):
            _rerun(pilot, *flags)
        assert len(wrote) == seen + 1, "the refusal must come from the lock's recheck"
        assert all_counts(pilot)["report_versions"] == versions
    monkeypatch.setattr(cli, "preflight", real)
    _use(monkeypatch, pilot, _superseded(SCORED, _apar()))
    body = _body(pilot, _rerun(pilot, *flags).draft_version_id)
    assert f"{SCORED}-fix" in body and "mapping corrected" in row(body, GROWTH_Q2)


def test_the_binder_reads_each_statements_own_exact_operands(
    pilot: Pilot, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A2, A7, F2, R5, R6, R9, P11, on one chain over one capture. A standalone promise judged on
    consolidated figures is false. The trace stores 9.50, which rounds to ten and would pass; the
    exact 9.495 misses, and the check refuses a typed-over figure, in the binding run or one
    carrying the claim. FY27's months at an FY26 run produce no verdict or trace. Growth on a
    non-positive base has no meaning: a stated reason in a written report, not a failed run."""
    cred = cred_module()
    _score(monkeypatch, pilot)
    pilot.registered("FY26_Q2")
    scope_ids = {
        seed(pilot, FY26_Q2, H1_26, "5000000000", **ALONE),
        seed(pilot, FY26_Q2, H1_25, "4000000000", **ALONE),
    }
    future = seed(pilot, FY26_Q2, (date(2026, 4, 1), date(2026, 9, 30)), "110", **ALONE)
    seed(pilot, FY26_Q2, FY25, "109495", **ALONE)
    seed(pilot, FY26_Q2, FY24, "100000", **ALONE)
    third, zero, negative = "profit_before_tax", "profit_for_period", "cfo"
    seed(pilot, FY26_Q2, FY25, "400", canonical=third, **ALONE)
    seed(pilot, FY26_Q2, FY24, "300", canonical=third, **ALONE)
    undefined = {
        seed(pilot, FY26_Q2, FY25, "1100", canonical=zero, **ALONE),
        seed(pilot, FY26_Q2, FY24, "0", canonical=zero, **ALONE),
        seed(pilot, FY26_Q2, FY25, "1100", canonical=negative, **ALONE),
        seed(pilot, FY26_Q2, FY24, "-100", canonical=negative, **ALONE),
    }
    seed(pilot, FY26_Q2, H1_26, "10", canonical=negative, **ALONE)
    seed(pilot, FY26_Q2, H1_26, "11", canonical=negative, **ALONE)
    seed(pilot, FY26_Q2, H1_25, "10", canonical=negative, **ALONE)
    crossing = Interval(lower=Fraction(-5), upper=Fraction(205))
    in_run = {
        seed(pilot, FY25_Q2, FY25, "1100"),
        seed(pilot, FY25_Q2, FY24, "100", interval=crossing),
    }
    reason = "comparator revenue not positive or its uncertainty reaches zero"

    result = pilot.run("FY26_Q2")
    update, draft = result.update, pilot.version(result.draft_version_id)
    assert SCORED_KEY not in {held.claim_key for held in draft.claims}
    assert traces_reading(pilot, *in_run) == 0
    line = row(_body(pilot, result.draft_version_id), SCORED_EPISODE)
    assert reason in line and set(outcomes(line)) == {"UNRESOLVED"}

    alone = registry("standalone")
    traces = all_counts(pilot)["calculation_traces"]
    pair = _stated("revenue_growth", "FY27", "standalone")
    inputs, section = direct(pilot, update, (pair,), alone, "FY26_Q2")
    assert inputs.actuals == () and inputs.exact == {} and traces_reading(pilot, future) == 0
    assert all_counts(pilot)["calculation_traces"] == traces
    line = row(section.body, "revenue_growth.standalone.FY27")
    assert set(outcomes(line)) == {"UNRESOLVED"} and "not due: target year not started" in line

    inputs, _ = direct(
        pilot,
        update,
        (
            _stated("revenue_growth", "FY26", "consolidated", 1),
            _stated("revenue_growth", "FY26", "standalone", 2),
        ),
        registry("consolidated", "standalone"),
        "FY26_Q2",
    )
    found = {held.claim_key: held for held in inputs.actuals}
    con = found["cred.revenue_growth.consolidated.FY26.ytd"]
    sta = found["cred.revenue_growth.standalone.FY26.ytd"]
    assert inputs.exact[con.claim_key] == H1_GROWTH and str(con.value) == H1_DIGITS
    assert inputs.exact[sta.claim_key] == Fraction(25) and str(sta.value) == "25.000000"
    assert con.measurement_key.basis is Basis.CONSOLIDATED
    assert sta.measurement_key.basis is Basis.STANDALONE
    assert operand_ids(pilot, sta) == scope_ids and not operand_ids(pilot, con) & scope_ids

    for metric, measures, exact, digits, phrase, outcome in (
        ("revenue_growth", alone, Fraction("9.495"), "9.495000", cred.ACTUAL_WHOLE, "MISSED"),
        (
            "third_growth",
            {("third_growth", "standalone"): measure(third, "third_growth")},
            Fraction(100, 3),
            "33.333333",
            cred.ACTUAL_CUT,
            "ACHIEVED",
        ),
    ):
        statement = _stated(metric, "FY25", "standalone")
        inputs, section = direct(pilot, update, (statement,), measures, "FY26_Q2")
        (actual,) = inputs.actuals
        assert inputs.exact[actual.claim_key] == exact and str(actual.value) == digits
        line = row(section.body, f"{metric}.standalone.FY25")
        assert outcomes(line) == [outcome] and phrase in line
        assert f"{{{{c:{actual.claim_key}|ref}}}}" in line
        assert f"{digits}%" in render_section(line, (*section.claims, actual))
        assert citation_state(pilot, actual) is ClaimState.MATCH
        typed = actual.model_copy(update={"value": Decimal("9.500000")})
        bare = actual.model_copy(update={"qualifiers": ()})
        assert citation_state(pilot, typed) is ClaimState.VALUE_MISMATCH
        assert citation_state(pilot, bare) is ClaimState.VALUE_MISMATCH
        traces = all_counts(pilot)["calculation_traces"]
        carried, again = direct(pilot, update, (statement,), measures, "FY26_Q2", (actual,))
        assert carried.actuals == (actual,) and carried.exact[actual.claim_key] == exact
        assert all_counts(pilot)["calculation_traces"] == traces
        assert outcomes(row(again.body, f"{metric}.standalone.FY25")) == [outcome]

    inputs, section = direct(
        pilot,
        update,
        (_stated("zero_base", "FY25", "standalone", 1), _stated("below", "FY25", "standalone", 2)),
        {
            ("zero_base", "standalone"): measure(zero, "zero_base"),
            ("below", "standalone"): measure(negative, "below"),
        },
        "FY26_Q2",
    )
    assert inputs.actuals == () and traces_reading(pilot, *undefined) == 0
    for metric in ("zero_base", "below"):
        line = row(section.body, f"{metric}.standalone.FY25")
        assert reason in line and set(outcomes(line)) == {"UNRESOLVED"}

    # P11's boundary: two values of one key on one capture are a store fault, not a row reason.
    with pytest.raises(RunDraftError, match="no single mapped interpretation"):
        direct(
            pilot,
            update,
            (_stated("twice", "FY26", "standalone"),),
            {("twice", "standalone"): measure(negative, "twice")},
            "FY26_Q2",
        )
