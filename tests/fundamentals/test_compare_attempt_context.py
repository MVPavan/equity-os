"""Mapping-dependent attempt outcomes decide only runs with the matching context."""

from datetime import UTC, date, datetime

from fundamentals.compare.engine_attempts import AttemptStates
from fundamentals.contracts.acquisition_outcome import ExtractionOutcome
from fundamentals.contracts.canonical import Basis, Representation, StatementFamily, ValueKind
from fundamentals.contracts.comparison import SourceState
from fundamentals.contracts.evidence import (
    AcquisitionAttempt,
    AttemptStage,
    InterpretationTriple,
    RunMode,
)
from fundamentals.contracts.measurement_key import DimensionSet, MeasurementKey, PeriodInterval
from fundamentals.contracts.observation import AccountingFramework
from fundamentals.evidence.first_party_extract import unsupported_schema_context


def test_unsupported_schema_attempt_decides_only_its_mapping_version() -> None:
    """Adding taxonomy support cannot inherit an unsupported verdict from an older mapping."""
    cutoff = datetime(2026, 10, 13, tzinfo=UTC)
    end = date(2025, 9, 30)
    key = MeasurementKey(
        entity_id=1,
        canonical_id="revenue_from_operations",
        period=PeriodInterval.duration(date(2025, 7, 1), end),
        basis=Basis.CONSOLIDATED,
        framework=AccountingFramework.IND_AS,
        currency="INR",
        value_kind=ValueKind.CURRENCY_AMOUNT,
        dimensions=DimensionSet(),
    )
    attempt = AcquisitionAttempt(
        attempt_id=1,
        stage=AttemptStage.EXTRACTION,
        source_id="nse-indas-xbrl-consolidated",
        surface="NSE_XBRL_INSTANCE",
        entity_id=1,
        period_end=end,
        basis=Basis.CONSOLIDATED,
        framework=AccountingFramework.IND_AS,
        representation=Representation.XBRL,
        statement_family=None,
        package_id=None,
        outcome=ExtractionOutcome.UNSUPPORTED_SCHEMA,
        reason="test: old mapping does not support taxonomy",
        capture=None,
        input_sha256="1" * 64,
        extractor_version="test-extractor",
        attempted_at=cutoff,
        extraction_context_sha256=unsupported_schema_context("v1"),
    )

    def states(mapping: str) -> AttemptStates:
        return AttemptStates(
            (attempt,),
            member_captures=(),
            cutoff=cutoff,
            mode=RunMode.AS_KNOWN,
            triple=InterpretationTriple(
                mapping_set=mapping,
                normalisation_policy="v1",
                extractor_xbrl="test-extractor",
                extractor_pdf="test-pdf-extractor",
            ),
            surfaces=("NSE_XBRL_INSTANCE",),
        )

    failure = states("v1").state(key, Representation.XBRL, StatementFamily.PL, None)
    assert failure is not None
    assert failure.selection.state is SourceState.UNAVAILABLE
    assert failure.attempt_id == 1
    assert states("v2").state(key, Representation.XBRL, StatementFamily.PL, None) is None
