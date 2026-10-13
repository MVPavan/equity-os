"""Self-contained SYNTHETIC witness seed for all-table SQL immutability checks.

Every metadata, identity and financial-source assertion is hand authored solely
for private schema mechanics. This fixture reads no ignored retained input and
establishes no actual issuer identity, vendor equivalence or approval authority.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path

import psycopg
import yaml
from pg_support import PgTestDatabase
from psycopg import sql
from test_vendor_config_publication import _draft_root, _publish_synthetic

from fundamentals.compare.run_config import ConfigVersions, load_run_config
from fundamentals.contracts.canonical import Basis, Representation
from fundamentals.contracts.evidence import FilingFamily
from fundamentals.contracts.observation import AccountingFramework
from fundamentals.evidence.capture_intake import retained_intake_from_manifest
from fundamentals.evidence.first_party_generation import append_first_party_generation
from fundamentals.pg.identity_seed import CITED_FIELDS, load_issuer_identity, seed_issuer_identity
from fundamentals.store.snapshot_store import SnapshotStore

_SYMBOL = "WITNESSFIX"
_QUARTER = "FY26_Q2"
_SOURCE_BODY = b"""<?xml version="1.0" encoding="UTF-8"?>
<!-- SYNTHETIC SQL fixture only; no actual issuer or financial-source claim. -->
<xbrli:xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance"
 xmlns:iso4217="http://www.xbrl.org/2003/iso4217"
 xmlns:in-bse-fin="http://www.bseindia.com/xbrl/fin/2020-03-31/in-bse-fin">
 <xbrli:context id="OneD"><xbrli:entity>
 <xbrli:identifier scheme="http://www.nseindia.com/NSESymbol">WITNESSFIX</xbrli:identifier>
 </xbrli:entity><xbrli:period><xbrli:startDate>2025-07-01</xbrli:startDate>
 <xbrli:endDate>2025-09-30</xbrli:endDate></xbrli:period></xbrli:context>
 <xbrli:context id="FourD"><xbrli:entity>
 <xbrli:identifier scheme="http://www.nseindia.com/NSESymbol">WITNESSFIX</xbrli:identifier>
 </xbrli:entity><xbrli:period><xbrli:startDate>2025-04-01</xbrli:startDate>
 <xbrli:endDate>2025-09-30</xbrli:endDate></xbrli:period></xbrli:context>
 <xbrli:unit id="INR"><xbrli:measure>iso4217:INR</xbrli:measure></xbrli:unit>
 <in-bse-fin:NameOfTheCompany contextRef="OneD">
Synthetic witness fixture</in-bse-fin:NameOfTheCompany>
 <in-bse-fin:ISIN contextRef="OneD">INEWITNESS001</in-bse-fin:ISIN>
 <in-bse-fin:Symbol contextRef="OneD">WITNESSFIX</in-bse-fin:Symbol>
 <in-bse-fin:ScripCode contextRef="OneD">500997</in-bse-fin:ScripCode>
 <in-bse-fin:SyntheticIssuerBasisStatus contextRef="OneD">
CONSOLIDATED_AND_STANDALONE</in-bse-fin:SyntheticIssuerBasisStatus>
 <in-bse-fin:DateOfStartOfFinancialYear contextRef="OneD">
2025-04-01</in-bse-fin:DateOfStartOfFinancialYear>
 <in-bse-fin:DateOfEndOfFinancialYear contextRef="OneD">
2026-03-31</in-bse-fin:DateOfEndOfFinancialYear>
 <in-bse-fin:DateOfEndOfReportingPeriod contextRef="OneD">
2025-09-30</in-bse-fin:DateOfEndOfReportingPeriod>
 <in-bse-fin:DisclosureOfNotesOnFinancialResultsExplanatoryTextBlock contextRef="OneD">
Synthetic statements prepared in accordance with Indian Accounting Standard.
</in-bse-fin:DisclosureOfNotesOnFinancialResultsExplanatoryTextBlock>
 <in-bse-fin:NatureOfReportStandaloneConsolidated contextRef="OneD">
Consolidated</in-bse-fin:NatureOfReportStandaloneConsolidated>
 <in-bse-fin:NatureOfReportStandaloneConsolidated contextRef="FourD">
Consolidated</in-bse-fin:NatureOfReportStandaloneConsolidated>
 <in-bse-fin:RevenueFromOperations contextRef="OneD" unitRef="INR" decimals="-7">
12000000000</in-bse-fin:RevenueFromOperations>
 <in-bse-fin:RevenueFromOperations contextRef="FourD" unitRef="INR" decimals="-7">
20000000000</in-bse-fin:RevenueFromOperations>
</xbrli:xbrl>
"""
_TABLES = (
    "retained_intake_witnesses",
    "retained_intake_witness_bindings",
    "retained_intake_witness_attempts",
    "retained_intake_witness_captures",
    "retained_intake_witness_pins",
    "retained_intake_witness_seals",
)


def seed_retained_intake_tables(
    pg_db: PgTestDatabase, runtime: psycopg.Connection, tmp_path: Path
) -> dict[str, int]:
    """Use the real opt-in producer/store, then return ordinary IDs for all six populated tables."""
    root = _draft_root(tmp_path)
    _publish_synthetic(root)
    loaded = load_run_config(
        root, ConfigVersions(mapping_set="v2"), allow_synthetic_vendor_config=True
    )
    inputs = tmp_path / "synthetic-witness-inputs"
    inputs.mkdir(mode=0o700)
    (inputs / "nse").mkdir(mode=0o700)
    (inputs / "nse" / "witness-fixture.xml").write_bytes(_SOURCE_BODY)
    digest = hashlib.sha256(_SOURCE_BODY).hexdigest()
    fields = {
        "display_name": "NameOfTheCompany",
        "isin": "ISIN",
        "nse_symbol": "Symbol",
        "bse_scrip": "ScripCode",
        "basis_status": "SyntheticIssuerBasisStatus",
        "fiscal_year_end_month": "DateOfEndOfFinancialYear",
    }
    identity = {
        "entity_key": _SYMBOL,
        "display_name": "Synthetic witness fixture",
        "isin": "INEWITNESS001",
        "share_class": "EQUITY",
        "nse_symbol": _SYMBOL,
        "bse_scrip": "500997",
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
    identity_path = root / "identity" / "witnessfix.yaml"
    identity_path.write_text(yaml.safe_dump(identity, sort_keys=True), encoding="utf-8")
    entity_id = seed_issuer_identity(runtime, load_issuer_identity(identity_path)).entity_ids[
        _SYMBOL
    ]
    # This unused PDF declaration provides complete issuer config only. No PDF
    # body is acquired, interpreted or asserted as a successful package member.
    unused_pdf_sha = hashlib.sha256(b"SYNTHETIC unused PDF declaration only").hexdigest()
    source_config = {
        "issuer": {
            "name": "Synthetic witness fixture",
            "nse_symbol": _SYMBOL,
            "entity_scheme": "nse-symbol",
        },
        "quarter": {
            "issuer_quarter": _QUARTER,
            "program_quarter": "QUARTER_0",
            "label": "SYNTHETIC Q2 FY26",
            "period_start": "2025-07-01",
            "period_end": "2025-09-30",
            "knowledge_cutoff": "2025-10-29T03:30:00Z",
        },
        "raw_dir": inputs.name,
        "store_db": ":memory:",
        "results_pdf": {
            "source_id": "witnessfix-fy26-q2-results-pdf",
            "source_class": "first_party",
            "filename": "nse_pdf/unused.pdf",
            "sha256": unused_pdf_sha,
        },
        "transcript_pdf": {
            "source_id": "witnessfix-unused-transcript",
            "source_class": "first_party",
            "filename": "nse_pdf/unused-transcript.pdf",
            "sha256": unused_pdf_sha,
        },
        "xbrl": {
            "source_id": "nse-indas-xbrl-consolidated",
            "symbol": _SYMBOL,
            "local_path": f"{inputs.name}/nse/witness-fixture.xml",
        },
    }
    source_path = root / "witnessfix-fy26-q2.yaml"
    source_path.write_text(yaml.safe_dump(source_config, sort_keys=True), encoding="utf-8")
    manifest_path = tmp_path / "synthetic-witness-manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "issuer": _SYMBOL,
                "authorization": "SYNTHETIC schema fixture only; no actual source authority claim",
                "entries": [
                    {
                        "quarter": _QUARTER,
                        "kind": "xbrl-consolidated",
                        "filename": "witness-fixture.xml",
                        "sha256": digest,
                        "filed_at_nse": "29-Oct-2025 09:00:00",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    store_root = tmp_path / "synthetic-witness-snapshots"
    store_root.mkdir(mode=0o700)
    intake = retained_intake_from_manifest(
        manifest_path,
        issuer=_SYMBOL,
        quarter=_QUARTER,
        kinds={Representation.XBRL: "xbrl-consolidated"},
        store_root=store_root,
        input_root=inputs,
        issuer_config=source_path,
    )
    with pg_db.runtime_pool() as pool:
        handoff = append_first_party_generation(
            intake=intake,
            snapshot_store=SnapshotStore(store_root),
            pool=pool,
            config=loaded,
            config_root=root,
            entity_id=entity_id,
            basis=Basis.CONSOLIDATED,
            framework=AccountingFramework.IND_AS,
            family=FilingFamily.FINANCIAL_RESULTS,
            reporting_period_end=date(2025, 9, 30),
            pdf_specs=None,
            retain_intake_witness=True,
        )
    if handoff.retained_intake_witness_id is None:
        raise AssertionError("synthetic producer did not seal the requested witness")
    header = runtime.execute(
        "SELECT id FROM eqos.retained_intake_witnesses WHERE evidence_input_id=%s",
        (handoff.retained_intake_witness_id,),
    ).fetchone()
    if header is None:
        raise AssertionError("synthetic sealed witness header did not reload")
    result = {_TABLES[0]: int(header[0])}
    for table in _TABLES[1:]:
        row = runtime.execute(
            sql.SQL("SELECT min(id) FROM eqos.{} WHERE witness_id=%s").format(
                sql.Identifier(table)
            ),
            (header[0],),
        ).fetchone()
        if row is None or row[0] is None:
            raise AssertionError(f"synthetic sealed witness did not populate {table}")
        result[table] = int(row[0])
    return result
