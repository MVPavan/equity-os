"""Retained Screener liabilities construction through extraction and durable storage."""

from __future__ import annotations

import hashlib
from datetime import date
from decimal import Decimal
from fractions import Fraction
from pathlib import Path
from typing import Any, cast

import pytest
from pg_evidence_schema_support import _insert
from vendor_retained_support import (
    draft_config,
    extractor_pin,
    identifiers,
    retained_page,
    stage_registered,
)

from fundamentals.contracts.canonical import Basis, StatementFamily
from fundamentals.contracts.evidence import (
    InterpretationOrigin,
    InterpretationReason,
    InterpretationStatus,
)
from fundamentals.contracts.evidence_tier import EvidenceTier
from fundamentals.contracts.interval import Interval
from fundamentals.contracts.measurement_key import PeriodInterval
from fundamentals.evidence.capture_interpretation import CaptureScope, interpret_generation
from fundamentals.evidence.native_construction import (
    NativeConstructionDefect,
    NativeConstructionError,
)
from fundamentals.evidence.repository import EvidenceRepository
from fundamentals.evidence.vendor_screener import ScreenerIssuerBinding, extract_screener_page
from fundamentals.ingest.screener_financials_models import Section
from fundamentals.ingest.screener_session_models import BasisTopology
from fundamentals.store.snapshot_store import SnapshotStore

pytestmark = pytest.mark.pg

TARGET_PERIOD = PeriodInterval.at(date(2025, 3, 31))
TARGET_CANONICAL_ID = "liabilities_incl_nci"
THERMAX_BODY_SHA256 = "6894f0979643755a618a6e8f572dc63ee3efb61abb6495ddf4766d5ec678f0ad"
HFCL_BODY_SHA256 = "4fefad29dfb80061be461597fd6b1bd1150c87ce8d2c59820cfaed4b4291e236"
SCREENER_EXTRACTOR_VERSION = "screener-v1"


def _binding(symbol: str) -> ScreenerIssuerBinding:
    identity = identifiers(symbol)
    return ScreenerIssuerBinding(
        symbol=symbol,
        company_id=identity["screener_company_id"],
        bse_code=identity["bse_scrip"],
        topology=BasisTopology(
            consolidated_warehouse_id=identity["screener_warehouse_id_consolidated"],
            standalone_warehouse_id=identity["screener_warehouse_id_standalone"],
        ),
        identity_evidence_ref="config/watchlist.yaml",
    )


def _entity(pg_db: Any, symbol: str) -> int:
    with pg_db.migrator_connection() as connection:
        evidence = _insert(
            connection,
            "evidence_inputs",
            {
                "kind": "ISSUER_IDENTITY",
                "label": f"retained Screener native construction test scope: {symbol}",
                "content_sha256": "a" * 64,
            },
        )
        return cast(
            int,
            _insert(
                connection,
                "reporting_entities",
                {
                    "entity_key": f"SCREENER-NATIVE-{symbol}",
                    "market": "IN",
                    "display_name": f"{symbol} retained test entity",
                    "evidence_input_id": evidence,
                },
            ),
        )


def _reserve_ids() -> Any:
    next_id = 10_000

    def reserve(count: int) -> tuple[int, ...]:
        nonlocal next_id
        ids = tuple(range(next_id, next_id + count))
        next_id += count
        return ids

    return reserve


def _prepared_source(
    tmp_path: Path, symbol: str = "THERMAX"
) -> tuple[Any, Any, Any, Any, Any, tuple[Any, ...]]:
    dictionary, mappings, policy = draft_config(tmp_path)
    request, capture, body = retained_page(symbol)
    request = request.model_copy(update={"statement_family": StatementFamily.BALANCE_SHEET})
    extracted = extract_screener_page(
        body,
        basis=request.basis,
        capture=capture,
        binding=_binding(symbol),
        section=Section.BALANCE_SHEET,
        extractor_version=SCREENER_EXTRACTOR_VERSION,
    )
    occurrences = tuple(
        occurrence.model_copy(update={"occurrence_id": index})
        for index, occurrence in enumerate(extracted.occurrences, start=1)
    )
    return dictionary, mappings, policy, request, capture, occurrences


def _interpret_source(
    prepared: tuple[Any, Any, Any, Any, Any, tuple[Any, ...]],
    *,
    occurrences: tuple[Any, ...] | None = None,
    basis: Basis | None = None,
    capture: Any | None = None,
) -> tuple[Any, ...]:
    dictionary, mappings, policy, request, source_capture, source_occurrences = prepared
    return cast(
        tuple[Any, ...],
        interpret_generation(
            occurrences or source_occurrences,
            scope=CaptureScope.model_validate(
                {
                    "capture": capture or source_capture,
                    "entity_id": request.entity_id,
                    "basis": basis or request.basis,
                    "framework": request.framework,
                    "mapping_set": mappings,
                    "policy": policy,
                    "dictionary": dictionary,
                    "fiscal_year_end_month": 3,
                    "expected_extractor_pin": extractor_pin("SCREENER_FINANCIALS"),
                }
            ),
            prior=(),
            prior_anchor_keys={},
            reserve_ids=_reserve_ids(),
            recorded_at=source_capture.registered_at,
        ),
    )


def test_thermax_native_rows_construct_the_hand_read_liabilities_aggregate(
    tmp_path: Path,
) -> None:
    """The public extraction/generation seam emits the independently calculated sum."""
    dictionary, mappings, policy = draft_config(tmp_path)
    request, capture, body = retained_page("THERMAX")
    request = request.model_copy(update={"statement_family": StatementFamily.BALANCE_SHEET})
    assert hashlib.sha256(body).hexdigest() == THERMAX_BODY_SHA256
    extracted = extract_screener_page(
        body,
        basis=request.basis,
        capture=capture,
        binding=_binding("THERMAX"),
        section=Section.BALANCE_SHEET,
        extractor_version=SCREENER_EXTRACTOR_VERSION,
    )
    occurrences = tuple(
        occurrence.model_copy(update={"occurrence_id": index})
        for index, occurrence in enumerate(extracted.occurrences, start=1)
    )
    rows = interpret_generation(
        occurrences,
        scope=CaptureScope.model_validate(
            {
                "capture": capture,
                "entity_id": request.entity_id,
                "basis": Basis.CONSOLIDATED,
                "framework": request.framework,
                "mapping_set": mappings,
                "policy": policy,
                "dictionary": dictionary,
                "fiscal_year_end_month": 3,
                "expected_extractor_pin": extractor_pin("SCREENER_FINANCIALS"),
            }
        ),
        prior=(),
        prior_anchor_keys={},
        reserve_ids=_reserve_ids(),
        recorded_at=capture.registered_at,
    )

    occurrence_by_id = {
        occurrence.occurrence_id: occurrence
        for occurrence in occurrences
        if occurrence.occurrence_id is not None
    }
    native_direct = {
        occurrence_by_id[row.occurrence_id].native_field: row
        for row in rows
        if row.occurrence_id in occurrence_by_id
        and occurrence_by_id[row.occurrence_id].period == TARGET_PERIOD
        and occurrence_by_id[row.occurrence_id].native_field
        in {"Borrowings", "Other Liabilities", "Total Liabilities"}
    }
    assert set(native_direct) == {"Borrowings", "Other Liabilities", "Total Liabilities"}
    assert all(
        row.origin is InterpretationOrigin.DIRECT
        and row.status is InterpretationStatus.UNMAPPED
        and row.mapping_entry_id is None
        and row.canonical_id is None
        and row.key is None
        and row.value is None
        for row in native_direct.values()
    )
    constructed = [
        row
        for row in rows
        if row.origin is InterpretationOrigin.CONSTRUCTED
        and row.canonical_id == TARGET_CANONICAL_ID
        and row.period == TARGET_PERIOD
    ]
    assert len(constructed) == 1, "retained native liabilities aggregate is missing"
    aggregate = constructed[0]
    assert aggregate.status is InterpretationStatus.MAPPED
    assert aggregate.value == Decimal("64460000000")
    assert aggregate.interval == Interval(
        lower=Fraction(64_450_000_000), upper=Fraction(64_470_000_000)
    )
    assert aggregate.tier is EvidenceTier.EQUIVALENCE_UNPROVEN
    trace_pins = aggregate.transform_trace["pins"]
    assert isinstance(trace_pins, dict)
    assert trace_pins["extractor"] == extractor_pin("SCREENER_FINANCIALS").model_dump(mode="json")
    assert aggregate.operand_interpretation_ids == (
        native_direct["Borrowings"].interpretation_id,
        native_direct["Other Liabilities"].interpretation_id,
    )
    assert native_direct["Total Liabilities"].interpretation_id not in set(
        aggregate.operand_interpretation_ids
    )


def test_missing_retained_operand_is_value_less_and_never_zero_filled(tmp_path: Path) -> None:
    """Removing the Mar 2025 source row records missing evidence, never an invented zero."""
    prepared = _prepared_source(tmp_path)
    occurrences = tuple(
        occurrence
        for occurrence in prepared[-1]
        if not (
            occurrence.native_field == "Other Liabilities" and occurrence.period == TARGET_PERIOD
        )
    )
    rows = _interpret_source(prepared, occurrences=occurrences)
    (aggregate,) = [
        row
        for row in rows
        if row.origin is InterpretationOrigin.CONSTRUCTED
        and row.canonical_id == TARGET_CANONICAL_ID
        and row.period == TARGET_PERIOD
    ]

    assert aggregate.status is InterpretationStatus.MAPPED
    assert aggregate.value is None and aggregate.interval is None
    assert aggregate.transform_trace["missing_operands"] == ["other_liabilities"]
    assert len(aggregate.operand_interpretation_ids) == 1


def test_hfcl_native_rows_match_the_second_hand_read_source_oracle(tmp_path: Path) -> None:
    """The second retained issuer proves the rule is source-shaped, not company-corrected."""
    prepared = _prepared_source(tmp_path, "HFCL")
    assert prepared[4].blob_sha256 == HFCL_BODY_SHA256
    rows = _interpret_source(prepared)
    (aggregate,) = [
        row
        for row in rows
        if row.origin is InterpretationOrigin.CONSTRUCTED
        and row.canonical_id == TARGET_CANONICAL_ID
        and row.period == TARGET_PERIOD
    ]

    assert aggregate.status is InterpretationStatus.MAPPED
    assert aggregate.value == Decimal("34670000000")
    assert aggregate.interval == Interval(
        lower=Fraction(34_660_000_000), upper=Fraction(34_680_000_000)
    )
    assert aggregate.tier is EvidenceTier.EQUIVALENCE_UNPROVEN


def test_duplicate_retained_operand_invalidates_the_aggregate(tmp_path: Path) -> None:
    """Two same-period Borrowings candidates remain ambiguous instead of first-match-wins."""
    prepared = _prepared_source(tmp_path)
    source_occurrences = prepared[-1]
    borrowings = next(
        occurrence
        for occurrence in source_occurrences
        if occurrence.native_field == "Borrowings" and occurrence.period == TARGET_PERIOD
    )
    duplicate = borrowings.model_copy(
        update={
            "occurrence_id": max(item.occurrence_id for item in source_occurrences) + 1,
            "anchor_key": f"{borrowings.anchor_key}:duplicate-candidate",
        }
    )
    rows = _interpret_source(prepared, occurrences=(*source_occurrences, duplicate))
    (aggregate,) = [
        row
        for row in rows
        if row.origin is InterpretationOrigin.CONSTRUCTED
        and row.canonical_id == TARGET_CANONICAL_ID
        and row.period == TARGET_PERIOD
    ]

    assert aggregate.status is InterpretationStatus.INVALID
    assert aggregate.reason is InterpretationReason.INTERPRETATION_AMBIGUOUS
    assert aggregate.value is None and aggregate.interval is None
    assert len(aggregate.transform_trace["operands"]["borrowings"]["candidates"]) == 2
    assert len(aggregate.operand_interpretation_ids) == 3


def test_standalone_retained_page_cannot_broaden_the_consolidated_rule(tmp_path: Path) -> None:
    """A real standalone page is inapplicable and emits no consolidated aggregate."""
    prepared = _prepared_source(tmp_path, "NETWEB")
    assert prepared[3].basis is Basis.STANDALONE
    rows = _interpret_source(prepared)

    assert not any(
        row.origin is InterpretationOrigin.CONSTRUCTED and row.canonical_id == TARGET_CANONICAL_ID
        for row in rows
    )


def test_cross_capture_retained_operand_refuses_the_generation(tmp_path: Path) -> None:
    """One matching row from another capture cannot enter the same construction."""
    prepared = _prepared_source(tmp_path)
    source_capture = prepared[4]
    assert source_capture.capture_ref_id is not None
    other_capture = source_capture.model_copy(
        update={
            "capture_ref_id": source_capture.capture_ref_id + 1,
            "capture_id": f"{source_capture.capture_id}-other",
        }
    )
    occurrences = tuple(
        occurrence.model_copy(update={"capture": other_capture})
        if occurrence.native_field == "Other Liabilities" and occurrence.period == TARGET_PERIOD
        else occurrence
        for occurrence in prepared[-1]
    )

    with pytest.raises(NativeConstructionError) as raised:
        _interpret_source(prepared, occurrences=occurrences)
    assert raised.value.defect is NativeConstructionDefect.PROVENANCE_MISMATCH


def test_thermax_native_rows_and_aggregate_roundtrip_through_guarded_postgres(
    pg_db: Any, tmp_path: Path
) -> None:
    """Borrowings plus Other Liabilities yields only the evidenced unproven aggregate."""
    dictionary, mappings, policy = draft_config(tmp_path)
    entity_id = _entity(pg_db, "THERMAX")
    request, _, body = retained_page("THERMAX")
    request = request.model_copy(
        update={"entity_id": entity_id, "statement_family": StatementFamily.BALANCE_SHEET}
    )
    assert hashlib.sha256(body).hexdigest() == THERMAX_BODY_SHA256

    with pg_db.runtime_pool() as pool:
        repository = EvidenceRepository(pool)
        before_capture = repository.store_clock()
        snapshot_root = tmp_path / "snapshots"
        snapshot_root.mkdir(mode=0o700)
        capture = stage_registered(request, repository, SnapshotStore(snapshot_root))
        after_capture = repository.store_clock()
        assert before_capture <= capture.registered_at == capture.first_seen_at <= after_capture

        extracted = extract_screener_page(
            body,
            basis=request.basis,
            capture=capture,
            binding=_binding("THERMAX"),
            section=Section.BALANCE_SHEET,
            extractor_version=SCREENER_EXTRACTOR_VERSION,
        )
        source_rows = {
            occurrence.native_field: occurrence
            for occurrence in extracted.occurrences
            if occurrence.period == TARGET_PERIOD
            and occurrence.native_field in {"Borrowings", "Other Liabilities", "Total Liabilities"}
        }
        assert set(source_rows) == {"Borrowings", "Other Liabilities", "Total Liabilities"}
        assert {
            label: (
                row.raw_value_text,
                row.raw_unit,
                row.raw_scale,
                row.declared_precision,
                row.anchor["table_id"],
                row.anchor["column_label"],
            )
            for label, row in source_rows.items()
        } == {
            "Borrowings": ("1,718", "INR", 7, 0, "balance-sheet:data-table", "Mar 2025"),
            "Other Liabilities": (
                "4,728",
                "INR",
                7,
                0,
                "balance-sheet:data-table",
                "Mar 2025",
            ),
            "Total Liabilities": (
                "11,382",
                "INR",
                7,
                0,
                "balance-sheet:data-table",
                "Mar 2025",
            ),
        }

        occurrences = repository.put_occurrences(extracted.occurrences)
        recorded_at = repository.store_clock()
        rows = interpret_generation(
            occurrences,
            scope=CaptureScope.model_validate(
                {
                    "capture": capture,
                    "entity_id": entity_id,
                    "basis": Basis.CONSOLIDATED,
                    "framework": request.framework,
                    "mapping_set": mappings,
                    "policy": policy,
                    "dictionary": dictionary,
                    "fiscal_year_end_month": 3,
                    "expected_extractor_pin": extractor_pin("SCREENER_FINANCIALS"),
                }
            ),
            prior=(),
            prior_anchor_keys={},
            reserve_ids=repository.reserve_interpretation_ids,
            recorded_at=recorded_at,
        )
        repository.put_interpretations(rows)
        stored = repository.get_interpretations(
            tuple(row.interpretation_id for row in rows if row.interpretation_id is not None)
        )

        occurrence_by_id = {
            occurrence.occurrence_id: occurrence
            for occurrence in occurrences
            if occurrence.occurrence_id is not None
        }
        native_direct = {
            occurrence_by_id[row.occurrence_id].native_field: row
            for row in stored
            if row.occurrence_id in occurrence_by_id
            and occurrence_by_id[row.occurrence_id].period == TARGET_PERIOD
            and occurrence_by_id[row.occurrence_id].native_field
            in {"Borrowings", "Other Liabilities", "Total Liabilities"}
        }
        assert set(native_direct) == {"Borrowings", "Other Liabilities", "Total Liabilities"}
        assert all(
            row.origin is InterpretationOrigin.DIRECT
            and row.status is InterpretationStatus.UNMAPPED
            and row.mapping_entry_id is None
            and row.canonical_id is None
            and row.key is None
            and row.value is None
            for row in native_direct.values()
        )

        constructed = [
            row
            for row in stored
            if row.origin is InterpretationOrigin.CONSTRUCTED
            and row.canonical_id == TARGET_CANONICAL_ID
            and row.period == TARGET_PERIOD
        ]
        assert len(constructed) == 1, "retained native liabilities aggregate is missing"
        aggregate = constructed[0]
        assert aggregate.status is InterpretationStatus.MAPPED
        assert aggregate.value == Decimal("64460000000")
        assert aggregate.interval == Interval(
            lower=Fraction(64_450_000_000), upper=Fraction(64_470_000_000)
        )
        assert aggregate.tier is EvidenceTier.EQUIVALENCE_UNPROVEN
        assert aggregate.operand_interpretation_ids == (
            native_direct["Borrowings"].interpretation_id,
            native_direct["Other Liabilities"].interpretation_id,
        )
        assert native_direct["Total Liabilities"].interpretation_id not in set(
            aggregate.operand_interpretation_ids
        )
        assert capture.registered_at <= aggregate.recorded_at == recorded_at
