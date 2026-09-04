"""Coverage for the bounded gzip decode, the equity filter, and the catalogs.

The traps pinned here are all ones the live-file census found and the vendor's
own documentation gets wrong: ``security_type`` does not exist on BSE equity
records, ``cas_eligible`` appears only when it is ``true``, and ``exchange_token``
is a string rather than the number the docs claim.

The hardest rule is the omission rule. A field the file did not carry must stay
distinguishable from a field the file carried as ``false`` — defaulting the two
together would let "the vendor never said" masquerade as "the vendor said no".
"""

from __future__ import annotations

import gzip
import hashlib
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from upstox_fixtures import (
    BSE_ISIN,
    NSE_ISIN,
    NSE_SYMBOL,
    bse_equity_row,
    debenture_row,
    derivative_row,
    etf_row,
    fetch_of,
    gzip_body,
    instruments_fetch,
    nse_equity_row,
    suspended_fetch,
    suspended_row,
    trade_to_trade_row,
)

from fundamentals.ingest.upstox_instruments import (
    DecompressedTooLargeError,
    UpstoxInstrumentCatalog,
    canonical_parsed_digest,
    decompress_bounded,
    read_instrument_catalog,
    read_suspended_catalog,
)
from fundamentals.ingest.upstox_source import AcquisitionOutcome

_CAP = 4 * 1024 * 1024


def _catalog(*rows: dict[str, object]) -> UpstoxInstrumentCatalog:
    """Read a catalog over the given synthetic rows."""
    return read_instrument_catalog(instruments_fetch(list(rows)), max_decompressed_bytes=_CAP)


# --- bounded decode ---------------------------------------------------------


def test_the_decompressed_cap_is_enforced_independently_of_the_compressed_one() -> None:
    """A gzip bomb is small on the wire and enormous in memory; both sides need a cap."""
    payload = gzip.compress(b"a" * 8192, mtime=0)
    assert len(payload) < 256
    with pytest.raises(DecompressedTooLargeError):
        decompress_bounded(payload, 1024)


def test_a_body_inside_the_decompressed_cap_round_trips() -> None:
    """The cap refuses, it never truncates: a truncated JSON document parses wrong."""
    assert decompress_bounded(gzip.compress(b"[]", mtime=0), 1024) == b"[]"


def test_corrupt_gzip_is_captured_with_a_hash_and_marked_schema_drift() -> None:
    """Unreadable bytes still produce a record, because the bytes are retained.

    The parse can be upgraded later and re-run over the same bytes; that is only
    possible if the failed attempt kept the hash instead of discarding the file.
    """
    payload = b"\x1f\x8b\x08\x00 definitely not a gzip member"
    catalog = read_instrument_catalog(fetch_of(payload), max_decompressed_bytes=_CAP)
    assert catalog.outcome is AcquisitionOutcome.SCHEMA_DRIFT
    assert catalog.content_sha256 == hashlib.sha256(payload).hexdigest()
    assert catalog.instruments == ()
    assert catalog.anomalies


def test_the_catalog_hash_covers_the_compressed_bytes_not_the_decoded_json() -> None:
    """The raw-body hash is the only restatement detector this vendor allows."""
    fetch = instruments_fetch([nse_equity_row()])
    catalog = read_instrument_catalog(fetch, max_decompressed_bytes=_CAP)
    assert catalog.content_sha256 == hashlib.sha256(fetch.raw_body).hexdigest()


def test_a_top_level_object_instead_of_an_array_is_schema_drift() -> None:
    """The files are bare JSON arrays; an envelope would mean the shape changed."""
    catalog = read_instrument_catalog(
        fetch_of(gzip.compress(b'{"data": []}', mtime=0)), max_decompressed_bytes=_CAP
    )
    assert catalog.outcome is AcquisitionOutcome.SCHEMA_DRIFT


def test_an_empty_file_is_ok_empty_rather_than_a_failure() -> None:
    """An empty array is a successful answer, and never the same as a broken one."""
    catalog = read_instrument_catalog(fetch_of(gzip_body([])), max_decompressed_bytes=_CAP)
    assert catalog.outcome is AcquisitionOutcome.OK_EMPTY


# --- the equity filter ------------------------------------------------------


def test_only_company_equity_rows_are_retained() -> None:
    """Non-equity rows are filtered BEFORE validation.

    They are dropped, not modelled: a discriminated union over record shapes we
    throw away is routing nobody consumes.
    """
    catalog = _catalog(nse_equity_row(), bse_equity_row(), derivative_row())
    assert catalog.record_count == 3
    assert catalog.retained_count == 2
    assert {row.isin for row in catalog.instruments} == {NSE_ISIN, BSE_ISIN}


def test_a_trade_to_trade_company_is_retained() -> None:
    """The regression. A company in NSE series ``BE`` is still that company.

    Two of ten pinned watchlist stocks — HFCL and MTARTECH — trade in ``BE`` and
    BSE group ``T``. The original ``instrument_type``-based filter dropped both
    of them silently: no anomaly, no drift, just absence from the entity map.
    """
    catalog = _catalog(trade_to_trade_row())
    assert catalog.retained_count == 1
    assert catalog.instruments[0].instrument_type == "BE"


def test_an_etf_in_the_equity_segment_is_not_retained() -> None:
    """176 ETFs share ``NSE_EQ``/``EQ`` with real equities and are not companies.

    Their ISIN says so: ``INF`` is a mutual-fund issuer. Under the old filter
    every one of them entered the entity map as though it were a listed company.
    """
    catalog = _catalog(nse_equity_row(), etf_row())
    assert catalog.retained_count == 1
    assert catalog.instruments[0].isin == NSE_ISIN


def test_a_company_debenture_is_not_retained() -> None:
    """An ``INE`` issuer is necessary and not sufficient: issue-type ``07`` is debt."""
    assert _catalog(nse_equity_row(), debenture_row()).retained_count == 1


def test_the_trading_series_is_retained_as_data_rather_than_used_as_a_filter() -> None:
    """It still matters — it just does not decide what a security is."""
    catalog = _catalog(nse_equity_row(), trade_to_trade_row(exchange_token="10002"))
    assert {row.instrument_type for row in catalog.instruments} == {"EQ", "BE"}


def test_a_file_with_rows_but_no_equity_rows_is_schema_drift() -> None:
    """A census that suddenly matches nothing means the segment values moved."""
    catalog = _catalog(derivative_row())
    assert catalog.outcome is AcquisitionOutcome.SCHEMA_DRIFT


def test_bse_equity_row_without_security_type_is_accepted() -> None:
    """``security_type`` is absent on every live BSE equity record, all 699 of them.

    A schema marking it required would reject an entire exchange.
    """
    catalog = _catalog(bse_equity_row())
    assert catalog.outcome is AcquisitionOutcome.OK
    assert catalog.instruments[0].security_type is None


def test_a_row_missing_an_always_present_field_is_schema_drift() -> None:
    """An unknown key is harmless drift; a vanished required field is not."""
    broken = nse_equity_row()
    del broken["exchange_token"]
    catalog = _catalog(broken)
    assert catalog.outcome is AcquisitionOutcome.SCHEMA_DRIFT
    assert catalog.instruments == ()


# --- the omission rule ------------------------------------------------------


def test_instrument_omissions_stay_none_and_are_not_defaulted_to_false() -> None:
    """``None`` means the file did not carry the field. ``False`` means it said no.

    ``cas_eligible`` is present only when true — never present-and-false — so
    collapsing absence into ``False`` would turn "unstated" into a vendor claim.
    """
    catalog = _catalog(nse_equity_row())
    row = catalog.instruments[0]
    assert row.cas_eligible is None
    assert row.mtf_enabled is None
    assert row.mtf_bracket is None


def test_a_present_flag_is_read_as_stated() -> None:
    """The flags this vendor does publish are read, not inferred."""
    catalog = _catalog(nse_equity_row(cas_eligible=True, mtf_enabled=True, mtf_bracket=23.37))
    row = catalog.instruments[0]
    assert row.cas_eligible is True
    assert row.mtf_bracket == Decimal("23.37")


def test_absence_as_false_is_offered_for_flags_and_withheld_from_the_number() -> None:
    """A consumer may read an absent flag as false; an absent number has no false."""
    row = _catalog(nse_equity_row()).instruments[0]
    assert row.cas_eligible_or_false is False
    assert row.mtf_enabled_or_false is False
    assert not hasattr(row, "mtf_bracket_or_false")


def test_numeric_wire_fields_are_decimal_and_never_float() -> None:
    """A float round-trip anywhere in this path would break the byte-identity check."""
    row = _catalog(nse_equity_row()).instruments[0]
    assert isinstance(row.tick_size, Decimal)
    assert isinstance(row.freeze_quantity, Decimal)
    assert row.tick_size == Decimal("5.0")


def test_qty_multiplier_is_required_on_equity_rows_though_the_docs_omit_it() -> None:
    """Found by the unknown-key census on the first live run, then confirmed.

    The vendor's schema table lists ``qty_multiplier`` only for suspended
    records. A full scan of the 2026-09-04 complete file found it on 3,337 of
    3,337 retained equity rows. Modelled required, so its disappearance is
    drift rather than a silent ``None``.
    """
    catalog = _catalog(nse_equity_row())
    assert catalog.unknown_keys == ()
    assert catalog.instruments[0].qty_multiplier == Decimal("1.0")


def test_an_equity_row_without_qty_multiplier_is_schema_drift() -> None:
    """Required means required: 100% presence twice over, so absence is a change."""
    broken = nse_equity_row()
    del broken["qty_multiplier"]
    assert _catalog(broken).outcome is AcquisitionOutcome.SCHEMA_DRIFT


def test_exchange_token_is_a_string_not_the_number_the_docs_claim() -> None:
    """It is an opaque handle. Arithmetic on it is always a mistake."""
    assert _catalog(bse_equity_row()).instruments[0].exchange_token == "590999"


# --- the instrument key -----------------------------------------------------


def test_instrument_key_shape_is_segment_pipe_isin() -> None:
    """The key is read from the file and never constructed, so its shape is checked."""
    row = _catalog(nse_equity_row()).instruments[0]
    assert row.instrument_key == f"NSE_EQ|{NSE_ISIN}"


def test_an_instrument_key_disagreeing_with_its_own_segment_is_schema_drift() -> None:
    """The segment prefix and the ``segment`` field must be the same statement."""
    catalog = _catalog(nse_equity_row(instrument_key=f"BSE_EQ|{NSE_ISIN}"))
    assert catalog.outcome is AcquisitionOutcome.SCHEMA_DRIFT


def test_an_instrument_key_without_exactly_one_pipe_is_schema_drift() -> None:
    """Equity keys are ``SEGMENT|ISIN``; other shapes belong to rows we do not retain."""
    catalog = _catalog(nse_equity_row(instrument_key="NSE_EQ"))
    assert catalog.outcome is AcquisitionOutcome.SCHEMA_DRIFT


# --- the unknown-key census -------------------------------------------------


def test_unknown_wire_key_is_recorded_in_the_review_section_and_is_not_fatal() -> None:
    """A vendor addition must neither fail the run nor pass unnoticed.

    ``extra="forbid"`` would turn a harmless new field into a total failure over
    a 117,344-record file; ignoring it silently would hide real drift. A census
    does neither.
    """
    catalog = _catalog(nse_equity_row(new_vendor_field="x"), nse_equity_row(new_vendor_field="y"))
    assert catalog.outcome is AcquisitionOutcome.OK
    assert catalog.unknown_keys == (("new_vendor_field", 2),)


def test_the_census_counts_only_retained_rows() -> None:
    """Keys on rows we filtered out say nothing about the schema we depend on."""
    catalog = _catalog(nse_equity_row(), derivative_row())
    assert dict(catalog.unknown_keys).keys() == set()


def test_no_prevalence_percentage_is_asserted_anywhere_in_the_census() -> None:
    """The census reports counts. A percentage would encode today's file size."""
    catalog = _catalog(nse_equity_row(new_vendor_field="x"))
    assert catalog.unknown_keys[0][1] == 1


# --- determinism ------------------------------------------------------------


def test_identical_bytes_produce_an_identical_canonical_parsed_digest() -> None:
    """Determinism is stated honestly: identical bytes in, identical digest out.

    ``retrieved_at`` is required wall-clock, so the artifact file itself cannot
    be byte-identical across runs. The digest excludes it, which is what makes
    the guarantee checkable at all.
    """
    rows = [nse_equity_row(), bse_equity_row()]
    first = read_instrument_catalog(instruments_fetch(rows), max_decompressed_bytes=_CAP)
    later = read_instrument_catalog(
        fetch_of(gzip_body(rows), retrieved_at=datetime(2027, 1, 1, tzinfo=UTC)),
        max_decompressed_bytes=_CAP,
    )
    assert first.retrieved_at != later.retrieved_at
    assert canonical_parsed_digest(first) == canonical_parsed_digest(later)


def test_row_order_in_the_file_does_not_change_the_parsed_rows() -> None:
    """Rows are sorted, so a vendor reordering yields the same parsed catalog.

    Deliberately asserted on the rows and not on the canonical digest. The
    digest covers ``content_sha256``, and reordered rows are genuinely different
    bytes — the guarantee this repo makes is "identical bytes in, identical
    digest out", and claiming more than that would be false.
    """
    forward = _catalog(nse_equity_row(), bse_equity_row())
    reverse = _catalog(bse_equity_row(), nse_equity_row())
    assert forward.instruments == reverse.instruments
    assert canonical_parsed_digest(forward) != canonical_parsed_digest(reverse)


# --- the suspended file -----------------------------------------------------


def test_suspended_rows_parse_with_their_own_twelve_field_model() -> None:
    """The cleanest schema in the verification pass: nothing optional, no surprises."""
    catalog = read_suspended_catalog(
        suspended_fetch([suspended_row()]), max_decompressed_bytes=_CAP
    )
    assert catalog.outcome is AcquisitionOutcome.OK
    assert catalog.suspended[0].qty_multiplier == Decimal("1.0")


def test_a_suspended_row_missing_qty_multiplier_is_schema_drift() -> None:
    """All twelve fields were present in 100% of 33,930 records; absence is drift."""
    broken = suspended_row()
    del broken["qty_multiplier"]
    catalog = read_suspended_catalog(suspended_fetch([broken]), max_decompressed_bytes=_CAP)
    assert catalog.outcome is AcquisitionOutcome.SCHEMA_DRIFT


def test_suspended_rows_are_grouped_by_isin_and_never_de_duplicated() -> None:
    """A file carries one row per series; collapsing them discards the distinction."""
    catalog = read_suspended_catalog(
        suspended_fetch([suspended_row(), suspended_row(instrument_type="EQ", exchange_token="1")]),
        max_decompressed_bytes=_CAP,
    )
    assert len(catalog.suspended) == 2
    assert len(catalog.by_isin()["INE999Z01046"]) == 2


def test_the_suspended_catalog_retains_the_sentinel_lot_size_uncorrected() -> None:
    """A handful of live rows carry ``999999999``. It is a curiosity, not ours to fix."""
    catalog = read_suspended_catalog(
        suspended_fetch([suspended_row(lot_size=999999999)]), max_decompressed_bytes=_CAP
    )
    assert catalog.suspended[0].lot_size == 999999999


def test_the_listed_catalog_groups_multiple_rows_per_isin() -> None:
    """A dual-listed issuer yields one row per exchange, both kept under one ISIN."""
    catalog = _catalog(
        nse_equity_row(),
        bse_equity_row(
            isin=NSE_ISIN, instrument_key=f"BSE_EQ|{NSE_ISIN}", trading_symbol="FIXTURECOB"
        ),
    )
    assert len(catalog.by_isin()[NSE_ISIN]) == 2
    assert {row.trading_symbol for row in catalog.by_isin()[NSE_ISIN]} == {NSE_SYMBOL, "FIXTURECOB"}
