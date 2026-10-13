"""Offline parser wiring proves content guards without claiming real vendor measurements."""

import hashlib
from datetime import UTC, datetime

import pytest

from fundamentals.evidence import vendor_tijori, vendor_upstox
from fundamentals.ingest.tijori_source import TijoriSource
from fundamentals.ingest.upstox_source import (
    AcquisitionOutcome,
    UpstoxCapture,
    UpstoxFetch,
    UpstoxSurface,
)
from fundamentals.ingest.upstox_statements import StatementBasis


def test_tijori_wiring_passes_the_same_pinned_buffer_to_offline_parser(monkeypatch):
    body = b"constructed parser wiring input"
    calls = []

    def parser(raw, **kwargs):
        calls.append((raw, kwargs))
        return ()

    monkeypatch.setattr(TijoriSource, "parse_all_tables_bytes", parser)
    result = vendor_tijori.read_financials(
        body,
        expected_sha256=hashlib.sha256(body).hexdigest(),
        slug="constructed",
        expected_symbol="CONSTRUCTED",
        expected_company_id=7,
        source_url="https://example.invalid/constructed",
        claimed_retrieved_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    assert result == () and len(calls) == 1
    assert calls[0][0] is body
    assert calls[0][1]["expected_symbol"] == "CONSTRUCTED"
    assert calls[0][1]["expected_company_id"] == 7
    assert calls[0][1]["retrieved_at"] == datetime(2026, 1, 1, tzinfo=UTC)
    with pytest.raises(ValueError, match="content pin"):
        vendor_tijori.read_financials(
            body,
            expected_sha256="0" * 64,
            slug="constructed",
            expected_symbol="CONSTRUCTED",
            expected_company_id=7,
            source_url="https://example.invalid/constructed",
            claimed_retrieved_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
    assert len(calls) == 1


def test_upstox_wiring_refuses_unpinned_bytes_before_statement_parser(monkeypatch):
    body = b"{}"
    capture = UpstoxCapture(
        surface=UpstoxSurface.INCOME_STATEMENT,
        route_key="constructed",
        request_url="https://example.invalid/constructed",
        http_status=200,
        media_type="application/json",
        byte_count=len(body),
        content_sha256="0" * 64,
        outcome=AcquisitionOutcome.OK,
        retrieved_at=datetime(2026, 1, 1, tzinfo=UTC),
    )

    def never_called(*args, **kwargs):
        raise AssertionError("unpinned bytes reached the statement parser")

    monkeypatch.setattr(vendor_upstox, "read_income_statement", never_called)
    with pytest.raises(ValueError, match="content pin"):
        vendor_upstox.read_statements(
            UpstoxFetch(raw_body=body, capture=capture), requested_basis=StatementBasis.CONSOLIDATED
        )
