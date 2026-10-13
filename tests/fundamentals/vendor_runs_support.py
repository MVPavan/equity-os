"""Synthetic public-run fixtures with independent source literals and real store clocks.

No fixture proves actual vendor evidence, equivalence or issuer identity. Both
financial sources and issuer assertions are explicitly hand-authored mechanisms.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import pymupdf
import yaml
from pg_support import PgTestDatabase
from psycopg_pool import ConnectionPool
from test_compare_vendor_inputs import arguments, fixture

from fundamentals.api.config import FundamentalsConfig
from fundamentals.compare.run import execute_run, replay_run
from fundamentals.compare.run_models import DatabaseIdentity, RunRecord, RunRequest, RunScope
from fundamentals.compare.vendor_inputs import append_vendor_generation, compose_vendor_generation
from fundamentals.compare.vendor_request import request_from_declaration
from fundamentals.contracts.canonical import Basis, Representation
from fundamentals.contracts.evidence import CaptureReference, FilingFamily, RunMode
from fundamentals.contracts.observation import AccountingFramework
from fundamentals.contracts.snapshot import SnapshotRights
from fundamentals.evidence.capture_intake import RetainedCaptureBinding, RetainedIntake
from fundamentals.evidence.first_party_generation import (
    FirstPartyGenerationHandoff,
    append_first_party_generation,
)
from fundamentals.evidence.repository import EvidenceRepository
from fundamentals.evidence.vendor_common import VendorGeneration
from fundamentals.pg.identity_seed import CITED_FIELDS, load_issuer_identity, seed_issuer_identity
from fundamentals.store.capture_local import capture_local_original
from fundamentals.store.snapshot_store import DirectoryAnchor, SnapshotStore

END = date(2025, 9, 30)
PL_REVENUE = "revenue_from_operations"
# Hand-authored independent source values: Q2 revenue 1,200 crore; six-month
# revenue 2,000 crore. The synthetic Screener HTML independently prints 1,200.
FIRST_PARTY_BODY = b"""<?xml version="1.0" encoding="UTF-8"?>
<!-- SYNTHETIC public-run mechanism fixture. No actual company/source claim. -->
<xbrli:xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance"
 xmlns:iso4217="http://www.xbrl.org/2003/iso4217"
 xmlns:in-bse-fin="http://www.bseindia.com/xbrl/fin/2020-03-31/in-bse-fin">
 <xbrli:context id="OneD"><xbrli:entity>
 <xbrli:identifier scheme="http://www.nseindia.com/NSESymbol">FIXTURECO</xbrli:identifier>
 </xbrli:entity><xbrli:period><xbrli:startDate>2025-07-01</xbrli:startDate>
 <xbrli:endDate>2025-09-30</xbrli:endDate></xbrli:period></xbrli:context>
 <xbrli:context id="FourD"><xbrli:entity>
 <xbrli:identifier scheme="http://www.nseindia.com/NSESymbol">FIXTURECO</xbrli:identifier>
 </xbrli:entity><xbrli:period><xbrli:startDate>2025-04-01</xbrli:startDate>
 <xbrli:endDate>2025-09-30</xbrli:endDate></xbrli:period></xbrli:context>
 <xbrli:unit id="INR"><xbrli:measure>iso4217:INR</xbrli:measure></xbrli:unit>
 <in-bse-fin:NameOfTheCompany contextRef="OneD">
Synthetic fixture company
</in-bse-fin:NameOfTheCompany>
 <in-bse-fin:ISIN contextRef="OneD">INEFIXTURE001</in-bse-fin:ISIN>
 <in-bse-fin:Symbol contextRef="OneD">FIXTURECO</in-bse-fin:Symbol>
 <in-bse-fin:ScripCode contextRef="OneD">500999</in-bse-fin:ScripCode>
 <in-bse-fin:SyntheticIssuerBasisStatus contextRef="OneD">
CONSOLIDATED_AND_STANDALONE
</in-bse-fin:SyntheticIssuerBasisStatus>
 <in-bse-fin:DateOfStartOfFinancialYear contextRef="OneD">
2025-04-01
</in-bse-fin:DateOfStartOfFinancialYear>
 <in-bse-fin:DateOfEndOfFinancialYear contextRef="OneD">
2026-03-31
</in-bse-fin:DateOfEndOfFinancialYear>
 <in-bse-fin:DateOfEndOfReportingPeriod contextRef="OneD">
2025-09-30
</in-bse-fin:DateOfEndOfReportingPeriod>
 <in-bse-fin:DisclosureOfNotesOnFinancialResultsExplanatoryTextBlock contextRef="OneD">
Synthetic statements prepared in accordance with Indian Accounting Standard.
</in-bse-fin:DisclosureOfNotesOnFinancialResultsExplanatoryTextBlock>
 <in-bse-fin:NatureOfReportStandaloneConsolidated contextRef="OneD">
Consolidated
</in-bse-fin:NatureOfReportStandaloneConsolidated>
 <in-bse-fin:NatureOfReportStandaloneConsolidated contextRef="FourD">
Consolidated
</in-bse-fin:NatureOfReportStandaloneConsolidated>
 <in-bse-fin:RevenueFromOperations contextRef="OneD" unitRef="INR" decimals="-7">
12000000000
</in-bse-fin:RevenueFromOperations>
 <in-bse-fin:RevenueFromOperations contextRef="FourD" unitRef="INR" decimals="-7">
20000000000
</in-bse-fin:RevenueFromOperations>
</xbrli:xbrl>
"""


@dataclass
class VendorRunCase:
    """One guarded database, synthetic publication and source-bound handoffs."""

    pool: ConnectionPool
    pg_db: PgTestDatabase
    producer_case: tuple[Any, ...]
    first_party: FirstPartyGenerationHandoff
    generation: VendorGeneration

    @property
    def config_root(self) -> Path:
        return self.producer_case[0]

    @property
    def repository(self) -> EvidenceRepository:
        return self.producer_case[5]

    def request(self, *, mode: RunMode = RunMode.AS_KNOWN) -> RunRequest:
        settings = self.pg_db.settings
        return RunRequest(
            scope=RunScope(
                entity_ids=(self.first_party.entity_id,),
                period_ends=(END,),
                bases=(Basis.CONSOLIDATED,),
                sources=("NSE_XBRL_INSTANCE", "NSE_RESULTS_PDF"),
                vendor_sources=(self.producer_case[3],),
            ),
            cutoff=self.repository.store_clock(),
            mode=mode,
            pinned=self.producer_case[2].pinned,
            code_version="SYNTHETIC-public-run-mechanism",
            database_identity=DatabaseIdentity(
                host=settings.host, port=settings.port, name=self.pg_db.dbname
            ),
        )

    def execute(self, request: RunRequest | None = None, **updates: Any) -> RunRecord:
        options = {
            "pool": self.pool,
            "config_root": self.config_root,
            "first_party_generation": self.first_party,
            "vendor_generations": (self.generation,),
            "vendor_input_anchor": DirectoryAnchor(self.producer_case[1]),
        }
        options.update(updates)
        return execute_run(request or self.request(), **options)

    def replay(self, run_id: int, **updates: Any) -> tuple[Any, ...]:
        return replay_run(run_id, pool=self.pool, config_root=self.config_root, **updates)

    def counts(self) -> dict[str, int]:
        names = (
            "capture_refs",
            "occurrences",
            "interpretations",
            "acquisition_attempts",
            "runs",
            "run_versions",
            "run_inputs",
            "results",
            "result_source_values",
            "result_surfaced_restatements",
            "pair_outcomes",
            "pair_adjustments",
            "queue_items",
            "queue_item_inputs",
            "queue_run_items",
            "queue_overlay_snapshots",
        )
        with self.pool.connection() as connection:
            return {
                name: int(connection.execute("SELECT count(*) FROM eqos." + name).fetchone()[0])
                for name in names
            }


def build_case(
    pg_db: PgTestDatabase,
    pool: ConnectionPool,
    tmp_path: Path,
    *,
    persist_vendor: bool = True,
    first_party_body: bytes = FIRST_PARTY_BODY,
) -> VendorRunCase:
    """Bind real synthetic source bytes and clocks; no actual retained input is needed."""
    repository = EvidenceRepository(pool)
    case = fixture(tmp_path)
    root, inputs, config, declaration, context, _ = case
    (inputs / "synthetic-first-party.xml").write_bytes(first_party_body)
    digest = hashlib.sha256(first_party_body).hexdigest()
    fields = {
        "display_name": "NameOfTheCompany",
        "isin": "ISIN",
        "nse_symbol": "Symbol",
        "bse_scrip": "ScripCode",
        "basis_status": "SyntheticIssuerBasisStatus",
        "fiscal_year_end_month": "DateOfEndOfFinancialYear",
    }
    identity = {
        "entity_key": "FIXTURECO",
        "display_name": "Synthetic fixture company",
        "isin": "INEFIXTURE001",
        "share_class": "EQUITY",
        "nse_symbol": "FIXTURECO",
        "bse_scrip": "500999",
        "basis_status": "CONSOLIDATED_AND_STANDALONE",
        "fiscal_year_end_month": 3,
        "citations": [
            {
                "field": field,
                "capture_sha256": digest,
                "native_field": fields[field],
                "context_ref": "OneD",
            }
            for field in sorted(CITED_FIELDS)
        ],
    }
    identity_path = root / "identity/fixtureco.yaml"
    identity_path.write_text(yaml.safe_dump(identity, sort_keys=True))
    with pg_db.migrator_connection() as connection:
        entity_id = seed_issuer_identity(
            connection, load_issuer_identity(identity_path)
        ).entity_ids["FIXTURECO"]
    # The accepted consumer independently rereads the issuer/quarter source config,
    # including the expected PDF source even for this XBRL-only package. Provide a
    # real, explicitly unused synthetic PDF and its actual hash; no PDF facts or
    # historical/actual-company evidence are claimed by this fixture.
    with pymupdf.open() as unused_pdf:
        page = unused_pdf.new_page()
        page.insert_text((40, 50), "SYNTHETIC unused document; no financial values")
        pdf_body = unused_pdf.tobytes()
    (inputs / "synthetic-unused-results.pdf").write_bytes(pdf_body)
    (inputs / "synthetic-unused-transcript.pdf").write_bytes(pdf_body)
    pdf_sha256 = hashlib.sha256(pdf_body).hexdigest()
    source_config = {
        "issuer": {
            "name": "Synthetic fixture company",
            "nse_symbol": "FIXTURECO",
            "entity_scheme": "nse-symbol",
        },
        "quarter": {
            "issuer_quarter": "FY26_Q2",
            "program_quarter": "QUARTER_0",
            "label": "SYNTHETIC Q2 FY26",
            "period_start": "2025-07-01",
            "period_end": END.isoformat(),
            "knowledge_cutoff": repository.store_clock().isoformat(),
        },
        "raw_dir": inputs.name,
        "store_db": ":memory:",
        "results_pdf": {
            "source_id": "fixtureco-fy26-q2-results-pdf",
            "source_class": "first_party",
            "filename": "synthetic-unused-results.pdf",
            "sha256": pdf_sha256,
        },
        "transcript_pdf": {
            "source_id": "fixtureco-fy26-q2-management-transcript",
            "source_class": "first_party",
            "filename": "synthetic-unused-transcript.pdf",
            "sha256": pdf_sha256,
        },
        "xbrl": {
            "source_id": "nse-indas-xbrl-consolidated",
            "symbol": "FIXTURECO",
            "local_path": f"{inputs.name}/synthetic-first-party.xml",
        },
    }
    FundamentalsConfig.model_validate(source_config)
    (root / "fixtureco-fy26-q2.yaml").write_text(yaml.safe_dump(source_config, sort_keys=True))
    declaration = declaration.model_copy(update={"entity_id": entity_id})
    store_root = tmp_path / "synthetic-snapshots"
    store_root.mkdir()
    snapshot_store = SnapshotStore(store_root)
    request = request_from_declaration(declaration)
    assert request.retained is not None
    record = capture_local_original(
        snapshot_store,
        input_anchor=DirectoryAnchor(inputs),
        source_id=request.source_id,
        surface=request.surface,
        request_key=request.identity_sha256(),
        expected_sha256=request.retained.expected_sha256,
        media_type="text/html",
        rights=SnapshotRights(authority_refs=("SYNTHETIC private mechanism fixture only",)),
        path=request.retained.relative_path,
        clock=repository.store_clock,
    )
    capture = repository.put_capture_ref(
        CaptureReference(
            capture_ref_id=None,
            source_id=record.request.source_id,
            surface=record.request.surface,
            request_key=record.request.request_key,
            capture_id=record.capture_id,
            blob_sha256=record.body.content_sha256,
            record_sha256=record.record_sha256,
            registered_at=record.retrieved_at,
            first_seen_at=record.retrieved_at,
        )
    )
    declaration = declaration.model_copy(update={"capture_ref_id": capture.capture_ref_id})
    # Entity changes alter logical scope; derive it from the publication, never a literal.
    from fundamentals.compare.vendor_request import logical_scope_sha256

    pin = next(pin for pin in config.pinned.vendor_extractors if pin.surface == request.surface)
    declaration = declaration.model_copy(
        update={
            "expected_logical_scope_sha256": logical_scope_sha256(
                request, extractor_pin=pin, composer_context=context
            )
        }
    )
    case = (root, inputs, config, declaration, context, repository)
    intake = RetainedIntake(
        bindings=(
            RetainedCaptureBinding(
                representation=Representation.XBRL,
                source_id="nse-indas-xbrl-consolidated",
                relative_path=Path("synthetic-first-party.xml"),
                expected_sha256=digest,
                filed_at_raw=repository.store_clock().isoformat(),
            ),
        ),
        retrieval_manifest_sha256=hashlib.sha256(b"SYNTHETIC public-run local intake").hexdigest(),
        issuer_config_sha256=None,
        authority_ref="SYNTHETIC mechanism only",
        store_anchor=DirectoryAnchor(store_root),
        input_anchor=DirectoryAnchor(inputs),
    )
    first_party = append_first_party_generation(
        intake=intake,
        snapshot_store=snapshot_store,
        pool=pool,
        config=config,
        config_root=root,
        entity_id=entity_id,
        basis=Basis.CONSOLIDATED,
        framework=AccountingFramework.IND_AS,
        family=FilingFamily.FINANCIAL_RESULTS,
        reporting_period_end=END,
        pdf_specs=None,
    )
    generation = compose_vendor_generation(**arguments(case))
    if persist_vendor:
        generation = append_vendor_generation(generation, **arguments(case)).generation
    return VendorRunCase(pool, pg_db, case, first_party, generation)
