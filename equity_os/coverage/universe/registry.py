"""The universe registry: load one retained Upstox instrument capture (plan D7 Task 1).

A load is identified by its capture reference, whose id carries the retrieval time stated in the
capture's own record — never today's clock — so replaying a retained capture is the same load
and writes nothing, while a later capture of identical bytes is a new load. Each load records one
sighting per listing (segment, ISIN) and, for each listing whose symbol differs from its sighting
in the preceding load, one candidate event. Nothing here writes the identity layers.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import LiteralString

import structlog
from psycopg_pool import ConnectionPool
from pydantic import BaseModel, ConfigDict

from equity_os.companies.onboarding.discovery import OK, Capture, Request, Response, store_captures
from equity_os.contracts.companies.onboarding import VerificationUnit
from equity_os.contracts.sourcing.source_catalog import UPSTOX_INSTRUMENTS
from equity_os.sourcing.vendors.upstox.upstox_instruments import read_instrument_catalog
from equity_os.sourcing.vendors.upstox.upstox_source import (
    AcquisitionOutcome,
    UpstoxCapture,
    UpstoxConfig,
    UpstoxFetch,
)
from equity_os.storage.raw_files.snapshot_store import SnapshotStore
from equity_os.storage.records.repository import EvidenceRepository

RAW_SUFFIX = ".raw.json.gz"
META_SUFFIX = "_meta.json"
LOADED_EVENT = "coverage.registry_loaded"
_UNREADABLE = "instrument capture {path} read as {outcome}"
_MISMATCH = "instrument capture {path} does not hash to its record's content_sha256"
# Arbitrary fixed key: loads serialise so "the preceding load" is the committed latest.
REGISTRY_LOCK: LiteralString = "SELECT pg_advisory_xact_lock(4215031024)"
_INSERT_LOAD: LiteralString = (
    "INSERT INTO eqos.registry_loads (capture_ref_id, content_sha256) VALUES (%s, %s) "
    "ON CONFLICT (capture_ref_id) DO NOTHING RETURNING id"
)
_EXISTING_LOAD: LiteralString = "SELECT id FROM eqos.registry_loads WHERE capture_ref_id = %s"
_INSERT_LISTINGS: LiteralString = (
    "INSERT INTO eqos.registry_listings (segment, isin) "
    "SELECT * FROM unnest(%s::text[], %s::text[]) ON CONFLICT DO NOTHING"
)
_INSERT_SIGHTINGS: LiteralString = (
    "INSERT INTO eqos.registry_sightings (listing_id, load_id, trading_symbol, exchange_token, "
    "name) SELECT l.id, %s, o.symbol, o.token, o.name "
    "FROM unnest(%s::text[], %s::text[], %s::text[], %s::text[], %s::text[]) "
    "AS o (segment, isin, symbol, token, name) "
    "JOIN eqos.registry_listings l ON l.segment = o.segment AND l.isin = o.isin"
)
_INSERT_EVENTS: LiteralString = (
    "INSERT INTO eqos.registry_candidate_events (listing_id, load_id, previous_symbol, "
    "observed_symbol) SELECT s.listing_id, s.load_id, p.trading_symbol, s.trading_symbol "
    "FROM eqos.registry_sightings s JOIN eqos.registry_sightings p ON p.listing_id = s.listing_id "
    "AND p.load_id = (SELECT max(id) FROM eqos.registry_loads WHERE id < %(load)s) "
    "WHERE s.load_id = %(load)s AND p.trading_symbol <> s.trading_symbol"
)


class RegistryLoad(BaseModel):
    """What one load wrote; a replayed capture is ``created=False`` with nothing new."""

    model_config = ConfigDict(frozen=True)

    load_id: int
    created: bool
    new_listings: int
    candidate_events: int


def load_registry(
    pool: ConnectionPool, instruments: Path, snapshots: SnapshotStore
) -> RegistryLoad:
    """Register the capture at ``instruments`` (beside its ``_meta.json`` record) and load it."""
    meta = instruments.with_name(instruments.name.removesuffix(RAW_SUFFIX) + META_SUFFIX)
    fetch = UpstoxFetch(
        raw_body=instruments.read_bytes(),
        capture=UpstoxCapture.model_validate_json(meta.read_bytes()),
    )
    if hashlib.sha256(fetch.raw_body).hexdigest() != fetch.capture.content_sha256:
        raise ValueError(_MISMATCH.format(path=instruments))
    catalog = read_instrument_catalog(
        fetch, max_decompressed_bytes=UpstoxConfig().max_decompressed_bytes
    )
    if catalog.outcome is not AcquisitionOutcome.OK:
        raise ValueError(_UNREADABLE.format(path=instruments, outcome=catalog.outcome.value))
    source_id, surface = UPSTOX_INSTRUMENTS
    request = Request(
        unit=VerificationUnit.UPSTOX,
        source_id=source_id,
        surface=surface,
        url=fetch.capture.request_url,
    )
    response = Response(outcome=OK, body=fetch.raw_body, retrieved_at=fetch.capture.retrieved_at)
    with snapshots.prepare_ordinary_output():
        ((_, ref),) = store_captures(
            snapshots, EvidenceRepository(pool), [Capture(request=request, response=response)]
        )
    rows = catalog.instruments
    with pool.connection() as conn, conn.transaction():
        conn.execute(REGISTRY_LOCK)
        inserted = conn.execute(
            _INSERT_LOAD, (ref.capture_ref_id, catalog.content_sha256)
        ).fetchone()
        if inserted is None:
            (existing,) = conn.execute(_EXISTING_LOAD, (ref.capture_ref_id,)).fetchall()
            return RegistryLoad(
                load_id=existing[0], created=False, new_listings=0, candidate_events=0
            )
        load_id = int(inserted[0])
        segments, isins = [row.segment for row in rows], [row.isin for row in rows]
        new_listings = conn.execute(_INSERT_LISTINGS, (segments, isins)).rowcount
        conn.execute(
            _INSERT_SIGHTINGS,
            (
                load_id,
                segments,
                isins,
                [row.trading_symbol for row in rows],
                [row.exchange_token for row in rows],
                [row.name for row in rows],
            ),
        )
        events = conn.execute(_INSERT_EVENTS, {"load": load_id}).rowcount
    structlog.get_logger(__name__).info(
        LOADED_EVENT, load_id=load_id, new_listings=new_listings, candidate_events=events
    )
    return RegistryLoad(
        load_id=load_id, created=True, new_listings=new_listings, candidate_events=events
    )
