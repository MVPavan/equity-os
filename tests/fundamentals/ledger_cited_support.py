"""D3.2 resolver support: one test database with the D2 legacy import, its acquisitions and
cited run cells (plan D8, D9).

The legacy facts and their captures are real (the D2 rig over the retained originals); the run
cells, traces and the vendor fact are direct inserts in the shape of
``pg_evidence_schema_support``'s rows, keyed by a real measurement-key digest.
"""

from __future__ import annotations

import shutil
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import psycopg
import pytest
from coverage_support import watchlist
from pg_evidence_schema_support import (
    NOW,
    PERIOD_END,
    PERIOD_START,
    SHA_A,
    _capture,
    _insert,
    _interpretation,
    _occurrence,
    _run_input,
    _trace,
)
from pg_support import PgTestDatabase
from psycopg import Cursor
from psycopg.types.json import Jsonb
from retained_support import APAR_MANIFEST
from selection_support import key
from test_legacy_import import Rig

from fundamentals.contracts.canonical import ValueKind
from fundamentals.contracts.guidance_claim import EpistemicClass
from fundamentals.contracts.ledger import (
    Citation,
    CitationKind,
    NumericClaim,
    ResolvedCitation,
    Rounding,
)
from fundamentals.contracts.measurement_key import MeasurementKey, PeriodInterval
from fundamentals.contracts.source_catalog import (
    BUILTIN_SOURCES,
    EvidenceRole,
    SourceClass,
    SourceDescriptor,
)
from fundamentals.ingest.pdf_source import load_pdf
from fundamentals.ledger import store
from fundamentals.ledger.citations import resolve_citation
from fundamentals.pg.settings import PgRole
from fundamentals.store.snapshot_store import SnapshotStore
from fundamentals.verify.quote_anchor import source_document

RUN = {
    "identity_hash": "9" * 64,
    "cutoff": NOW,
    "mode": "AS_KNOWN",
    "status": "COMPLETE",
    "code_version": "abc1234",
    "manifest": Jsonb({}),
    "manifest_sha256": SHA_A,
}
RESULT = {
    "canonical_id": "profit_before_tax",
    "dictionary_version": "v1",
    "period_start": PERIOD_START,
    "period_end": PERIOD_END,
    "basis": "CONSOLIDATED",
    "framework": "IND_AS",
    "currency": "INR",
    "value_kind": "CURRENCY_AMOUNT",
    "dimension_set": Jsonb([]),
    "dimension_hash": "dims-empty",
    "value_identity": "REPORTED",
    "applicability": "APPLICABLE",
    "applicability_rule_id": "always",
    "extraction_status": "AGREE",
    "corroboration_status": "FILING_ONLY",
}
OPERAND = {
    "ordinal": 0,
    "operand_name": "profit_before_tax",
    "key_digest": "operand-key",
    "temporal_role": "DURATION",
    "scoped_tier": "EQUIVALENCE_UNPROVEN",
    "selection_source": "PACKAGE_AS_REPORTED",
    "source_state": "VALUE",
    "value": Decimal(100),
}
PDF_SOURCES = "aparinds-%"
MANIFEST_SHA256 = "c47866ce13f719521bbcc7826fc23590acc73f9904cfc1749a1ad911bb399a1b"
_REVENUE = (
    "SELECT origin, origin_id, file_sha256 FROM eqos.fact_rows WHERE file_sha256 LIKE %s "
    "AND fact_json LIKE %s AND canonical_status = 'canonical'"
)
_REGISTERED = (
    "SELECT c.registered_at FROM eqos.capture_refs c JOIN eqos.legacy_evidence_bindings b "
    "ON b.capture_ref_id = c.id WHERE b.file_sha256 = %s"
)
_VENDOR = {"source_id": "screener-subscriber", "surface": "SCREENER_FINANCIALS"}


class Cited:
    """The D2 legacy import with its acquisitions, plus first-party and vendor run cells,
    traces, a vendor fact and a vendor capture, all on one test database."""

    def __init__(self, pg_db: PgTestDatabase, tmp_path: Path, stack: ExitStack) -> None:
        self.started = datetime.now(UTC)
        rig = Rig(pg_db, tmp_path)
        rig.register()
        rig.run(*rig.pair())
        self.pools = {role: stack.enter_context(pg_db.role_pool(role)) for role in PgRole}
        self.snapshots, self.tmp_path = SnapshotStore(rig.snapshots), tmp_path
        ((self.revenue_origin, self.revenue_origin_id, self.revenue_file_sha256),) = self.query(
            _REVENUE, "f76a131a%", "%RevenueFromOperations%"
        )
        self.revenue_registered_at = self.query(_REGISTERED, self.revenue_file_sha256)
        copy = tmp_path / "retrieval-manifest.json"
        shutil.copyfile(APAR_MANIFEST, copy)
        self.manifest_bytes, self.manifest_sha256 = copy.read_bytes(), MANIFEST_SHA256
        with self.panel() as cursor:
            store.insert_acquisitions(cursor, copy.read_bytes(), expected_sha256=MANIFEST_SHA256)
        copy.unlink()
        ((self.entity_id,),) = self.query(
            "SELECT id FROM eqos.reporting_entities WHERE entity_key = 'APARINDS'"
        )
        self.cell_key = key("profit_before_tax", PeriodInterval.duration(PERIOD_START, PERIOD_END))
        self.cell_key = self.cell_key.model_copy(update={"entity_id": self.entity_id})
        self.cell_value, self.fixture_first_seen = Decimal(100), NOW
        watchlist(
            self.pools, self.entity_id, self.snapshots
        )  # SEED: runtime drafts pass the gate (plan D7 R6)
        with self.pools[PgRole.RUNTIME].connection() as conn, conn.transaction():
            self.ids = _seed_cells(conn, self.entity_id, self.cell_key.digest())
        pdf_sources = self.query(
            "SELECT DISTINCT source_id FROM eqos.capture_refs WHERE source_id LIKE %s", PDF_SOURCES
        )
        self.catalog = BUILTIN_SOURCES.extend(
            *(
                SourceDescriptor(
                    source_id=source_id,
                    source_class=SourceClass.FIRST_PARTY,
                    evidence_role=EvidenceRole.RECONCILABLE,
                )
                for (source_id,) in pdf_sources
            )
        )

    def query(self, statement: str, *params: object) -> list[tuple[Any, ...]]:
        """Rows of one runtime-role query."""
        with self.runtime() as cursor:
            return [tuple(row) for row in cursor.execute(statement, params).fetchall()]  # type: ignore[arg-type]

    @contextmanager
    def runtime(self) -> Iterator[Cursor[Any]]:
        """A runtime cursor in one committed transaction."""
        with self.pools[PgRole.RUNTIME].connection() as conn, conn.transaction():
            yield conn.cursor()

    @contextmanager
    def panel(self) -> Iterator[Cursor[Any]]:
        """A panel cursor in one committed transaction."""
        with self.pools[PgRole.PANEL].connection() as conn, conn.transaction():
            yield conn.cursor()

    def resolve(self, cited: NumericClaim, entity_id: int | None = None) -> ResolvedCitation | None:
        """The real resolver on this database, at the current overlay position, for a report of
        ``entity_id`` (default: the seeded issuer)."""
        with self.runtime() as cursor:
            return resolve_citation(
                cursor,
                cited,
                entity_id=self.entity_id if entity_id is None else entity_id,
                overlay_position=datetime.now(UTC),
                catalog=self.catalog,
                snapshots=self.snapshots,
            )

    def legacy_revenue(self) -> NumericClaim:
        """FY27_Q1 revenue on its legacy fact."""
        return _figure(
            self.cell_key, fact_origin=self.revenue_origin, fact_origin_id=self.revenue_origin_id
        )

    def vendor_fact(self) -> NumericClaim:
        """A ``FIGURE`` on a fact bound to a vendor capture."""
        return _figure(self.cell_key, fact_origin="vendor-seed", fact_origin_id=1)

    def interpretation_figure(
        self, *, not_selected: bool = False, other_key: bool = False
    ) -> NumericClaim:
        """A ``FIGURE`` on the run's selected (or a not-selected) interpretation."""
        interpretation = self.ids["not_selected" if not_selected else "selected"]
        cell_key = key("revenue_from_operations") if other_key else self.cell_key
        return _figure(cell_key, interpretation_id=interpretation, run_id=self.ids["run"])

    def first_party_trace(self) -> NumericClaim:
        """A ``CALCULATION`` on a trace over a first-party operand."""
        citation = Citation(kind=CitationKind.CALCULATION, calculation_trace_id=self.ids["trace"])
        return _figure(self.cell_key).model_copy(update={"citation": citation})

    def vendor_operand_trace(self) -> NumericClaim:
        """A ``CALCULATION`` on a trace over a vendor operand."""
        citation = Citation(
            kind=CitationKind.CALCULATION, calculation_trace_id=self.ids["vendor_trace"]
        )
        return _figure(self.cell_key).model_copy(update={"citation": citation})

    def comparison(self) -> NumericClaim:
        """A ``COMPARISON`` on the run cell's first-party/vendor pair."""
        citation = Citation(
            kind=CitationKind.COMPARISON, run_id=self.ids["run"], pair_outcome_id=self.ids["pair"]
        )
        return _figure(self.cell_key).model_copy(update={"citation": citation})

    def vendor_quote(self) -> NumericClaim:
        """A ``SOURCE_QUOTE`` on the vendor capture."""
        citation = Citation(
            kind=CitationKind.SOURCE_QUOTE,
            capture_ref_id=self.ids["vendor"],
            anchor="p1.b0.0:1",
            quote="x",
        )
        return _figure(None).model_copy(update={"citation": citation})

    def location(self, which: str, anchor: str) -> tuple[str, str]:
        """A marker's capture id and anchor: ``valid``, ``zero`` and ``whitespace`` spans are
        found in a registered PDF's own blocks; other anchors are literal."""
        rows = self.query(
            "SELECT id, source_id, surface, request_key, capture_id, blob_sha256 "
            "FROM eqos.capture_refs WHERE source_id LIKE %s ORDER BY id LIMIT 1",
            PDF_SOURCES,
        )
        capture_ref_id, *identity, blob = rows[0]
        _, body = self.snapshots.read_capture_verified(*identity)
        path = self.tmp_path / "located.pdf"
        path.write_bytes(body)
        blocks = source_document(load_pdf(source_id=identity[0], path=path, expected_sha256=blob))
        block = next(b for b in blocks.blocks if len(b.text.strip()) >= 10 and " " in b.text)
        at, space = f"p{block.page}.b{block.block}", block.text.index(" ")
        spans = {
            "valid": f"{at}.0:{len(block.text)}",
            "zero": f"{at}.0:0",
            "whitespace": f"{at}.{space}:{space + 1}",
        }
        ids = {"pdf": capture_ref_id, "vendor": self.ids["vendor"], "missing": 10**9}
        return str(ids[which]), spans.get(anchor, anchor)


def _figure(cell_key: MeasurementKey | None, **citation: Any) -> NumericClaim:
    """A crore ``FIGURE`` claim with the given citation fields."""
    return NumericClaim(
        claim_key="fact.cited",
        section_key="results",
        citation=Citation(kind=CitationKind.FIGURE, **citation),
        measurement_key=cell_key,
        value_kind=ValueKind.CURRENCY_AMOUNT,
        unit="INR crore",
        currency="INR",
        scale=10_000_000,
        value=Decimal("6591.06"),
        precision=2,
        rounding=Rounding.ROUND_HALF_UP,
        epistemic_class=EpistemicClass.OBSERVED,
    )


def _seed_cells(conn: psycopg.Connection, entity_id: int, digest: str) -> dict[str, int]:
    """Run cells, traces and a vendor fact on a first-party and a vendor capture."""
    first = _insert(conn, "capture_refs", _capture("ledger-first-party"))
    vendor = _insert(conn, "capture_refs", _capture("ledger-vendor") | _VENDOR)
    ids = {"vendor": vendor}

    def interpretation(capture: int, value: int, **update: Any) -> int:
        occurrence = _insert(conn, "occurrences", _occurrence(capture, f"ledger-{value}"))
        row = _interpretation(entity_id, capture, occurrence, key_digest=digest, **update)
        return _insert(
            conn, "interpretations", row | dict.fromkeys(("value", "lower", "upper"), value)
        )

    ids["selected"] = selected = interpretation(first, 100)
    ids["not_selected"] = interpretation(first, 200, input_digest="not-selected")
    vendor_value = interpretation(vendor, 300)
    run = ids["run"] = _insert(conn, "runs", RUN)
    for interpretation_id, disposition in (
        (selected, "SELECTED"),
        (ids["not_selected"], "NOT_SELECTED"),
    ):
        row = _run_input(run, "INTERPRETATION", interpretation_id=interpretation_id)
        _insert(conn, "run_inputs", row | {"disposition": disposition})
    result = _insert(
        conn, "results", RESULT | {"run_id": run, "entity_id": entity_id, "key_digest": digest}
    )
    first_party = {"source_role": "FIRST_PARTY", "representation": "XBRL"}
    vendor_side = {"source_role": "INDEPENDENT_VENDOR", "representation": "HTML"} | _VENDOR
    left, right = (
        _insert(
            conn,
            "result_source_values",
            side
            | {"result_id": result, "source_state": "VALUE", "value": value}
            | {"interpretation_id": interpretation_id},
        )
        for side, value, interpretation_id in (
            (first_party, 100, selected),
            (vendor_side, 300, vendor_value),
        )
    )
    ids["pair"] = _insert(
        conn,
        "pair_outcomes",
        {"result_id": result, "pair_kind": "CORROBORATION", "left_value_id": left}
        | {"right_value_id": right, "outcome": "MISMATCH", "difference": -200},
    )
    for name, operand, sha in (("trace", selected, "d"), ("vendor_trace", vendor_value, "e")):
        ids[name] = trace = _insert(conn, "calculation_traces", _trace(sha * 64))
        _insert(
            conn,
            "calculation_trace_operands",
            OPERAND | {"calculation_trace_id": trace, "interpretation_id": operand},
        )
    _seed_vendor_fact(conn, entity_id, vendor)
    return ids


def _seed_vendor_fact(conn: psycopg.Connection, entity_id: int, capture: int) -> None:
    """Fact row 1 of store ``vendor-seed``, bound to the vendor capture."""
    store_id, row = "vendor-seed", {"target_store": "vendor-seed", "row_handle": 1}
    _insert_rows(
        conn,
        (
            "fact_stores",
            {"store_id": store_id, "kind": "LEGACY_SQLITE", "file_label": "vendor"}
            | {"file_sha256": SHA_A},
        ),
        (
            "fact_rows",
            {"target_store": store_id, "handle": 1, "origin": store_id, "origin_id": 1}
            | {"content_identity": "c", "value_hash": "v", "revision_family": "f"}
            | {"revision_ordinal": 1, "canonical_status": "canonical", "source_id": "screener"}
            | {"file_sha256": SHA_A, "anchor": "{}", "valid_time_start": "2025-07-01"}
            | {"knowledge_time": "2025-11-06T12:05:34+00:00", "first_seen_time": "t"}
            | {"fact_json": '{"observation": {}}', "created_at": "t"},
        ),
        (
            "legacy_fact_translations",
            row
            | {"translation_version": "v", "entity_id": entity_id, "canonical_id": "revenue"}
            | {"period_start": PERIOD_START, "period_end": PERIOD_END, "basis": "CONSOLIDATED"}
            | {"framework": "IND_AS", "value_kind": "CURRENCY_AMOUNT", "dimension_set": Jsonb([])},
        ),
        (
            "legacy_evidence_bindings",
            row | {"capture_ref_id": capture, "file_sha256": SHA_A, "anchor": "{}"},
        ),
    )


def _insert_rows(conn: psycopg.Connection, *rows: tuple[str, dict[str, Any]]) -> None:
    """Insert rows with no identity column."""
    for table, values in rows:
        columns = ", ".join(values)
        marks = ", ".join(["%s"] * len(values))
        conn.execute(
            f"INSERT INTO eqos.{table} ({columns}) VALUES ({marks})", tuple(values.values())
        )  # type: ignore[arg-type]


@pytest.fixture
def cited(pg_db: PgTestDatabase, tmp_path: Path) -> Iterator[Cited]:
    """The resolver's seeded database with its role pools open."""
    with ExitStack() as stack:
        yield Cited(pg_db, tmp_path, stack)
