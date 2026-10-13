"""Retained raw Screener evidence through the public offline extraction seam."""

from __future__ import annotations

from fractions import Fraction
from importlib import import_module
from typing import Any

import pytest
from vendor_retained_support import QUARTER, SALES_ORACLE, identifiers, retained_page

from fundamentals.contracts.evidence import KnowledgeTimeStatus, PrecisionKind
from fundamentals.ingest.screener_financials_models import Section
from fundamentals.ingest.screener_session_models import BasisTopology


def adapter() -> Any:
    try:
        return import_module("fundamentals.evidence.vendor_screener")
    except ModuleNotFoundError:
        pytest.fail("retained Screener extraction has not been built")


def binding(symbol: str = "THERMAX") -> Any:
    ids = identifiers(symbol)
    return adapter().ScreenerIssuerBinding(
        symbol=symbol,
        company_id=ids["screener_company_id"],
        bse_code=ids["bse_scrip"],
        topology=BasisTopology(
            consolidated_warehouse_id=ids["screener_warehouse_id_consolidated"],
            standalone_warehouse_id=ids["screener_warehouse_id_standalone"],
        ),
        identity_evidence_ref="config/watchlist.yaml",
    )


@pytest.mark.parametrize("symbol,printed", SALES_ORACLE.items())
def test_retained_quarter_sales_preserve_native_units_period_and_honest_clocks(
    symbol: str,
    printed: int,
) -> None:
    request, capture, body = retained_page(symbol)
    result = adapter().extract_screener_page(
        request, body=body, capture=capture, binding=binding(symbol), section=Section.QUARTERS
    )
    cell = next(
        item
        for item in result.occurrences
        if item.native_field == "Sales" and item.period == QUARTER
    )
    assert Fraction(cell.raw_value_text.replace(",", "")) * 10**cell.raw_scale == Fraction(
        printed * 10_000_000
    )
    assert cell.raw_unit == "INR" and cell.raw_scale == 7
    assert cell.precision_kind is PrecisionKind.FINITE and cell.declared_precision == 0
    assert cell.knowledge_time is None and cell.knowledge_time_status is KnowledgeTimeStatus.UNKNOWN
    assert cell.first_seen_at == capture.first_seen_at
    assert cell.anchor["table_id"] == "quarters:data-table"
    assert cell.anchor["column_label"] == "Dec 2024"
    assert result.outcome.value == "COMPLETE"


def test_hash_mismatch_is_refused_before_extraction() -> None:
    request, capture, body = retained_page()
    with pytest.raises(adapter().ScreenerExtractionError) as raised:
        adapter().extract_screener_page(
            request, body=body + b" ", capture=capture, binding=binding(), section=Section.QUARTERS
        )
    assert raised.value.outcome.value == "FAILED"


def test_wrong_issuer_binding_is_refused() -> None:
    request, capture, body = retained_page()
    with pytest.raises(adapter().ScreenerExtractionError) as raised:
        adapter().extract_screener_page(
            request, body=body, capture=capture, binding=binding("TITAN"), section=Section.QUARTERS
        )
    assert raised.value.outcome.value in ("IDENTITY_REJECTED", "PARSE_FAILED")


def test_schedule_other_income_keeps_nonzero_exceptional_lexeme_and_separate_capture() -> None:
    from vendor_retained_support import RAW_ROOT, retained_schedule

    page_request, page_capture, page_body = retained_page("SONACOMS")
    request, capture, body = retained_schedule("SONACOMS", "quarters", "Other Income")
    metadata = (
        RAW_ROOT / "screener-financials/SONACOMS/consolidated/screener_financials_meta.json"
    ).read_bytes()
    result = adapter().extract_screener_schedule(
        request,
        body=body,
        capture=capture,
        page_request=page_request,
        page_body=page_body,
        page_capture=page_capture,
        binding=binding("SONACOMS"),
        section=Section.QUARTERS,
        parent="Other Income",
        metadata_body=metadata,
    )
    exceptional = next(
        item
        for item in result.occurrences
        if item.native_field == "Exceptional items" and item.period == QUARTER
    )
    assert exceptional.raw_value_text == "-5.70"
    assert exceptional.raw_sign == -1 and exceptional.declared_precision == 2
    assert exceptional.capture == capture and exceptional.capture != page_capture
    assert exceptional.anchor["json_path"] == ["Exceptional items", "Dec 2024"]
    assert exceptional.disclosure["supporting_page_sha256"] == page_capture.blob_sha256
    assert exceptional.knowledge_time is None


def test_unverified_surface_claim_survives_a_complete_package_flag() -> None:
    from vendor_retained_support import RAW_ROOT, retained_schedule

    page_request, page_capture, page_body = retained_page("LAURUSLABS")
    request, capture, body = retained_schedule("LAURUSLABS", "quarters", "Net Profit")
    metadata = (
        RAW_ROOT / "screener-financials/LAURUSLABS/consolidated/screener_financials_meta.json"
    ).read_bytes()
    result = adapter().extract_screener_schedule(
        request,
        body=body,
        capture=capture,
        page_request=page_request,
        page_body=page_body,
        page_capture=page_capture,
        binding=binding("LAURUSLABS"),
        section=Section.QUARTERS,
        parent="Net Profit",
        metadata_body=metadata,
    )
    assert result.outcome.value == "PARTIAL"
    assert result.occurrences
    assert all(
        item.disclosure["capture_complete_claim"] is True
        and item.disclosure["surface_unverified"] is True
        for item in result.occurrences
    )


@pytest.mark.parametrize(
    "raw,state",
    [(None, "SOURCE_NULL"), ("", "BLANK"), ("-", "DASH"), ("0", "ZERO_PRINTED"), ("bad", "VALUE")],
)
def test_schedule_missing_and_invalid_lexemes_survive_without_zero_fill(
    raw: object, state: str
) -> None:
    import json

    from vendor_retained_support import marked_body, retained_schedule

    page_request, page_capture, page_body = retained_page()
    request, capture, original = retained_schedule("THERMAX", "quarters", "Other Income")
    document = json.loads(original)
    document["Exceptional items"]["Dec 2024"] = raw
    body = json.dumps(document).encode()
    request, capture = marked_body(request, capture, body)
    result = adapter().extract_screener_schedule(
        request,
        body=body,
        capture=capture,
        page_request=page_request,
        page_body=page_body,
        page_capture=page_capture,
        binding=binding(),
        section=Section.QUARTERS,
        parent="Other Income",
    )
    cell = next(
        item
        for item in result.occurrences
        if item.native_field == "Exceptional items" and item.period == QUARTER
    )
    assert cell.raw_value_text == raw and cell.missing_state.value == state
    if raw == "0":
        assert cell.precision_kind is PrecisionKind.FINITE
    else:
        assert cell.precision_kind is PrecisionKind.UNSUPPORTED


def test_source_other_income_maps_to_aggregate_and_not_plain_income(tmp_path: Any) -> None:
    from datetime import UTC, datetime

    from vendor_retained_support import draft_config

    from fundamentals.contracts.canonical import PeriodKind
    from fundamentals.contracts.evidence_tier import EvidenceTier
    from fundamentals.contracts.qualification import QualificationContext
    from fundamentals.evidence.interpret import interpret

    dictionary, mappings, policy = draft_config(tmp_path)
    request, capture, body = retained_page("SONACOMS")
    extracted = adapter().extract_screener_page(
        request, body=body, capture=capture, binding=binding("SONACOMS"), section=Section.QUARTERS
    )
    occurrence = next(
        item
        for item in extracted.occurrences
        if item.native_field == "Other Income" and item.period == QUARTER
    )
    interpreted = interpret(
        occurrence.model_copy(update={"occurrence_id": 1}),
        entity_id=request.entity_id,
        basis=request.basis,
        framework=request.framework,
        mapping_set=mappings,
        policy=policy,
        dictionary=dictionary,
        fiscal_year_end_month=3,
        qualification=QualificationContext(
            schema_identity=request.schema_identity,
            surface=request.surface,
            basis=request.basis,
            period_kind=PeriodKind.QUARTER,
            proven={},
        ),
        recorded_at=datetime.now(UTC),
    )
    assert interpreted.canonical_id == "other_income_incl_exceptional"
    assert Fraction(interpreted.value) == 410_000_000
    # Source-independent XML OneD facts: OtherIncome467906000 + Exceptional-56992000.
    assert interpreted.interval is not None
    assert interpreted.interval.lower <= Fraction(410_914_000) <= interpreted.interval.upper
    assert not interpreted.interval.lower <= Fraction(467_906_000) <= interpreted.interval.upper
    assert interpreted.tier is EvidenceTier.EQUIVALENCE_UNPROVEN


def test_page_total_liabilities_never_maps_to_a_liabilities_key(tmp_path: Any) -> None:
    from datetime import UTC, datetime

    from vendor_retained_support import draft_config

    from fundamentals.contracts.canonical import PeriodKind, StatementFamily
    from fundamentals.contracts.qualification import QualificationContext
    from fundamentals.evidence.interpret import interpret

    dictionary, mappings, policy = draft_config(tmp_path)
    request, capture, body = retained_page()
    request = request.model_copy(update={"statement_family": StatementFamily.BALANCE_SHEET})
    extracted = adapter().extract_screener_page(
        request, body=body, capture=capture, binding=binding(), section=Section.BALANCE_SHEET
    )
    occurrence = next(
        item for item in extracted.occurrences if item.native_field == "Total Liabilities"
    )
    interpreted = interpret(
        occurrence.model_copy(update={"occurrence_id": 1}),
        entity_id=request.entity_id,
        basis=request.basis,
        framework=request.framework,
        mapping_set=mappings,
        policy=policy,
        dictionary=dictionary,
        fiscal_year_end_month=3,
        qualification=QualificationContext(
            schema_identity=request.schema_identity,
            surface=request.surface,
            basis=request.basis,
            period_kind=PeriodKind.INSTANT,
            proven={},
        ),
        recorded_at=datetime.now(UTC),
    )
    assert interpreted.status.value == "UNMAPPED" and interpreted.canonical_id is None
    assert interpreted.value is None


def test_public_retained_reader_refuses_another_authority_surface() -> None:
    from vendor_retained_support import RAW_ROOT, SOURCE

    from fundamentals.contracts.source_catalog import (
        EvidenceRole,
        SourceCatalog,
        SourceClass,
        SourceDescriptor,
        SurfaceAuthority,
    )
    from fundamentals.evidence.vendor_common import VendorAuthorityError
    from fundamentals.store.snapshot_store import DirectoryAnchor

    request, capture, _ = retained_page()
    catalog = SourceCatalog.of(
        SourceDescriptor(
            source_id=SOURCE,
            source_class=SourceClass.DERIVED,
            evidence_role=EvidenceRole.RECONCILABLE,
        )
    )
    authority = SurfaceAuthority(
        source_id=SOURCE,
        surface="SCREENER_SCHEDULE",
        representation=request.representation,
        evidence_role=EvidenceRole.RECONCILABLE,
        authority_ref="constructed refusal test",
        authority_sha256="a" * 64,
    )
    with pytest.raises(VendorAuthorityError):
        adapter().read_retained_screener_page(
            request,
            input_anchor=DirectoryAnchor(RAW_ROOT),
            capture=capture,
            binding=binding(),
            section=Section.QUARTERS,
            catalog=catalog,
            authority=authority,
        )


def test_retained_page_and_schedule_generation_roundtrip_through_guarded_postgres(
    pg_db: Any, tmp_path: Any
) -> None:
    from pg_evidence_schema_support import _insert
    from vendor_retained_support import RAW_ROOT, draft_config, retained_schedule, stage_registered

    from fundamentals.evidence.capture_interpretation import CaptureScope, interpret_generation
    from fundamentals.evidence.repository import EvidenceRepository

    dictionary, mappings, policy = draft_config(tmp_path)
    with pg_db.migrator_connection() as conn:
        evidence = _insert(
            conn,
            "evidence_inputs",
            {
                "kind": "ISSUER_IDENTITY",
                "label": "retained Screener test scope",
                "content_sha256": "a" * 64,
            },
        )
        entity = _insert(
            conn,
            "reporting_entities",
            {
                "entity_key": "SCREENER-TEST-THERMAX",
                "market": "IN",
                "display_name": "Thermax test entity",
                "evidence_input_id": evidence,
            },
        )
    page_request, _, page_body = retained_page()
    request, _, schedule_body = retained_schedule("THERMAX", "quarters", "Other Income")
    page_request = page_request.model_copy(update={"entity_id": entity})
    request = request.model_copy(update={"entity_id": entity})
    with pg_db.runtime_pool() as pool:
        repository = EvidenceRepository(pool)
        before = repository.store_clock()
        from fundamentals.store.snapshot_store import SnapshotStore

        store_root = tmp_path / "snapshots"
        store_root.mkdir(mode=0o700)
        store = SnapshotStore(store_root)
        page_capture = stage_registered(page_request, repository, store)
        schedule_capture = stage_registered(request, repository, store)
        assert before <= page_capture.first_seen_at <= repository.store_clock()
        assert page_capture.first_seen_at == page_capture.registered_at
        page = adapter().extract_screener_page(
            page_request,
            body=page_body,
            capture=page_capture,
            binding=binding(),
            section=Section.QUARTERS,
        )
        schedule = adapter().extract_screener_schedule(
            request,
            body=schedule_body,
            capture=schedule_capture,
            page_request=page_request,
            page_body=page_body,
            page_capture=page_capture,
            binding=binding(),
            section=Section.QUARTERS,
            parent="Other Income",
            metadata_body=(
                RAW_ROOT / "screener-financials/THERMAX/consolidated/screener_financials_meta.json"
            ).read_bytes(),
        )
        for scope_request, scope_capture, extracted in [
            (page_request, page_capture, page),
            (request, schedule_capture, schedule),
        ]:
            occurrences = repository.put_occurrences(extracted.occurrences)
            interpretations = interpret_generation(
                occurrences,
                scope=CaptureScope(
                    capture=scope_capture,
                    entity_id=entity,
                    basis=scope_request.basis,
                    framework=scope_request.framework,
                    mapping_set=mappings,
                    policy=policy,
                    dictionary=dictionary,
                    fiscal_year_end_month=3,
                ),
                prior=(),
                prior_anchor_keys={},
                reserve_ids=repository.reserve_interpretation_ids,
                recorded_at=repository.store_clock(),
            )
            repository.put_interpretations(interpretations)
            assert (
                repository.get_occurrences(tuple(item.occurrence_id for item in occurrences))
                == occurrences
            )
            saved = repository.get_interpretations(
                tuple(item.interpretation_id for item in interpretations)
            )
            assert len(saved) == len(interpretations)
            assert all(item.capture_ref_id == scope_capture.capture_ref_id for item in saved)
        sales = next(
            item
            for item in repository.list_capture_interpretations(page_capture.capture_ref_id)
            if item.canonical_id == "revenue_from_operations" and item.period == QUARTER
        )
        assert Fraction(sales.value) == 25_290_000_000
        assert sales.transform_trace["raw_value_text"] == "2,529"


def test_caller_cannot_convert_retrieval_claim_to_publication_time() -> None:
    from datetime import UTC, datetime

    request, capture, body = retained_page()
    request = request.model_copy(
        update={
            "knowledge_time": datetime(2026, 9, 4, tzinfo=UTC),
            "knowledge_time_evidence_ref": "metadata fetched_at claim",
        }
    )
    with pytest.raises(adapter().ScreenerExtractionError) as raised:
        adapter().extract_screener_page(
            request, body=body, capture=capture, binding=binding(), section=Section.QUARTERS
        )
    assert raised.value.outcome.value == "FAILED"
