"""Continuing PAT qualified on both sides under mapping set v3 (data spec §2, §5; D1b.5).

LAURUSLABS Q3 FY25 consolidated, retained bytes: XBRL ``OneD``
ProfitLossForPeriodFromContinuingOperations 906100000 (``decimals="-7"``, 90.61 crore ± 0.5),
ProfitLossFromDiscontinuedOperationsAfterTax 0.00, ProfitLossForPeriod 929400000 (92.94);
Tijori qt_c Dec 2024 "Net Profit" 90.61 (≤ 100: ± 0.005). Tijori discriminates continuing
PAT from profit for period, so it is one of the D3 cases the v3 scopes record.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from test_compare_vendor_runs import CONFIG, LAURUS, Q3_END, Issuer, _row

from fundamentals.compare.queue import overlay_boundary, read_overlay
from fundamentals.compare.run import execute_run, load_results, replay_run
from fundamentals.compare.run_config import ConfigVersions
from fundamentals.compare.run_models import ResultRow
from fundamentals.compare.tables import ComparisonSide
from fundamentals.compare.trust import trusted
from fundamentals.contracts.canonical import Representation
from fundamentals.contracts.comparison import CorroborationStatus, PairOutcome, SourceState
from fundamentals.contracts.evidence import Interpretation
from fundamentals.contracts.evidence_tier import EvidenceTier

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
