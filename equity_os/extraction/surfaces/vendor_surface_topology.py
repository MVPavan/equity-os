"""Bind both Screener bases only from retained, identity-matching marker proofs."""

from collections.abc import Mapping

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from equity_os.contracts.measurement.evidence import CaptureReference
from equity_os.contracts.sourcing.snapshot import BodyCompleteness
from equity_os.extraction.surfaces.vendor_surface_parse import CompanyIds
from equity_os.extraction.vendors.screener.screener_session_models import Basis, BasisTopology
from equity_os.extraction.vendors.screener.screener_session_page import (
    parse_document,
    read_identity,
    read_markers,
)
from equity_os.storage.raw_files.snapshot_store import SnapshotStore
from equity_os.storage.records.repository_rows import capture_of


def bind_topology(
    pool: ConnectionPool,
    store: SnapshotStore,
    ids: CompanyIds,
    entity_id: int,
    pages: Mapping[Basis, CaptureReference],
) -> BasisTopology | None:
    """Reuse entity bindings, then verified onboarding and this run's two registered pages."""
    if ids.topology is not None:
        return ids.topology
    with pool.connection() as conn:
        bound: dict[str, int] = dict(
            conn.execute(
                "SELECT basis,warehouse_id FROM eqos.vendor_basis_bindings "
                "WHERE entity_id=%s AND screener_company_id=%s",
                (entity_id, ids.screener_company_id),
            ).fetchall()
        )
        with conn.cursor(row_factory=dict_row) as cursor:
            rows = cursor.execute(
                "SELECT c.* FROM eqos.onboarding_records o "
                "JOIN eqos.namespace_verifications v ON v.onboarding_record_id=o.id "
                "JOIN eqos.evidence_input_captures i ON i.evidence_input_id=v.evidence_input_id "
                "JOIN eqos.capture_refs c ON c.id=i.capture_ref_id "
                "JOIN eqos.capture_addresses a ON a.capture_ref_id=c.id "
                "WHERE o.entity_id=%s AND v.unit='SCREENER' AND v.state='VERIFIED' "
                "AND a.url LIKE %s AND eqos.capture_state(c.id) IN ('RETAINED','RESTORED') "
                "ORDER BY c.id DESC",
                (entity_id, "%/consolidated/"),
            ).fetchall()
        proofs = [(Basis.CONSOLIDATED, capture_of(row), "ONBOARDING") for row in rows]
        proofs.extend((basis, ref, "FIRST_CAPTURE") for basis, ref in pages.items())
        for basis, ref, evidence in proofs:
            if basis.name in bound:
                continue
            record = store.get_capture(ref.source_id, ref.surface, ref.request_key, ref.capture_id)
            if (
                record.http_status != 200
                or record.effective_body_completeness is not BodyCompleteness.COMPLETE
            ):
                continue
            tree = parse_document(store.read_body(record).decode())
            company, warehouse = read_identity(tree)
            marker = "Consolidated Figures" if basis is Basis.CONSOLIDATED else "Standalone Figures"
            if (
                company != ids.screener_company_id
                or warehouse is None
                or marker not in read_markers(tree)
            ):
                continue
            conn.execute(
                "INSERT INTO eqos.vendor_basis_bindings "
                "(entity_id,basis,screener_company_id,warehouse_id,capture_ref_id,evidence) "
                "VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                (entity_id, basis.name, company, warehouse, ref.capture_ref_id, evidence),
            )
        bound = dict(
            conn.execute(
                "SELECT basis,warehouse_id FROM eqos.vendor_basis_bindings "
                "WHERE entity_id=%s AND screener_company_id=%s",
                (entity_id, ids.screener_company_id),
            ).fetchall()
        )
    return (
        BasisTopology(
            consolidated_warehouse_id=bound[Basis.CONSOLIDATED.name],
            standalone_warehouse_id=bound[Basis.STANDALONE.name],
        )
        if len(bound) == 2
        else None
    )
