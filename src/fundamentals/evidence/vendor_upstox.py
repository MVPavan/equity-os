"""Upstox diagnostic income statement to lossless occurrences, never a vote (spec §2–§3).

The requested basis and periodicity are the capture record's own request parameters. Each
block keeps its real periodicity: the summary follows the request, ``full_statement`` is
annual even on a quarterly request. An empty response cannot be told apart from an unknown
ISIN, so it is rejected and yields no values. The reader refuses any ``units_in`` other than
crore; EPS rows are per share, never crore (the docs wrongly call every value crore), so they
keep no unit. API numerals declare no precision.
"""

from __future__ import annotations

from urllib.parse import urlencode

from fundamentals.contracts.acquisition_outcome import ExtractionOutcome
from fundamentals.contracts.canonical import Basis, StatementFamily
from fundamentals.contracts.evidence import CaptureReference
from fundamentals.contracts.snapshot import CaptureRecord
from fundamentals.evidence.interpret import input_digest
from fundamentals.evidence.vendor_ingest import (
    VendorExtraction,
    VendorExtractionError,
    json_occurrence,
    month_period,
)
from fundamentals.ingest.upstox_retention import (
    ORIGIN_PARAMETER,
    PATH_PARAMETER,
    ROUTE_PARAMETER,
)
from fundamentals.ingest.upstox_source import (
    AcquisitionOutcome,
    UpstoxCapture,
    UpstoxFetch,
    UpstoxSurface,
)
from fundamentals.ingest.upstox_statements import (
    StatementBasis,
    StatementPeriodicity,
    read_income_statement,
)

SOURCE_ID = "upstox"
EXTRACTOR_VERSION = "upstox-v2"
SUMMARY = "summary"
FULL_STATEMENT = "full_statement"
SCHEMA_IDENTITY = {
    SUMMARY: "upstox-income-statement-summary-v2",
    FULL_STATEMENT: "upstox-income-statement-full-statement-v2",
}
CRORE = ("INR", 7)  # The reader refuses every ``units_in`` but crore.
UNKNOWN_UNIT = ("unknown", 0)
_PER_SHARE_PREFIX = "EPS"
_MONTHS = {StatementPeriodicity.QUARTERLY: 3, StatementPeriodicity.YEARLY: 12}
_EMPTY = "empty response: an unknown ISIN answers the same, so it proves nothing"
_OTHER_BASIS = "capture requested {requested!r}, not {basis!r}"
_UNSUPPORTED = "Upstox surface {surface!r} has no diagnostic adapter"


def extract_upstox(
    body: bytes,
    *,
    capture: CaptureReference,
    record: CaptureRecord,
    extractor_version: str,
    basis: Basis,
) -> VendorExtraction:
    """Read both income-statement blocks of one registered capture."""
    if capture.surface != UpstoxSurface.INCOME_STATEMENT.value:
        raise VendorExtractionError(
            ExtractionOutcome.UNSUPPORTED_SCHEMA, _UNSUPPORTED.format(surface=capture.surface)
        )
    params = {item.name: item.value for item in record.request.parameters}
    requested = params.get("type")
    if requested != basis.value.lower():
        raise VendorExtractionError(
            ExtractionOutcome.IDENTITY_REJECTED,
            _OTHER_BASIS.format(requested=requested, basis=basis.value.lower()),
        )
    periodicity = StatementPeriodicity(params.get("time_period", StatementPeriodicity.YEARLY))
    query = {
        name: value
        for name, value in params.items()
        if name not in (ORIGIN_PARAMETER, PATH_PARAMETER, ROUTE_PARAMETER)
    }
    document = read_income_statement(
        UpstoxFetch(
            raw_body=body,
            capture=UpstoxCapture(
                surface=UpstoxSurface.INCOME_STATEMENT,
                route_key=params[ROUTE_PARAMETER],
                request_url=f"{params[ORIGIN_PARAMETER]}{params[PATH_PARAMETER]}?"
                + urlencode(sorted(query.items())),
                http_status=record.http_status or 0,
                media_type=record.media_type,
                byte_count=len(body),
                content_sha256=capture.blob_sha256,
                outcome=AcquisitionOutcome.OK,
                retrieved_at=record.retrieved_at,
            ),
        ),
        requested_basis=StatementBasis(basis.value.lower()),
        requested_periodicity=periodicity,
    )
    if document.outcome is AcquisitionOutcome.OK_EMPTY:
        raise VendorExtractionError(ExtractionOutcome.IDENTITY_REJECTED, _EMPTY)
    if document.outcome is not AcquisitionOutcome.OK:
        raise VendorExtractionError(
            ExtractionOutcome.UNSUPPORTED_SCHEMA, "; ".join(document.anomalies)
        )
    blocks = [
        (SUMMARY, series.category, series.history, _MONTHS[periodicity])
        for series in document.summary
    ] + [(FULL_STATEMENT, line.particular, line.history, 12) for line in document.full_statement]
    occurrences = tuple(
        json_occurrence(
            capture,
            extractor_version=extractor_version,
            label=label,
            lexeme=str(point.value),
            value=point.value,
            raw_unit=unit,
            raw_scale=scale,
            period=month_period(point.period, months),
            native_context={
                "schema_identity": SCHEMA_IDENTITY[block],
                "basis": basis.value,
                "statement_family": StatementFamily.PL.value,
                "label": label,
                "section": block,
                "header_months": months,
            },
            anchor={
                "anchor_type": "API_DOCUMENT",
                "table_key": block,
                "row_label": label,
                "column_label": point.period,
            },
            disclosure={"anomalies": list(document.anomalies)},
        )
        for block, label, history, months in blocks
        for unit, scale in [UNKNOWN_UNIT if label.startswith(_PER_SHARE_PREFIX) else CRORE]
        for point in history
    )
    return VendorExtraction(
        occurrences=occurrences,
        outcome=ExtractionOutcome.COMPLETE,
        reasons=document.anomalies,
        issuer=params[PATH_PARAMETER].split("/")[3],  # /v2/fundamentals/{isin}/income-statement
        basis=basis,
        extraction_context_sha256=input_digest(
            {
                "surface": capture.surface,
                "capture_sha256": capture.blob_sha256,
                "basis": basis.value,
                "periodicity": periodicity.value,
            }
        ),
    )
