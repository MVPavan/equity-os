"""Coordinator regressions for queue evidence and approval provenance."""

import hashlib
from typing import Any

import psycopg
import pytest
from pg_evidence_schema_support import NOW, _insert, _run_input, migrator, runtime, seeded
from pg_support import PgTestDatabase
from psycopg.types.json import Jsonb
from test_compare_queue import _draft, _publish, _seed_verified_synthetic_accept

from fundamentals.compare.queue import capture_queue_overlay, publish_queue_drafts
from fundamentals.contracts.canonical import Representation
from fundamentals.contracts.comparison import SourceRef, SourceRole

__all__ = ["migrator", "runtime", "seeded"]
pytestmark = pytest.mark.pg


def test_queue_draft_cannot_relabel_first_party_evidence_as_vendor_source(
    seeded: dict[str, int], runtime: psycopg.Connection[Any]
) -> None:
    """A real XBRL row cannot lend provenance to an invented HTML vendor side."""
    draft = _draft(seeded, pair_identity="forged-vendor-source").model_copy(
        update={
            "source_refs": (
                SourceRef(
                    source_role=SourceRole.INDEPENDENT_VENDOR,
                    representation=Representation.HTML,
                    source_id="invented-vendor",
                    surface="SCREENER_FINANCIALS",
                ),
            )
        }
    )
    before = runtime.execute("SELECT count(*) FROM eqos.queue_items").fetchone()[0]
    with pytest.raises(ValueError, match="(?i)(source|provenance|representation)"):
        with runtime.transaction(), runtime.cursor() as cursor:
            publish_queue_drafts(cursor, run_id=seeded["runs"], drafts=(draft,))
    assert runtime.execute("SELECT count(*) FROM eqos.queue_items").fetchone()[0] == before


def test_queue_draft_cannot_add_an_undeclared_missing_vendor_side(
    seeded: dict[str, int], runtime: psycopg.Connection[Any]
) -> None:
    draft = _draft(seeded, pair_identity="undeclared-missing-vendor")
    invented = SourceRef(
        source_role=SourceRole.INDEPENDENT_VENDOR,
        representation=Representation.HTML,
        source_id="invented-vendor",
        surface="SCREENER_FINANCIALS",
    )
    draft = draft.model_copy(update={"source_refs": (draft.source_refs[0], invented)})
    before = runtime.execute("SELECT count(*) FROM eqos.queue_items").fetchone()[0]
    with pytest.raises(ValueError, match="(?i)(source|provenance)"):
        with runtime.transaction(), runtime.cursor() as cursor:
            publish_queue_drafts(cursor, run_id=seeded["runs"], drafts=(draft,))
    assert runtime.execute("SELECT count(*) FROM eqos.queue_items").fetchone()[0] == before


def test_declared_missing_vendor_side_keeps_actual_first_party_provenance(
    seeded: dict[str, int], runtime: psycopg.Connection[Any]
) -> None:
    label = "declared-missing-vendor-side"
    digest = hashlib.sha256(label.encode()).hexdigest()
    run_id = _insert(
        runtime,
        "runs",
        {
            "identity_hash": digest,
            "cutoff": NOW,
            "mode": "AS_KNOWN",
            "status": "COMPLETE",
            "code_version": "queue-provenance-fixture",
            "manifest": Jsonb(
                {
                    "scope": {
                        "sources": ["NSE_XBRL_INSTANCE"],
                        "vendor_sources": [
                            {
                                "source_id": "declared-vendor",
                                "surface": "DECLARED_HTML",
                                "representation": "HTML",
                            }
                        ],
                    }
                }
            ),
            "manifest_sha256": hashlib.sha256(f"manifest:{label}".encode()).hexdigest(),
        },
    )
    _insert(
        runtime,
        "run_inputs",
        _run_input(
            run_id,
            "INTERPRETATION",
            interpretation_id=seeded["interpretations"],
        ),
    )
    base = _draft(seeded, pair_identity=label)
    vendor = SourceRef(
        source_role=SourceRole.INDEPENDENT_VENDOR,
        representation=Representation.HTML,
        source_id="declared-vendor",
        surface="DECLARED_HTML",
    )
    draft = base.model_copy(update={"source_refs": (base.source_refs[0], vendor)})

    (stored,) = _publish(runtime, run_id, (draft,))

    assert set(stored.source_refs) == set(draft.source_refs)


def _run_declaring_vendor_representation(
    runtime: psycopg.Connection[Any],
    *,
    label: str,
    representation: Representation,
) -> int:
    digest = hashlib.sha256(label.encode()).hexdigest()
    return _insert(
        runtime,
        "runs",
        {
            "identity_hash": digest,
            "cutoff": NOW,
            "mode": "AS_KNOWN",
            "status": "COMPLETE",
            "code_version": "queue-representation-fixture",
            "manifest": Jsonb(
                {
                    "scope": {
                        "sources": ["NSE_XBRL_INSTANCE"],
                        "vendor_sources": [
                            {
                                "source_id": "declared-vendor",
                                "surface": "DECLARED_VENDOR",
                                "representation": representation.value,
                            }
                        ],
                    }
                }
            ),
            "manifest_sha256": hashlib.sha256(f"manifest:{label}".encode()).hexdigest(),
        },
    )


def test_actual_vendor_evidence_representation_must_match_the_stored_declaration(
    seeded: dict[str, int], runtime: psycopg.Connection[Any]
) -> None:
    run_id = _run_declaring_vendor_representation(
        runtime,
        label="actual-vendor-representation",
        representation=Representation.HTML,
    )
    attempt_id = _insert(
        runtime,
        "acquisition_attempts",
        {
            "stage": "ACQUISITION",
            "source_id": "declared-vendor",
            "surface": "DECLARED_VENDOR",
            "entity_id": seeded["_entity"],
            "period_end": NOW.date(),
            "basis": "CONSOLIDATED",
            "framework": "IND_AS",
            "representation": "JSON",
            "statement_family": "PL",
            "package_id": None,
            "capture_ref_id": None,
            "input_sha256": hashlib.sha256(b"actual-vendor-json").hexdigest(),
            "extractor_version": "constructed-json-v1",
            "extraction_context_sha256": hashlib.sha256(b"json-context").hexdigest(),
            "outcome": "COMPLETE",
            "reason": None,
        },
    )
    _insert(runtime, "run_inputs", _run_input(run_id, "ATTEMPT", attempt_id=attempt_id))
    draft = _draft(
        seeded,
        pair_identity="actual-vendor-wrong-representation",
        interpretation_ids=(),
        attempt_ids=(attempt_id,),
    ).model_copy(
        update={
            "source_refs": (
                SourceRef(
                    source_role=SourceRole.INDEPENDENT_VENDOR,
                    representation=Representation.JSON,
                    source_id="declared-vendor",
                    surface="DECLARED_VENDOR",
                ),
            )
        }
    )
    before = runtime.execute("SELECT count(*) FROM eqos.queue_items").fetchone()[0]

    with pytest.raises(ValueError, match="(?i)(source|provenance|representation)"):
        with runtime.transaction(), runtime.cursor() as cursor:
            publish_queue_drafts(cursor, run_id=run_id, drafts=(draft,))

    assert runtime.execute("SELECT count(*) FROM eqos.queue_items").fetchone()[0] == before


def test_declared_missing_vendor_side_representation_must_match_the_stored_declaration(
    seeded: dict[str, int], runtime: psycopg.Connection[Any]
) -> None:
    run_id = _run_declaring_vendor_representation(
        runtime,
        label="missing-vendor-representation",
        representation=Representation.HTML,
    )
    _insert(
        runtime,
        "run_inputs",
        _run_input(
            run_id,
            "INTERPRETATION",
            interpretation_id=seeded["interpretations"],
        ),
    )
    base = _draft(seeded, pair_identity="missing-vendor-wrong-representation")
    wrong_vendor_side = SourceRef(
        source_role=SourceRole.INDEPENDENT_VENDOR,
        representation=Representation.JSON,
        source_id="declared-vendor",
        surface="DECLARED_VENDOR",
    )
    draft = base.model_copy(update={"source_refs": (base.source_refs[0], wrong_vendor_side)})
    before = runtime.execute("SELECT count(*) FROM eqos.queue_items").fetchone()[0]

    with pytest.raises(ValueError, match="(?i)(source|provenance|representation)"):
        with runtime.transaction(), runtime.cursor() as cursor:
            publish_queue_drafts(cursor, run_id=run_id, drafts=(draft,))

    assert runtime.execute("SELECT count(*) FROM eqos.queue_items").fetchone()[0] == before


def test_constructed_sql_receipt_cannot_close_a_queue_overlay_item(
    seeded: dict[str, int], pg_db: PgTestDatabase
) -> None:
    """Schema-only fixture evidence is not a verified authenticated decision."""
    with pg_db.runtime_pool() as pool:
        overlay = capture_queue_overlay(pool, run_id=seeded["runs"])
    assert seeded["queue_items"] in {item.item_id for item in overlay.open_items}
    assert seeded["queue_items"] not in {
        disposition.item_id for disposition in overlay.accepted_dispositions
    }


@pytest.mark.parametrize(
    "source_ref",
    (
        SourceRef(
            source_role=SourceRole.FIRST_PARTY,
            representation=Representation.XBRL,
            source_id="invented-first-party",
            surface="NSE_XBRL_INSTANCE",
        ),
        SourceRef(
            source_role=SourceRole.FIRST_PARTY,
            representation=Representation.XBRL,
            source_id="nse-indas-xbrl-consolidated",
            surface="NSE_RESULTS_PDF",
        ),
        SourceRef(
            source_role=SourceRole.REPORTED_COUNTERPART,
            representation=Representation.PDF,
        ),
    ),
)
def test_queue_draft_refuses_each_forged_provenance_component_before_dml(
    seeded: dict[str, int],
    runtime: psycopg.Connection[Any],
    source_ref: SourceRef,
) -> None:
    draft = _draft(seeded, pair_identity="forged-provenance-component").model_copy(
        update={"source_refs": (source_ref,)}
    )
    before = runtime.execute("SELECT count(*) FROM eqos.queue_items").fetchone()[0]
    with pytest.raises(ValueError, match="(?i)(source|provenance|representation)"):
        with runtime.transaction(), runtime.cursor() as cursor:
            publish_queue_drafts(cursor, run_id=seeded["runs"], drafts=(draft,))
    assert runtime.execute("SELECT count(*) FROM eqos.queue_items").fetchone()[0] == before


@pytest.mark.parametrize("invalid_proof", ("subject", "proposal", "raw", "document"))
def test_each_invalid_accept_proof_stays_open_with_an_explicit_failure(
    seeded: dict[str, int],
    runtime: psycopg.Connection[Any],
    migrator: psycopg.Connection[Any],
    pg_db: PgTestDatabase,
    invalid_proof: str,
) -> None:
    (item,) = _publish(
        runtime,
        seeded["runs"],
        (_draft(seeded, pair_identity=f"invalid-{invalid_proof}-accept"),),
    )
    assert item.item_id is not None
    disposition_id = _seed_verified_synthetic_accept(
        migrator,
        item.item_id,
        invalid_proof=invalid_proof,
    )

    with pg_db.runtime_pool() as pool:
        overlay = capture_queue_overlay(pool, run_id=seeded["runs"])

    assert item.item_id in {queued.item_id for queued in overlay.open_items}
    assert item.item_id not in {
        disposition.item_id for disposition in overlay.accepted_dispositions
    }
    assert disposition_id in {failure.disposition_id for failure in overlay.closure_failures}
