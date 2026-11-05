"""eqos-dna.1 Tasks 2-4: what the Sol panel found missing from a run draft's narrative.

A reader resolves every claim from the narrative alone (claim references), sees why a drifted
comparison is comparable, which guidance names no target period, a falsifier line that states
its trigger condition instead of asserting the comparison, and the explicit scope of what the
version does not contain; a selective rework keeps the disclosures as they were.
"""

from __future__ import annotations

import pytest
from evidence_support import ingest, policy
from prep2b_support import Pilot
from prep5_support import _rerun
from test_ledger_display import numeric
from test_prep2b_run_draft import dictionary, mapping_set, pilot
from test_prep5_rework import CABLES, _request_changes, _successor

from equity_os.analysis.calculations import run_traces
from equity_os.analysis.calculations.run_traces import CHANGES
from equity_os.analysis.lenses.thesis_tests.falsifier_status import FALSIFIER_STATUS
from equity_os.contracts.verification.comparative import TAXONOMY_DRIFT_PREFIX
from equity_os.interface.workflows.pipeline import PipelineResult
from equity_os.publication.approval import lifecycle
from equity_os.publication.drafting import run_draft
from equity_os.publication.drafting.display import PLACEHOLDER, render_section
from equity_os.publication.drafting.management_ledger import LedgerStatus
from equity_os.publication.drafting.run_draft import GUIDANCE, RESULTS

__all__ = ["dictionary", "ingest", "mapping_set", "pilot", "policy"]

UNSPECIFIED = "target period not specified by the extracted guidance"
DRIFT = "taxonomy drift accepted in the issuer config: {drift}; both figures read as {canonical}"
FALSIFIER_INTRO = "observed traced value, trigger condition (operator and thesis threshold), status"
QUESTION = (
    "- Which fiscal year or window applies to {label}? Why it matters: the "
    "guidance cannot be checked against an outcome period without it. Evidence required: the "
    "transcript context around the quoted guidance {{{{c:{key}|ref}}}}, or a later management "
    "statement naming the period. Status: open; owner not assigned."
)
NOT_DONE = (
    "forward scenarios",
    "forensic checks",
    "a judgment of management credibility",
    "a narrative thesis-impact assessment",
    "no claim carries a materiality decision",
)
STATUSES = ("HELD (not triggered)", "WEAKENED (triggered)")


@pytest.fixture
def drafted(pilot: Pilot) -> tuple[Pilot, PipelineResult, int]:
    """FY26_Q2's run and its draft, submitted: ``submit`` scans every section's numerals."""
    result = pilot.run("FY26_Q2")
    version = result.draft_version_id
    assert version is not None
    with pilot.pg_db.runtime_pool() as runtime:
        lifecycle.submit(runtime, version, **pilot.sources())
    return pilot, result, version


@pytest.mark.parametrize(
    ("horizon", "specified"),
    [("FY27", True), ("FY27_Q2", True), ("annual", False), ("Q2", False)],
)
def test_only_a_fiscal_period_horizon_is_specified(horizon: str, specified: bool) -> None:
    """A fiscal year or fiscal quarter names the outcome period; a bare quarter or a cadence
    does not, and its guidance line says so rather than implying one."""
    claim = numeric(
        bounds=("9.5", "10"), claim_key="ledger.x", horizon=horizon, metric_label="X guidance"
    )
    assert run_draft._specified(horizon) is specified
    assert (UNSPECIFIED in run_draft._guided(claim, LedgerStatus.NEW)) is not specified


@pytest.mark.pg
@pytest.mark.retained
def test_the_run_draft_shows_what_the_panel_found_missing(
    drafted: tuple[Pilot, PipelineResult, int],
) -> None:
    """On one submitted FY26_Q2 draft: every claim line references each claim it shows (and
    renders its citation), the drifted comparison states its basis, guidance names its missing
    target period, falsifier lines state their trigger condition, and the draft ends with the
    outstanding questions and the scope it does not cover."""
    pilot, result, version_id = drafted
    version = pilot.version(version_id)
    claims = {claim.claim_key: claim for claim in version.claims}
    bodies = {section.section_key: section.body for section in version.sections}

    assert "management_credibility" in bodies  # the loop below reads the section
    # Task 2: a claim line references exactly the claims it shows; a claimless line none.
    for line in (line for body in bodies.values() for line in body.splitlines()):
        found = PLACEHOLDER.findall(line)
        shown = {key for key, style in found if style != "ref"}
        referenced = {key for key, style in found if style == "ref"}
        if shown:
            assert referenced == shown, line
    [revenue] = [line for line in bodies[RESULTS].splitlines() if "{{c:fact.revenue|" in line]
    rendered = render_section(revenue, version.claims)
    origin = claims["fact.revenue"].citation.fact_origin_id
    assert "[fact.revenue: FIGURE " in rendered and f"fact_origin_id={origin}" in rendered

    # Task 3: drift basis, unspecified horizon, trigger wording.
    roles = {fact.concept_qname: fact.role.value for fact in result.update.facts}
    changes, drifted = bodies[CHANGES].splitlines(), set()
    for comparative in result.update.comparatives:
        for change in (comparative.qoq, comparative.yoy):
            prior = f"cmp.{roles[comparative.concept_qname]}.{change.kind.value.lower()}.prior"
            if prior not in claims:
                continue
            [line] = [line for line in changes if f"{{{{c:{prior}|" in line]
            drift = (change.taxonomy_drift or "").removeprefix(TAXONOMY_DRIFT_PREFIX)
            key = claims[prior].measurement_key
            assert key is not None
            if drift:
                drifted.add(prior)
                assert DRIFT.format(drift=drift, canonical=key.canonical_id) in line
            else:
                assert "taxonomy drift" not in line
    assert "cmp.revenue.yoy.prior" in drifted and "cmp.revenue.qoq.prior" not in drifted
    guided = [line for line in bodies[GUIDANCE].splitlines() if line.startswith("- ")]
    assert guided and all(UNSPECIFIED in line for line in guided)
    assert FALSIFIER_INTRO in bodies[FALSIFIER_STATUS]
    rows = {
        line.split()[1]: line
        for line in bodies[FALSIFIER_STATUS].splitlines()
        if line.endswith(STATUSES)
    }
    assert "F1" in rows and "triggers when below " in rows["F1"]
    for fid, line in rows.items():
        assert ": observed {{c:" in line and "; triggers when " in line, line
        assert f"{{{{c:thesis.{fid}|ref}}}}" in line, line

    # Task 4: the outstanding questions and the disclosed scope close the draft.
    keys = [section.section_key for section in version.sections]
    assert keys[-2:] == [run_traces.OPEN_QUESTIONS, run_traces.NOT_PERFORMED]
    guidance = [claim for claim in version.claims if claim.section_key == GUIDANCE]
    open_ = [c for c in guidance if not run_draft._specified(c.horizon)]
    questions = [
        line for line in bodies[run_traces.OPEN_QUESTIONS].splitlines() if line.startswith("- ")
    ]
    assert len(open_) == 2
    assert questions == [QUESTION.format(label=c.metric_label, key=c.claim_key) for c in open_]
    not_performed = bodies[run_traces.NOT_PERFORMED]
    assert all(scope in not_performed for scope in NOT_DONE)


@pytest.mark.pg
@pytest.mark.retained
def test_a_guidance_rework_keeps_the_disclosures(
    drafted: tuple[Pilot, PipelineResult, int],
) -> None:
    """The disclosures are regenerated outside the rework contract: rejecting a guidance claim
    reruns it, and the successor's open questions and scope are the predecessor's, byte for
    byte, the rejected claim's question still outstanding."""
    pilot, _, version = drafted
    _request_changes(pilot, version, CABLES)
    assert _rerun(pilot).draft_version_id == _successor(pilot, version)
    disclosed = run_traces.DISCLOSED

    def bodies(version_id: int) -> dict[str, str]:
        sections = pilot.version(version_id).sections
        return {s.section_key: s.body for s in sections if s.section_key in disclosed}

    before, after = bodies(version), bodies(_successor(pilot, version))
    assert set(after) == disclosed and after == before
    assert f"{{{{c:{CABLES}|ref}}}}" in after[run_traces.OPEN_QUESTIONS]
