"""Eligibility gate at the insertion boundary (plan D6 D4.5).

Called inside ``EvidenceRepository.put_generation``'s transaction, before anything is
inserted, for every capture the generation's occurrences and attempts cite. A capture is
refused (the whole generation rolls back) when its surface is identity-only, or when bytes
equal to it were captured by onboarding discovery and are not both (a) verified in some
``ONBOARDED``/``PARTIAL`` record and (b) absent from every record with another outcome.
Captures never linked to a ``DISCOVERY`` input (every pilot capture) pass.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any, LiteralString

import psycopg

from fundamentals.contracts.comparison import SourceRole
from fundamentals.contracts.onboarding import OnboardingOutcome, VerificationState
from fundamentals.contracts.source_catalog import VENDOR_SURFACES
from fundamentals.pg.identity_seed import EvidenceInputKind

_IDENTITY_SURFACES = frozenset(
    (item.source_id, item.surface) for item in VENDOR_SURFACES if item.role is SourceRole.IDENTITY
)
_ADMITTING = [OnboardingOutcome.ONBOARDED.value, OnboardingOutcome.PARTIAL.value]
_REFUSED = "capture {capture_id} ({source_id}/{surface}) is not eligible for occurrences: {why}"
_IDENTITY_ONLY = "identity-only surface"
_UNADMITTED = "discovery evidence not admitted by an ONBOARDED or PARTIAL verification"


class IneligibleCaptureError(RuntimeError):
    """A capture may not become an occurrence or attempt; nothing was written."""


def refuse_ineligible(conn: psycopg.Connection[Any], capture_ids: Iterable[int | None]) -> None:
    """Raise :class:`IneligibleCaptureError` for the first ineligible capture."""
    ids = sorted({capture_id for capture_id in capture_ids if capture_id is not None})
    if not ids:
        return
    params = {
        "ids": ids,
        "discovery": EvidenceInputKind.DISCOVERY.value,
        "verified": VerificationState.VERIFIED.value,
        "admitting": _ADMITTING,
    }
    for capture_id, source_id, surface, linked, admitted in conn.execute(_ELIGIBILITY, params):
        why = None
        if (source_id, surface) in _IDENTITY_SURFACES:
            why = _IDENTITY_ONLY
        elif linked and not admitted:
            why = _UNADMITTED
        if why:
            detail = _REFUSED.format(
                capture_id=capture_id, source_id=source_id, surface=surface, why=why
            )
            raise IneligibleCaptureError(detail)


# Per capture: whether equal bytes are linked to a DISCOVERY input, and whether they are
# admitted (some such input VERIFIED under an admitting record, none under another outcome).
_ELIGIBILITY: LiteralString = (
    "SELECT c.id, c.source_id, c.surface, count(i.id) > 0, "
    "COALESCE(bool_or(v.state = %(verified)s AND o.outcome = ANY(%(admitting)s)), false) "
    "AND NOT COALESCE(bool_or(o.outcome <> ALL(%(admitting)s)), false) "
    "FROM eqos.capture_refs c "
    "LEFT JOIN eqos.capture_refs d ON d.blob_sha256 = c.blob_sha256 "
    "LEFT JOIN eqos.evidence_input_captures l ON l.capture_ref_id = d.id "
    "LEFT JOIN eqos.evidence_inputs i ON i.id = l.evidence_input_id AND i.kind = %(discovery)s "
    "LEFT JOIN eqos.namespace_verifications v ON v.evidence_input_id = i.id "
    "LEFT JOIN eqos.onboarding_records o ON o.id = v.onboarding_record_id "
    "WHERE c.id = ANY(%(ids)s) GROUP BY c.id, c.source_id, c.surface ORDER BY c.id"
)
