"""Upstox bindings for the shared capture store, without a second ledger."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from urllib.parse import parse_qsl, unquote, urlsplit

from fundamentals.contracts.acquisition_outcome import OutcomeRecord
from fundamentals.contracts.snapshot import (
    CAPTURE_SCHEMA_VERSION,
    BlobRef,
    BodyCompleteness,
    BodyReadIssue,
    CaptureRecord,
    RequestIdentity,
    RequestParameter,
    SnapshotRights,
    canonical_sha256,
)

SOURCE_ID = "upstox"
CANDLES = "candles"
INSTRUMENTS = "instruments"
UPSTOX_RIGHTS = SnapshotRights(authority_refs=("owner-decision-2026-09-04",))
SNAPSHOTS_DIRECTORY = "snapshots"
PATH_PARAMETER = "path"
ORIGIN_PARAMETER = "origin"
ROUTE_PARAMETER = "route_key"


def candle_request_key(instrument_key: str, unit: str, interval: str) -> str:
    """Group captures of one series across requested windows."""
    return "series-" + canonical_sha256([instrument_key, unit, interval])[:24]


def request_identity(surface: str, route_key: str, url: str) -> RequestIdentity:
    """Bind the complete URL path and query without storing auth headers."""
    parsed = urlsplit(url)
    parameters = (
        RequestParameter(name=ORIGIN_PARAMETER, value=f"{parsed.scheme}://{parsed.netloc}"),
        RequestParameter(name=ROUTE_PARAMETER, value=route_key),
        RequestParameter(name=PATH_PARAMETER, value=parsed.path),
    ) + tuple(
        RequestParameter(name=name, value=value)
        for name, value in sorted(parse_qsl(parsed.query, keep_blank_values=True))
    )
    key = route_key
    if surface == CANDLES:
        parts = tuple(unquote(part) for part in parsed.path.split("/"))
        key = candle_request_key(parts[-5], parts[-4], parts[-3])
    elif surface != INSTRUMENTS:
        key += "-" + canonical_sha256([parsed.path, parsed.query])[:24]
    return RequestIdentity(
        source_id=SOURCE_ID, surface=surface, request_key=key, parameters=parameters
    )


def seal_capture(
    *,
    surface: str,
    route_key: str,
    url: str,
    retrieved_at: datetime,
    http_status: int | None,
    media_type: str | None,
    content_encoding: str | None,
    raw_body: bytes | None,
    outcome: OutcomeRecord,
    body_completeness: BodyCompleteness | None = None,
    body_read_issue: BodyReadIssue | None = None,
) -> CaptureRecord:
    """Seal exact response bytes and metadata under the existing owner decision."""
    if retrieved_at.utcoffset() is None:
        raise ValueError("retrieved_at must be timezone-aware")
    body = (
        None
        if raw_body is None
        else BlobRef(
            source_id=SOURCE_ID,
            content_sha256=hashlib.sha256(raw_body).hexdigest(),
            byte_count=len(raw_body),
        )
    )
    return CaptureRecord.make(
        request_identity(surface, route_key, url),
        retrieved_at.astimezone(UTC),
        http_status,
        media_type,
        content_encoding,
        body,
        outcome,
        UPSTOX_RIGHTS,
        schema_version=CAPTURE_SCHEMA_VERSION,
        body_completeness=(
            body_completeness
            if body_completeness is not None
            else BodyCompleteness.ABSENT
            if raw_body is None
            else BodyCompleteness.COMPLETE
        ),
        body_read_issue=body_read_issue,
    )
