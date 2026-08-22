"""Reconcile-layer tests: per-fact agreement classification and the gold file.

Synthetic multi-source observations exercise every classifier branch — two
first-party sources agreeing (AGREE), a first-party value corroborated only by a
derived aggregator (SINGLE_FIRST_PARTY), first-party sources that materially
disagree (CONFLICT), and an incompatible column that must be excluded from the
comparison. The gold file is round-tripped through disk and ``regress`` is shown
to catch a drifted value on a re-run.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

from fundamentals.contracts.observation import (
    AccountingFramework,
    Observation,
    PeriodType,
    Scope,
)
from fundamentals.contracts.provenance import Provenance, SourceAnchorType
from fundamentals.reconcile.agreement import (
    AgreementStatus,
    SourceClass,
    classify_agreement,
    classify_source,
)
from fundamentals.reconcile.gold_file import (
    DriftKind,
    build_gold_file,
    read_gold_file,
    regress,
    write_gold_file,
)

_RETRIEVED_AT = datetime(2024, 7, 18, tzinfo=UTC)

REVENUE = "in-bse-fin:RevenueFromOperations"
PAT = "in-bse-fin:ProfitLossForPeriod"

NSE = "nse-indas-xbrl-consolidated"
BSE = "bse-xbrl"
PDF = "infy-q1-fy25-results-pdf"
SCREENER = "screener"
TIJORI = "tijori"


def _xbrl_provenance(source_id: str) -> Provenance:
    return Provenance(
        source_id=source_id,
        file_sha256="0" * 64,
        anchor_type=SourceAnchorType.XBRL_CONTEXT,
        context_ref="OneD",
        retrieved_at=_RETRIEVED_AT,
    )


def _pdf_provenance(source_id: str) -> Provenance:
    return Provenance(
        source_id=source_id,
        file_sha256="a" * 64,
        anchor_type=SourceAnchorType.PDF_SPAN,
        page=11,
        block=4,
        span="0:5",
        retrieved_at=_RETRIEVED_AT,
    )


def _observation(
    concept: str,
    value: Decimal,
    provenance: Provenance,
    *,
    scope: Scope = Scope.CONSOLIDATED,
    scale: int = 10_000_000,
    decimals: int = -7,
    unit: str = "INR crore",
    currency: str = "INR",
) -> Observation:
    """Build a consolidated Ind AS INR-crore Q1 observation from a given source."""
    return Observation(
        concept_qname=concept,
        raw_value=str(int(value) * scale),
        normalized_value=value,
        normalized_unit=unit,
        context_ref="OneD",
        entity_scheme="nse-symbol",
        entity_id="INFY",
        scope=scope,
        accounting_basis=AccountingFramework.IND_AS,
        period_type=PeriodType.DURATION,
        period_start=date(2024, 4, 1),
        period_end=date(2024, 6, 30),
        currency=currency,
        scale=scale,
        decimals=decimals,
        provenance=provenance,
    )


# --- source classification -----------------------------------------------------


def test_classify_source_marks_aggregators_derived() -> None:
    assert classify_source(NSE) is SourceClass.FIRST_PARTY
    assert classify_source(BSE) is SourceClass.FIRST_PARTY
    assert classify_source(PDF) is SourceClass.FIRST_PARTY
    assert classify_source(SCREENER) is SourceClass.DERIVED
    assert classify_source(TIJORI) is SourceClass.DERIVED


# --- agreement classification --------------------------------------------------


def test_two_first_party_sources_agree() -> None:
    observations = [
        _observation(PAT, Decimal(6374), _xbrl_provenance(NSE)),
        _observation(PAT, Decimal(6374), _pdf_provenance(PDF)),
    ]
    result = classify_agreement(observations)

    assert result.status is AgreementStatus.AGREE
    assert result.agreed_value == Decimal(6374)
    assert result.first_party_source_count == 2
    assert set(result.agreed_sources) == {NSE, PDF}
    assert result.needs_human_review is False


def test_first_party_corroborated_only_by_derived_is_flagged() -> None:
    observations = [
        _observation(PAT, Decimal(6374), _xbrl_provenance(NSE)),
        _observation(PAT, Decimal(6374), _xbrl_provenance(SCREENER)),
        _observation(PAT, Decimal(6374), _xbrl_provenance(TIJORI)),
    ]
    result = classify_agreement(observations)

    assert result.status is AgreementStatus.SINGLE_FIRST_PARTY
    assert result.first_party_source_count == 1
    assert result.agreed_value == Decimal(6374)
    assert result.agreed_sources == (NSE,)
    # Derived sources corroborate but never count toward the required two.
    assert set(result.corroborating_sources) == {SCREENER, TIJORI}
    assert result.needs_human_review is True


def test_materially_different_first_party_sources_conflict() -> None:
    observations = [
        _observation(PAT, Decimal(6374), _xbrl_provenance(NSE)),
        _observation(PAT, Decimal(6100), _pdf_provenance(PDF)),
    ]
    result = classify_agreement(observations)

    assert result.status is AgreementStatus.CONFLICT
    assert result.agreed_value is None
    assert result.agreed_sources == ()
    assert result.first_party_source_count == 2
    assert result.needs_human_review is True


def test_minor_diff_within_looser_band() -> None:
    # 6374 vs 6376: outside the half-ULP tight tolerance (1.0), inside the 0.5% band.
    observations = [
        _observation(PAT, Decimal(6374), _xbrl_provenance(NSE)),
        _observation(PAT, Decimal(6376), _pdf_provenance(PDF)),
    ]
    result = classify_agreement(observations)

    assert result.status is AgreementStatus.MINOR_DIFF
    assert result.first_party_source_count == 2
    assert result.agreed_value in (Decimal(6374), Decimal(6376))


def test_incompatible_key_is_excluded_from_comparison() -> None:
    # A standalone value must not corroborate the consolidated column.
    observations = [
        _observation(PAT, Decimal(6374), _xbrl_provenance(NSE)),
        _observation(PAT, Decimal(6374), _pdf_provenance(PDF)),
        _observation(PAT, Decimal(5000), _xbrl_provenance(BSE), scope=Scope.STANDALONE),
    ]
    result = classify_agreement(observations)

    assert result.status is AgreementStatus.AGREE
    assert result.comparison_key.scope is Scope.CONSOLIDATED
    assert BSE in result.incompatible_sources
    assert {value.source_id for value in result.source_values} == {NSE, PDF}


# --- gold file: round-trip and regression --------------------------------------


def _revenue_agree() -> list[Observation]:
    return [
        _observation(REVENUE, Decimal(39315), _xbrl_provenance(NSE)),
        _observation(REVENUE, Decimal(39315), _pdf_provenance(PDF)),
    ]


def _pat_agree() -> list[Observation]:
    return [
        _observation(PAT, Decimal(6374), _xbrl_provenance(NSE)),
        _observation(PAT, Decimal(6374), _pdf_provenance(PDF)),
    ]


def test_gold_file_round_trip_and_deterministic(tmp_path: Path) -> None:
    results = [classify_agreement(_revenue_agree()), classify_agreement(_pat_agree())]
    path = write_gold_file("INFY", "Q1FY25", results, out_dir=tmp_path)
    assert path == tmp_path / "INFY-Q1FY25.json"

    loaded = read_gold_file(path)
    assert loaded.symbol == "INFY"
    assert loaded.quarter == "Q1FY25"
    assert {fact.concept_qname for fact in loaded.facts} == {REVENUE, PAT}
    pat_fact = next(fact for fact in loaded.facts if fact.concept_qname == PAT)
    assert pat_fact.value == "6374"
    assert pat_fact.agreement_status is AgreementStatus.AGREE
    assert pat_fact.first_party_source_count == 2

    # Re-writing an unchanged reconciliation is byte-identical (canonical JSON).
    first_bytes = path.read_bytes()
    write_gold_file("INFY", "Q1FY25", list(reversed(results)), out_dir=tmp_path)
    assert path.read_bytes() == first_bytes


def test_regress_detects_a_drifted_value(tmp_path: Path) -> None:
    stored_results = [classify_agreement(_revenue_agree()), classify_agreement(_pat_agree())]
    path = write_gold_file("INFY", "Q1FY25", stored_results, out_dir=tmp_path)
    gold = read_gold_file(path)

    # Fresh run: revenue unchanged, PAT drifted to a new agreed value.
    drifted_pat = [
        _observation(PAT, Decimal(6300), _xbrl_provenance(NSE)),
        _observation(PAT, Decimal(6300), _pdf_provenance(PDF)),
    ]
    fresh = [classify_agreement(_revenue_agree()), classify_agreement(drifted_pat)]

    report = regress(gold, fresh)
    assert report.has_drift is True
    value_drifts = [drift for drift in report.drifts if drift.kind is DriftKind.VALUE_DRIFT]
    assert len(value_drifts) == 1
    assert value_drifts[0].concept_qname == PAT
    assert value_drifts[0].gold_value == "6374"
    assert value_drifts[0].fresh_value == "6300"


def test_regress_clean_when_extraction_matches(tmp_path: Path) -> None:
    results = [classify_agreement(_revenue_agree()), classify_agreement(_pat_agree())]
    path = write_gold_file("INFY", "Q1FY25", results, out_dir=tmp_path)
    gold = read_gold_file(path)

    fresh = [classify_agreement(_revenue_agree()), classify_agreement(_pat_agree())]
    report = regress(gold, fresh)
    assert report.has_drift is False


def test_build_gold_file_orders_facts_deterministically() -> None:
    results = [classify_agreement(_pat_agree()), classify_agreement(_revenue_agree())]
    gold = build_gold_file("INFY", "Q1FY25", results)
    concepts = [fact.concept_qname for fact in gold.facts]
    assert concepts == sorted(concepts)
