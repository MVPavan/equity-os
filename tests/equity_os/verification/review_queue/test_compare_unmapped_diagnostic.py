"""Unmapped queue proposals preserve the actual source role without inventing a key."""

from equity_os.contracts.measurement.canonical import Representation
from equity_os.contracts.verification.comparison import SourceRef, SourceRole
from equity_os.contracts.verification.review_queue import QueueSeverity
from equity_os.verification.review_queue.routing import route_unmapped_occurrence_draft


def test_unmapped_proposals_preserve_diagnostic_and_independent_roles() -> None:
    """Both roles remain LOW; only the actual diagnostic source carries that flag."""
    cases = (
        (SourceRole.DIAGNOSTIC, Representation.JSON, "synthetic-upstox", True),
        (SourceRole.INDEPENDENT_VENDOR, Representation.HTML, "synthetic-tijori", False),
    )
    for role, representation, source_id, diagnostic in cases:
        source = SourceRef(
            source_role=role,
            representation=representation,
            source_id=source_id,
            surface="SYNTHETIC_UNMAPPED_SURFACE",
        )
        item = route_unmapped_occurrence_draft(occurrence_id=42, source_ref=source)
        assert item.diagnostic is diagnostic, role
        assert item.severity is QueueSeverity.LOW, role
        assert item.key is None, role
        assert item.evidence_occurrence_ids == (42,), role
        assert item.source_refs == (source,), role
