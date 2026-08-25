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
from typing import Any

import pytest
from pydantic import ValidationError

from fundamentals.contracts import (
    AccountingFramework,
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


def test_provenance_pdf_span_requires_page_block_span() -> None:
    with pytest.raises(ValidationError):
        Provenance(
            source_id="infy-q1-fy25-results-pdf",
            file_sha256="a" * 64,
            anchor_type=SourceAnchorType.PDF_SPAN,
            page=11,  # block and span missing
            retrieved_at=_RETRIEVED_AT,
        )


def test_provenance_xbrl_context_requires_context_ref() -> None:
    with pytest.raises(ValidationError):
        Provenance(
            source_id="nse-indas-xbrl-consolidated",
            file_sha256="0" * 64,
            anchor_type=SourceAnchorType.XBRL_CONTEXT,
            context_ref=None,
            retrieved_at=_RETRIEVED_AT,
        )


def test_provenance_json_island_requires_typed_location_fields() -> None:
    with pytest.raises(ValidationError, match="JSON_ISLAND anchor requires"):
        Provenance(
            source_id="tijori",
            file_sha256="0" * 64,
            anchor_type=SourceAnchorType.JSON_ISLAND,
            context_ref="https://example.invalid/#fin_tables_data/qt_c/Dec 2024/tijori:sales",
            retrieved_at=_RETRIEVED_AT,
        )


def test_provenance_api_document_requires_typed_location_fields() -> None:
    """An API anchor without its location triple could not be re-fetched or compared."""
    with pytest.raises(ValidationError, match="API_DOCUMENT anchor requires"):
        Provenance(
            source_id="tijori",
            file_sha256="0" * 64,
            anchor_type=SourceAnchorType.API_DOCUMENT,
            document_id="api:cash_flow_waterfall",
            retrieved_at=_RETRIEVED_AT,
        )


def test_provenance_api_document_requires_the_full_request_path() -> None:
    """Without context_ref the anchor names an API but not which request made it."""
    with pytest.raises(ValidationError, match="API_DOCUMENT anchor requires"):
        Provenance(
            source_id="tijori",
            file_sha256="0" * 64,
            anchor_type=SourceAnchorType.API_DOCUMENT,
            document_id="api:cash_flow_waterfall",
            table_key="1yr",
            row_label="0/WCC",
            column_label="y",
            retrieved_at=_RETRIEVED_AT,
        )


def test_provenance_api_document_rejects_an_island_id() -> None:
    """An API anchor carrying island fields would read as a page island downstream."""
    with pytest.raises(ValidationError, match="must not set island_id"):
        Provenance(
            source_id="tijori",
            file_sha256="0" * 64,
            anchor_type=SourceAnchorType.API_DOCUMENT,
            context_ref="https://example.invalid/api/v1/ind/cash_flow_waterfall/81/#1yr",
            document_id="api:cash_flow_waterfall",
            island_id="fin_tables_data",
            table_key="1yr",
            row_label="0/WCC",
            column_label="y",
            retrieved_at=_RETRIEVED_AT,
        )


def test_provenance_json_island_rejects_api_and_html_fields() -> None:
    """The rejection is symmetric: no anchor kind may borrow another's addressing."""
    with pytest.raises(ValidationError, match="must not set column_index, document_id"):
        Provenance(
            source_id="tijori",
            file_sha256="0" * 64,
            anchor_type=SourceAnchorType.JSON_ISLAND,
            context_ref="https://example.invalid/#fin_tables_data/qt_c/Dec 2024/x",
            island_id="fin_tables_data",
            document_id="api:cash_flow_waterfall",
            table_key="qt_c",
            row_label="Net Sales",
            column_label="Dec 2024",
            column_index=0,
            retrieved_at=_RETRIEVED_AT,
        )


def test_provenance_html_table_rejects_island_and_api_fields() -> None:
    """Symmetric with the island and API rules, and safe for every committed producer."""
    with pytest.raises(ValidationError, match="must not set island_id"):
        Provenance(
            source_id="tijori",
            file_sha256="0" * 64,
            anchor_type=SourceAnchorType.HTML_TABLE,
            table_id="shareholding",
            row_path="promoters",
            row_label="Promoters",
            column_index=0,
            column_label="Dec 2024",
            island_id="fin_tables_data",
            retrieved_at=_RETRIEVED_AT,
        )


def test_provenance_valid_anchors_construct() -> None:
    pdf = Provenance(
        source_id="infy-q1-fy25-results-pdf",
        file_sha256="a" * 64,
        anchor_type=SourceAnchorType.PDF_SPAN,
        page=11,
        block=3,
        span="12:44",
        retrieved_at=_RETRIEVED_AT,
    )
    assert pdf.anchor_type is SourceAnchorType.PDF_SPAN

    xbrl = _xbrl_provenance()
    assert xbrl.context_ref == "OneD"


def _opt_date(value: str | None) -> date | None:
    return date.fromisoformat(value) if value else None


def _provenance_for(entry: dict[str, Any]) -> Provenance:
    """Build an XBRL-anchored Provenance from a manifest fact/distractor entry."""
    provenance = entry.get("provenance", {})
    return Provenance(
        source_id=entry.get("source_id", "nse-indas-xbrl-consolidated"),
        file_sha256="0" * 64,
        anchor_type=SourceAnchorType.XBRL_CONTEXT,
        page=provenance.get("page"),
        context_ref=entry["context_ref"],
        retrieved_at=_RETRIEVED_AT,
    )


def _observation_for(entry: dict[str, Any], payload: dict[str, Any]) -> Observation:
    """Map a manifest fact/distractor onto the Observation contract vocabulary."""
    taxonomy = payload["taxonomy"]
    issuer = payload["issuer"]
    dimensions = tuple((axis, member) for axis, member in entry.get("dimensions", []))
    return Observation(
        concept_qname=entry["concept_qname"],
        taxonomy_namespace=taxonomy["namespace"],
        registry_version=f"{taxonomy['registry']}/{taxonomy['version']}",
        raw_value=entry["raw_value"],
        normalized_value=Decimal(entry["normalized_value"]),
        normalized_unit=entry["normalized_unit"],
        context_ref=entry["context_ref"],
        entity_scheme="nse-symbol",
        entity_id=issuer["nse_symbol"],
        scope=Scope(entry["scope"]),
        accounting_basis=AccountingFramework.IND_AS,
        period_type=PeriodType(entry["period_type"]),
        period_start=_opt_date(entry.get("period_start")),
        period_end=_opt_date(entry.get("period_end")),
        period_instant=_opt_date(entry.get("period_instant")),
        unit_ref=entry.get("unit_ref"),
        currency=entry.get("currency", payload["reporting_currency"]),
        scale=entry["scale"],
        decimals=entry["decimals"],
        dimensions=dimensions,
        provenance=_provenance_for(entry),
    )


def test_every_oracle_fact_maps_onto_observation_contract() -> None:
    payload = json.loads(MANIFEST_PATH.read_text())
    facts = payload["facts"]

    observations = {fact["label"]: _observation_for(fact, payload) for fact in facts}
    assert len(observations) == 6

    profit = observations["Profit for the period"]
    assert profit.concept_qname == "in-bse-fin:ProfitLossForPeriod"
    assert profit.normalized_value == Decimal("6374")
    assert profit.scope is Scope.CONSOLIDATED
    assert profit.accounting_basis is AccountingFramework.IND_AS
    assert profit.provenance.anchor_type is SourceAnchorType.XBRL_CONTEXT
    assert profit.provenance.context_ref == "OneD"
    assert profit.provenance.page == 11


def test_valued_distractors_construct_and_are_marked_reject() -> None:
    payload = json.loads(MANIFEST_PATH.read_text())
    distractors = payload["distractors"]

    for dist in distractors:
        assert dist["trap"]  # every distractor carries an explicit reject marker
        assert dist["reason"]
        if "raw_value" in dist:
            obs = _observation_for(dist, payload)
            assert obs.concept_qname == dist["concept_qname"]
            assert obs.scope is Scope(dist["scope"])

    valued = [dist for dist in distractors if "raw_value" in dist]
    assert len(valued) == 3

    # The segment-dimension trap is a value-free structural distractor: it carries
    # a dimension shape rather than a (fabricated) segment number.
    segment = [dist for dist in distractors if dist["trap"] == "segment-dimension"]
    assert len(segment) == 1
    assert segment[0]["dimensions"]
    assert "raw_value" not in segment[0]


def test_fourth_cross_foot_identity_is_encoded_and_holds() -> None:
    payload = json.loads(MANIFEST_PATH.read_text())
    identities = payload["cross_foot_identities"]

    assert len(identities) == 4
    nci_identity = identities[3]
    assert nci_identity["expected"] == "6374 = 6368 + 6"
    assert 6368 + 6 == 6374
