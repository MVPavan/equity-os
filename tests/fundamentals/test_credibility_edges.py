"""Plan-required credibility refusals and reasons the sealed tests reach no other way (S2)."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import yaml
from credibility_support import (
    chain,
    claim,
    cred_module,
    entry,
    gt_module,
    outcomes,
    prepared,
    registry,
    row,
    unresolved,
    write_targets,
)
from evidence_support import ingest, policy
from prep2b_support import Pilot
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
from fundamentals.contracts.role import FactRole
from fundamentals.extract.xbrl_parser import FactSelectionError
from fundamentals.ledger.run_traces import RunDraftError

__all__ = ["dictionary", "ingest", "mapping_set", "pilot", "policy"]


def _bound_open_window(root: Path, measures: Any) -> Any:
    """``bind_credibility`` of an FY28 target whose window is open at February 29."""
    cred = cred_module()
    held = claim(quote="growth of 10% in FY28")
    prep = cred.prepare(
        (held,),
        cred.Record(),
        cred.Record(),
        write_targets(root, entry("A", held, "FY28")),
        period="FY28_Q4",
        period_end=date(2028, 2, 29),
        month=3,
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
