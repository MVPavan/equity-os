"""The two Upstox instrument files: bounded decode, equity filter, typed catalogs.

``complete.json.gz`` is ~3.2 MB on the wire and ~54.6 MB decoded, so the decode
is streamed under its own cap rather than handed to :func:`gzip.decompress`,
which would allocate the whole thing before anyone could refuse it.

Only company-equity rows are retained, and the filter runs **before**
validation. Routing every record shape through a discriminated union would type
thousands of derivative rows nobody reads.

**The filter reads the ISIN, not the trading series.** An earlier version
retained ``NSE_EQ``/``EQ`` and ``BSE_EQ``/``A`` only. That silently dropped two
of ten pinned watchlist stocks, which trade in NSE series ``BE`` and BSE group
``T`` — a company moved to trade-to-trade is still that company. It also
admitted 176 ETFs, because ``NSE_EQ``/``EQ`` mixes them in. The Indian numbering
agency states what a security *is* in the ISIN itself, and that is what is read.

Three findings from the full live census drive the models, and all three
contradict the vendor's own documentation:

* ``security_type`` does not exist on BSE equity records — not "usually absent",
  absent in all 699 of them;
* ``cas_eligible`` appears only when it is ``true``, never present-and-``false``;
* ``exchange_token`` is a string, not the number the docs claim.

A fourth landed on the first live run: ``qty_multiplier`` is on every retained
equity row, and the vendor's schema table lists it only for suspended records.
The unknown-key census is what surfaced it.

The omission rule follows from the second: ``None`` means the file did not carry
the field and must stay distinguishable from ``False``, which would be a claim
the vendor never made. A derived property offers absence-as-false to a consumer
that wants a boolean. ``mtf_bracket`` gets no such property — it is numeric, and
absence-as-false on a number is a category error.

An unknown key is recorded and counted, never fatal and never ignored:
``extra="forbid"`` would turn a harmless vendor addition into a total failure
across a 117,344-record file. A **retained row that fails validation** is fatal,
because that means a field the entity map depends on changed type or vanished.
"""

from __future__ import annotations

import gzip
import hashlib
import io
import json
import zlib
from collections.abc import Mapping, Sequence
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from fundamentals.ingest.upstox_source import (
    AcquisitionOutcome,
    UpstoxFetch,
    UpstoxSurface,
)

NSE_EQUITY_SEGMENT = "NSE_EQ"
BSE_EQUITY_SEGMENT = "BSE_EQ"

# The two cash segments. They are necessary but nowhere near sufficient: a full
# scan of the 2026-09-04 file found 22,458 rows in them, of which only 7,845 are
# company equity. The rest are government securities, treasury bills,
# debentures, ETFs and mutual-fund units, all trading in the same segment.
EQUITY_SEGMENTS: frozenset[str] = frozenset({NSE_EQUITY_SEGMENT, BSE_EQUITY_SEGMENT})

# An Indian ISIN is IN | issuer-type | 4-char issuer | 2-char issue-type |
# 2-char serial | check digit. ``E`` is a company and ``01`` is equity shares —
# the numbering agency's own statement of what the security is, which is why it
# is read here rather than inferred from a trading series.
EQUITY_ISIN_PREFIX = "INE"
EQUITY_ISIN_ISSUE_TYPE = "01"
_ISSUE_TYPE_SLICE = slice(7, 9)
_MIN_ISIN_LENGTH = 12

INSTRUMENT_KEY_SEPARATOR = "|"

_SEGMENT_FIELD = "segment"
_ISIN_FIELD = "isin"

_NOT_A_JSON_ARRAY = "instrument file is not a top-level JSON array"
_UNREADABLE_GZIP = "instrument file could not be decompressed: {reason}"
_UNREADABLE_JSON = "instrument file is not valid JSON: {reason}"
_ROW_REJECTED = "row {index} failed validation: {reason}"
_NO_EQUITY_ROWS = (
    "file carried {count} rows and no retained equity rows; the segment or "
    "instrument_type values have moved"
)


class DecompressedTooLargeError(ValueError):
    """Raised when a gzip member expands past its cap.

    Never a truncation: a truncated JSON array either fails to parse or, worse,
    parses as a shorter but complete-looking file.
    """


class UpstoxInstrumentError(ValueError):
    """Base for refusals raised while reading an instrument catalog."""


def decompress_bounded(payload: bytes, max_bytes: int) -> bytes:
    """Decompress one gzip member, refusing anything over ``max_bytes``.

    Reads one byte past the cap so an over-cap member is detected without
    materialising the whole expansion.
    """
    with gzip.GzipFile(fileobj=io.BytesIO(payload)) as member:
        decoded = member.read(max_bytes + 1)
    if len(decoded) > max_bytes:
        raise DecompressedTooLargeError(
            f"decompressed instrument file exceeded maximum {max_bytes} bytes"
        )
    return decoded


class UpstoxInstrument(BaseModel):
    """One retained equity row of ``complete.json.gz``, as the file states it.

    Every optional field below is optional because the live census found it
    missing on real rows, not because an example omitted it.
    """

    model_config = ConfigDict(frozen=True, extra="ignore")

    segment: str = Field(min_length=1)
    exchange: str = Field(min_length=1)
    name: str = Field(min_length=1)
    isin: str = Field(min_length=1)
    instrument_type: str = Field(min_length=1)
    instrument_key: str = Field(min_length=1)
    trading_symbol: str = Field(min_length=1)
    # A string on the wire, and an opaque handle by meaning: arithmetic on an
    # exchange token is always a mistake.
    exchange_token: str = Field(min_length=1)
    lot_size: int
    freeze_quantity: Decimal
    tick_size: Decimal
    # Undocumented on equity rows: the vendor's schema table lists it only for
    # suspended records. Present on 3,337/3,337 retained equity rows in the
    # 2026-09-04 full scan, so it is modelled required and its absence is drift.
    # Every observed value was 1.0; that is today's data, not a constant, and is
    # deliberately not baked into the type.
    qty_multiplier: Decimal

    # Missing on roughly a third of live equity rows.
    short_name: str | None = None
    # Absent on every BSE equity record in the file.
    security_type: str | None = None
    # Present only when true. ``None`` is "the file did not say", not "no".
    cas_eligible: bool | None = None
    mtf_enabled: bool | None = None
    mtf_bracket: Decimal | None = None

    @model_validator(mode="after")
    def _check_instrument_key_agrees_with_its_segment(self) -> UpstoxInstrument:
        """Equity keys are ``SEGMENT|ISIN``, and the segment must be the same one.

        The key is read from the file and never constructed, so this is the only
        place its shape is confirmed. A key naming a different segment than the
        row it sits on is two contradictory statements about one security.
        """
        parts = self.instrument_key.split(INSTRUMENT_KEY_SEPARATOR)
        if len(parts) != 2:
            raise ValueError(f"equity instrument_key {self.instrument_key!r} is not SEGMENT|ISIN")
        if parts[0] != self.segment:
            raise ValueError(
                f"instrument_key {self.instrument_key!r} contradicts segment {self.segment!r}"
            )
        return self

    @property
    def cas_eligible_or_false(self) -> bool:
        """Absence read as false, for a consumer that wants a plain boolean."""
        return self.cas_eligible is True

    @property
    def mtf_enabled_or_false(self) -> bool:
        """Absence read as false, for a consumer that wants a plain boolean."""
        return self.mtf_enabled is True


class UpstoxSuspendedInstrument(BaseModel):
    """One row of ``suspended-instrument.json.gz`` — twelve fields, all required.

    The cleanest schema in the whole verification pass: every field present in
    100% of 33,930 records, nothing optional, no type surprises. It is also our
    only delisting and suspension signal.
    """

    model_config = ConfigDict(frozen=True, extra="ignore")

    segment: str = Field(min_length=1)
    exchange: str = Field(min_length=1)
    name: str = Field(min_length=1)
    isin: str = Field(min_length=1)
    instrument_type: str = Field(min_length=1)
    instrument_key: str = Field(min_length=1)
    trading_symbol: str = Field(min_length=1)
    exchange_token: str = Field(min_length=1)
    # A handful of live rows carry a sentinel 999999999 here and in
    # ``freeze_quantity``. It is a data-quality curiosity, retained as stated.
    lot_size: int
    freeze_quantity: Decimal
    tick_size: Decimal
    qty_multiplier: Decimal


class _CatalogHeader(BaseModel):
    """What both catalogs record about the file they were read from."""

    model_config = ConfigDict(frozen=True)

    surface: UpstoxSurface
    route_key: str
    source_url: str
    content_sha256: str
    byte_count: int
    retrieved_at: datetime
    outcome: AcquisitionOutcome
    record_count: int
    retained_count: int
    # Wire keys present on retained rows that no model declares, with their
    # counts. Counts, never percentages: a percentage encodes today's file size.
    unknown_keys: tuple[tuple[str, int], ...] = ()
    anomalies: tuple[str, ...] = ()


class UpstoxInstrumentCatalog(_CatalogHeader):
    """The retained equity rows of one ``complete.json.gz`` capture."""

    instruments: tuple[UpstoxInstrument, ...] = ()

    def by_isin(self) -> Mapping[str, tuple[UpstoxInstrument, ...]]:
        """Group rows by ISIN without collapsing them.

        A dual-listed issuer yields one row per exchange, and de-duplicating
        would discard the exchange distinction that is the only thing telling
        those rows apart.
        """
        return _group_by_isin(self.instruments)


class UpstoxSuspendedCatalog(_CatalogHeader):
    """The rows of one ``suspended-instrument.json.gz`` capture.

    Emits no entity assertions and has no code consumer: it is retained
    evidence of suspension, and acting on it is a separate decision.
    """

    suspended: tuple[UpstoxSuspendedInstrument, ...] = ()

    def by_isin(self) -> Mapping[str, tuple[UpstoxSuspendedInstrument, ...]]:
        """Group rows by ISIN, one row per series, never de-duplicated."""
        return _group_by_isin(self.suspended)


def _group_by_isin[RowT: (UpstoxInstrument, UpstoxSuspendedInstrument)](
    rows: Sequence[RowT],
) -> Mapping[str, tuple[RowT, ...]]:
    """Collect rows under their stated ISIN, preserving the catalog's order."""
    grouped: dict[str, list[RowT]] = {}
    for row in rows:
        grouped.setdefault(row.isin, []).append(row)
    return {isin: tuple(members) for isin, members in grouped.items()}


def canonical_parsed_digest(catalog: _CatalogHeader) -> str:
    """Hash a catalog with its wall-clock stamp removed.

    ``retrieved_at`` is required wall-clock, so two runs over identical bytes
    cannot produce byte-identical files. The determinism guarantee this repo can
    actually make is narrower and checkable: identical bytes in, identical
    canonical digest out.
    """
    payload = catalog.model_dump_json(exclude={"retrieved_at"})
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def read_instrument_catalog(
    fetch: UpstoxFetch, *, max_decompressed_bytes: int
) -> UpstoxInstrumentCatalog:
    """Read one ``complete.json.gz`` capture into its retained equity rows.

    A capture that cannot be decoded still produces a catalog carrying the raw
    bytes' hash and a ``SCHEMA_DRIFT`` outcome, so a reviewed parser upgrade can
    re-read the same retained bytes later.
    """
    raw_rows, anomalies = _decode_rows(fetch, max_decompressed_bytes)
    if raw_rows is None:
        return UpstoxInstrumentCatalog(
            **_header(fetch, AcquisitionOutcome.SCHEMA_DRIFT, 0, 0, (), anomalies)
        )
    retained = [row for row in raw_rows if _is_retained_equity(row)]
    rows, row_anomalies = _validate_rows(retained, UpstoxInstrument)
    anomalies = anomalies + row_anomalies
    if rows is None:
        return UpstoxInstrumentCatalog(
            **_header(fetch, AcquisitionOutcome.SCHEMA_DRIFT, len(raw_rows), 0, (), anomalies)
        )
    if raw_rows and not retained:
        anomalies = anomalies + (_NO_EQUITY_ROWS.format(count=len(raw_rows)),)
        return UpstoxInstrumentCatalog(
            **_header(fetch, AcquisitionOutcome.SCHEMA_DRIFT, len(raw_rows), 0, (), anomalies)
        )
    ordered = tuple(sorted(rows, key=_instrument_sort_key))
    return UpstoxInstrumentCatalog(
        **_header(
            fetch,
            AcquisitionOutcome.OK if raw_rows else AcquisitionOutcome.OK_EMPTY,
            len(raw_rows),
            len(ordered),
            _census(retained, UpstoxInstrument),
            anomalies,
        ),
        instruments=ordered,
    )


def read_suspended_catalog(
    fetch: UpstoxFetch, *, max_decompressed_bytes: int
) -> UpstoxSuspendedCatalog:
    """Read one ``suspended-instrument.json.gz`` capture. Every row is retained."""
    raw_rows, anomalies = _decode_rows(fetch, max_decompressed_bytes)
    if raw_rows is None:
        return UpstoxSuspendedCatalog(
            **_header(fetch, AcquisitionOutcome.SCHEMA_DRIFT, 0, 0, (), anomalies)
        )
    rows, row_anomalies = _validate_rows(raw_rows, UpstoxSuspendedInstrument)
    anomalies = anomalies + row_anomalies
    if rows is None:
        return UpstoxSuspendedCatalog(
            **_header(fetch, AcquisitionOutcome.SCHEMA_DRIFT, len(raw_rows), 0, (), anomalies)
        )
    ordered = tuple(sorted(rows, key=_instrument_sort_key))
    return UpstoxSuspendedCatalog(
        **_header(
            fetch,
            AcquisitionOutcome.OK if raw_rows else AcquisitionOutcome.OK_EMPTY,
            len(raw_rows),
            len(ordered),
            _census(raw_rows, UpstoxSuspendedInstrument),
            anomalies,
        ),
        suspended=ordered,
    )


def _header(
    fetch: UpstoxFetch,
    outcome: AcquisitionOutcome,
    record_count: int,
    retained_count: int,
    unknown_keys: tuple[tuple[str, int], ...],
    anomalies: tuple[str, ...],
) -> dict[str, Any]:
    """The metadata every catalog carries, bound to the capture it was read from."""
    capture = fetch.capture
    return {
        "surface": capture.surface,
        "route_key": capture.route_key,
        "source_url": capture.request_url,
        "content_sha256": capture.content_sha256,
        "byte_count": capture.byte_count,
        "retrieved_at": capture.retrieved_at,
        "outcome": outcome,
        "record_count": record_count,
        "retained_count": retained_count,
        "unknown_keys": unknown_keys,
        "anomalies": anomalies,
    }


def _decode_rows(
    fetch: UpstoxFetch, max_decompressed_bytes: int
) -> tuple[list[dict[str, Any]] | None, tuple[str, ...]]:
    """Decompress and parse one capture into wire rows, or say why it could not be.

    Returns ``None`` rather than raising so the caller can still record a
    catalog carrying the raw bytes' hash. Every number is read with
    ``parse_float=Decimal``: a float round-trip anywhere in this path would
    break the byte-identity the restatement check depends on.
    """
    try:
        decoded = decompress_bounded(fetch.raw_body, max_decompressed_bytes)
    except DecompressedTooLargeError:
        raise
    except (OSError, EOFError, zlib.error) as error:
        return None, (_UNREADABLE_GZIP.format(reason=type(error).__name__),)
    try:
        payload = json.loads(decoded.decode("utf-8"), parse_float=Decimal)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        return None, (_UNREADABLE_JSON.format(reason=type(error).__name__),)
    if not isinstance(payload, list):
        return None, (_NOT_A_JSON_ARRAY,)
    return [row for row in payload if isinstance(row, dict)], ()


def _is_retained_equity(row: Mapping[str, Any]) -> bool:
    """Whether one wire row is company equity, read from the segment and the ISIN.

    ``instrument_type`` is deliberately **not** part of this test. It is a
    trading series — NSE ``EQ``/``BE``/``BZ``, BSE ``A``/``B``/``T``/``X`` — and
    a company moved to trade-to-trade is still that company. Filtering on it
    silently dropped two of ten pinned watchlist stocks, and it does not even
    separate equity from non-equity: ``NSE_EQ``/``EQ`` carries 176 ETFs.
    """
    if row.get(_SEGMENT_FIELD) not in EQUITY_SEGMENTS:
        return False
    isin = row.get(_ISIN_FIELD)
    if not isinstance(isin, str) or len(isin) < _MIN_ISIN_LENGTH:
        return False
    return isin.startswith(EQUITY_ISIN_PREFIX) and isin[_ISSUE_TYPE_SLICE] == EQUITY_ISIN_ISSUE_TYPE


def _validate_rows[RowT: (UpstoxInstrument, UpstoxSuspendedInstrument)](
    raw_rows: Sequence[Mapping[str, Any]], model: type[RowT]
) -> tuple[tuple[RowT, ...] | None, tuple[str, ...]]:
    """Type every retained row, refusing the whole file if any one of them fails.

    Fail-closed on purpose: a retained row that will not validate means a field
    the entity map joins on changed type or disappeared, and half a catalog
    would be read downstream as a complete one.
    """
    rows: list[RowT] = []
    for index, raw in enumerate(raw_rows):
        try:
            rows.append(model.model_validate(raw))
        except ValidationError as error:
            return None, (_ROW_REJECTED.format(index=index, reason=error.errors()[0]["msg"]),)
    return tuple(rows), ()


def _census(
    raw_rows: Sequence[Mapping[str, Any]], model: type[BaseModel]
) -> tuple[tuple[str, int], ...]:
    """Count wire keys on retained rows that no model declares.

    Recorded rather than ignored, and counted rather than refused: a vendor
    addition is drift worth seeing and never a reason to fail a whole file.
    """
    declared = set(model.model_fields)
    counts: dict[str, int] = {}
    for row in raw_rows:
        for key in row:
            if key not in declared:
                counts[key] = counts.get(key, 0) + 1
    return tuple(sorted(counts.items()))


def _instrument_sort_key(row: UpstoxInstrument | UpstoxSuspendedInstrument) -> tuple[str, ...]:
    """Order rows deterministically, so a vendor reordering is not read as drift."""
    return (row.isin, row.segment, row.instrument_type, row.exchange_token)
