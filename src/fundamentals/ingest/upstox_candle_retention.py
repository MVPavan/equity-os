"""Read-time candle versions derived exclusively from shared retained captures."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from decimal import Decimal
from urllib.parse import unquote

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from fundamentals.contracts.acquisition_outcome import OutcomeCode
from fundamentals.contracts.snapshot import BodyCompleteness, CaptureRecord, canonical_sha256
from fundamentals.ingest.upstox_retention import (
    CANDLES,
    PATH_PARAMETER,
    SOURCE_ID,
    candle_request_key,
)
from fundamentals.store.snapshot_store import SnapshotStore

INDIA_OFFSET = timedelta(hours=5, minutes=30)
DAILY_UNIT = "days"
DAILY_INTERVAL = "1"
SCHEMA_VERSION = 1


class CandleReplayError(ValueError):
    """A retained capture cannot support a candle version; its bytes remain retained."""


class RetainedDailyCandle(BaseModel):
    """One vendor observation, with decimal prices and an explicit timestamp."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    timestamp: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int = Field(ge=0, strict=True)
    open_interest: int = Field(ge=0, strict=True)

    @field_validator("timestamp")
    @classmethod
    def _india_timestamp(cls, value: datetime) -> datetime:
        """Refuse timestamps with an unknown daily-candle timezone."""
        if value.utcoffset() != INDIA_OFFSET:
            raise ValueError("daily candle timestamp must carry +05:30")
        return value

    @field_validator("open", "high", "low", "close")
    @classmethod
    def _finite_price(cls, value: Decimal) -> Decimal:
        """Refuse invalid numeric observations rather than composing them."""
        if not value.is_finite() or value < 0:
            raise ValueError("daily candle prices must be finite and non-negative")
        return value


class ObservedCandleCoverage(BaseModel):
    """Exact returned dates, bound to the capture hash, without inferred gaps."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    observed_dates: tuple[date, ...]
    capture_sha256: str


class CandleSeriesVersion(BaseModel):
    """A version of observed bytes; capture time is excluded from its content identity."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: int = SCHEMA_VERSION
    instrument_key: str
    capture: CaptureRecord
    coverage: ObservedCandleCoverage
    candles: tuple[RetainedDailyCandle, ...]
    version_sha256: str


class CandleReplayFailure(BaseModel):
    """A rejected replay with its complete, unchanged acquisition provenance."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    capture: CaptureRecord
    error: str


class CandleReplayResult(BaseModel):
    """Usable versions and explicit failures from retained successful acquisitions."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    versions: tuple[CandleSeriesVersion, ...]
    failures: tuple[CandleReplayFailure, ...]


def candle_version(store: SnapshotStore, capture: CaptureRecord) -> CandleSeriesVersion:
    """Validate and replay one successful daily capture without writing another ledger."""
    try:
        if capture.effective_body_completeness is not BodyCompleteness.COMPLETE:
            raise ValueError("incomplete capture cannot support a candle version")
        if capture.request.source_id != SOURCE_ID or capture.request.surface != CANDLES:
            raise ValueError("capture is not an Upstox candle response")
        if capture.outcome.code not in (OutcomeCode.OK, OutcomeCode.OK_EMPTY):
            raise ValueError("failed capture cannot support a candle version")
        path = next(p.value for p in capture.request.parameters if p.name == PATH_PARAMETER)
        parts = tuple(unquote(part) for part in path.split("/"))
        instrument_key, unit, interval, end, start = parts[-5:]
        if unit != DAILY_UNIT or interval != DAILY_INTERVAL:
            raise ValueError("only daily candle versions are implemented")
        first, last = date.fromisoformat(start), date.fromisoformat(end)
        if first > last:
            raise ValueError("candle window is reversed")
        payload = json.loads(store.read_body(capture), parse_float=Decimal)
        if not isinstance(payload, dict) or payload.get("status") != "success":
            raise ValueError("candle response has no success envelope")
        data = payload.get("data")
        if not isinstance(data, dict) or not isinstance(data.get("candles"), list):
            raise ValueError("candle response has no candle array")
        candles = []
        for row in data["candles"]:
            if not isinstance(row, list) or len(row) != 7:
                raise ValueError("candle row must contain exactly seven fields")
            candle = RetainedDailyCandle(
                timestamp=row[0],
                open=row[1],
                high=row[2],
                low=row[3],
                close=row[4],
                volume=row[5],
                open_interest=row[6],
            )
            if not first <= candle.timestamp.date() <= last:
                raise ValueError("returned candle is outside the requested window")
            candles.append(candle)
        ordered = tuple(sorted(candles, key=lambda candle: candle.timestamp))
        dates = tuple(candle.timestamp.date() for candle in ordered)
        if len(set(dates)) != len(dates):
            raise ValueError("daily candle dates must be unique")
        if capture.body is None:
            raise ValueError("candle capture has no retained body")
        coverage = ObservedCandleCoverage(
            observed_dates=dates, capture_sha256=capture.body.content_sha256
        )
        version_hash = canonical_sha256(
            {
                "schema_version": SCHEMA_VERSION,
                "instrument_key": instrument_key,
                "coverage": coverage.model_dump(mode="json"),
                "candles": [candle.model_dump(mode="json") for candle in ordered],
            }
        )
        return CandleSeriesVersion(
            instrument_key=instrument_key,
            capture=capture,
            coverage=coverage,
            candles=ordered,
            version_sha256=version_hash,
        )
    except (ValueError, TypeError, KeyError, StopIteration, ValidationError) as error:
        raise CandleReplayError(f"capture {capture.capture_id}: {error}") from error


def candle_versions(store: SnapshotStore, instrument_key: str) -> tuple[CandleSeriesVersion, ...]:
    """Strict compatibility API; use replay_candle_versions for partial replay with failures."""
    key = candle_request_key(instrument_key, DAILY_UNIT, DAILY_INTERVAL)
    return tuple(
        candle_version(store, capture)
        for capture in store.list_captures(SOURCE_ID, CANDLES, key)
        if capture.outcome.code in (OutcomeCode.OK, OutcomeCode.OK_EMPTY)
    )


def replay_candle_versions(store: SnapshotStore, instrument_key: str) -> CandleReplayResult:
    """Replay every successful acquisition, rejecting bad captures without hiding later ones.

    Failures remain explicit alongside versions; callers can pass result.versions to
    compose_series. Acquisition outcomes and stored capture records remain unchanged.
    """
    key = candle_request_key(instrument_key, DAILY_UNIT, DAILY_INTERVAL)
    versions: list[CandleSeriesVersion] = []
    failures: list[CandleReplayFailure] = []
    for capture in store.list_captures(SOURCE_ID, CANDLES, key):
        if capture.outcome.code not in (OutcomeCode.OK, OutcomeCode.OK_EMPTY):
            continue
        try:
            versions.append(candle_version(store, capture))
        except CandleReplayError as error:
            failures.append(CandleReplayFailure(capture=capture, error=str(error)))
    return CandleReplayResult(versions=tuple(versions), failures=tuple(failures))


def compose_series(versions: tuple[CandleSeriesVersion, ...]) -> tuple[RetainedDailyCandle, ...]:
    """Compose observations at read time; latest retrieval wins per observed date."""
    if len({version.instrument_key for version in versions}) > 1:
        raise ValueError("cannot compose candle series for different instruments")
    by_date: dict[date, RetainedDailyCandle] = {}
    for version in sorted(versions, key=lambda version: version.capture.retrieved_at):
        by_date.update((candle.timestamp.date(), candle) for candle in version.candles)
    return tuple(by_date[day] for day in sorted(by_date))
