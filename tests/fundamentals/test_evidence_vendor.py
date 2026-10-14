"""D1b.1 Verify cell: retained vendor captures through ``ingest_vendor`` on PostgreSQL.

One case per Verify claim. Expected lexemes and periods were read by hand from the raw
captures (Tijori island JSON, Upstox bodies, Screener HTML), never from adapter output.
Tijori: ``data/raw/snapshots/v1/tijori`` (2026-09-05); qt_c money intervals follow the display
rule of the retained ``fin-tables.js`` (``config/mappings/tijori/v1/display.yaml``). Upstox:
``data/raw/snapshots/v1/upstox`` (owner-authorised live fetch, 2026-10-14). Screener:
``data/raw/watchlist``, staged into a private snapshot store. The NETWEB "degenerate
consolidated page" case re-interprets the retained standalone-only page under a consolidated
request (no consolidated page is retained).
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from datetime import date, timedelta
from fractions import Fraction
from functools import partial
from pathlib import Path
from typing import Any, NamedTuple

import pytest
from pg_evidence_schema_support import _insert
from test_evidence_vendor_screener import binding as screener_binding
from vendor_retained_support import identifiers, retained_page, stage_registered

from fundamentals.canon.dictionary import load_dictionary
from fundamentals.canon.interval import load_rounding_policy
from fundamentals.contracts.acquisition_outcome import ExtractionOutcome
from fundamentals.contracts.canonical import Basis, PeriodKind, Representation
from fundamentals.contracts.evidence import (
    AttemptStage,
    EligibilityBoundary,
    InterpretationReason,
    InterpretationStatus,
    KnowledgeTimeStatus,
)
from fundamentals.contracts.measurement_key import PeriodInterval
from fundamentals.contracts.observation import AccountingFramework
from fundamentals.contracts.snapshot import BlobRef, CaptureRecord
from fundamentals.evidence import vendor_tijori, vendor_upstox
from fundamentals.evidence.mapping import load_mapping_set, load_normalisation_policy
from fundamentals.evidence.repository import EvidenceRepository
from fundamentals.evidence.selection import is_eligible
from fundamentals.evidence.vendor_ingest import VendorIngestRequest, ingest_vendor
from fundamentals.evidence.vendor_screener import extract_screener_page
from fundamentals.ingest.screener_financials_models import Section
from fundamentals.store.snapshot_store import SnapshotStore

REPO = Path(__file__).resolve().parents[2]
RETAINED = REPO / "data/raw/snapshots/v1"
TIJORI_THERMAX = ("tijori", "financials", "thermax-limited", "20260905T113125.708476Z-8745b6623baf")
UPSTOX = ("upstox", "income-statement")
POLYCAB_QUARTERLY = (
    *UPSTOX,
    "default-cfca1e489fa27667b6cd3de0",
    "20261014T071522.096013Z-94ef72092672",
)
NETWEB_CONSOLIDATED = (
    *UPSTOX,
    "default-4f732806df2fa93560222cb5",
    "20261014T071519.894428Z-a5ae6a0cc42c",
)
NETWEB_STANDALONE = (
    *UPSTOX,
    "default-230fe12acd34d282d9b5a775",
    "20261014T071518.813551Z-04c5a17a73ec",
)
SCREENER_UNREGISTERED = ("screener-subscriber", "SCREENER_UNREGISTERED", "none", "none")
STAGED = "staged"  # The Screener capture is staged into a private store by the test.
FY26 = PeriodInterval.duration(date(2025, 4, 1), date(2026, 3, 31))


class Row(NamedTuple):
    """One hand-read cell and how it must be stored."""

    section: str
    field: str
    column: str
    lexeme: str
    period: PeriodInterval | None
    kind: PeriodKind | None
    canonical_id: str | None
    status: InterpretationStatus
    reason: InterpretationReason | None
    raw_unit: str | None = None
    interval_crore: tuple[str, str] | None = None  # Hand-computed from the display rule.
    rendered: str | None = None  # The page's displayed number, when it differs from ``lexeme``.


class Case(NamedTuple):
    """One Verify claim: a capture, the request it is ingested for, and what is stored."""

    claim: str
    capture: tuple[str, str, str, str]
    representation: Representation
    basis: Basis
    adapter: Callable[[], Any]
    extractor_version: str
    outcome: ExtractionOutcome
    rows: tuple[Row, ...] = ()
    screener_symbol: str = ""
    units_in: str = ""  # Restage the Upstox capture with this ``units_in``.


def tijori(slug: str, symbol: str) -> Any:
    ids = identifiers(symbol)
    assert ids["tijori_slug"] == slug
    return partial(
        vendor_tijori.extract_tijori,
        binding=vendor_tijori.TijoriBinding(
            slug=slug, symbol=symbol, company_id=ids["tijori_company_id"]
        ),
        display=vendor_tijori.load_tijori_display(REPO / "config/mappings/tijori/v1/display.yaml"),
        basis=Basis.CONSOLIDATED,
    )


def upstox(basis: Basis) -> Any:
    return partial(vendor_upstox.extract_upstox, basis=basis)


def screener(symbol: str, basis: Basis, section: Section) -> Any:
    def extract(body: bytes, *, capture: Any, record: Any, extractor_version: str) -> Any:
        del record
        return extract_screener_page(
            body,
            capture=capture,
            binding=screener_binding(symbol),
            basis=basis,
            section=section,
            extractor_version=extractor_version,
        )

    return extract


UNIT = InterpretationReason.UNIT_MISMATCH  # No evidenced unit outside Tijori qt_c money rows.
PRECISION = InterpretationReason.PRECISION_UNSUPPORTED  # API numerals declare no precision.
INVALID = InterpretationStatus.INVALID
CASES = (
    Case(
        "tijori_ttm_column_stored_as_ttm",
        TIJORI_THERMAX,
        Representation.HTML,
        Basis.CONSOLIDATED,
        lambda: tijori("thermax-limited", "THERMAX"),
        vendor_tijori.EXTRACTOR_VERSION,
        ExtractionOutcome.COMPLETE,
        (
            # pl_c_s footer "TTM Values as of Jun 2026"; final column Sales.
            Row(
                "pl_c_s",
                "Sales",
                "Jun 2026",
                "10839.350000000002",
                PeriodInterval.duration(date(2025, 7, 1), date(2026, 6, 30)),
                PeriodKind.TTM,
                "revenue_from_operations",
                INVALID,
                UNIT,
                raw_unit="unknown",  # pl_* is outside the qt_c display fact.
            ),
            Row(
                "pl_c_s",
                "Sales",
                "Mar 2026",
                "10694.15",
                FY26,
                PeriodKind.YEAR,
                "revenue_from_operations",
                INVALID,
                UNIT,
            ),
        ),
    ),
    Case(
        "upstox_annual_on_quarterly_request_stored_as_annual",
        POLYCAB_QUARTERLY,
        Representation.JSON,
        Basis.CONSOLIDATED,
        lambda: upstox(Basis.CONSOLIDATED),
        vendor_upstox.EXTRACTOR_VERSION,
        ExtractionOutcome.COMPLETE,
        (
            Row(
                "full_statement",
                "Total Revenue",
                "Mar 2026",
                "29120.04",
                FY26,
                PeriodKind.YEAR,
                "total_income",
                INVALID,
                PRECISION,
                raw_unit="INR",
            ),
            Row(
                "full_statement",
                "EPS - Basic",
                "Mar 2026",
                "177.53",
                FY26,
                PeriodKind.YEAR,
                None,
                InterpretationStatus.UNMAPPED,
                None,
                raw_unit="unknown",  # Per share, never crore.
            ),
            Row(
                "summary",
                "revenue",
                "Mar 2026",
                "8924.9",
                PeriodInterval.duration(date(2026, 1, 1), date(2026, 3, 31)),
                PeriodKind.QUARTER,
                "total_income",
                INVALID,
                PRECISION,
            ),
        ),
    ),
    Case(
        "netweb_degenerate_consolidated_screener_page_yields_no_values",
        ("screener-subscriber", "SCREENER_FINANCIALS", STAGED, STAGED),
        Representation.HTML,
        Basis.CONSOLIDATED,
        lambda: screener("NETWEB", Basis.CONSOLIDATED, Section.QUARTERS),
        "screener-v1",
        ExtractionOutcome.PARSE_FAILED,
        screener_symbol="NETWEB",
    ),
    Case(
        "netweb_empty_upstox_consolidated_response_yields_no_values",
        NETWEB_CONSOLIDATED,
        Representation.JSON,
        Basis.CONSOLIDATED,
        lambda: upstox(Basis.CONSOLIDATED),
        vendor_upstox.EXTRACTOR_VERSION,
        ExtractionOutcome.IDENTITY_REJECTED,
    ),
    Case(
        "unregistered_surface_not_authorised",
        SCREENER_UNREGISTERED,
        Representation.HTML,
        Basis.CONSOLIDATED,
        lambda: screener("THERMAX", Basis.CONSOLIDATED, Section.QUARTERS),
        "screener-v1",
        ExtractionOutcome.NOT_AUTHORISED,
    ),
    Case(
        "missing_capture_is_one_captureless_acquisition_attempt",
        (*UPSTOX, "default-230fe12acd34d282d9b5a775", "20261014T000000.000000Z-000000000000"),
        Representation.JSON,
        Basis.STANDALONE,
        lambda: upstox(Basis.STANDALONE),
        vendor_upstox.EXTRACTOR_VERSION,
        ExtractionOutcome.FAILED,
    ),
    Case(
        "vendor_capture_never_eligible_before_registration",
        NETWEB_STANDALONE,
        Representation.JSON,
        Basis.STANDALONE,
        lambda: upstox(Basis.STANDALONE),
        vendor_upstox.EXTRACTOR_VERSION,
        ExtractionOutcome.COMPLETE,
        (
            Row(
                "full_statement",
                "Profit Before Tax",
                "Mar 2025",
                "153.0",
                PeriodInterval.duration(date(2024, 4, 1), date(2025, 3, 31)),
                PeriodKind.YEAR,
                "profit_before_tax",
                INVALID,
                PRECISION,
            ),
        ),
    ),
    Case(
        "screener_total_liabilities_maps_to_no_liabilities_row",
        ("screener-subscriber", "SCREENER_FINANCIALS", STAGED, STAGED),
        Representation.HTML,
        Basis.CONSOLIDATED,
        lambda: screener("THERMAX", Basis.CONSOLIDATED, Section.BALANCE_SHEET),
        "screener-v1",
        ExtractionOutcome.COMPLETE,
        (
            Row(
                "balance-sheet",
                "Total Liabilities",
                "Mar 2025",
                "11,382",
                PeriodInterval.at(date(2025, 3, 31)),
                PeriodKind.INSTANT,
                None,
                InterpretationStatus.UNMAPPED,
                None,
            ),
        ),
        screener_symbol="THERMAX",
    ),
    Case(
        "upstox_units_in_other_than_crore_yields_no_values",
        ("upstox", "income-statement", STAGED, STAGED),
        Representation.JSON,
        Basis.CONSOLIDATED,
        lambda: upstox(Basis.CONSOLIDATED),
        vendor_upstox.EXTRACTOR_VERSION,
        ExtractionOutcome.UNSUPPORTED_SCHEMA,
        units_in="lakh",
    ),
    Case(
        "tijori_qt_c_net_profit_maps_to_continuing_pat",
        TIJORI_THERMAX,
        Representation.HTML,
        Basis.CONSOLIDATED,
        lambda: tijori("thermax-limited", "THERMAX"),
        vendor_tijori.EXTRACTOR_VERSION,
        ExtractionOutcome.COMPLETE,
        (
            Row(
                "qt_c",
                "Net Profit",
                "Dec 2025",
                "205.11999999999998",
                PeriodInterval.duration(date(2025, 10, 1), date(2025, 12, 31)),
                PeriodKind.QUARTER,
                "profit_continuing_after_tax",
                InterpretationStatus.MAPPED,
                None,
                raw_unit="INR",
                # |v| > 100 displays Math.round(v): "205", 0 decimals, ± 0.5 crore.
                interval_crore=("204.5", "205.5"),
                rendered="205",
            ),
            Row(
                "qt_c",
                "Net Profit",
                "Jun 2026",
                "21.79",
                PeriodInterval.duration(date(2026, 4, 1), date(2026, 6, 30)),
                PeriodKind.QUARTER,
                "profit_continuing_after_tax",
                InterpretationStatus.MAPPED,
                None,
                raw_unit="INR",
                # |v| <= 100 displays v.toFixed(2): ± 0.005 crore.
                interval_crore=("21.785", "21.795"),
            ),
            Row(
                "qt_c",
                "EPS",
                "Dec 2025",
                "18.1252",
                PeriodInterval.duration(date(2025, 10, 1), date(2025, 12, 31)),
                PeriodKind.QUARTER,
                None,
                InterpretationStatus.UNMAPPED,
                None,
                raw_unit="unknown",  # Quarterly Ratios subtree: not crore.
            ),
        ),
    ),
)


@pytest.fixture(scope="module")
def config() -> tuple[Any, Any, Any, Any]:
    """The committed vendor config: dictionary and mapping set v2, policies v1."""
    dictionary = load_dictionary(REPO / "config/dictionary", "v2")
    mappings = load_mapping_set(REPO / "config/mappings", "v2", dictionary=dictionary)
    policy = load_normalisation_policy(REPO / "config/normalisation_policy/v1.yaml")
    rounding = load_rounding_policy(REPO / "config/rounding_policy/v1.yaml")
    return dictionary, mappings, policy, rounding


@pytest.mark.pg
@pytest.mark.parametrize("case", CASES, ids=[case.claim for case in CASES])
def test_d1b1_vendor_claim(
    case: Case, pg_db: Any, tmp_path: Path, config: tuple[Any, Any, Any, Any]
) -> None:
    dictionary, mappings, policy, rounding = config
    entity = _entity(pg_db)
    with pg_db.runtime_pool() as pool:
        repository = EvidenceRepository(pool)
        started = repository.store_clock()
        store, capture = _located(case, repository, tmp_path)
        report = ingest_vendor(
            VendorIngestRequest(
                source_id=capture[0],
                surface=capture[1],
                request_key=capture[2],
                capture_id=capture[3],
                representation=case.representation,
                entity_id=entity,
                period_end=date(2026, 3, 31),
                basis=case.basis,
                framework=AccountingFramework.IND_AS,
            ),
            extract=case.adapter(),
            extractor_version=case.extractor_version,
            snapshot_store=store,
            repository=repository,
            dictionary=dictionary,
            mapping_set=mappings,
            policy=policy,
            rounding_policy=rounding,
            fiscal_year_end_month=3,
        )
        assert report.attempt.attempt_id is not None
        assert repository.get_attempts([report.attempt.attempt_id]) == (report.attempt,)
        stored_occurrences = repository.get_occurrences(
            [item.occurrence_id for item in report.occurrences if item.occurrence_id]
        )
        stored = {
            item.occurrence_id: item
            for item in repository.get_interpretations(
                [
                    item.interpretation_id
                    for item in report.interpretations
                    if item.interpretation_id
                ]
            )
        }
    assert report.attempt.outcome is case.outcome
    if case.outcome in (ExtractionOutcome.NOT_AUTHORISED, ExtractionOutcome.FAILED):
        assert report.attempt.stage is AttemptStage.ACQUISITION and report.attempt.capture is None
    if not case.rows:
        assert report.occurrences == () and report.interpretations == ()
        return
    assert stored_occurrences == report.occurrences
    registration = report.attempt.capture
    assert registration is not None and registration.registered_at >= started
    for occurrence in report.occurrences:
        assert occurrence.knowledge_time is None
        assert occurrence.knowledge_time_status is KnowledgeTimeStatus.UNKNOWN
        assert occurrence.first_seen_at == registration.registered_at
    before = EligibilityBoundary.at(registration.registered_at - timedelta(microseconds=1))
    assert not any(is_eligible(item, before) for item in report.occurrences)
    at = EligibilityBoundary.at(registration.registered_at)
    assert all(is_eligible(item, at) for item in report.occurrences)
    for row in case.rows:
        (occurrence,) = (
            item
            for item in report.occurrences
            if (item.native_context["section"], item.native_field, item.anchor["column_label"])
            == (row.section, row.field, row.column)
        )
        assert occurrence.raw_value_text == (row.rendered or row.lexeme)
        assert occurrence.native_context.get("island_value", row.lexeme) == row.lexeme
        assert occurrence.period == row.period
        assert (occurrence.period.kind(3) if occurrence.period else None) is row.kind
        interpretation = stored[occurrence.occurrence_id]
        assert interpretation.canonical_id == row.canonical_id
        assert interpretation.period == row.period
        assert (interpretation.status, interpretation.reason) == (row.status, row.reason)
        if row.raw_unit is not None:
            assert occurrence.raw_unit == row.raw_unit
        if row.interval_crore is None:
            assert interpretation.value is None  # no unit, precision or mapping: never invented
            continue
        crore = Fraction(10**7)
        assert interpretation.value is not None and interpretation.interval is not None
        assert Fraction(interpretation.value) == Fraction(row.rendered or row.lexeme) * crore
        assert (interpretation.interval.lower, interpretation.interval.upper) == tuple(
            Fraction(bound) * crore for bound in row.interval_crore
        )


def _entity(pg_db: Any) -> int:
    with pg_db.migrator_connection() as conn:
        evidence = _insert(
            conn,
            "evidence_inputs",
            {"kind": "ISSUER_IDENTITY", "label": "D1b.1 vendor test", "content_sha256": "b" * 64},
        )
        return _insert(
            conn,
            "reporting_entities",
            {
                "entity_key": "D1B1-VENDOR-TEST",
                "market": "IN",
                "display_name": "D1b.1 vendor test entity",
                "evidence_input_id": evidence,
            },
        )


def _located(
    case: Case, repository: EvidenceRepository, tmp_path: Path
) -> tuple[SnapshotStore, tuple[str, str, str, str]]:
    """The retained store, or a private store a Screener page or altered body is staged into."""
    if case.units_in:
        record, body = SnapshotStore(RETAINED).read_capture_verified(*POLYCAB_QUARTERLY)
        altered = body.replace(b'"units_in":"crore"', f'"units_in":"{case.units_in}"'.encode())
        assert altered != body
        blob = BlobRef(
            source_id=record.request.source_id,
            content_sha256=hashlib.sha256(altered).hexdigest(),
            byte_count=len(altered),
        )
        staged_record = CaptureRecord.make(
            record.request,
            record.retrieved_at,
            record.http_status,
            record.media_type,
            record.content_encoding,
            blob,
            record.outcome,
            record.rights,
        )
        (tmp_path / "snapshots").mkdir(mode=0o700)
        store = SnapshotStore(tmp_path / "snapshots")
        store.put_capture(staged_record, altered)
        return store, (*POLYCAB_QUARTERLY[:3], staged_record.capture_id)
    if not case.screener_symbol:
        return SnapshotStore(RETAINED), case.capture
    root = tmp_path / "snapshots"
    root.mkdir(mode=0o700)
    store = SnapshotStore(root)
    request, _, _ = retained_page(case.screener_symbol)
    staged = stage_registered(request, repository, store)
    return store, (staged.source_id, staged.surface, staged.request_key, staged.capture_id)
