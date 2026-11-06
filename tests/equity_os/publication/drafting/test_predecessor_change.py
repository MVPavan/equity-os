"""A vendor-valued predecessor prior recalculates the QoQ change, including whether a percent
exists: the filed comparator's zero/nonzero state must not leak into the substituted one."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from equity_os.contracts.measurement.provenance import Provenance, SourceAnchorType
from equity_os.contracts.verification.comparative import (
    REASON_PRIOR_ZERO,
    ComparatorKind,
    calculate_change,
)
from equity_os.contracts.verification.vendor_first import AdmissionLabel
from equity_os.publication.checking.claim_check import CRORE, UNITS
from equity_os.publication.drafting.earnings_update import AdmittedFact, predecessor_change
from equity_os.storage.facts.fact_store import FactRef

CURRENT = Decimal("12")


def _source(name: str) -> Provenance:
    """A synthetic XBRL anchor."""
    return Provenance(
        source_id=name,
        file_sha256="0" * 63 + "1",
        anchor_type=SourceAnchorType.XBRL_CONTEXT,
        context_ref=name,
        retrieved_at=datetime(2027, 10, 20, 6, tzinfo=UTC),
    )


@pytest.mark.parametrize(
    ("filed", "admitted"),
    [(Decimal("10"), Decimal("0")), (Decimal("0"), Decimal("8")), (Decimal("10"), Decimal("8"))],
    ids=["filed-nonzero-admitted-zero", "filed-zero-admitted-nonzero", "both-nonzero"],
)
def test_percent_follows_the_substituted_prior(filed: Decimal, admitted: Decimal) -> None:
    """The percent, its trace and its unavailable reason come from the admitted prior alone."""
    change = calculate_change(
        kind=ComparatorKind.QOQ,
        period_start=date(2027, 4, 1),
        period_end=date(2027, 6, 30),
        current_value=CURRENT,
        prior_value=filed,
        prior_source=_source("filed"),
    )
    fact = AdmittedFact(
        ref=FactRef(store_id="synthetic", origin="vendor", origin_id=1),
        value=admitted * (UNITS[CRORE][2] or 1),
        decimals=0,
        provenance=_source("admitted"),
        label=AdmissionLabel.VENDORS_AGREE_NOT_CHECKED,
        interpretation_id=1,
        witness_interpretation_id=2,
    )

    result = predecessor_change(change, CURRENT, fact, CRORE)

    assert result.prior_value == admitted
    assert result.prior_source == fact.provenance
    assert result.absolute_change == CURRENT - admitted
    assert result.absolute_trace is not None and str(admitted) in result.absolute_trace
    if admitted == 0:
        assert result.percent_change is None and result.percent_trace is None
        assert result.percent_unavailable_reason == REASON_PRIOR_ZERO
    else:
        expected = ((CURRENT - admitted) / admitted * 100).quantize(Decimal("0.01"))
        assert result.percent_change == expected
        assert result.percent_trace is not None and str(admitted) in result.percent_trace
        assert result.percent_unavailable_reason is None
    # The rebuilt state is one the contract accepts.
    type(result).model_validate(result.model_dump())
