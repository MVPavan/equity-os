"""D1b source-qualified persistence of vendor values, pins and vendor-capture traces.

All figures, sources and captures here are constructed plumbing fixtures. They are not
vendor qualification evidence. PostgreSQL writes use only the guarded pg_db harness.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from fractions import Fraction

import psycopg
import pytest
from pg_evidence_schema_support import _capture, _insert, _interpretation, _occurrence, _trace
from pg_support import PgTestDatabase
from psycopg import errors
from selection_support import capture, interpretation, key, member, occurrence

from equity_os.contracts.measurement.canonical import Basis, Representation, ValueIdentity
from equity_os.contracts.measurement.evidence import RunMode, VendorExtractorPin
from equity_os.normalisation.derivation.formula import CalculationTrace, TraceOperand
from equity_os.storage.records.repository import EvidenceRepository
from equity_os.verification.comparison.run_config import load_run_config
from equity_os.verification.comparison.run_models import (
    DatabaseIdentity,
    PairRecord,
    ResultRow,
    RunManifest,
    RunScope,
    RunStatus,
    SourceRef,
    SourceValue,
    row_id,
)
from equity_os.verification.comparison.run_store import RunStore

NOW = datetime(2026, 10, 13, tzinfo=UTC)
END = date(2025, 9, 30)


def _seed(conn: psycopg.Connection) -> tuple[int, int]:
    evidence = _insert(
        conn,
        "evidence_inputs",
        {
            "kind": "ISSUER_IDENTITY",
            "label": "constructed vendor schema",
            "content_sha256": "1" * 64,
        },
    )
    entity = _insert(
        conn,
        "reporting_entities",
        {
            "entity_key": "CONSTRUCTED-VENDOR",
            "market": "IN",
            "display_name": "Constructed Ltd",
            "evidence_input_id": evidence,
        },
    )
    definition = _insert(
        conn, "definition_sets", {"version": "constructed", "content_sha256": "2" * 64}
    )
    return entity, definition


def _value(
    source: str,
    surface: str,
    representation: str,
    interpretation_id: int,
    role: str = "INDEPENDENT_VENDOR",
) -> SourceValue:
    return SourceValue.model_validate(
        {
            "source_role": role,
            "representation": representation,
            "source_id": source,
            "surface": surface,
            "state": "VALUE",
            "reason": None,
            "value": "1000000000",
            "lower": "999950000",
            "upper": "1000050000",
            "interpretation_id": interpretation_id,
            "calculation_trace_id": None,
            "attempt_id": None,
            "calculation_state": None,
        }
    )


@pytest.mark.pg
def test_two_html_vendors_and_two_diagnostic_surfaces_survive_runstore_roundtrip(
    pg_db: PgTestDatabase,
) -> None:
    with pg_db.migrator_connection() as conn:
        entity, definition = _seed(conn)
    with pg_db.runtime_pool() as pool:
        repository = EvidenceRepository(pool)
        sources = (
            ("fixture-a", "HTML_A", "HTML", "INDEPENDENT_VENDOR"),
            ("fixture-b", "HTML_B", "HTML", "INDEPENDENT_VENDOR"),
            ("fixture-c", "JSON_C1", "JSON", "DIAGNOSTIC"),
            ("fixture-c", "JSON_C2", "JSON", "DIAGNOSTIC"),
        )
        values = []
        for index, (source, surface, representation, role) in enumerate(sources, 1):
            clock = repository.store_clock()
            ref = repository.put_capture_ref(
                capture(index, clock).model_copy(
                    update={
                        "capture_ref_id": None,
                        "source_id": source,
                        "surface": surface,
                    }
                )
            )
            owner = member(Representation.XBRL, index, clock, clock).model_copy(
                update={"capture": ref}
            )
            native = occurrence(index, owner).model_copy(
                update={
                    "occurrence_id": None,
                    "capture": ref,
                    "representation": Representation(representation),
                }
            )
            (stored,) = repository.put_occurrences((native,))
            (iid,) = repository.reserve_interpretation_ids(1)
            measurement = key().model_copy(update={"entity_id": entity})
            interpreted = interpretation(iid, owner, measurement=measurement).model_copy(
                update={
                    "occurrence_id": stored.occurrence_id,
                    "capture_ref_id": ref.capture_ref_id,
                    "representation": Representation(representation),
                    "recorded_at": repository.store_clock(),
                    "input_digest": f"constructed:{ref.capture_ref_id}:{stored.occurrence_id}",
                }
            )
            repository.put_interpretations((interpreted,))
            values.append(_value(source, surface, representation, iid, role))
        refs = [
            SourceRef.model_validate(
                {
                    "source_role": value.source_role,
                    "representation": value.representation,
                    "source_id": source,
                    "surface": surface,
                }
            )
            for value, (source, surface, _, _) in zip(values, sources, strict=True)
        ]
        pairs = tuple(
            PairRecord.model_validate(
                {
                    "pair_kind": "DIAGNOSTIC",
                    "left": diagnostic,
                    "right": ref,
                    "outcome": "AGREE_UNQUALIFIED",
                    "reason": None,
                    "triage": None,
                    "difference": "0",
                    "interval_gap": "0",
                    "definition_record_id": None,
                }
            )
            for diagnostic in refs[2:]
            for ref in refs[:2]
        )
        measurement = key().model_copy(update={"entity_id": entity})
        result = ResultRow.model_validate(
            {
                "row_id": row_id(measurement, ValueIdentity.REPORTED),
                "key": measurement,
                "dictionary_version": "v1",
                "value_identity": "REPORTED",
                "applicability": "APPLICABLE",
                "applicability_rule_id": "results.every_period",
                "extraction_status": "NONE",
                "extraction_reason": None,
                "corroboration_status": "VENDOR_ONLY",
                "corroboration_reason": None,
                "source_values": values,
                "pairs": pairs,
                "surfaced_restatements": (),
            }
        )
        from pathlib import Path

        pinned = load_run_config(Path(__file__).resolve().parents[4] / "config").pinned
        pinned = pinned.model_copy(
            update={
                "vendor_extractors": tuple(
                    VendorExtractorPin(
                        source_id=source,
                        surface=surface,
                        version="x1",
                        content_sha256="3" * 64,
                    )
                    for source, surface, _, _ in sources
                ),
            }
        )
        manifest = RunManifest(
            scope=RunScope(
                entity_ids=(entity,),
                period_ends=(END,),
                bases=(Basis.CONSOLIDATED,),
                sources=("NSE_XBRL_INSTANCE",),
            ),
            cutoff=repository.store_clock(),
            mode=RunMode.AS_KNOWN,
            pinned=pinned,
            code_version="constructed-schema",
            database_identity=DatabaseIdentity(host="constructed", port=5432, name=pg_db.dbname),
            inputs=(),
            status=RunStatus.COMPLETE,
        )
        store = RunStore(pool)
        run_id, created = store.publish(manifest, (result,), definition_set_id=definition)
        assert created
        (loaded,) = store.read_results(run_id)
        assert loaded == result
        assert {(v.source_id, v.surface) for v in loaded.source_values} == {
            ("fixture-a", "HTML_A"),
            ("fixture-b", "HTML_B"),
            ("fixture-c", "JSON_C1"),
            ("fixture-c", "JSON_C2"),
        }
        assert len(loaded.pairs) == 4
        assert store.read_manifest(run_id) == manifest
        assert store.read_versions(run_id) == pinned


@pytest.mark.pg
def test_vendor_capture_trace_selection_roundtrips_and_requires_value_provenance(
    pg_db: PgTestDatabase,
) -> None:
    with pg_db.migrator_connection() as conn:
        entity, _ = _seed(conn)
        capture_id = _insert(
            conn,
            "capture_refs",
            {**_capture(), "source_id": "constructed-vendor", "surface": "CONSTRUCTED_HTML"},
        )
        occurrence_id = _insert(
            conn, "occurrences", _occurrence(capture_id, "vendor-cell", representation="HTML")
        )
        interpretation_id = _insert(
            conn,
            "interpretations",
            _interpretation(entity, capture_id, occurrence_id, representation="HTML"),
        )
    with pg_db.runtime_pool() as pool:
        repository = EvidenceRepository(pool)
        leaf = TraceOperand.model_validate(
            {
                "name": "constructed",
                "key_digest": "constructed-key",
                "temporal_role": "DURATION",
                "interpretation_id": interpretation_id,
                "operand_trace_id": None,
                "alignment_proof_id": None,
                "mapping_entry_id": "constructed",
                "qualification_ref": None,
                "scoped_tier": "EQUIVALENCE_UNPROVEN",
                "selection_source": "VENDOR_CAPTURE",
                "source_state": "VALUE",
                "value": "12.34",
                "lower": "12.33",
                "upper": "12.35",
                "exact_value": Fraction(617, 50),
                "exact_interval": {"lower": Fraction(1233, 100), "upper": Fraction(247, 20)},
            }
        )
        trace = CalculationTrace.model_validate(
            {
                **_trace(),
                "operands": (leaf,),
                "exact_value": Fraction(617, 50),
                "exact_interval": {"lower": Fraction(1233, 100), "upper": Fraction(247, 20)},
            }
        )
        child_id = repository.put_calculation_trace(trace)
        parent_operand = leaf.model_copy(
            update={"interpretation_id": None, "operand_trace_id": child_id}
        )
        parent = trace.model_copy(update={"operands": (parent_operand,)})
        trace_id = repository.put_calculation_trace(parent)
        with pg_db.migrator_connection() as conn:
            spare = _insert(conn, "calculation_traces", _trace("f" * 64))
            with pytest.raises(errors.CheckViolation, match="calculation_trace_operands_check"):
                _insert(
                    conn,
                    "calculation_trace_operands",
                    {
                        "calculation_trace_id": spare,
                        "ordinal": 0,
                        "operand_name": "missing-source",
                        "key_digest": "constructed-key",
                        "temporal_role": "DURATION",
                        "scoped_tier": "EQUIVALENCE_UNPROVEN",
                        "selection_source": "VENDOR_CAPTURE",
                        "source_state": "VALUE",
                        "value": Decimal("12.34"),
                    },
                )
        (stored,) = repository.get_calculation_traces((trace_id,))
        assert stored.trace.operands[0].selection_source.value == "VENDOR_CAPTURE"
        assert stored.trace.operands[0].operand_trace_id == child_id
