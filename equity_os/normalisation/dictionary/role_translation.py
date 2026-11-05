"""Versioned legacy concept → measurement key translation (data spec §1, legacy role translation).

Legacy ``ProfitBeforeTax`` is the before-associates figure, so it maps to
``profit_before_tax``, never to the headline PBT including associates.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping

from equity_os.contracts.measurement.canonical import Basis, ValueKind
from equity_os.contracts.measurement.fact import Fact
from equity_os.contracts.measurement.measurement_key import (
    DimensionSet,
    MeasurementKey,
    PeriodInterval,
)

TRANSLATION_VERSION = "legacy-translation/1"
LEGACY_CONCEPTS: Mapping[str, str] = {
    "in-capmkt:RevenueFromOperations": "revenue_from_operations",
    "in-capmkt:Income": "total_income",
    "in-capmkt:Expenses": "total_expenses",
    "in-capmkt:ProfitBeforeTax": "profit_before_tax",
    "in-capmkt:ProfitLossForPeriod": "profit_for_period",
    "in-capmkt:BasicEarningsLossPerShareFromContinuingAndDiscontinuedOperations": "eps_basic",
}
_VALUE_KINDS: Mapping[str, ValueKind] = {
    "INR crore": ValueKind.CURRENCY_AMOUNT,
    "INR per share": ValueKind.PER_SHARE_AMOUNT,
}


def translation_sha256() -> str:
    """The pin of the concept table this version translates with."""
    return hashlib.sha256(json.dumps(dict(LEGACY_CONCEPTS), sort_keys=True).encode()).hexdigest()


def translate(fact: Fact, *, entity_id: int) -> MeasurementKey | None:
    """The measurement key of a legacy fact, or ``None`` when it is untranslatable."""
    observation = fact.observation
    canonical_id = LEGACY_CONCEPTS.get(observation.concept_qname)
    value_kind = _VALUE_KINDS.get(observation.normalized_unit)
    if canonical_id is None or value_kind is None or observation.dimensions:
        return None
    return MeasurementKey(
        entity_id=entity_id,
        canonical_id=canonical_id,
        period=PeriodInterval(
            start=observation.period_start,
            end=observation.period_end,
            instant=observation.period_instant,
        ),
        basis=Basis[observation.scope.name],
        framework=observation.accounting_basis,
        currency=observation.currency,
        value_kind=value_kind,
        dimensions=DimensionSet(),
    )
