"""VENDOR-1 Task 9: both thesis adapters pass the evidence's admission label to the rendered
facts table, and legacy evidence without one renders no label. Values are synthetic."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

from equity_os.analysis.thesis_models import (
    ValidatedFactSet,
    build_thesis,
    from_gold_file,
    from_stock_report,
    render_thesis_document,
)
from equity_os.contracts.measurement.observation import (
    AccountingFramework,
    PeriodType,
    Scope,
)
from equity_os.contracts.measurement.provenance import Provenance, SourceAnchorType
from equity_os.contracts.verification.vendor_first import LABEL_TEXT, AdmissionLabel
from equity_os.verification.comparison.agreement import AgreementStatus, SourceClass, SourceValue
from equity_os.verification.comparison.comparison_key import ComparisonKey
from equity_os.verification.diagnostics.gold_file import GoldFact, GoldFile

REVENUE = "in-bse-fin:RevenueFromOperations"
UNCHECKED = AdmissionLabel.VENDORS_AGREE_NOT_CHECKED


def _rendered(fact_set: ValidatedFactSet) -> str:
    """The thesis document's Markdown for ``fact_set``, with no models run."""
    return render_thesis_document(
        build_thesis(fact_set, []), generated_at=datetime(2026, 11, 6, tzinfo=UTC)
    )


def _gold(tmp_path: Path, label: AdmissionLabel | None) -> Path:
    """A one-fact gold file whose revenue carries ``label``."""
    key = ComparisonKey(
        entity_scheme="nse-symbol",
        entity_id="SYNTH",
        concept_qname=REVENUE,
        period_type=PeriodType.DURATION,
        period_start=date(2025, 7, 1),
        period_end=date(2025, 9, 30),
        scope=Scope.CONSOLIDATED,
        accounting_basis=AccountingFramework.IND_AS,
        currency="INR",
        unit="INR crore",
        scale=10_000_000,
    )
    provenance = Provenance(
        source_id="tijori",
        file_sha256="0" * 64,
        anchor_type=SourceAnchorType.XBRL_CONTEXT,
        context_ref="synthetic",
        retrieved_at=datetime(2025, 11, 1, tzinfo=UTC),
    )
    fact = GoldFact(
        concept_qname=REVENUE,
        comparison_key=key,
        value="1234.5",
        normalized_unit="INR crore",
        agreement_status=AgreementStatus.AGREE,
        agreed_sources=("tijori", "screener-subscriber"),
        corroborating_sources=(),
        incompatible_sources=(),
        first_party_source_count=0,
        needs_human_review=False,
        source_values=(
            SourceValue(
                source_id="tijori",
                source_class=SourceClass.FIRST_PARTY,
                normalized_value=Decimal("1234.5"),
                normalized_unit="INR crore",
                provenance=provenance,
            ),
        ),
        admission_label=label,
    )
    path = tmp_path / "SYNTH.json"
    gold = GoldFile(schema_version=1, symbol="SYNTH", quarter="FY26_Q2", facts=(fact,))
    path.write_text(gold.model_dump_json(), encoding="utf-8")
    return path


def _stock_report(label: AdmissionLabel | None) -> SimpleNamespace:
    """A one-fact goal-runner report whose revenue carries ``label``."""
    reading = SimpleNamespace(
        source_id="tijori",
        source_class=SourceClass.FIRST_PARTY,
        value="1234.5",
        normalized_unit="INR crore",
    )
    fact = SimpleNamespace(
        concept_qname=REVENUE,
        status=AgreementStatus.AGREE,
        agreed_value="1234.5",
        agreed_sources=("tijori", "screener-subscriber"),
        corroborating_sources=(),
        first_party_source_count=0,
        readings=(reading,),
        admission_label=label,
    )
    return SimpleNamespace(
        symbol="SYNTH",
        name="Synthetic",
        domain="Test",
        quarter="FY26_Q2",
        facts=(fact,),
        discrepancies=(),
        missing_material_concepts=(),
    )


def test_adapters_carry_admission_label_to_the_rendered_table(tmp_path: Path) -> None:
    """An unchecked admitted fact renders qualified on both routes; legacy evidence does not."""
    for label in (UNCHECKED, None):
        gold = from_gold_file(_gold(tmp_path, label))
        report = from_stock_report(_stock_report(label))  # type: ignore[arg-type]
        for fact_set in (gold, report):
            assert fact_set.facts[0].admission_label is label
            assert fact_set.facts[0].single_sourced is False  # never the label's source
            assert (LABEL_TEXT[UNCHECKED] in _rendered(fact_set)) is (label is not None)
