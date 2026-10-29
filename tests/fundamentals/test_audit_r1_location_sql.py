"""F03 issuer eligibility through real PostgreSQL and retained synthetic transcripts."""

import hashlib
from datetime import UTC, datetime, timedelta

import pg_evidence_schema_support as schema_support
import psycopg
import pymupdf
import pytest
from ledger_support import Ledger, ledger
from pg_evidence_schema_support import (
    NOW,
    _capture,
    _insert,
    _interpretation,
    _occurrence,
    runtime,
    seeded,
)
from test_ledger_claim_check import LEDGER_SECTION, QUOTED

from fundamentals.contracts.ledger import Citation, CitationKind
from fundamentals.contracts.snapshot import (
    INTAKE_RIGHTS,
    BlobRef,
    CaptureRecord,
    OutcomeCode,
    OutcomeRecord,
    RequestIdentity,
)
from fundamentals.contracts.source_catalog import BUILTIN_SOURCES
from fundamentals.ledger.citations import resolve_location

__all__ = ["ledger", "runtime", "seeded"]
pytestmark = pytest.mark.pg
QUOTE = "Demand remains steady."
ANCHOR = f"p1.b0.0:{len(QUOTE)}"


@pytest.fixture(autouse=True)
def legacy_time(monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest) -> None:
    insert = schema_support._insert_ignoring_conflict

    def seed(conn: psycopg.Connection, table: str, row: dict) -> None:
        if table == "fact_rows":
            row = row | {"knowledge_time": getattr(request, "param", NOW.isoformat())}
        insert(conn, table, row)

    monkeypatch.setattr(schema_support, "_insert_ignoring_conflict", seed)


@pytest.fixture
def transcript(ledger: Ledger, runtime: psycopg.Connection) -> tuple[int, str]:
    with pymupdf.open() as pdf:
        pdf.new_page().insert_text((72, 72), QUOTE)
        body = pdf.tobytes()
    digest = hashlib.sha256(body).hexdigest()
    source = "bse-results-pdf"
    record = CaptureRecord.make(
        request=RequestIdentity(source_id=source, surface="BSE_RESULTS_PDF", request_key="a" * 64),
        retrieved_at=NOW,
        http_status=200,
        media_type="application/pdf",
        content_encoding=None,
        body=BlobRef(source_id=source, content_sha256=digest, byte_count=len(body)),
        outcome=OutcomeRecord(code=OutcomeCode.OK, native_kind="synthetic", native_value="OK"),
        rights=INTAKE_RIGHTS,
    )
    ledger.snapshots.put_capture(record, body)
    capture = _insert(
        runtime,
        "capture_refs",
        _capture(record.capture_id)
        | {
            "source_id": source,
            "surface": record.request.surface,
            "request_key": record.request.request_key,
            "blob_sha256": digest,
            "record_sha256": record.record_sha256,
        },
    )
    return capture, digest


def _resolves(ledger: Ledger, runtime: psycopg.Connection, capture: int, cutoff: datetime) -> bool:
    return resolve_location(
        runtime.cursor(),
        str(capture),
        ANCHOR,
        entity_id=ledger.entity_id,
        cutoff=cutoff,
        catalog=BUILTIN_SOURCES,
        snapshots=ledger.snapshots,
    )


@pytest.mark.parametrize("future", [False, True], ids=["known", "future"])
def test_interpretation_recording_must_precede_cutoff(
    ledger: Ledger, runtime: psycopg.Connection, transcript: tuple[int, str], future: bool
) -> None:
    capture, _ = transcript
    cutoff = NOW + timedelta(days=1)
    occurrence = _insert(runtime, "occurrences", _occurrence(capture, "qualitative-binding"))
    _insert(
        runtime,
        "interpretations",
        _interpretation(
            ledger.entity_id,
            capture,
            occurrence,
            recorded_at=cutoff + timedelta(days=1) if future else NOW,
        ),
    )
    assert _resolves(ledger, runtime, capture, cutoff) is (not future)


def test_sealed_imported_quote_binds_retained_transcript(
    ledger: Ledger, runtime: psycopg.Connection, transcript: tuple[int, str]
) -> None:
    capture, digest = transcript
    before_seal = datetime.now(UTC)
    citation = Citation(
        kind=CitationKind.SOURCE_QUOTE, source_sha256=digest, anchor=ANCHOR, quote=QUOTE
    )
    quoted = QUOTED.model_copy(update={"citation": citation, "unresolved": True})
    ledger.imported(
        ledger.report(),
        sections=(LEDGER_SECTION,),
        claims=(quoted,),
        import_sources=(("reports/transcript.json", b"{}"),),
    )
    assert _resolves(ledger, runtime, capture, datetime.now(UTC))
    assert not _resolves(ledger, runtime, capture, before_seal)
    assert not resolve_location(
        runtime.cursor(),
        str(capture),
        ANCHOR,
        entity_id=ledger.entity_id + 1000,
        cutoff=datetime.now(UTC),
        catalog=BUILTIN_SOURCES,
        snapshots=ledger.snapshots,
    )


@pytest.mark.parametrize("legacy_time", ["t"], indirect=True)
def test_unrelated_invalid_legacy_time_does_not_error(
    ledger: Ledger, runtime: psycopg.Connection, transcript: tuple[int, str]
) -> None:
    capture, _ = transcript
    assert not _resolves(ledger, runtime, capture, datetime.now(UTC))
