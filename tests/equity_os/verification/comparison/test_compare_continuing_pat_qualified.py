"""Continuing PAT qualified on both sides under mapping set v3 (data spec §2, §5; D1b.5).

LAURUSLABS Q3 FY25 consolidated, retained bytes: XBRL ``OneD``
ProfitLossForPeriodFromContinuingOperations 906100000 (``decimals="-7"``, 90.61 crore ± 0.5),
ProfitLossFromDiscontinuedOperationsAfterTax 0.00, ProfitLossForPeriod 929400000 (92.94);
Tijori qt_c Dec 2024 "Net Profit" 90.61 (≤ 100: ± 0.005). Tijori discriminates continuing
PAT from profit for period, so it is one of the D3 cases the v3 scopes record.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterator
from datetime import timedelta
from decimal import Decimal
from fractions import Fraction
from pathlib import Path
from typing import Any

import pytest
from test_compare_vendor_runs import CONFIG, LAURUS, Q3_END, Issuer, _row

from equity_os.contracts.measurement.canonical import Representation
from equity_os.contracts.measurement.evidence import (
    Interpretation,
    InterpretationReason,
    InterpretationStatus,
    RevisionCause,
)
from equity_os.contracts.measurement.evidence_tier import EvidenceTier
from equity_os.contracts.measurement.interval import Interval
from equity_os.contracts.verification.comparison import (
    CorroborationStatus,
    PairOutcome,
    SourceState,
)
from equity_os.verification.comparison.run import execute_run, load_results, replay_run
from equity_os.verification.comparison.run_config import ConfigVersions
from equity_os.verification.comparison.run_models import ResultRow
from equity_os.verification.comparison.tables import ComparisonSide
from equity_os.verification.review_queue.queue import overlay_boundary, read_overlay
from equity_os.verification.review_queue.trust import trusted

V3 = ConfigVersions(dictionary="v2", mapping_set="v3")
TIJORI = (("tijori", "financials"),)


class Run:
    """A completed v3 LAURUSLABS run (XBRL plus Tijori) and its continuing-PAT row."""

    def __init__(self, issuer: Issuer) -> None:
        issuer.first_party()
        issuer.tijori()
        self.issuer = issuer
        self.run_id = execute_run(
            issuer.request(Q3_END, TIJORI), pool=issuer.pool, config_root=CONFIG
        ).run_id
        self.rows = load_results(self.run_id, pool=issuer.pool)
        self.pat: ResultRow = _row(self.rows, "profit_continuing_after_tax")

    def filing(self) -> Interpretation:
        """The stored XBRL interpretation the row selected."""
        (value,) = [
            item for item in self.pat.source_values if item.representation is Representation.XBRL
        ]
        assert value.interpretation_id is not None
        (found,) = self.issuer.repository.get_interpretations([value.interpretation_id])
        return found


@pytest.fixture
def run(pg_db: Any, tmp_path: Path) -> Iterator[Run]:
    with pg_db.runtime_pool() as pool:
        yield Run(Issuer(LAURUS, pg_db, pool, tmp_path, V3))


@pytest.mark.pg
@pytest.mark.retained
def test_tijori_net_profit_agrees_qualified_and_the_cell_is_trusted(run: Run) -> None:
    """Both mappings are demonstrated in scope, the filing's own zero discontinued profit
    proves the condition, so the pair is ``AGREE`` and the cell trusted; replay reproduces."""
    filing = run.filing()
    assert filing.tier is EvidenceTier.EQUIVALENCE_DEMONSTRATED
    assert filing.qualification_ref == "bsefin-continuing-pat-quarter"
    assert [proof.holds for proof in filing.condition_evidence] == [True]
    (pair,) = run.pat.pairs
    assert pair.outcome is PairOutcome.AGREE
    assert run.pat.corroboration_status is CorroborationStatus.CORROBORATED
    pool = run.issuer.pool
    overlay = read_overlay(pool, run_id=run.run_id, as_of=overlay_boundary(pool))
    trust = trusted(
        run_id=run.run_id,
        key=run.pat.key,
        extraction=run.pat.extraction_status,
        corroboration=run.pat.corroboration_status,
        first_party_state=SourceState.VALUE,
        overlay=overlay,
    )
    assert trust.trusted
    assert replay_run(run.run_id, pool=pool, config_root=CONFIG) == run.rows


@pytest.mark.pg
@pytest.mark.retained
@pytest.mark.parametrize(
    ("change", "outcome"),
    [
        pytest.param({}, PairOutcome.AGREE, id="selected-filing-in-scope"),
        pytest.param(
            {"mapping_entry_ids": ("capmkt.profit_continuing_after_tax",)},
            PairOutcome.AGREE_UNQUALIFIED,
            id="out-of-taxonomy",
        ),
        pytest.param(
            {"condition_evidence": ()}, PairOutcome.AGREE_UNQUALIFIED, id="condition-missing"
        ),
        pytest.param("nonzero", PairOutcome.AGREE_UNQUALIFIED, id="condition-nonzero"),
    ],
)
def test_vendor_scope_is_read_from_the_selected_filing(
    run: Run, change: dict[str, object] | str, outcome: PairOutcome
) -> None:
    """The stored Tijori side meets the real filing side with one fact altered in memory:
    another taxonomy, the discontinued fact withheld, or it nonzero. The first-party tier
    stays demonstrated, so only the vendor's filing-scoped tier decides the outcome."""
    filing = run.filing()
    assert filing.key is not None and filing.mapping_entry_id is not None
    side = ComparisonSide(
        key=filing.key,
        state=SourceState.VALUE,
        value=filing.value,
        interval=filing.interval,
        tier=filing.tier,
        aligned_by_proof=False,
        mapping_entry_ids=(filing.mapping_entry_id,),
        package_id=None,
        calculation_state=None,
        reasons=(),
        condition_evidence=filing.condition_evidence,
    )
    if change == "nonzero":
        change = {
            "condition_evidence": tuple(
                proof.model_copy(update={"holds": False}) for proof in filing.condition_evidence
            )
        }
    assert isinstance(change, dict)
    found = run.issuer.sides(filing.key, side.model_copy(update=change), vendors=TIJORI)
    (pair,) = found.pairs
    assert pair.outcome is outcome


FIFTY_CRORE = Decimal(500_000_000)
CORRECTIONS = {
    # A manual correction: discontinued profit 50 crore ± 0.5 (excludes zero).
    "nonzero": {
        "value": FIFTY_CRORE,
        "interval": Interval(
            lower=Fraction(FIFTY_CRORE) - 5_000_000, upper=Fraction(FIFTY_CRORE) + 5_000_000
        ),
        "revision_cause": RevisionCause.MANUAL_CORRECTION,
    },
    # A manual correction refusing the line.
    "invalid": {
        "status": InterpretationStatus.INVALID,
        "value": None,
        "interval": None,
        "reason": InterpretationReason.UNREADABLE_CELL,
        "revision_cause": RevisionCause.MANUAL_CORRECTION,
    },
    # A second unsuperseded zero: two current interpretations of one key are ambiguous.
    "ambiguous": {"supersedes_interpretation_id": None},
}


@pytest.mark.pg
@pytest.mark.retained
@pytest.mark.parametrize("correction", sorted(CORRECTIONS))
def test_a_later_condition_correction_withholds_both_sides(run: Run, correction: str) -> None:
    """The PAT interpretation keeps its stored holds=True proof, but the run re-proves the
    condition from the current discontinued-profit selection: before the correction's
    cutoff the pair is AGREE; after it neither side is qualified (spec §2). Both replay."""
    (proof,) = run.filing().condition_evidence
    repository, pool = run.issuer.repository, run.issuer.pool
    (zero,) = repository.get_interpretations(proof.evidence_interpretation_ids)
    (replacement_id,) = repository.reserve_interpretation_ids(1)
    before = repository.store_clock()
    corrected = zero.model_copy(
        update={
            "interpretation_id": replacement_id,
            "input_digest": hashlib.sha256(correction.encode()).hexdigest(),
            "supersedes_interpretation_id": zero.interpretation_id,
            "recorded_at": before + timedelta(microseconds=1),
            **CORRECTIONS[correction],
        }
    )
    repository.put_interpretations([corrected])
    request = run.issuer.request(Q3_END, TIJORI)
    outcomes = {}
    for cutoff in (before, request.cutoff):
        record = execute_run(
            request.model_copy(update={"cutoff": cutoff}), pool=pool, config_root=CONFIG
        )
        rows = load_results(record.run_id, pool=pool)
        pat = _row(rows, "profit_continuing_after_tax")
        (pair,) = pat.pairs
        outcomes[cutoff] = (pair.outcome, pat.corroboration_status)
        assert replay_run(record.run_id, pool=pool, config_root=CONFIG) == rows
    (agreed, agreed_status), (after, after_status) = outcomes.values()
    assert (agreed, agreed_status) == (PairOutcome.AGREE, CorroborationStatus.CORROBORATED)
    assert after is PairOutcome.AGREE_UNQUALIFIED
    assert after_status is not CorroborationStatus.CORROBORATED
