"""Plan-required credibility refusals and reasons the sealed tests reach no other way (S2)."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import yaml
from credibility_support import (
    built,
    chain,
    claim,
    cred_module,
    direction,
    entry,
    finish,
    gt_module,
    outcomes,
    prepared,
    registry,
    row,
    unresolved,
    write_targets,
)
from evidence_support import ingest, policy
from ledger_cited_support import OPERAND, Cited, cited
from pg_evidence_schema_support import _insert, _trace
from prep2b_support import Pilot
from test_credibility import stated
from test_credibility_binding import (
    FY24,
    FY25,
    FY25_Q2,
    SCORED_EPISODE,
    SCORED_KEY,
    _edited,
    _score,
    _use,
    all_counts,
    seed,
)
from test_prep2b_run_draft import dictionary, mapping_set, pilot

from fundamentals.api import run_comparatives
from fundamentals.contracts.evidence import RunMode
from fundamentals.contracts.ledger import Citation, CitationKind, ClaimState
from fundamentals.contracts.role import FactRole
from fundamentals.extract.xbrl_parser import FactSelectionError
from fundamentals.ledger.claim_check import check_claim
from fundamentals.ledger.display import EXACT_DIGITS
from fundamentals.ledger.run_traces import RunDraftError
from fundamentals.pg.settings import PgRole

__all__ = ["cited", "dictionary", "ingest", "mapping_set", "pilot", "policy"]


def _bound_open_window(root: Path, measures: Any) -> Any:
    """``bind_credibility`` of an FY28 target whose window is open at February 29."""
    cred = cred_module()
    held = claim(quote="growth of 10% in FY28")
    prep = cred.prepare(
        (held,),
        cred.Record(),
        cred.Record(),
        write_targets(root, entry("A", held, "FY28")),
        period="FY28_Q3",
        period_end=date(2028, 2, 29),
        month=5,
        filed_at={},
        actual_blobs=frozenset(),
    )
    update = SimpleNamespace(
        period_start="2027-12-01",
        period_end="2028-02-29",
        facts=[SimpleNamespace(role=FactRole.PROFIT_BEFORE_TAX, sources=[None])],
        comparatives=[],
    )
    versions = SimpleNamespace(dictionary="", mapping_set="", normalisation_policy="")
    return cred.bind_credibility(
        None, update, prep, (), entity_id=1, versions=versions, registry=measures
    )


def test_a_leap_day_period_end_has_no_comparator_window(tmp_path: Path) -> None:
    """Task 2: February 29 has no day a year earlier, so an open window states that, unscored."""
    built = _bound_open_window(tmp_path, registry())
    reason = "a leap day has no comparator"
    assert built.unavailable == {"cred.revenue_growth.consolidated.FY28.ytd": reason}
    unresolved(row(built.body, "revenue_growth.consolidated.FY28"), reason)


@pytest.mark.parametrize(
    ("measures", "reason"),
    [({}, "no filed measure"), (registry(interim=False), "no interim rule")],
    ids=["unregistered", "no-interim-rule"],
)
def test_a_window_without_a_usable_measure_binds_nothing(
    tmp_path: Path, measures: Any, reason: str
) -> None:
    """P7, Task 3: only a registered measure with a rule for this window may compute an actual."""
    built = _bound_open_window(tmp_path, measures)
    assert built.actuals == () and built.exact == {} and built.unavailable == {}
    unresolved(row(built.body, "revenue_growth.consolidated.FY28"), reason)


def test_a_retired_line_outside_its_block_refuses(tmp_path: Path) -> None:
    """Task 2: a retired line above the header could carry a pin the block never checks."""
    a = claim(page=1)
    b = claim(low="12", page=2, quote="growth of 12% in FY26")
    section = chain(a, b, write_targets(tmp_path, entry("A", a), entry("B", b)))
    stray = f"- retired Z sha256 {'0' * 64} successor A\n"
    body = section.body.replace(
        "{{e:computed}} Retired entries:", stray + "{{e:computed}} Retired entries:"
    )
    with pytest.raises(RunDraftError, match="does not parse"):
        cred_module().read_record(body, section.claims)


@pytest.mark.parametrize(
    "text",
    ["", "{}", "entries: null", "entries: [bad]", "entries: [{id: A}]", "entries: [", "- a"],
    ids=["empty", "no-entries", "null", "not-a-mapping", "missing-fields", "not-yaml", "a-list"],
)
def test_a_malformed_mapping_file_is_a_refusal(tmp_path: Path, text: str) -> None:
    """Task 1: any malformed file is the run's named refusal, not a crash of another class."""
    path = tmp_path / "config" / "guidance_targets" / "test.yaml"
    path.parent.mkdir(parents=True)
    path.write_text(text, "utf-8")
    with pytest.raises(RunDraftError, match="guidance targets of TEST"):
        gt_module().load_targets("TEST", tmp_path)


def test_a_definition_cannot_carry_section_markup(tmp_path: Path) -> None:
    """P12: a correction line shows the definition, so a placeholder there reaches validation."""
    with pytest.raises(RunDraftError, match="definition"):
        write_targets(tmp_path, entry("A", claim(), definition="{{c:ghost|ref}}"))


def test_a_correction_the_scanner_would_refuse_is_refused_in_prepare(tmp_path: Path) -> None:
    """P12: a stray digit in a correction's definition must refuse before ``AS_KNOWN``."""
    held = claim()
    first = write_targets(tmp_path, entry("A", held))
    prior = cred_module().build(
        prepared((held,), first, "FY26_Q2"), actuals=(), exact={}, unavailable={}
    )
    fixed = entry("B", held, supersedes="A", definition="growth 2")
    mapping = write_targets(tmp_path, entry("A", held), fixed)
    with pytest.raises(RunDraftError, match="UNREGISTERED_NUMBER"):
        prepared((), mapping, "FY26_Q3", prior)


@pytest.mark.pg
@pytest.mark.retained
def test_a_scanner_invalid_mapping_refuses_with_every_table_unchanged(
    pilot: Pilot, monkeypatch: pytest.MonkeyPatch
) -> None:
    """P12: an id the section scanner refuses is found before traces, probes or facts persist; only
    the version would have rolled back at ``AS_KNOWN``."""
    pilot.registered("FY26_Q2")
    before = all_counts(pilot)
    _use(monkeypatch, pilot, _edited("cables-growth-FY26_Q2", id="growth-v2"))
    with pytest.raises(RunDraftError, match="UNREGISTERED_NUMBER"):
        pilot.run("FY26_Q2")
    assert all_counts(pilot) == before


@pytest.mark.pg
@pytest.mark.retained
@pytest.mark.parametrize(
    ("other_capture", "want"),
    [(None, "MISSED"), ("1200000000", "filed value differs across admitted captures")],
    ids=["annual-operands-found", "disagreement-refused"],
)
def test_a_comparator_no_comparison_could_use_is_still_searched(
    pilot: Pilot, monkeypatch: pytest.MonkeyPatch, other_capture: str | None, want: str
) -> None:
    """A declared QoQ XBRL is admitted though selection failed for its every comparison: its annual
    operands score the row, and its disagreement with another capture blocks a verdict."""
    _score(monkeypatch, pilot)
    _, argv = pilot.registered("FY26_Q2")
    config = yaml.safe_load(Path(argv[argv.index("--config") + 1]).read_text("utf-8"))
    qoq = config["comparators"]["qoq"]["sha256"]
    seed(pilot, qoq, FY25, "1100000000")
    seed(pilot, qoq, FY24, "1000000000")
    if other_capture:
        seed(pilot, FY25_Q2, FY25, other_capture)
        seed(pilot, FY25_Q2, FY24, "1000000000")
    select = run_comparatives._select_prior

    def unusable(observations: Any, concept: str, instance: Any) -> Any:
        if instance.sha256 == qoq:
            raise FactSelectionError("synthetic")
        return select(observations, concept, instance)

    monkeypatch.setattr(run_comparatives, "_select_prior", unusable)
    result = pilot.run("FY26_Q2")
    assert all(item.qoq.prior_source is None for item in result.update.comparatives)
    version = pilot.version(result.draft_version_id)
    body = next(s.body for s in version.sections if s.section_key == "management_credibility")
    line = row(body, SCORED_EPISODE)
    keys = {held.claim_key for held in version.claims}
    if other_capture:
        assert want in line and SCORED_KEY not in keys
    else:
        assert outcomes(line) == [want] and SCORED_KEY in keys


@pytest.mark.pg
@pytest.mark.retained
@pytest.mark.parametrize(
    ("value", "state"),
    [("1", ClaimState.MATCH), ("10000000", ClaimState.VALUE_MISMATCH)],
    ids=["one-crore", "the-rupee-figure-called-crore"],
)
def test_exact_digits_are_read_in_the_claims_scale(
    cited: Cited, value: str, state: ClaimState
) -> None:
    """P4, r5 (C1): a trace of 10,000,000 INR supports one crore; the same digits in crore inflate
    it ten-million-fold, and the exact-digit path shares the validator with every currency claim."""
    figure = dict.fromkeys(("value", "lower", "upper"), Decimal(10_000_000))
    exact = dict.fromkeys(("exact_value", "exact_lower", "exact_upper"), "10000000")
    digest = {"key_digest": cited.cell_key.digest()}
    with cited.pools[PgRole.RUNTIME].connection() as conn, conn.transaction():
        trace = _insert(conn, "calculation_traces", _trace("f" * 64) | figure | exact | digest)
        operand = {"calculation_trace_id": trace, "interpretation_id": cited.ids["selected"]}
        _insert(conn, "calculation_trace_operands", OPERAND | operand)
    update = {
        "citation": Citation(kind=CitationKind.CALCULATION, calculation_trace_id=trace),
        "qualifiers": (EXACT_DIGITS,),
        "value": Decimal(value),
        "precision": 6,
    }
    held = cited.first_party_trace().model_copy(update=update)
    at = datetime.now(UTC)
    assert (
        check_claim(held, cited.resolve(held), mode=RunMode.AS_KNOWN, cutoff=at, imported=False)
        is state
    )


@pytest.mark.parametrize(
    ("text", "want"),
    [
        ("growth of 10% this year and next year", "MULTI_YEAR"),
        ("growth of 10% next year and the current year", "MULTI_YEAR"),
        ("growth of 10% in FY26 and next year", "MULTI_YEAR"),
        ("growth of 10% in FY27 next year", "FY27"),
        ("growth of 10% this year, FY26", "FY26"),
    ],
)
def test_a_quote_naming_two_years_is_not_a_single_year_target(text: str, want: str) -> None:
    """P3, r5 (C2): one window scored for a promise over two would report it achieved on half."""
    filed = datetime(2026, 2, 4, tzinfo=UTC)  # during FY26
    assert gt_module().derive_window(text, filed, date(2025, 12, 31), 3) == want


def test_two_relative_years_refuse_a_single_year_mapping_and_stay_unresolved(
    tmp_path: Path,
) -> None:
    """P3, OD-5, r5 (C2): the two-year quote cannot be mapped to a year, and as ``MULTI_YEAR`` no
    actual reaches a verdict."""
    held = claim(quote="growth of 10% this year and next year")
    filed = {held.citation.source_sha256: datetime(2026, 2, 4, tzinfo=UTC)}
    with pytest.raises(RunDraftError, match="window FY27 where its words give MULTI_YEAR"):
        prepared((held,), write_targets(tmp_path, entry("A", held, "FY27")), "FY26_Q3", filed=filed)
    mapping = write_targets(tmp_path, entry("A", held, "MULTI_YEAR"))
    section = built((held,), mapping, "FY26_Q3", filed=filed, measures=registry())
    unresolved(row(section.body, "revenue_growth.consolidated.MULTI_YEAR"), "not single-year")


def _prepare(
    held: Any, record: Any, same: Any, mapping: Any, period: str, end: date, month: int
) -> Any:
    """``prepare`` of one quarter under the fiscal-year-end ``month``."""
    return cred_module().prepare(
        held,
        record,
        same,
        mapping,
        period=period,
        period_end=end,
        month=month,
        filed_at={},
        actual_blobs=frozenset(),
    )


@pytest.mark.parametrize("same_period", [False, True], ids=["carried", "same-period"])
def test_a_later_fiscal_calendar_cannot_reinterpret_a_sealed_promise(
    tmp_path: Path, same_period: bool
) -> None:
    """P7, r5 (C3): FY26 sealed on a March year would become an open December year, its annual
    result no longer governing and other year-to-date months sought, with every pin unchanged."""
    cred, held = cred_module(), claim()
    mapping = write_targets(tmp_path, entry("A", held))
    head = built((held,), mapping, "FY26_Q2")
    sealed, none = cred.read_record(head.body, head.claims), cred.Record()
    pair = (none, sealed) if same_period else (sealed, none)
    args = ((held,), *pair, mapping, "FY26_Q3", date(2025, 12, 31))
    with pytest.raises(RunDraftError, match="stated FY26_Q2: .*month 3, this run's 12"):
        _prepare(*args, 12)
    assert _prepare(*args, 3).month == 3


@pytest.mark.pg
@pytest.mark.retained
def test_an_effective_fiscal_setting_change_refuses_the_next_run_with_every_table_unchanged(
    pilot: Pilot,
) -> None:
    """P7, P12, r5 (C3): a setting valid from the next quarter must not reread what the sealed head
    promised. It refuses before the first write, under the month the real resolver supplies."""
    result = pilot.run("FY26_Q2")
    pilot.approve(result.draft_version_id)
    pilot.registered("FY26_Q3")
    with pilot.pg_db.runtime_pool() as pool, pool.connection() as conn:
        inserted = conn.execute(
            "INSERT INTO eqos.settings_records "
            "(entity_id, setting_key, value_text, evidence_input_id, valid_from) "
            "SELECT entity_id, setting_key, '12', evidence_input_id, %s FROM eqos.settings_records "
            "WHERE entity_id = %s AND setting_key = 'FISCAL_YEAR_END_MONTH' LIMIT 1",
            (date(2025, 10, 1), pilot.entity_id),
        )
        assert inserted.rowcount == 1
    before = all_counts(pilot)
    with pytest.raises(RunDraftError, match="stated FY26_Q2: .*month 3, this run's 12"):
        pilot.run("FY26_Q3")
    assert all_counts(pilot) == before


def test_a_label_its_calendar_cannot_give_is_refused_before_it_can_be_sealed(
    tmp_path: Path,
) -> None:
    """P7, r5 (C3): FY26_Q2 ending September fixes a March year. Sealed under December, that line
    would refuse December and pass a later March run, rereading the promise's fiscal window."""
    cred, held = cred_module(), claim()
    mapping = write_targets(tmp_path, entry("A", held))
    none = cred.Record()
    with pytest.raises(RunDraftError, match="FY26_Q2 ended 2025-09-30: .*month 3, this run's 12"):
        _prepare((held,), none, none, mapping, "FY26_Q2", date(2025, 9, 30), 12)
    first = finish(_prepare((held,), none, none, mapping, "FY25_Q3", date(2025, 9, 30), 12))
    sealed = cred.read_record(first.body, first.claims)
    with pytest.raises(RunDraftError, match="stated FY25_Q3: .*month 12, this run's 3"):
        _prepare((), sealed, none, mapping, "FY26_Q3", date(2025, 12, 31), 3)


def test_a_december_year_chain_carries_under_its_own_calendar(tmp_path: Path) -> None:
    """P7, r5 (C3): the refusal is a change of calendar, not a preference for March."""
    cred, held = cred_module(), claim()
    mapping = write_targets(tmp_path, entry("A", held))
    none = cred.Record()
    first = finish(_prepare((held,), none, none, mapping, "FY26_Q1", date(2026, 3, 31), 12))
    sealed = cred.read_record(first.body, first.claims)
    carried = _prepare((), sealed, none, mapping, "FY26_Q2", date(2026, 6, 30), 12)
    assert carried.windows == {("revenue_growth", "consolidated", "FY26"): cred.WindowState.OPEN}


@pytest.mark.parametrize(
    ("before", "after", "reason"),
    [
        ("20+", "20-22", "range narrowed"),
        ("20-22", "20+", "range widened"),
        ("20", "20+", "range widened"),
        ("20+", "20", "range narrowed"),
    ],
)
def test_moving_between_a_bounded_and_an_open_promise_is_a_revision(
    before: str, after: str, reason: str
) -> None:
    """P5, r5 (C4): equal floors do not make "20%-plus" and "20-22%" one promise. Up and down name
    the floor's move, so this has no direction, only the range's change."""
    revision, higher = cred_module().revision, direction("HIGHER")
    event = revision(stated(before), stated(after), higher)
    assert (event.kind.value, event.reason) == ("REVISED", reason)
    assert revision(stated(before), stated(before), higher).kind.value == "REAFFIRMED"
