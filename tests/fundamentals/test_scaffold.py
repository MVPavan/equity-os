"""Slice 0 scaffold test.

Proves the frozen contract models import and construct, that frozen-ness is
enforced, and that the Q1 FY25 measurement-manifest oracle parses and carries
its six verified facts plus the adversarial distractors.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from fundamentals.contracts import (
    CanonicalStatus,
    EpistemicClass,
    Fact,
    GuidanceClaim,
    IssuerQuarter,
    Observation,
    PeriodType,
    ProgramQuarter,
    Provenance,
    ReconciliationStatus,
    Scope,
    SourceAnchorType,
)

MANIFEST_PATH = Path(__file__).resolve().parent / "fixtures" / "infy_q1_fy25_manifest.json"

_RETRIEVED_AT = datetime(2024, 7, 18, tzinfo=UTC)

EXPECTED_FACT_LABELS = {
    "Revenue from operations",
    "Total income",
    "Total expenses",
    "Profit before tax",
    "Profit for the period",
    "Basic EPS",
}


def _xbrl_provenance() -> Provenance:
    return Provenance(
        source_id="nse-indas-xbrl-consolidated",
        file_sha256="0" * 64,
        anchor_type=SourceAnchorType.XBRL_CONTEXT,
        context_ref="OneD",
        retrieved_at=_RETRIEVED_AT,
    )


def _revenue_observation() -> Observation:
    return Observation(
        concept_qname="in-bse-fin:RevenueFromOperations",
        taxonomy_namespace="http://www.bseindia.com/xbrl/fin/2020-03-31/in-bse-fin",
        registry_version="in-bse-fin/2020-03-31",
        raw_value="393150000000",
        normalized_value=Decimal("39315"),
        normalized_unit="INR crore",
        context_ref="OneD",
        entity_scheme="nse-symbol",
        entity_id="INFY",
        scope=Scope.CONSOLIDATED,
        period_type=PeriodType.DURATION,
        period_start=date(2024, 4, 1),
        period_end=date(2024, 6, 30),
        unit_ref="INR",
        currency="INR",
        scale=10_000_000,
        decimals=-7,
        provenance=_xbrl_provenance(),
    )


def test_program_and_issuer_quarter_enums() -> None:
    assert ProgramQuarter.QUARTER_1.value == "QUARTER_1"
    assert IssuerQuarter.FY25_Q1.value == "FY25_Q1"


def test_provenance_constructs() -> None:
    prov = _xbrl_provenance()
    assert prov.anchor_type is SourceAnchorType.XBRL_CONTEXT
    assert prov.context_ref == "OneD"


def test_observation_constructs() -> None:
    obs = _revenue_observation()
    assert obs.normalized_value == Decimal("39315")
    assert obs.scope is Scope.CONSOLIDATED


def test_fact_constructs() -> None:
    fact = Fact(
        observation=_revenue_observation(),
        reconciliation_status=ReconciliationStatus.CROSS_SOURCE_CONFIRMED,
        canonical_status=CanonicalStatus.CANONICAL,
        revision_family="infy-fy25q1-revenue",
        valid_time_start=date(2024, 4, 1),
        valid_time_end=date(2024, 6, 30),
        knowledge_time=_RETRIEVED_AT,
        first_seen_time=_RETRIEVED_AT,
    )
    assert fact.observation.concept_qname == "in-bse-fin:RevenueFromOperations"
    assert fact.canonical_status is CanonicalStatus.CANONICAL


def test_guidance_claim_constructs() -> None:
    claim = GuidanceClaim(
        metric="revenue_growth",
        lower_bound=Decimal("3"),
        upper_bound=Decimal("4"),
        unit="percent",
        constant_currency=True,
        horizon="FY25",
        scope=Scope.CONSOLIDATED,
        qualifiers=("constant currency",),
        provenance=Provenance(
            source_id="infy-q1-fy25-results-pdf",
            file_sha256="a" * 64,
            anchor_type=SourceAnchorType.PDF_SPAN,
            page=1,
            block=3,
            span="12:44",
            retrieved_at=_RETRIEVED_AT,
        ),
    )
    assert claim.epistemic_class is EpistemicClass.FORECAST
    assert claim.constant_currency is True


def test_models_are_frozen() -> None:
    obs = _revenue_observation()
    with pytest.raises(ValidationError):
        obs.normalized_value = Decimal("0")  # type: ignore[misc]


def test_manifest_parses_and_has_expected_keys() -> None:
    payload = json.loads(MANIFEST_PATH.read_text())

    for key in ("manifest_id", "issuer", "period", "taxonomy", "sources", "facts", "distractors"):
        assert key in payload, key

    assert payload["basis"] == "consolidated"
    assert payload["period"] == {"type": "duration", "start": "2024-04-01", "end": "2024-06-30"}


def test_manifest_carries_six_verified_facts() -> None:
    payload = json.loads(MANIFEST_PATH.read_text())
    facts = payload["facts"]

    assert len(facts) == 6
    assert {fact["label"] for fact in facts} == EXPECTED_FACT_LABELS

    by_label = {fact["label"]: fact for fact in facts}
    assert by_label["Revenue from operations"]["normalized_value"] == "39315"
    assert by_label["Total income"]["normalized_value"] == "40153"
    assert by_label["Total expenses"]["normalized_value"] == "31132"
    assert by_label["Profit before tax"]["normalized_value"] == "9021"
    assert by_label["Profit for the period"]["normalized_value"] == "6374"
    assert by_label["Profit for the period"]["concept_qname"] == "in-bse-fin:ProfitLossForPeriod"
    assert by_label["Basic EPS"]["normalized_value"] == "15.38"

    for fact in facts:
        assert fact["scope"] == "consolidated"
        assert fact["context_ref"] == "OneD"


def test_manifest_carries_standalone_distractors() -> None:
    payload = json.loads(MANIFEST_PATH.read_text())
    distractors = payload["distractors"]

    standalone = [dist for dist in distractors if dist["scope"] == "standalone"]
    normalized = {dist["normalized_value"] for dist in standalone}
    assert "5768" in normalized  # standalone PAT
    assert "13.90" in normalized  # standalone EPS

    traps = {dist["trap"] for dist in distractors}
    assert {"standalone-vs-consolidated", "segment-dimension", "concept-mismatch"} <= traps
