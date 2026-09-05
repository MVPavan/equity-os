"""Retaining every Tijori financials attempt, then parsing what was retained.

Order is the whole point. The page (or the failure) is committed to the snapshot
store first, with its outcome already sealed, and only an ``OK`` capture is then
parsed — from the bytes the store hands back, not from the bytes in memory, so a
retained body that cannot be re-read is a loud failure rather than a silent
divergence between the tables and the evidence behind them.

Retries are bounded and honest: only ``TRANSPORT_ERROR`` is retried, every
attempt is committed as its own record, and a rate limit or a block is terminal
the first time it is seen. Replay never takes a source at all, so re-deriving
tables from a retained capture cannot reach the vendor.
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import Final, Self

import structlog
from pydantic import BaseModel, ConfigDict, model_validator

from fundamentals.contracts.acquisition_outcome import OutcomeCode
from fundamentals.contracts.snapshot import CaptureRecord
from fundamentals.ingest.tijori_capture import capture_record_for
from fundamentals.ingest.tijori_source import TijoriSource
from fundamentals.ingest.tijori_tables import (
    TijoriParseError,
    TijoriTable,
    TijoriTableAbsentError,
    TijoriTableKey,
    TijoriTablesAbsentError,
)
from fundamentals.store.snapshot_store import SnapshotStore

_LOGGER = structlog.get_logger(__name__)

TRANSPORT_ATTEMPT_RETAINED: Final = "tijori_transport_attempt_retained"
PARSE_FAILED_ON_RETAINED_BODY: Final = "tijori_retained_body_parse_failed"
TABLES_WITHOUT_OK_CAPTURE: Final = "tables may only come from an OK capture that parsed cleanly"
REPLAY_REFUSED: Final = "capture {capture_id} is {code}, not OK; it holds no tables to replay"


class TijoriRetention(BaseModel):
    """The committed capture of one acquisition, and whatever it yielded."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    record: CaptureRecord
    tables: tuple[TijoriTable, ...]
    parse_error: str | None

    @model_validator(mode="after")
    def _demand_tables_are_earned(self) -> Self:
        """Refuse tables that did not come from a clean parse of an OK capture."""
        if self.tables and (
            self.record.outcome.code is not OutcomeCode.OK or self.parse_error is not None
        ):
            raise ValueError(TABLES_WITHOUT_OK_CAPTURE)
        return self


def _parse_retained(
    body: bytes,
    *,
    slug: str,
    expected_symbol: str,
    expected_company_id: int | None,
    table_key: TijoriTableKey | None,
    retrieved_at: datetime,
) -> tuple[TijoriTable, ...]:
    """Parse the retained body, stamping the tables with the capture's own instant."""
    if table_key is None:
        return TijoriSource.parse_all_tables_bytes(
            body,
            slug=slug,
            expected_symbol=expected_symbol,
            expected_company_id=expected_company_id,
            retrieved_at=retrieved_at,
        )
    return (
        TijoriSource.parse_table_bytes(
            body,
            key=table_key.value,
            slug=slug,
            expected_symbol=expected_symbol,
            expected_company_id=expected_company_id,
            retrieved_at=retrieved_at,
        ),
    )


def retain_tijori_tables(
    source: TijoriSource,
    store: SnapshotStore,
    *,
    slug: str,
    expected_symbol: str,
    table_key: TijoriTableKey | None = None,
) -> TijoriRetention:
    """Commit every attempt for one financials page, then parse the retained body.

    Only ``TRANSPORT_ERROR`` is retried; a rate limit, a block, an expired
    session and an identity mismatch are all sealed on their first answer.
    """
    config = source.config
    attempts = max(1, config.max_retries)
    attempt = 1
    page = source.fetch_financials_page(slug, expected_symbol=expected_symbol)
    record = store.put_capture(capture_record_for(page), page.raw)
    while page.outcome.code is OutcomeCode.TRANSPORT_ERROR and attempt < attempts:
        _LOGGER.warning(
            TRANSPORT_ATTEMPT_RETAINED,
            slug=slug,
            attempt=attempt,
            capture_id=record.capture_id,
            native_value=page.outcome.native_value,
        )
        time.sleep(config.retry_backoff_seconds * attempt)
        attempt += 1
        page = source.fetch_financials_page(slug, expected_symbol=expected_symbol)
        record = store.put_capture(capture_record_for(page), page.raw)

    if page.outcome.code is not OutcomeCode.OK:
        return TijoriRetention(record=record, tables=(), parse_error=None)
    try:
        tables = _parse_retained(
            store.read_body(record),
            slug=slug,
            expected_symbol=expected_symbol,
            expected_company_id=config.expected_company_id,
            table_key=table_key,
            retrieved_at=record.retrieved_at,
        )
    except (TijoriTablesAbsentError, TijoriTableAbsentError):
        # An acquisition that found no table to write stays a loud failure: the
        # capture is already committed, so the evidence is kept either way, and
        # the pre-S3 contract of this command is that "nothing was published for
        # this company" is not an ordinary empty result.
        raise
    except TijoriParseError as error:
        _LOGGER.warning(
            PARSE_FAILED_ON_RETAINED_BODY,
            slug=slug,
            capture_id=record.capture_id,
            error_type=type(error).__name__,
        )
        return TijoriRetention(record=record, tables=(), parse_error=str(error))
    return TijoriRetention(record=record, tables=tables, parse_error=None)


def replay_tijori_tables(
    store: SnapshotStore,
    record: CaptureRecord,
    *,
    expected_symbol: str,
    expected_company_id: int | None,
    table_key: TijoriTableKey | None = None,
) -> tuple[TijoriTable, ...]:
    """Re-derive the tables of one retained capture without touching the vendor."""
    if record.outcome.code is not OutcomeCode.OK:
        raise ValueError(
            REPLAY_REFUSED.format(capture_id=record.capture_id, code=record.outcome.code.value)
        )
    return _parse_retained(
        store.read_body(record),
        slug=record.request.request_key,
        expected_symbol=expected_symbol,
        expected_company_id=expected_company_id,
        table_key=table_key,
        retrieved_at=record.retrieved_at,
    )
