"""Append-only document intake state; the caller owns each registration transaction."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from datetime import date, datetime, timedelta
from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from pydantic import BaseModel, ConfigDict

from fundamentals.contracts.source_catalog import DocumentKind
from fundamentals.entity.discovery import OK, TOO_LARGE

WRONG_TYPE = "WRONG_TYPE"
TERMINAL = frozenset({WRONG_TYPE, TOO_LARGE, "HTTP_404", "HTTP_410"})


def refusal(kind: DocumentKind, body: bytes) -> str:
    """Accept PDF bytes, or an annual-report ZIP, without interpreting either."""
    return (
        OK
        if body.startswith(b"%PDF-")
        or (kind is DocumentKind.ANNUAL_REPORT and body.startswith(b"PK\x03\x04"))
        else WRONG_TYPE
    )


class Observation(BaseModel):
    """The latest observed revision of an occurrence."""

    model_config = ConfigDict(frozen=True)
    id: int
    occurrence_key: str
    payload: dict[str, Any]
    observed_at: datetime


class Attempt(BaseModel):
    """One document outcome, scoped to its observation and URL."""

    model_config = ConfigDict(frozen=True)
    outcome: str
    attempted_at: datetime


class DocumentIntake:
    """SQL for listing revisions, attempt histories and continuous coverage."""

    def __init__(self, conn: psycopg.Connection[Any]) -> None:
        self.conn = conn

    def record_listing(
        self, listing: Mapping[str, Any], observations: Sequence[tuple[str, dict[str, Any]]]
    ) -> int:
        """Record a fetch and only revisions different from the latest occurrence payload."""
        row = self.conn.execute(
            "INSERT INTO eqos.document_listings (entity_id,symbol,surface,span_from,span_to,"
            "retrieved_at,outcome,capture_ref_id) VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
            tuple(
                listing[k]
                for k in (
                    "entity_id",
                    "symbol",
                    "surface",
                    "span_from",
                    "span_to",
                    "retrieved_at",
                    "outcome",
                    "capture_ref_id",
                )
            ),
        ).fetchone()
        assert row is not None
        latest = {
            o.occurrence_key: o.payload
            for o in self.latest(listing["entity_id"], listing["surface"])
        }
        inserted = 0
        for key, payload in observations:
            digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
            if (
                key in latest
                and hashlib.sha256(json.dumps(latest[key], sort_keys=True).encode()).hexdigest()
                == digest
            ):
                continue
            self.conn.execute(
                "INSERT INTO eqos.document_observations (listing_id,occurrence_key,payload_sha256,"
                "payload,observed_at) VALUES (%s,%s,%s,%s,%s)",
                (row[0], key, digest, Jsonb(payload), listing["retrieved_at"]),
            )
            latest[key] = payload
            inserted += 1
        return inserted

    def latest(self, entity_id: int, surface: str) -> list[Observation]:
        """Latest revision per occurrence on this issuer's listing surface."""
        with self.conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                "SELECT DISTINCT ON (o.occurrence_key) o.id,o.occurrence_key,o.payload,"
                "o.observed_at "
                "FROM eqos.document_observations o JOIN eqos.document_listings l "
                "ON l.id=o.listing_id "
                "WHERE l.entity_id=%s AND l.surface=%s "
                "ORDER BY o.occurrence_key,o.observed_at DESC,o.id DESC",
                (entity_id, surface),
            )
            return [Observation(**row) for row in cur.fetchall()]

    def attempts(self, observation_id: int, url: str) -> list[Attempt]:
        """Every attempt of this exact revision and URL."""
        with self.conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                "SELECT outcome,attempted_at FROM eqos.document_attempts "
                "WHERE observation_id=%s AND url=%s ORDER BY id",
                (observation_id, url),
            )
            return [Attempt(**row) for row in cur.fetchall()]

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
        self.conn.execute(
            "INSERT INTO eqos.document_attempts (observation_id,url,attempted_at,"
            "outcome,body_sha256,capture_ref_id) VALUES (%s,%s,%s,%s,%s,%s)",
            (observation_id, url, attempted_at, outcome, body_sha256, capture_ref_id),
        )

    def coverage(self, entity_id: int, surface: str) -> date | None:
        """End of the unbroken successful span union, capped at each fetch's IST date."""
        spans = self.conn.execute(
            "SELECT span_from, LEAST(span_to,(retrieved_at AT TIME ZONE 'Asia/Kolkata')::date) "
            "FROM eqos.document_listings WHERE entity_id=%s AND surface=%s AND outcome='OK' "
            "AND span_from IS NOT NULL ORDER BY span_from",
            (entity_id, surface),
        ).fetchall()
        end = None
        for start, stop in spans:
            if start > stop:
                continue
            if end is not None and start > end + timedelta(days=1):
                break
            end = max(end or stop, stop)
        return end


RETENTION_SHARED = "SELECT eqos.retention_shared()"

# Read statements shared with the composition root; SQL stays in this module.
COVERED = (
    "SELECT DISTINCT subject_id FROM eqos.decisions "
    "WHERE subject_kind='WATCHLIST' AND eqos.watchlisted(subject_id) ORDER BY subject_id"
)
INTAKE_ISSUERS = (
    "SELECT DISTINCT entity_id,symbol FROM eqos.document_listings ORDER BY entity_id,symbol"
)
REGISTERED = (
    "SELECT 1 FROM eqos.capture_refs WHERE source_id=%s AND surface=%s "
    "AND request_key=%s AND capture_id=%s"
)
FAILED_START = (
    "WITH spans AS (SELECT span_from,span_to,outcome,"
    "LEAST(span_to,(retrieved_at AT TIME ZONE 'Asia/Kolkata')::date) AS stop "
    "FROM eqos.document_listings WHERE entity_id=%s AND surface=%s AND span_from IS NOT NULL) "
    "SELECT min(f.span_from) FROM spans f WHERE f.outcome<>'OK' AND NOT coalesce("
    "(SELECT range_agg(daterange(s.span_from,s.stop+1,'[)')) "
    "@> daterange(f.span_from,GREATEST(f.span_from,f.stop)+1,'[)') "
    "FROM spans s WHERE s.outcome='OK' AND s.stop>=s.span_from),false)"
)
