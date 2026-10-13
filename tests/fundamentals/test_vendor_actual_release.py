"""Actual committed vendor v2 release and retained first-party generation proof."""

from pathlib import Path

import pytest
from evidence_support import Ingest, dictionary, ingest, mapping_set, policy
from test_first_party_generation import _append

from fundamentals.compare.run_config import (
    ConfigVersions,
    load_run_config,
    require_published_generation,
)
from fundamentals.evidence.first_party_context import QUALIFICATION_CONTEXT_TRACE_KEY
from fundamentals.evidence.vendor_config import PublicationState

__all__ = ["dictionary", "ingest", "mapping_set", "policy"]

CONFIG = Path(__file__).resolve().parents[2] / "config"
PUBLICATION_SHA256 = "1770517e47e08cf2b33f220efd90e11e6ada26f3013ccfa518785370cb1d1693"


def test_committed_actual_vendor_v2_release_loads_without_synthetic_authority() -> None:
    """The public loader proves the actual A/review/C/H chain and exact release pins."""
    loaded = load_run_config(CONFIG, ConfigVersions(dictionary="v2", mapping_set="v2"))
    publication = require_published_generation(loaded, config_root=CONFIG)
    assert publication.state is PublicationState.RELEASED
    assert publication.version == "v2"
    assert publication.content_sha256 == PUBLICATION_SHA256
    assert loaded.pinned.vendor_publication is not None
    assert loaded.pinned.vendor_publication.content_sha256 == PUBLICATION_SHA256
    assert len(loaded.dictionary.rows) == 260
    assert len(loaded.mapping_set.entries) == 416
    assert not any(authority.source_id == "upstox" for authority in publication.authorities)
    assert {
        (item.source_id, item.surface): item.disposition.value
        for item in publication.surface_ledger
        if item.source_id == "upstox"
    } == {
        ("upstox", "income-statement"): "EXCLUDED",
        ("upstox", "balance-sheet"): "EXCLUDED",
        ("upstox", "cash-flow"): "EXCLUDED",
        ("upstox", "key-ratios"): "EXCLUDED",
    }


@pytest.mark.pg
@pytest.mark.retained
def test_actual_release_appends_retained_first_party_v2_and_preserves_v1(ingest: Ingest) -> None:
    """Real retained bytes use the committed release; synthetic receipts are not supplied."""
    before = ingest.run(ingest.intake())
    old_ids = tuple(row_id for member in before.members for row_id in member.interpretation_ids)
    old_rows = ingest.repository.get_interpretations(old_ids)
    loaded = load_run_config(CONFIG, ConfigVersions(dictionary="v2", mapping_set="v2"))
    with ingest.pg_db.runtime_pool() as pool:
        handoff = _append(ingest, CONFIG, loaded, pool)
        repeated = _append(ingest, CONFIG, loaded, pool)
    new_ids = tuple(row_id for member in handoff.members for row_id in member.interpretation_ids)
    new_rows = ingest.repository.get_interpretations(new_ids)
    assert handoff.publication_state is PublicationState.RELEASED
    assert handoff.publication_sha256 == PUBLICATION_SHA256
    assert handoff == repeated
    assert set(new_ids).isdisjoint(old_ids)
    assert len(new_rows) == len(new_ids)
    assert all(row.mapping_set_version == "v2" for row in new_rows)
    assert all(QUALIFICATION_CONTEXT_TRACE_KEY in row.transform_trace for row in new_rows)
    assert ingest.repository.get_interpretations(old_ids) == old_rows
