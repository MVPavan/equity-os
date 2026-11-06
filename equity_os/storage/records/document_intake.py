"""Append-only document intake state; the caller owns each registration transaction."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from datetime import date, datetime
from typing import Any

import psycopg
from psycopg.rows import class_row
from psycopg.types.json import Jsonb
from pydantic import BaseModel, ConfigDict

from equity_os.companies.onboarding.discovery import OK, TOO_LARGE
from equity_os.contracts.sourcing.source_catalog import DocumentKind

WRONG_TYPE = "WRONG_TYPE"
TRUNCATED = "TRUNCATED"
TERMINAL = frozenset({WRONG_TYPE, TOO_LARGE, "HTTP_404", "HTTP_410"})

RETENTION_SHARED = "SELECT eqos.retention_shared()"
COVERED = (
    "SELECT DISTINCT subject_id FROM eqos.decisions "
    "WHERE subject_kind='WATCHLIST' AND eqos.watchlisted(subject_id) ORDER BY subject_id"
)
INTAKE_ISSUERS = (
    "SELECT DISTINCT ON (entity_id) entity_id,symbol FROM eqos.document_listings "
    "ORDER BY entity_id,id DESC"
)
REGISTERED = (
    "SELECT 1 FROM eqos.capture_refs WHERE source_id=%s AND surface=%s "
    "AND request_key=%s AND capture_id=%s"
)
_INSERT_LISTING = (
    "INSERT INTO eqos.document_listings (entity_id,symbol,surface,span_from,span_to,"
    "retrieved_at,outcome,capture_ref_id) VALUES (%(entity_id)s,%(symbol)s,%(surface)s,"
    "%(span_from)s,%(span_to)s,%(retrieved_at)s,%(outcome)s,%(capture_ref_id)s) RETURNING id"
)
_INSERT_OBSERVATION = (
    "INSERT INTO eqos.document_observations (listing_id,occurrence_key,payload_sha256,"
    "payload,observed_at) VALUES (%s,%s,%s,%s,%s)"
)
_LATEST = (
    "SELECT DISTINCT ON (o.occurrence_key) o.id,o.occurrence_key,o.payload,o.payload_sha256,"
    "o.observed_at FROM eqos.document_observations o JOIN eqos.document_listings l "
    "ON l.id=o.listing_id WHERE l.entity_id=%s AND l.surface=%s "
    "ORDER BY o.occurrence_key,o.observed_at DESC,o.id DESC"
)
_ATTEMPTS = (
    "SELECT outcome FROM eqos.document_attempts WHERE observation_id=%s AND url=%s ORDER BY id"
)
_INSERT_ATTEMPT = (
    "INSERT INTO eqos.document_attempts (observation_id,url,attempted_at,outcome,body_sha256,"
    "capture_ref_id) VALUES (%s,%s,%s,%s,%s,%s)"
)
_STOP = "LEAST(span_to,(retrieved_at AT TIME ZONE 'Asia/Kolkata')::date)"
_OK_SPANS = (
    f"SELECT span_from,{_STOP} FROM eqos.document_listings WHERE entity_id=%s AND surface=%s "
    f"AND outcome='OK' AND span_from<={_STOP} ORDER BY span_from"
)
_OK_ATTEMPT = (
    "SELECT a.body_sha256,a.capture_ref_id,c.capture_id FROM eqos.document_attempts a "
    "JOIN eqos.capture_refs c ON c.id=a.capture_ref_id "
    "WHERE a.observation_id=%s AND a.url=%s AND a.outcome='OK' ORDER BY a.id LIMIT 1"
)
_FIRST_SPAN = "SELECT min(span_from) FROM eqos.document_listings WHERE entity_id=%s AND surface=%s"


def refusal(kind: DocumentKind, body: bytes) -> str:
    """Accept complete PDF bytes, or a complete annual-report ZIP, without interpreting either.
    A body without its end marker near the end is TRUNCATED, retried within the attempt bound
    (eqos-tmof: NSE served a 2.9 MB prefix of a 20.6 MB annual report three times)."""
    if body.startswith(b"%PDF-"):
        return OK if b"%%EOF" in body[-1024:] else TRUNCATED
    if kind is DocumentKind.ANNUAL_REPORT and body.startswith(b"PK\x03\x04"):
        return OK if b"PK\x05\x06" in body[-65557:] else TRUNCATED
    return WRONG_TYPE


class Observation(BaseModel):
    """The latest observed revision of an occurrence."""

    model_config = ConfigDict(frozen=True)
    id: int
    occurrence_key: str
    payload: dict[str, Any]
    payload_sha256: str
    observed_at: datetime


class DocumentIntake:
    """SQL for listing revisions, attempt histories and continuous coverage."""

    def __init__(self, conn: psycopg.Connection[Any]) -> None:
        self.conn = conn

    def record_listing(
        self, listing: Mapping[str, Any], observations: Sequence[tuple[str, dict[str, Any]]]
    ) -> int:
        """Record a fetch and only revisions different from the latest occurrence payload."""
        [(listing_id,)] = self.conn.execute(_INSERT_LISTING, listing).fetchall()
        latest = {
            o.occurrence_key: o.payload_sha256
            for o in self.latest(listing["entity_id"], listing["surface"])
        }
        inserted = 0
        for key, payload in observations:
            digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
            if latest.get(key) != digest:
                params = (listing_id, key, digest, Jsonb(payload), listing["retrieved_at"])
                self.conn.execute(_INSERT_OBSERVATION, params)
                latest[key] = digest
                inserted += 1
        return inserted

    def latest(self, entity_id: int, surface: str) -> list[Observation]:
        """Latest revision per occurrence on this issuer's listing surface."""
        with self.conn.cursor(row_factory=class_row(Observation)) as cur:
            return cur.execute(_LATEST, (entity_id, surface)).fetchall()

    def attempts(self, observation_id: int, url: str) -> list[str]:
        """Outcomes, oldest first, of every attempt of this exact revision and URL."""
        rows = self.conn.execute(_ATTEMPTS, (observation_id, url)).fetchall()
        return [outcome for (outcome,) in rows]

    def record_attempt(
        self,
        observation_id: int,
        url: str,
        attempted_at: datetime,
        outcome: str,
        body_sha256: str | None,
        capture_ref_id: int | None,
    ) -> None:
        """Append one fetch outcome in the caller's capture-registration transaction."""
        params = (observation_id, url, attempted_at, outcome, body_sha256, capture_ref_id)
        self.conn.execute(_INSERT_ATTEMPT, params)

    def first_span(self, entity_id: int, surface: str) -> date | None:
        """Earliest span ever requested, OK or failed, so a failed first span is not skipped."""
        first: date | None
        [(first,)] = self.conn.execute(_FIRST_SPAN, (entity_id, surface)).fetchall()
        return first

    def ok_attempt(self, observation_id: int, url: str) -> tuple[str, int, str] | None:
        """The registered successful attempt and its store capture identity."""
        return self.conn.execute(_OK_ATTEMPT, (observation_id, url)).fetchone()

    def ok_spans(self, entity_id: int, surface: str) -> list[tuple[date, date]]:
        """Successful listing intervals capped at their retrieval date."""
        return self.conn.execute(_OK_SPANS, (entity_id, surface)).fetchall()
