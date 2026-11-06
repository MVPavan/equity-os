"""VENDOR-1 Task 9: a ``fundamentals run --compare-run <id>`` whose required facts are admitted
from the vendors, end to end through ``main`` (plan Task 9 cases (a), (b) and (c)).

Each case starts with no admissions for its comparison run. Apar FY26_Q2's revenue is
``VENDORS_AGREE`` at 5,715 crore against a filed 5,715.42 (row 1); the withheld world of
``vendor_report_support`` makes all six roles row 3.
"""

from __future__ import annotations

from decimal import Decimal
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
    row-1 revenue drafts at the vendors' 5,715 crore labelled "checked against filing", its
    calculations computed from the admitted value; a pipeline failure after selection, rerun,
    selects nothing twice."""
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
    assert revenue.value == Decimal("5715") and CHECKED.value in revenue.qualifiers
    assert render_claim(revenue, DisplayStyle()).endswith(f"({LABEL_TEXT[CHECKED]})")
    for role in REQUIRED_ROLES:  # filed values too are checked against filing (row 2)
        assert CHECKED.value in claims[f"fact.{role.value}"].qualifiers, role
    assert {vendor[0][0]} <= {row[0] for row in pilot.query(OPERANDS)}  # computed from it
    labelled = [c for c in claims.values() if c.claim_key.startswith("calc.")]
    assert any(CHECKED.value in c.qualifiers for c in labelled)
    assert _matched(pilot)  # filed tax, probe and credibility resolve beside it


def test_withheld_package_drafts_every_number_unchecked(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> None:
    """(b) with no package published by the cutoff, all six roles are row 3: the draft seals,
    every fact and every calculation from them labelled "vendors agree, not checked"."""
    pilot = vendor_pilot(request, monkeypatch, withheld=True)
    run_id = compare(pilot, ELIGIBILITY)
    assert pilot.query(ADMISSIONS, run_id) == []
    pilot.evidence_ingest(QUARTER, XBRL_KIND, END)  # after the run: the filed tax line's source
    assert report(pilot, run_id) == 0
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
