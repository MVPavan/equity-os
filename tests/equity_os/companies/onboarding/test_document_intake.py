"""Transactional document intake and append-only revision history."""

from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import psycopg
import pytest
from pg_support import PgTestDatabase


@pytest.mark.pg
def test_revisions_returning_to_old_payload_and_coverage(pg_db: PgTestDatabase) -> None:
    """A correction back to A remains history; a repeat of latest A adds nothing."""
    from equity_os.storage.records.document_intake import DocumentIntake

    with pg_db.runtime_pool() as pool, pool.connection() as conn:
        intake = DocumentIntake(conn)
        at = datetime(2026, 10, 27, tzinfo=UTC)
        for index, value in enumerate(("A", "B", "A", "A")):
            count = intake.record_listing(
                dict(
                    entity_id=1,
                    symbol="SYNTH",
                    surface="ANNOUNCEMENTS_LISTING",
                    span_from=date(2026, 10, 24),
                    span_to=date(2026, 10, 27),
                    retrieved_at=at + timedelta(seconds=index),
                    outcome="HTTP_403",
                    capture_ref_id=None,
                ),
                [("occurrence", {"value": value})],
            )
            assert count == (1 if index < 3 else 0)
        latest = intake.latest(1, "ANNOUNCEMENTS_LISTING")
        assert len(latest) == 1 and latest[0].payload == {"value": "A"}
        assert latest[0].observed_at == at + timedelta(seconds=2)
        assert conn.execute("SELECT count(*) FROM eqos.document_observations").fetchone() == (3,)
        assert intake.ok_spans(1, "ANNOUNCEMENTS_LISTING") == []
        for table in ("document_listings", "document_observations", "document_attempts"):
            for action in ("UPDATE {} SET id=id", "DELETE FROM {}", "TRUNCATE {}"):
                with pytest.raises(psycopg.Error), conn.transaction():
                    conn.execute(
                        psycopg.sql.SQL(action).format(psycopg.sql.Identifier("eqos", table))
                    )


@pytest.mark.pg
def test_attempts_pin_routes_rights_times_and_refuse_wrong_bytes(
    pg_db: PgTestDatabase, tmp_path: Path
) -> None:
    """Only PDF/annual ZIP bodies register; failed bytes keep their diagnostic hash."""
    import hashlib

    from equity_os.companies.onboarding.discovery import (
        Capture,
        Request,
        acquiring_fetch,
        authorised,
        register_capture,
    )
    from equity_os.contracts.companies.onboarding import VerificationUnit
    from equity_os.contracts.sourcing.source_catalog import VENDOR_SURFACES, DocumentKind
    from equity_os.sourcing.transport.http_session import ResponseTooLargeError
    from equity_os.storage.raw_files.capture_retention import Registration
    from equity_os.storage.raw_files.snapshot_store import SnapshotStore
    from equity_os.storage.records.document_intake import DocumentIntake, refusal

    at = datetime(2026, 10, 27, tzinfo=UTC)
    store = SnapshotStore(tmp_path / "snapshots")
    with pg_db.runtime_pool() as pool, pool.connection() as conn:
        intake = DocumentIntake(conn)
        intake.record_listing(
            dict(
                entity_id=1,
                symbol="SYNTH",
                surface="ANNOUNCEMENTS_LISTING",
                span_from=None,
                span_to=None,
                retrieved_at=at,
                outcome="HTTP_403",
                capture_ref_id=None,
            ),
            [("one", {})],
        )
        observation = intake.latest(1, "ANNOUNCEMENTS_LISTING")[0]
        cases = [
            (DocumentKind.TRANSCRIPT, b"%PDF-1.7\n%%EOF\n", 200, "OK"),
            (DocumentKind.ANNUAL_REPORT, b"PK\x03\x04zip" + b"PK\x05\x06" + bytes(18), 200, "OK"),
            (DocumentKind.ANNUAL_REPORT, b"PK\x03\x04zip", 200, "TRUNCATED"),
            (DocumentKind.RESULTS, b"<html>denied</html>", 200, "WRONG_TYPE"),
            (DocumentKind.PRESENTATION, b"", 403, "HTTP_403"),
            (DocumentKind.CREDIT_RATING, b"", 999, "TOO_LARGE"),
        ]
        for kind, body, status, expected in cases:
            request = Request(
                unit=VerificationUnit.EXCHANGE,
                source_id="nse-documents",
                surface=f"NSE_{kind}",
                url=f"https://nsearchives.nseindia.com/{kind}/{expected}",
            )

            def send(_: Request, status: int = status, body: bytes = body) -> tuple[int, bytes]:
                if status == 999:
                    raise ResponseTooLargeError("oversize")
                return status, body

            response = acquiring_fetch(send, lambda: at, [])(
                request, authorised(request, VENDOR_SURFACES)
            )
            outcome = refusal(kind, body) if response.outcome == "OK" else response.outcome
            ref_id = None
            with conn.transaction():
                if outcome == "OK":
                    _, ref = register_capture(
                        store, Registration(conn), Capture(request=request, response=response)
                    )
                    ref_id = ref.capture_ref_id
                    record = store.list_captures(ref.source_id, ref.surface, ref.request_key)[0]
                    assert record.retrieved_at == at
                    assert record.rights.authority_refs == (
                        "docs/evidence/phase-0a/a-05-rights-decision-004-private-use.md",
                    )
                intake.record_attempt(
                    observation.id,
                    request.url,
                    response.retrieved_at,
                    outcome,
                    hashlib.sha256(response.body).hexdigest()
                    if response.body is not None
                    else None,
                    ref_id,
                )
            assert intake.attempts(observation.id, request.url) == [expected]
        assert conn.execute("SELECT count(*) FROM eqos.capture_refs").fetchone() == (2,)
        assert conn.execute(
            "SELECT body_sha256 IS NOT NULL, capture_ref_id FROM eqos.document_attempts "
            "WHERE outcome='WRONG_TYPE'"
        ).fetchone() == (True, None)
