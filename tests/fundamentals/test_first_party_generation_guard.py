"""Publication guard regressions for the public first-party ingest seam."""

from __future__ import annotations

from pathlib import Path

import pytest
from evidence_support import Ingest, dictionary, ingest, mapping_set, policy
from test_vendor_config_publication import _draft_root

from fundamentals.evidence.mapping import load_mapping_set
from fundamentals.evidence.vendor_config import VendorConfigPublicationError

__all__ = ["dictionary", "ingest", "mapping_set", "policy"]

pytestmark = [pytest.mark.pg, pytest.mark.retained]


def test_public_ingest_refuses_vendor_mapping_without_verified_publication_before_write(
    ingest: Ingest, tmp_path: Path
) -> None:
    """A joined vendor mapping cannot use the legacy ingest path as a write bypass."""
    config_root = _draft_root(tmp_path)
    joined_mapping = load_mapping_set(config_root / "mappings", "v2", dictionary=ingest.dictionary)
    before = ingest.table_counts()

    try:
        with pytest.raises(
            VendorConfigPublicationError,
            match="verified vendor publication",
        ):
            ingest.run(ingest.intake(), mapping_set=joined_mapping)
    finally:
        assert ingest.table_counts() == before
