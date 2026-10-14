"""B1: a vendor capture's interpretations are reused only under the same versions and scope."""

from __future__ import annotations

from datetime import date
from typing import Any

import pytest
from test_evidence_vendor import RETAINED, TIJORI_THERMAX, _entity, config, tijori

from fundamentals.contracts.canonical import Basis, Representation
from fundamentals.contracts.observation import AccountingFramework
from fundamentals.evidence import vendor_tijori
from fundamentals.evidence.repository import EvidenceRepository, InterpretationConflictError
from fundamentals.evidence.vendor_ingest import VendorIngestRequest, ingest_vendor
from fundamentals.store.snapshot_store import SnapshotStore

__all__ = ["config"]

CAPTURE_FIELDS = ("source_id", "surface", "request_key", "capture_id")


@pytest.mark.pg
def test_interpretations_are_not_reused_across_a_basis_change(
    pg_db: Any, config: tuple[Any, Any, Any, Any]
) -> None:
    """The same occurrences under another basis never reuse the earlier scope's rows (B1); the
    store keys interpretations by occurrence and versions alone, so the new write is refused."""
    dictionary, mappings, policy, rounding = config
    entity, consolidated = _entity(pg_db, "THERMAX"), tijori("thermax-limited", "THERMAX")

    def ingest(basis: Basis, extract: Any) -> Any:
        return ingest_vendor(
            VendorIngestRequest(
                **dict(zip(CAPTURE_FIELDS, TIJORI_THERMAX, strict=True)),
                representation=Representation.HTML,
                entity_id=entity,
                period_end=date(2026, 3, 31),
                basis=basis,
                framework=AccountingFramework.IND_AS,
            ),
            extract=extract,
            extractor_version=vendor_tijori.EXTRACTOR_VERSION,
            snapshot_store=SnapshotStore(RETAINED),
            repository=EvidenceRepository(pool),
            dictionary=dictionary,
            mapping_set=mappings,
            policy=policy,
            rounding_policy=rounding,
            fiscal_year_end_month=3,
        )

    def relabelled(*args: Any, **kwargs: Any) -> Any:
        return consolidated(*args, **kwargs).model_copy(update={"basis": Basis.STANDALONE})

    with pg_db.runtime_pool() as pool:
        assert ingest(Basis.CONSOLIDATED, consolidated).interpretations
        with pytest.raises(InterpretationConflictError):
            ingest(Basis.STANDALONE, relabelled)
