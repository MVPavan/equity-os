"""VENDOR-1 Phase 2 phase-review findings 1 and 5 and closing-review findings 2, 4 and 5: checking
and sealing hold the vendor summary to the block drafting renders, vendor text is cited nowhere
else, a duplicate span drafting discards never resolves, and a capture whose reader loses its
issuer reference or that expires before its bytes are read shows nothing while others still do.

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
from equity_os.contracts.sourcing.snapshot import IntegrityError
from equity_os.contracts.sourcing.source_catalog import BUILTIN_SOURCES
from equity_os.contracts.storage.retention import OriginalExpiredError
from equity_os.extraction.model.vendor_surface_claims import extract_text
from equity_os.extraction.model.vendor_surface_model import ModelReply
from equity_os.extraction.surfaces import vendor_text_readers
from equity_os.extraction.surfaces.vendor_text_readers import WRONG_ADDRESS, ReaderText
from equity_os.publication.approval import lifecycle
from equity_os.publication.approval.lifecycle import DecisionRefusedError
from equity_os.publication.checking import vendor_text
from equity_os.publication.checking.citations import resolve_location
from equity_os.publication.checking.numeral_scan import LOCATION_MARKER, scan_section
from equity_os.publication.drafting.display import content_hash
from equity_os.publication.drafting.vendor_summary import VENDOR_SUMMARY, vendor_summary_section
from equity_os.sourcing.surfaces.vendor_surface_fetch import Fetched, Site
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
    observed = body.rstrip().rsplit("\n\n", 1)[1].replace("{{e:inferred}}", "{{e:observed}}")
    revisions = {
        "changed text": f"{head}\n\n{{{{e:inferred}}}} Plant opens {marker}\n",
        "anchor removed": body.replace(marker, ""),
        "placeholder": body.replace(marker, f"{{{{c:{key}|}}}} {marker}"),
        "number word": f"{head}\n\n{{{{e:inferred}}}} Two plants opened {marker}\n",
        "period or date": f"{head}\n\n{{{{e:inferred}}}} Opened FY26, 2026-01-01 {marker}\n",
        "extra prose": body + "\n{{e:inferred}} Plant opens\n",
        "heading": body.replace(GUIDANCE, "outlook"),
    }
    distinct = len(set(revisions.values()) | {body}) == len(revisions) + 1
    assert distinct, "a revision repeats another or the block"
    # Revisions that leave the vendor section: renamed, its paragraph moved into an ordinary
    # observed section, or deleted while the rendering at the version's cutoffs is not empty.
    elsewhere = {
        "renamed": body,
        "moved as observed": f"## notes\n\n{observed}\n",
        "deleted": "## notes\n",
    }
    valid = lifecycle_states(world, body, now)
    assert valid == ((), True)
    results = {
        name: (scan_clean(world, b, now), *lifecycle_states(world, b, now))
        for name, b in revisions.items()
    } | {
        name: (scan_clean(world, b, now), *lifecycle_states(world, b, now, key="notes"))
        for name, b in elsewhere.items()
    }
    expected = dict.fromkeys(revisions | elsewhere, (True, (VersionState.UNCITED_PROSE,), False))
    assert results == expected


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
    same = read.text == world.concall.text
    assert same, "the duplicate is not the same retained text"
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
    markers = LOCATION_MARKER.findall(body)
    assert markers == [canonical]  # drafting keeps the canonical only
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

    swapped = body.replace(f"s:{canonical[0]}|{canonical[1]}", f"s:{duplicate[0]}|{duplicate[1]}")
    results = {
        "block": lifecycle_states(world, body, now),
        "swapped block": lifecycle_states(world, swapped, now),
    }
    assert results == {"block": ((), True), "swapped block": ((VersionState.UNCITED_PROSE,), False)}


def test_a_capture_whose_reader_loses_its_issuer_reference_shows_nothing(
    world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A completed concall extraction whose reader now finds no or two breadcrumb company links
    refuses that capture's location and block; another issuer's span still resolves, and any
    other reader refusal still raises."""
    now = world.now
    body = rendered(world, now)
    results = {}
    for name, xpath in (("missing", "//nothing/@href"), ("ambiguous", "//a/@href")):
        monkeypatch.setattr(vendor_text_readers, "SUMMARY_COMPANY_XPATH", xpath)
        results[name] = (
            world.resolves("claim"),
            world.resolves("other_item", entity=world.other),
            lifecycle_states(world, body, now),
        )
    refused = (False, True, ((VersionState.UNCITED_PROSE,), False))
    assert results == {"missing": refused, "ambiguous": refused}

    def broken(body: bytes, url: str) -> ReaderText:
        raise ValueError(WRONG_ADDRESS)

    monkeypatch.setitem(vendor_text_readers.READERS, (Site.SCREENER, "concall-summary"), broken)
    with pytest.raises(ValueError, match=WRONG_ADDRESS):
        world.resolves("claim")


def test_a_capture_expiring_before_its_bytes_are_read_is_unresolved(
    world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Purge can expire a capture between the retention predicate and the byte read: that
    capture's location is unresolved and its block uncited, others still resolve; a retained
    capture missing its body still raises."""
    now = world.now
    body = rendered(world, now)
    concall = world.refs["concall"].capture_ref_id
    real = vendor_text.retained_capture

    def expiring(conn: Any, store: Any, ref: Any) -> Any:
        if ref.capture_ref_id == concall:
            raise OriginalExpiredError(f"ORIGINAL_EXPIRED: capture {concall} is EXPIRED")
        return real(conn, store, ref)

    monkeypatch.setattr(vendor_text, "retained_capture", expiring)
    results = (
        world.resolves("claim"),
        world.resolves("other_item", entity=world.other),
        lifecycle_states(world, body, now),
    )
    assert results == (False, True, ((VersionState.UNCITED_PROSE,), False))

    def lost(conn: Any, store: Any, ref: Any) -> Any:
        raise IntegrityError("retained capture lost its body")

    monkeypatch.setattr(vendor_text, "retained_capture", lost)
    with pytest.raises(IntegrityError):
        world.resolves("claim")
