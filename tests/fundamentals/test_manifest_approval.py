"""The manifest-before-e2e rule (plan D6 Task 5d): the manifest at the e2e's parent must carry
its own APPROVE; the per-manifest checks are ``test_frozen_manifests.py``'s."""

from __future__ import annotations

import pytest
from manifest_support import approved, payload_sha256


def test_an_approval_added_after_the_e2e_is_refused() -> None:
    """SYNTHETIC: a payload PENDING at the e2e's parent and APPROVEd only later refuses, though
    the payload is unchanged."""
    pending = b"header:\n  approval: {verdict: PENDING}\n  id: zz\nrows: [1]\n"
    signed = f"APPROVE, date: 2026-10-16, payload_sha256: {payload_sha256(pending)}}}"
    later = pending.replace(b"PENDING}", signed.encode())
    approved(later, later)
    with pytest.raises(AssertionError):
        approved(pending, later)
