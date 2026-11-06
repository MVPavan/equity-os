"""VENDOR-1 Task 9: a ``fundamentals run --compare-run <id>`` whose required facts are admitted
from the vendors, end to end through ``main`` (plan Task 9 cases (a), (b) and (c)).

Each case starts with no admissions for its comparison run. Apar FY26_Q2's revenue is
``VENDORS_AGREE`` within tolerance of the filed value (row 1); the withheld world of
``vendor_report_support`` makes all six roles row 3. Vendor readings are read from the retained
interpretations at runtime, never written here.
"""

from __future__ import annotations

import re
from typing import Any

import pytest
from evidence_support import CONFIG, XBRL_KIND, ingest, policy
from prep2b_support import Pilot
from vendor_report_support import (
    ELIGIBILITY,
    END,
    QUARTER,
    compare,
    report,
    vendor_pilot,
    witness_captures,
)

import equity_os.interface.entry.cli as cli
from equity_os.analysis.calculations.run_traces import RunDraftError
from equity_os.contracts.publication.ledger import DisplayStyle, NumericClaim
from equity_os.contracts.verification.vendor_first import LABEL_TEXT, AdmissionLabel
from equity_os.normalisation.dictionary.dictionary import CanonicalDictionary, load_dictionary
from equity_os.normalisation.mapping.mapping import MappingSet, load_mapping_set
from equity_os.publication.checking.claim_check import ClaimState
from equity_os.publication.drafting.display import render_claim
from equity_os.publication.drafting.earnings_update import REQUIRED_ROLES
from equity_os.publication.drafting.pnl_lines import TAX_LABEL
from equity_os.publication.drafting.run_draft import RUN_AUTHOR
from equity_os.verification.comparison import run_config

__all__ = ["ingest", "policy"]

pytestmark = [pytest.mark.pg, pytest.mark.retained]

ADMISSIONS = (
    "SELECT interpretation_id, witness_interpretation_id, label FROM eqos.fact_admissions "
    "WHERE run_id = %s ORDER BY id"
)
SELECTIONS = "SELECT count(*) FROM eqos.fact_selections"
VERSION = "SELECT max(id) FROM eqos.report_versions WHERE author = %s"
OPERANDS = "SELECT DISTINCT interpretation_id FROM eqos.calculation_trace_operands"
VALUE = "SELECT value FROM eqos.interpretations WHERE id = %s"
CRORE = 10**7
CHECKED, UNCHECKED = AdmissionLabel.CHECKED_AGAINST_FILING, AdmissionLabel.VENDORS_AGREE_NOT_CHECKED


@pytest.fixture(scope="module")
def dictionary() -> CanonicalDictionary:
    """Canonical dictionary v2."""
    return load_dictionary(CONFIG / "normalisation/dictionary", "v2")


@pytest.fixture(scope="module")
def mapping_set(dictionary: CanonicalDictionary) -> MappingSet:
    """Mapping set v9, the pilot comparison pin."""
    return load_mapping_set(CONFIG / "normalisation/mappings", "v9", dictionary=dictionary)


def _claims(pilot: Pilot) -> dict[str, NumericClaim]:
    """The latest run draft's claims by key."""
    ((version_id,),) = pilot.query(VERSION, RUN_AUTHOR)
    return {claim.claim_key: claim for claim in pilot.version(version_id).claims}


def _matched(pilot: Pilot) -> bool:
    """Whether every claim of the latest run draft matches on a runtime check."""
    ((version_id,),) = pilot.query(VERSION, RUN_AUTHOR)
    return set(dict(pilot.validate(version_id).claim_states).values()) == {ClaimState.MATCH}


def test_row_one_vendor_value_drafts_checked(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> None:
    """(c) a tampered vendor extractor refuses at static validation, admitting nothing; (a) the
    row-1 revenue drafts at the chosen vendor interpretation's value, labelled "checked against
    filing", its calculations computed from the admitted value; a pipeline failure after
    selection, rerun, selects nothing twice."""
    pilot = vendor_pilot(request, monkeypatch)
    run_id = compare(pilot)
    tampered = dict(run_config.VENDOR_EXTRACTORS)
    version, files = tampered["tijori"]
    tampered["tijori"] = (f"{version}-tampered", files)
    with monkeypatch.context() as patched:
        patched.setattr(run_config, "VENDOR_EXTRACTORS", tampered)
        with pytest.raises(RunDraftError, match=f"comparison run {run_id}: "):
            report(pilot, run_id)
    assert pilot.query(ADMISSIONS, run_id) == []

    def failed(*_: Any, **__: Any) -> int:
        raise RunDraftError("test: the pipeline failed after selection")

    with monkeypatch.context() as patched:
        patched.setattr(cli, "write_run_draft", failed)
        with pytest.raises(RunDraftError, match="after selection"):
            report(pilot, run_id)
    selected = pilot.query(SELECTIONS)
    assert report(pilot, run_id) == 0
    assert pilot.query(SELECTIONS) == selected  # the rerun selects nothing twice

    admissions = pilot.query(ADMISSIONS, run_id)
    vendor = [row for row in admissions if row[1] is not None]
    assert [row[2] for row in vendor] == [CHECKED.value]
    assert {row[1] for row in witness_captures(pilot, *vendor[0][:2])} == {
        "screener-subscriber",
        "tijori",
    }
    claims = _claims(pilot)
    revenue = claims["fact.revenue"]
    ((chosen,),) = pilot.query(VALUE, vendor[0][0])
    same = revenue.value is not None and revenue.value * CRORE == chosen
    assert same, "revenue is not the chosen vendor reading"  # compared, never printed
    assert CHECKED.value in revenue.qualifiers
    assert render_claim(revenue, DisplayStyle()).endswith(f"({LABEL_TEXT[CHECKED]})")
    for role in REQUIRED_ROLES:  # filed values too are checked against filing (row 2)
        assert CHECKED.value in claims[f"fact.{role.value}"].qualifiers, role
    assert {vendor[0][0]} <= {row[0] for row in pilot.query(OPERANDS)}  # computed from it
    labelled = [c for c in claims.values() if c.claim_key.startswith("calc.")]
    assert any(CHECKED.value in c.qualifiers for c in labelled)
    assert _matched(pilot)  # filed tax, probe and credibility resolve beside it


def test_withheld_package_drafts_every_number_unchecked(
    request: pytest.FixtureRequest,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """(b) with no package published by the cutoff, all six roles are row 3: the draft seals,
    every fact and every calculation from them labelled "vendors agree, not checked", in the
    ledger and in the emitted Markdown."""
    pilot = vendor_pilot(request, monkeypatch, withheld=True)
    run_id = compare(pilot, ELIGIBILITY)
    assert pilot.query(ADMISSIONS, run_id) == []
    pilot.evidence_ingest(QUARTER, XBRL_KIND, END)  # after the run: the filed tax line's source
    capsys.readouterr()
    assert report(pilot, run_id) == 0
    _assert_markdown_unchecked(capsys.readouterr().out)
    admissions = pilot.query(ADMISSIONS, run_id)
    chosen = {row[0] for row in admissions if row[2] == UNCHECKED.value}
    assert len(chosen) >= len(REQUIRED_ROLES)
    claims = _claims(pilot)
    for role in REQUIRED_ROLES:
        assert UNCHECKED.value in claims[f"fact.{role.value}"].qualifiers, role
    assert {row[0] for row in pilot.query(OPERANDS)} & chosen
    computed = [c for c in claims.values() if c.claim_key.startswith(("calc.", "cmp."))]
    assert any(UNCHECKED.value in c.qualifiers for c in computed)
    assert not any(CHECKED.value in c.qualifiers for c in computed)  # weakest label wins
    assert _matched(pilot)


def _assert_markdown_unchecked(markdown: str) -> None:
    """The emitted Markdown cites each role's comparative to its admitted anchor, as the facts
    table does, and labels the comparatives, their traces and every calculation from the roles
    unchecked; the filed tax line alone carries no label. Checked as booleans so a failure
    never prints a vendor reading."""
    sections = dict(re.findall(r"^## \d+\. (\w+)\n(.*?)(?=^## |^---)", markdown, re.M | re.S))
    text = f"({LABEL_TEXT[UNCHECKED]})"
    rows = r"^\| ([^|]+?) \| .*?(\[\^\d+\])(.*)$"  # a row's label, first footnote, rest
    facts = {row[0]: row[1] for row in re.findall(rows, sections["facts"], re.M)}
    changes = re.findall(rows, sections["changes"], re.M)
    cited = {row[0]: row[1] for row in changes}
    assert len(facts) == len(REQUIRED_ROLES) and cited == facts, "comparatives cite the filing"
    assert all(text in row[2] for row in changes), "a comparative is unlabelled"
    traces = sections["changes"].split("Computed traces:")[1].strip().splitlines()
    assert traces and all(line.endswith(text) for line in traces), "a trace is unlabelled"
    calculations = sections["calculations"].strip().splitlines()
    labelled = {line.split("**")[1]: text in line for line in calculations}
    assert labelled == {label: label != TAX_LABEL for label in labelled}
