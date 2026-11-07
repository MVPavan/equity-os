"""VENDOR-1 Phase 2 phase-review findings 1 and 5: checking and sealing hold the vendor summary to
the block drafting renders, and a duplicate span drafting discards never resolves.

Reuses the extracted ``World`` of ``test_vendor_text_citation``. Revisions edit the rendered block
by marker and synthetic words only; no vendor text is written here or printed.
"""

from __future__ import annotations

import json
from datetime import datetime
from functools import partial
from typing import Any
from unittest.mock import Mock

import pytest
from ledger_support import claim, ledger
from pg_evidence_schema_support import runtime, seeded
from retention_support import record_of
from test_vendor_surface_claims import RETAINED, registered_addresses, retained_texts
from test_vendor_text_citation import SETTINGS, SOURCE, World, world
from test_vendor_values_store import outcome

from equity_os.contracts.publication.ledger import ReportSection, RunMode, VersionState
from equity_os.contracts.sourcing.source_catalog import BUILTIN_SOURCES
from equity_os.extraction.model.vendor_surface_claims import extract_text
from equity_os.extraction.model.vendor_surface_model import ModelReply
from equity_os.publication.approval import lifecycle
from equity_os.publication.approval.lifecycle import DecisionRefusedError
from equity_os.publication.checking.citations import resolve_location
from equity_os.publication.checking.numeral_scan import LOCATION_MARKER, scan_section
from equity_os.publication.drafting.display import content_hash
from equity_os.publication.drafting.vendor_summary import VENDOR_SUMMARY, vendor_summary_section
from equity_os.sourcing.surfaces.vendor_surface_fetch import Fetched
from equity_os.storage.database.settings import PgRole
from equity_os.storage.raw_files.snapshot_store import SnapshotStore
from equity_os.storage.records.vendor_values_store import VendorValuesStore, register

__all__ = ["ledger", "runtime", "seeded", "world"]

pytestmark = [pytest.mark.pg, pytest.mark.retained]

GUIDANCE = "guidance, not evidence"


def rendered(world: World, now: datetime) -> str:
    """The vendor block drafting renders for Apar at ``now`` as both cutoffs."""
    with world.pool.connection() as conn, conn.cursor() as cursor:
        section = vendor_summary_section(
            cursor,
            entity_id=world.ledger.entity_id,
            source_cutoff=now,
            knowledge_cutoff=now,
            snapshots=world.store,
        )
    assert section is not None
    return section[1]


def scan_clean(world: World, body: str, now: datetime) -> bool:
    """Whether the generic section scan, with the real resolver, raises nothing."""
    with world.pool.connection() as conn, conn.cursor() as cursor:
        resolves = partial(
            resolve_location,
            cursor,
            entity_id=world.ledger.entity_id,
            cutoff=now,
            catalog=BUILTIN_SOURCES,
            snapshots=world.store,
            source_cutoff=now,
        )
        return scan_section(body, resolves=resolves) == ()


def lifecycle_states(
    world: World, body: str, now: datetime, key: str = VENDOR_SUMMARY
) -> tuple[tuple[VersionState, ...], bool]:
    """A fresh version holding one section: its checked states, and whether submission seals."""
    section = ReportSection(ordinal=0, section_key=key, body=body)
    named = claim(world.ledger.trace_id).model_copy(update={"section_key": key})
    claims = (named,)  # a placeholder needs a claim to name
    version = world.ledger.draft(
        world.ledger.report(),
        source_cutoff=now,
        knowledge_cutoff=now,
        sections=(section,),
        claims=claims,
        content_hash=content_hash((section,), claims),
    )
    sources: dict[str, Any] = {"catalog": BUILTIN_SOURCES, "snapshots": world.store}
    pool = world.ledger.pools[PgRole.RUNTIME]
    states = lifecycle.validate(pool, version, mode=RunMode.AS_KNOWN, **sources).version_states
    try:
        lifecycle.submit(pool, version, **sources)
    except DecisionRefusedError as refused:
        assert VersionState.UNCITED_PROSE in str(refused), "submission refused for another state"
        return states, False
    return states, True


def test_checking_and_sealing_hold_the_vendor_block_to_its_rendering(world: World) -> None:
    """Each revision keeps a resolving anchor or drops it, so the generic scan passes; only the
    vendor-section check refuses it at checking and at submission."""
    now = world.now
    body = rendered(world, now)
    (capture, anchor), *more = LOCATION_MARKER.findall(body)
    assert not more and (capture, anchor) == world.anchor("claim")
    marker = f"{{{{s:{capture}|{anchor}}}}}"
    key = claim(world.ledger.trace_id).claim_key
    # The block's one paragraph is its last; replace it whole, keeping heading and title.
    head = body.rstrip().rsplit("\n\n", 1)[0]
    revisions = {
        "changed text": f"{head}\n\n{{{{e:inferred}}}} Plant opens {marker}\n",
        "anchor removed": body.replace(marker, ""),
        "placeholder": body.replace(marker, f"{{{{c:{key}|}}}} {marker}"),
        "number word": f"{head}\n\n{{{{e:inferred}}}} Two plants opened {marker}\n",
        "period or date": f"{head}\n\n{{{{e:inferred}}}} Opened FY26, 2026-01-01 {marker}\n",
        "extra prose": body + "\n{{e:inferred}} Plant opens\n",
        "heading": body.replace(GUIDANCE, "outlook"),
    }
    assert len(set(revisions.values()) | {body}) == len(revisions) + 1
    assert lifecycle_states(world, body, now) == ((), True)
    results = {
        name: (scan_clean(world, b, now), *lifecycle_states(world, b, now))
        for name, b in revisions.items()
    }
    assert results == dict.fromkeys(revisions, (True, (VersionState.UNCITED_PROSE,), False))


def duplicate_capture(world: World) -> tuple[str, str]:
    """Register the same retained concall summary on a second route and extract the same claim
    span from it; returns the duplicate's location marker parts."""
    key, capture, read = next((k, c, r) for k, c, r in retained_texts("concall-summary") if r.text)
    retained = SnapshotStore(RETAINED.parent)
    body = retained.read_body(retained.get_capture(SOURCE, "vs.concall-summary", key, capture))
    record = record_of(body, SOURCE, "vs.concall-summary")
    world.store.put_capture(record, body)
    ref = register(
        world.pool, Fetched(record=record, url=registered_addresses()[key], location=None)
    )
    values = VendorValuesStore(world.pool)
    values.record(
        ref, outcome(version="kept.v1", surface="concall-summary", values=()), row_count=0
    )
    _, start, end = world.spans["claim"]
    reply = json.dumps([{"kind": "CLAIM", "start": start, "end": end}])
    model = Mock(
        model_id="fake",
        complete=Mock(return_value=ModelReply(text=reply, input_tokens=1, output_tokens=1)),
    )
    assert read.text == world.concall.text, "the duplicate is not the same retained text"
    assert extract_text(world.pool, world.store, model, SETTINGS) == 1
    assert (
        ref.capture_ref_id is not None and ref.capture_ref_id > world.refs["concall"].capture_ref_id
    )
    return str(ref.capture_ref_id), f"vt:{start}-{end}:{ref.blob_sha256}"


def test_a_discarded_duplicate_is_neither_drafted_nor_resolved(world: World) -> None:
    """Equal texts are kept once at their lowest (capture, start) before any capture filter, so
    drafting, checking and sealing select the same span."""
    duplicate = duplicate_capture(world)
    now = world.clock()
    canonical = world.anchor("claim")
    body = rendered(world, now)
    assert LOCATION_MARKER.findall(body) == [canonical]  # drafting keeps the canonical only
    with world.pool.connection() as conn, conn.cursor() as cursor:
        resolved = {
            name: resolve_location(
                cursor,
                *where,
                entity_id=world.ledger.entity_id,
                cutoff=now,
                catalog=BUILTIN_SOURCES,
                snapshots=world.store,
                source_cutoff=now,
            )
            for name, where in (("canonical", canonical), ("duplicate", duplicate))
        }
    assert resolved == {"canonical": True, "duplicate": False}

    def cited(where: tuple[str, str]) -> str:
        return f"{{{{e:inferred}}}} {{{{s:{where[0]}|{where[1]}}}}}"

    swapped = body.replace(f"s:{canonical[0]}|{canonical[1]}", f"s:{duplicate[0]}|{duplicate[1]}")
    results = {
        "block": lifecycle_states(world, body, now),
        "swapped block": lifecycle_states(world, swapped, now),
        "canonical": lifecycle_states(world, cited(canonical), now, key="notes"),
        "duplicate": lifecycle_states(world, cited(duplicate), now, key="notes"),
    }
    refused = ((VersionState.UNCITED_PROSE,), False)
    assert results == {
        "block": ((), True),
        "swapped block": refused,
        "canonical": ((), True),
        "duplicate": refused,
    }
