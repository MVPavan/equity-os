"""RESEARCH-3 S2 Task 3: management credibility at the run, on the retained pilot.

A verdict stands on filed operands read from the run's own package, so these tests go through the
real ``_Binder``, ``check_claim`` and the CLI over the retained Apar originals. Interpretations a
filing does not hold are stored in the test database through the real repository (``seed``), so
binder selection itself is under test. Production names new in S2 are imported inside each test.

Contracts the tests fix for the implementer (each is the plan's seam, named):
``cli.load_targets``, ``cli.preflight`` and ``cli.write_run_draft`` are module globals of ``cli``;
``credibility.ACTUALS`` is a plain dict, the default registry; ``prepare`` calls ``derive_window``
as a global of ``credibility``. Real runs cannot score Apar's undated quotes (C-8), so the scored
harness ``_score`` patches exactly those two seams and nothing else.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from fractions import Fraction
from pathlib import Path
from typing import Any

import pytest
import yaml
from credibility_support import (
    all_counts,
    citation_state,
    claim,
    cred_module,
    direct,
    entry,
    event_of,
    gt_module,
    operand_ids,
    outcomes,
    record_lines,
    registry,
    row,
    same_statement,
    seed,
    trace_count,
    traces_reading,
    version_count,
    write_targets,
)
from evidence_support import ingest, policy
from prep2b_support import Pilot
from prep5_support import _rerun
from retained_support import APAR_MANIFEST, REPO_ROOT
from test_prep2b_run_draft import dictionary, mapping_set, pilot
from test_prep5_rework import CABLES, _request_changes, _successor

from fundamentals.api import cli
from fundamentals.api.cli import _build_parser, run_command
from fundamentals.api.ledger_cli import DEFAULT_IMPORT_CONFIG
from fundamentals.canon.interval import Interval
from fundamentals.contracts.canonical import Basis
from fundamentals.contracts.ledger import ClaimState, NumericClaim, VersionDraft
from fundamentals.ledger import lifecycle, run_draft
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


# The harness ------------------------------------------------------------------------------------


def _apar() -> list[dict[str, Any]]:
    """The committed mapping file's entries."""
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
    """The mapping with one entry changed."""
    return [{**held, **change} if held["id"] == id_ else held for held in _apar()]


def _superseded(id_: str, entries: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """The mapping plus a correction reading the entry's quote as descriptive."""
    held = _apar() if entries is None else entries
    old = next(item for item in held if item["id"] == id_)
    fix = {**old, "id": f"{id_}-fix", "supersedes": id_, "reading": "DESCRIPTIVE"}
    return [*held, fix]


def _submit(pilot: Pilot, version: int) -> None:
    """The draft goes to review."""
    with pilot.pg_db.runtime_pool() as pool:
        lifecycle.submit(pool, version, **pilot.sources())


def _run_approved(pilot: Pilot, *quarters: str) -> dict[str, Any]:
    """The quarters run and approved in order; each result by quarter."""
    results = {}
    for quarter in quarters:
        results[quarter] = pilot.run(quarter)
        pilot.approve(results[quarter].draft_version_id)
    return results


def _score(monkeypatch: pytest.MonkeyPatch, pilot: Pilot) -> None:
    """Apar's FY26_Q2 cables quote scored against FY25 in real runs: the two seams C-8 forces (a
    registered measure, the window rule reading FY25 for one quote), and a file declaring it."""
    cred = cred_module()
    measure = cred.Actual(
        numerator=REVENUE,
        better=cred.Better.HIGHER,
        unit="%",
        currency=None,
        definition="cables_revenue_growth",
        interim=False,
    )
    monkeypatch.setitem(cred.ACTUALS, ("cables_revenue_growth", "consolidated"), measure)
    quote = next(held["quote"] for held in _apar() if held["id"] == SCORED)
    real = cred.derive_window

    def selective(text: str, *args: Any) -> str:
        return "FY25" if text == quote else real(text, *args)

    monkeypatch.setattr(cred, "derive_window", selective)
    _use(monkeypatch, pilot, _edited(SCORED, window="FY25"))


def _seed_fy25(pilot: Pilot, now: str = "1100000000", then: str = "1000000000") -> tuple[int, int]:
    """Annual FY25 and FY24 revenue on the YoY capture, which holds neither."""
    pilot.registered("FY26_Q2")
    return seed(pilot, FY25_Q2, FY25, now), seed(pilot, FY25_Q2, FY24, then)


def _measure(numerator: str, definition: str, *, interim: bool = True) -> Any:
    """A registered percentage growth measure."""
    cred = cred_module()
    return cred.Actual(
        numerator=numerator,
        better=cred.Better.HIGHER,
        unit="%",
        currency=None,
        definition=definition,
        interim=interim,
    )


def _stated(
    metric: str, window: str, scope: str, page: int = 1
) -> tuple[NumericClaim, dict[str, Any]]:
    """A statement of ten percent for the window, and its entry."""
    held = claim(metric, scope=scope, quote=f"growth of 10% in {window}", page=page)
    return held, entry(f"{metric}-{scope}-{window}", held, window)


# PILOT-4 ----------------------------------------------------------------------------------------


def check_credibility(pilot: Pilot, version_ids: Mapping[str, int]) -> None:
    """PILOT-4's credibility checks on each quarter's version. Apar's quotes name no single year,
    so the record is events and reasons only: any outcome or ``cred.*`` here is a false verdict."""
    gt, cred = gt_module(), cred_module()
    mapping = gt.load_targets("APARINDS")
    for quarter, version_id in version_ids.items():
        version = pilot.version(version_id)
        keys = [section.section_key for section in version.sections]
        assert keys[keys.index(PROBE_SECTION) + 1] == SECTION, f"PILOT-4: {quarter} {keys}"
        claims = {held.claim_key: held for held in version.claims}
        guidance = [held for held in version.claims if held.section_key == GUIDANCE]
        assert all(held.claim_key.startswith("ledger.") for held in guidance), quarter
        section = [held for held in version.claims if held.section_key == SECTION]
        assert not [key for key in claims if key.startswith("cred.")], f"PILOT-4: {quarter} cred"
        want = {
            f"episode.{name}.{role}"
            for name in EPISODES[quarter]
            for role in ("original", "latest")
        }
        assert {held.claim_key for held in section} == want, f"PILOT-4: {quarter} episodes"
        body = next(s.body for s in version.sections if s.section_key == SECTION)
        lines = record_lines(body)
        due = {
            id_ for id_, (at, _) in EVENTS.items() if QUARTERS.index(at) <= QUARTERS.index(quarter)
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
        _check_endpoints(pilot, quarter, version, claims)
        states = set(dict(pilot.validate(version_id).claim_states).values())
        assert states == {ClaimState.MATCH}, f"PILOT-4: {quarter} claim check {states}"


def _check_endpoints(
    pilot: Pilot, quarter: str, version: VersionDraft, claims: dict[str, NumericClaim]
) -> None:
    """``.original`` never moves across the chain; ``.latest`` moves only on a restatement, and
    then it is that quarter's guidance claim."""
    previous = run_draft._predecessor(quarter)
    with pilot.pg_db.runtime_pool() as pool, pool.connection() as conn:
        head = run_draft._head(conn.cursor(), pilot.entity_id, previous)
    if head is None:
        return
    before = {held.claim_key: held for held in pilot.version(head).claims}
    guidance = [held for held in version.claims if held.section_key == GUIDANCE]
    for name in EPISODES[previous] if previous in EPISODES else ():
        original, latest = f"episode.{name}.original", f"episode.{name}.latest"
        assert claims[original] == before[original], f"PILOT-4: {quarter} {name} original moved"
        moved = claims[latest] != before[latest]
        assert moved is (name in LATEST_MOVES.get(quarter, ())), f"PILOT-4: {quarter} {name}"
        if moved:
            assert any(same_statement(claims[latest], held) for held in guidance), quarter


# Actuals ----------------------------------------------------------------------------------------


def test_filed_actuals_on_retained_statements(pilot: Pilot) -> None:
    """A verdict's actual is Apar's real filed growth, cited. Half-year FY26 on the FY26_Q2 run
    (interim) and annual FY26 on the FY26_Q4 run equal independently computed constants, exactly and
    at six cut digits, and each resolves ``MATCH``; another formula or window could not."""
    cred = cred_module()
    held, mapped = _stated("revenue_growth", "FY26", "consolidated")
    measures = registry()
    runs = _run_approved(pilot, "FY26_Q2", "FY26_Q3", "FY26_Q4")
    key = "cred.revenue_growth.consolidated.FY26"
    for quarter, want_key, exact, digits, outcome in (
        ("FY26_Q2", f"{key}.ytd", H1_GROWTH, H1_DIGITS, "ON_TRACK"),
        ("FY26_Q4", key, ANNUAL_GROWTH, ANNUAL_DIGITS, "ACHIEVED"),
    ):
        inputs, section = direct(
            pilot, runs[quarter].update, (held,), (mapped,), measures, period=quarter
        )
        (actual,) = inputs.actuals
        assert actual.claim_key == want_key and inputs.exact[want_key] == exact
        assert str(actual.value) == digits and actual.precision == cred.EXACT_PLACES
        assert citation_state(pilot, actual) is ClaimState.MATCH
        (stored,) = pilot.query(
            "SELECT count(*) FROM eqos.calculation_traces WHERE id = %s AND formula_id = %s",
            actual.citation.calculation_trace_id,
            "run.change_pct",
        )
        assert stored == (1,)
        assert outcomes(row(section.body, "revenue_growth.consolidated.FY26")) == [outcome]


def test_a_carried_actual_keeps_its_citation_and_captures(
    pilot: Pilot, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The next quarter's package does not hold the capture behind a carried actual, so its blobs
    must be admitted, or the figure's evidence is outside what the version pinned."""
    _score(monkeypatch, pilot)
    _seed_fy25(pilot)
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
    assert set(dict(pilot.validate(second).claim_states).values()) == {ClaimState.MATCH}


@pytest.mark.parametrize("change", ["edit", "delete"])
def test_a_changed_entry_refuses_before_any_write(
    pilot: Pilot, monkeypatch: pytest.MonkeyPatch, change: str
) -> None:
    """A10: a sealed version was judged on this entry. Editing or deleting it would rewrite that
    history unseen, so the next quarter refuses, names it and writes nothing."""
    gt_module()
    _use(monkeypatch, pilot, _apar())
    _run_approved(pilot, "FY26_Q2")
    pilot.registered("FY26_Q3")
    before = all_counts(pilot)
    held = (
        _edited(SCORED, definition="edited")
        if change == "edit"
        else [item for item in _apar() if item["id"] != SCORED]
    )
    _use(monkeypatch, pilot, held)
    with pytest.raises(RunDraftError, match=SCORED):
        pilot.run("FY26_Q3")
    assert all_counts(pilot) == before


def _invalid(fault: str) -> list[dict[str, Any]]:
    """A file whose new entry fails its first use; each loads, so ``prepare`` is what refuses."""
    if fault == "quote-differs":
        return _edited(SCORED, quote=next(e["quote"] for e in _apar() if e["id"] == SCORED) + " or")
    if fault == "window-fails-first-use":
        return _edited(SCORED, window="FY26")
    later = next(e for e in _apar() if e["id"] == "conductor-ebitda-FY26_Q4")
    absent = {k: v for k, v in later.items() if k != "same_as"}
    absent |= {"id": ABSENT, "anchor": "p1.b1.0:1"}
    return [absent, *_edited("conductor-ebitda-FY26_Q2", same_as=ABSENT)]


@pytest.mark.parametrize("fault", ["quote-differs", "window-fails-first-use", "link-to-absent"])
def test_a_new_invalid_entry_refuses_before_upstream_writes(
    pilot: Pilot, monkeypatch: pytest.MonkeyPatch, fault: str
) -> None:
    """F1: a run is refused before its first write. The same run on a valid file then adds traces
    and facts, which proves the refused run had writes to make and made none."""
    gt_module()
    pilot.registered("FY26_Q2")
    before = all_counts(pilot)
    _use(monkeypatch, pilot, _invalid(fault))
    with pytest.raises(RunDraftError, match=ABSENT if fault == "link-to-absent" else SCORED):
        pilot.run("FY26_Q2")
    assert all_counts(pilot) == before
    _use(monkeypatch, pilot, _apar())
    pilot.run("FY26_Q2")
    after = all_counts(pilot)
    assert after["calculation_traces"] > before["calculation_traces"]
    assert after["fact_admissions"] > before["fact_admissions"]


def test_a_prior_episodes_ineligible_capture_refuses_before_upstream_writes(pilot: Pilot) -> None:
    """F1's fourth case, on the real manifest route: a carried statement's transcript published
    after the run's cutoff fails ``check_blobs``. Today that refuses only after upstream writes, so
    an empty delta proves the check moved first; nothing here touches the call order."""
    gt_module()
    _run_approved(pilot, "FY26_Q2")
    context, argv = pilot.registered("FY26_Q3")
    before = all_counts(pilot)
    manifest = json.loads(APAR_MANIFEST.read_text("utf-8"))
    blob = next(e["source_sha256"] for e in _apar() if e["id"] == SCORED)
    (late,) = [item for item in manifest["entries"] if item["sha256"] == blob]
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


def test_an_ended_target_reads_its_operands_from_the_qoq_capture(pilot: Pilot) -> None:
    """F5: a target first mapped after its year ended has its figures on an earlier filing. Every
    admitted capture is searched, so a filed figure does not read "not yet filed", and two captures
    that disagree are not silently resolved. Each row is a separate metric on one chain's run."""
    _run_approved(pilot, "FY26_Q2", "FY26_Q3", "FY26_Q4")
    own, qoq = _capture_blobs(pilot, "FY27_Q1")
    assert qoq == FY26_Q4
    alone = {"basis": Basis.STANDALONE}
    only_qoq = {
        seed(pilot, qoq, FY26, "1100", **alone),
        seed(pilot, qoq, FY25, "1000", **alone),
    }
    same = "profit_before_tax"
    own_now = seed(pilot, own, FY26, "1200", canonical=same, **alone)
    own_then = seed(pilot, own, FY25, "1000", canonical=same, **alone)
    seed(pilot, qoq, FY26, "1200", canonical=same, **alone)
    seed(pilot, qoq, FY25, "1000", canonical=same, **alone)
    differ = "profit_for_period"
    differing = {
        seed(pilot, own, FY26, "1300", canonical=differ, **alone),
        seed(pilot, qoq, FY26, "1350", canonical=differ, **alone),
        seed(pilot, own, FY25, "1000", canonical=differ, **alone),
    }
    update = pilot.run("FY27_Q1").update
    names = {"m_qoq": REVENUE, "m_same": same, "m_differ": differ, "m_none": "cfo"}
    stated = [_stated(name, "FY26", "standalone", page) for page, name in enumerate(names, 1)]
    measures = {(name, "standalone"): _measure(num, name) for name, num in names.items()}
    inputs, section = direct(
        pilot,
        update,
        tuple(held for held, _ in stated),
        tuple(mapped for _, mapped in stated),
        measures,
        period="FY27_Q1",
    )
    found = {held.claim_key: held for held in inputs.actuals}
    assert set(found) == {f"cred.{n}.standalone.FY26" for n in ("m_qoq", "m_same")}
    held = found["cred.m_qoq.standalone.FY26"]
    assert operand_ids(pilot, held) == only_qoq and citation_state(pilot, held) is ClaimState.MATCH
    assert inputs.exact[held.claim_key] == Fraction(10)
    assert operand_ids(pilot, found["cred.m_same.standalone.FY26"]) == {own_now, own_then}
    assert traces_reading(pilot, *differing) == 0
    assert "filed value differs across admitted captures" in row(
        section.body, "m_differ.standalone"
    )
    assert "actual not yet filed" in row(section.body, "m_none.standalone")
    assert "actual not yet filed" not in row(section.body, "m_qoq.standalone")


def _capture_blobs(pilot: Pilot, quarter: str) -> tuple[str, str]:
    """The quarter's own and QoQ XBRL blobs, from its approved config."""
    _, argv = pilot.registered(quarter)
    config = yaml.safe_load(Path(argv[argv.index("--config") + 1]).read_text("utf-8"))
    own, qoq = config["xbrl"], config["comparators"]["qoq"]
    own_sha, qoq_sha = (
        hashlib.sha256(Path(held["local_path"]).read_bytes()).hexdigest() for held in (own, qoq)
    )
    return own_sha, qoq_sha


def test_a_future_target_binds_no_interim_actual(pilot: Pilot) -> None:
    """F2: FY27's target at an FY26 run has not begun. Figures labelled for FY27's months must not
    produce a verdict or even a stored trace before its first quarter."""
    pilot.registered("FY26_Q2")
    alone = {"basis": Basis.STANDALONE}
    seeded = (
        seed(pilot, FY26_Q2, (date(2026, 4, 1), date(2026, 9, 30)), "110", **alone),
        seed(pilot, FY26_Q2, H1_26, "100", **alone),
    )
    update = pilot.run("FY26_Q2").update
    held, mapped = _stated("revenue_growth", "FY27", "standalone")
    before = trace_count(pilot)
    inputs, section = direct(
        pilot, update, (held,), (mapped,), registry("standalone"), period="FY26_Q2"
    )
    assert inputs.actuals == () and inputs.exact == {} and trace_count(pilot) == before
    assert traces_reading(pilot, *seeded) == 0
    line = row(section.body, "revenue_growth.standalone.FY27")
    assert set(outcomes(line)) == {"UNRESOLVED"} and "not due: target year not started" in line


# Rework and pins --------------------------------------------------------------------------------


@pytest.mark.parametrize("rejected", ["episode", "actual"])
def test_a_rejected_episode_claim_routes_to_a_mapping_correction(
    pilot: Pilot, monkeypatch: pytest.MonkeyPatch, rejected: str
) -> None:
    """A rework reruns lines, but an episode claim comes from the mapping: an ordinary rerun could
    never change it. The refusal names the real route and holds even with the correction in the
    file, because only ``--full-successor`` rebuilds; it must not send the reader to the thesis."""
    gt_module()
    _score(monkeypatch, pilot)
    _seed_fy25(pilot)
    version = pilot.run("FY26_Q2").draft_version_id
    _submit(pilot, version)
    key = {
        "episode": "episode.cables_revenue_growth.consolidated.FY25.original",
        "actual": SCORED_KEY,
    }[rejected]
    _request_changes(pilot, version, key)
    before = all_counts(pilot)
    for attempt in (None, _superseded(SCORED, _edited(SCORED, window="FY25"))):
        if attempt:
            _use(monkeypatch, pilot, attempt)
        with pytest.raises(RunDraftError, match=ROUTE) as refused:
            _rerun(pilot)
        assert "thesis" not in str(refused.value).lower()
        assert all_counts(pilot) == before
    _rerun(pilot, "--full-successor")
    body = next(
        s.body
        for s in pilot.version(_successor(pilot, version)).sections
        if s.section_key == SECTION
    )
    assert f"{SCORED}-fix" in body
    assert record_lines(body)[f"{SCORED}-fix"]["event"] == "DESCRIBED"
    if rejected == "episode":
        assert "mapping corrected" in row(body, "cables_revenue_growth.consolidated.FY25")


@pytest.mark.parametrize("head", ["rejected", "approved"])
def test_a_same_quarter_rerun_holds_that_quarters_pins(
    pilot: Pilot, monkeypatch: pytest.MonkeyPatch, head: str
) -> None:
    """R1: the bootstrap quarter has no previous-quarter head, so only its own head remembers the
    pins. Otherwise an edit just before a rerun would rewrite the version it replaces. A stale view
    of that head refuses under lock, so no rerun overwrites a head it did not read."""
    gt_module()
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
    for held in (
        _edited(SCORED, definition="edited"),
        [item for item in _apar() if item["id"] != SCORED],
    ):
        _use(monkeypatch, pilot, held)
        with pytest.raises(RunDraftError, match=SCORED):
            _rerun(pilot, *flags)
        assert all_counts(pilot) == before
    _use(monkeypatch, pilot, _apar())
    real, wrote = cli.preflight, []
    write = cli.write_run_draft

    def spy(*args: Any, **kwargs: Any) -> Any:
        wrote.append(args)
        return write(*args, **kwargs)

    monkeypatch.setattr(cli, "write_run_draft", spy)
    for stale in ({"same_period_digest": "0" * 64}, {"same_period_id": None}):
        monkeypatch.setattr(
            cli, "preflight", lambda *a, _s=stale, **k: real(*a, **k).model_copy(update=_s)
        )
        count, seen = version_count(pilot), len(wrote)
        with pytest.raises(RunDraftError):
            _rerun(pilot, *flags)
        assert len(wrote) == seen + 1, "the refusal must come from the lock's recheck"
        assert version_count(pilot) == count
    monkeypatch.setattr(cli, "preflight", real)
    _use(monkeypatch, pilot, _superseded(SCORED))
    new = _rerun(pilot, *flags).draft_version_id
    body = next(s.body for s in pilot.version(new).sections if s.section_key == SECTION)
    assert f"{SCORED}-fix" in body and "mapping corrected" in row(body, GROWTH_Q2)


# The figures ------------------------------------------------------------------------------------


def test_standalone_and_consolidated_bind_their_own_statements(pilot: Pilot) -> None:
    """A7, R9: a standalone promise judged on consolidated figures is false. On one capture
    each scope's claim holds its own basis, operands and independently computed value."""
    pilot.registered("FY26_Q2")
    alone = {"basis": Basis.STANDALONE}
    operands = {
        seed(pilot, FY26_Q2, H1_26, "5000000000", **alone),
        seed(pilot, FY26_Q2, H1_25, "4000000000", **alone),
    }
    update = pilot.run("FY26_Q2").update
    one, first = _stated("revenue_growth", "FY26", "consolidated", 1)
    other, second = _stated("revenue_growth", "FY26", "standalone", 2)
    inputs, _ = direct(
        pilot,
        update,
        (one, other),
        (first, second),
        registry("consolidated", "standalone"),
        period="FY26_Q2",
    )
    found = {held.claim_key: held for held in inputs.actuals}
    con = found["cred.revenue_growth.consolidated.FY26.ytd"]
    sta = found["cred.revenue_growth.standalone.FY26.ytd"]
    assert inputs.exact[con.claim_key] == H1_GROWTH and str(con.value) == H1_DIGITS
    assert inputs.exact[sta.claim_key] == Fraction(25) and str(sta.value) == "25.000000"
    assert con.measurement_key.basis is Basis.CONSOLIDATED
    assert sta.measurement_key.basis is Basis.STANDALONE
    assert operand_ids(pilot, sta) == operands and not operand_ids(pilot, con) & operands


@pytest.mark.parametrize(
    ("now", "then", "exact", "digits", "whole", "outcome"),
    [
        ("109495", "100000", Fraction("9.495"), "9.495000", True, "MISSED"),
        ("400", "300", Fraction(100, 3), "33.333333", False, "ACHIEVED"),
    ],
    ids=["binding-tolerance", "non-terminating"],
)
def test_a_verdict_reads_the_exact_trace_value(
    pilot: Pilot, now: str, then: str, exact: Fraction, digits: str, whole: bool, outcome: str
) -> None:
    """R5, OD-7: the trace stores 9.50, which rounds to ten and would pass; the exact 9.495 misses.
    The claim holds the cut digits and the check enforces them, so neither the stored rounding nor
    a typed-over figure can stand in, in the binding run or one carrying the claim."""
    cred = cred_module()
    pilot.registered("FY26_Q2")
    alone = {"basis": Basis.STANDALONE}
    seed(pilot, FY26_Q2, FY25, now, **alone)
    seed(pilot, FY26_Q2, FY24, then, **alone)
    update = pilot.run("FY26_Q2").update
    held, mapped = _stated("revenue_growth", "FY25", "standalone")
    measures = registry("standalone")
    inputs, section = direct(pilot, update, (held,), (mapped,), measures, period="FY26_Q2")
    (actual,) = inputs.actuals
    assert inputs.exact[actual.claim_key] == exact and str(actual.value) == digits
    episode, phrase = (
        "revenue_growth.standalone.FY25",
        cred.ACTUAL_WHOLE if whole else cred.ACTUAL_CUT,
    )
    line = row(section.body, episode)
    assert outcomes(line) == [outcome] and phrase in line
    assert f"{{{{c:{actual.claim_key}|ref}}}}" in line
    assert f"{digits}%" in render_section(line, (*section.claims, actual))
    assert citation_state(pilot, actual) is ClaimState.MATCH
    typed = actual.model_copy(update={"value": Decimal("9.500000")})
    bare = actual.model_copy(update={"qualifiers": ()})
    assert citation_state(pilot, typed) is ClaimState.VALUE_MISMATCH
    assert citation_state(pilot, bare) is ClaimState.VALUE_MISMATCH
    count = trace_count(pilot)
    carried, again = direct(
        pilot, update, (held,), (mapped,), measures, period="FY26_Q2", prior_actuals=(actual,)
    )
    assert carried.actuals == (actual,) and trace_count(pilot) == count
    assert carried.exact[actual.claim_key] == exact
    assert outcomes(row(again.body, episode)) == [outcome]


@pytest.mark.parametrize(
    ("comparator", "interval"),
    [
        ("0", None),
        ("-100", None),
        ("100", Interval(lower=Fraction(-5), upper=Fraction(205))),
    ],
    ids=["zero", "negative", "interval-crosses-zero"],
)
def test_an_undefined_comparator_is_a_row_reason(
    pilot: Pilot, monkeypatch: pytest.MonkeyPatch, comparator: str, interval: Interval | None
) -> None:
    """P11: growth on a non-positive base has no meaning, and one whose uncertainty reaches zero has
    no bound. Either is a stated reason in a written report, not a figure and not a failed run."""
    _score(monkeypatch, pilot)
    pilot.registered("FY26_Q2")
    now = seed(pilot, FY25_Q2, FY25, "1100")
    then = seed(pilot, FY25_Q2, FY24, comparator, interval=interval)
    version = pilot.run("FY26_Q2").draft_version_id
    claims = pilot.version(version)
    assert SCORED_KEY not in {held.claim_key for held in claims.claims}
    assert traces_reading(pilot, now, then) == 0
    body = next(s.body for s in claims.sections if s.section_key == SECTION)
    line = row(body, "cables_revenue_growth.consolidated.FY25")
    assert "comparator revenue not positive or its uncertainty reaches zero" in line
    assert set(outcomes(line)) == {"UNRESOLVED"}


def test_two_mapped_interpretations_of_one_key_still_raise(
    pilot: Pilot, monkeypatch: pytest.MonkeyPatch
) -> None:
    """P11's boundary: two values of one key on one capture are a store fault, not a row reason, and
    must refuse rather than pick one."""
    _score(monkeypatch, pilot)
    _seed_fy25(pilot)
    seed(pilot, FY25_Q2, FY24, "1000000001", salt="second")
    count = version_count(pilot)
    with pytest.raises(RunDraftError, match="no single mapped interpretation"):
        pilot.run("FY26_Q2")
    assert version_count(pilot) == count
