"""Raw Screener page/schedule bytes to lossless occurrences under an explicit issuer binding.

The capture's surface must be registered in the source catalog (else ``NOT_AUTHORISED``).
Callers supply an actual registered capture. HTML and schedule JSON remain separate captures,
and legacy metadata is a claim, never a store-clock receipt. Screener declares no publication
time, so knowledge time is ``UNKNOWN``.
"""

from __future__ import annotations

import calendar
import hashlib
import json
from datetime import date
from typing import Any
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field

from fundamentals.contracts.acquisition_outcome import ExtractionOutcome
from fundamentals.contracts.canonical import Basis, Representation, StatementFamily
from fundamentals.contracts.evidence import (
    CaptureReference,
    KnowledgeTimeStatus,
    Occurrence,
    PrecisionKind,
    RevisionCause,
)
from fundamentals.contracts.measurement_key import PeriodInterval
from fundamentals.contracts.source_catalog import SurfaceNotAuthorisedError, surface_authority
from fundamentals.evidence.interpret import input_digest
from fundamentals.evidence.vendor_ingest import VendorExtraction as ScreenerExtraction
from fundamentals.evidence.vendor_ingest import VendorExtractionError as ScreenerExtractionError
from fundamentals.evidence.vendor_ingest import missing_state
from fundamentals.ingest.screener_financials_models import (
    RESERVED_SUB_ROW_KEYS,
    Period,
    PeriodKind,
    ReconciliationStatus,
    Section,
    SectionTable,
    Unit,
)
from fundamentals.ingest.screener_financials_schedules import parse_sub_rows, read_schedule
from fundamentals.ingest.screener_financials_tables import (
    read_number,
    read_section,
    schedule_parents,
)
from fundamentals.ingest.screener_session_models import (
    Basis as ScreenerBasis,
)
from fundamentals.ingest.screener_session_models import (
    BasisTopology,
    PageOutcome,
    ScreenerSessionError,
)
from fundamentals.ingest.screener_session_page import parse_document, read_page_evidence

SOURCE = "screener-subscriber"
PAGE_SURFACE = "SCREENER_FINANCIALS"
PAGE_SCHEMA = "screener-financials-html-v1"
SCHEDULE_SURFACE = "SCREENER_SCHEDULE"
SCHEDULE_SCHEMA = "screener-financials-schedule-v1"
EXTRACTOR_VERSION = "screener-v1"
FAMILY_BY_SECTION = {
    Section.QUARTERS: StatementFamily.PL,
    Section.PROFIT_LOSS: StatementFamily.PL,
    Section.BALANCE_SHEET: StatementFamily.BALANCE_SHEET,
    Section.CASH_FLOW: StatementFamily.CASH_FLOW,
    Section.RATIOS: StatementFamily.DERIVED,
}
_REPRESENTATION = {PAGE_SURFACE: Representation.HTML, SCHEDULE_SURFACE: Representation.JSON}
_SCHEMA = {PAGE_SURFACE: PAGE_SCHEMA, SCHEDULE_SURFACE: SCHEDULE_SCHEMA}
_UNIT = {
    Unit.RS_CRORE: ("INR", 7),
    Unit.RUPEES: ("INR per share", 0),
    Unit.PERCENT: ("percent", 0),
    Unit.DAYS: ("days", 0),
    Unit.COUNT: ("count", 0),
    Unit.RATIO: ("ratio", 0),
}


class ScreenerIssuerBinding(BaseModel):
    """Composition-root issuer identity, already backed by its independently reviewed config."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    symbol: str = Field(min_length=1)
    company_id: int = Field(gt=0)
    bse_code: str = Field(pattern=r"^\d+$")
    topology: BasisTopology
    identity_evidence_ref: str = Field(min_length=1)
    fiscal_year_end_month: int = Field(default=3, ge=1, le=12)


def extract_screener_page(
    body: bytes,
    *,
    capture: CaptureReference,
    binding: ScreenerIssuerBinding,
    basis: Basis,
    section: Section,
    extractor_version: str = EXTRACTOR_VERSION,
) -> ScreenerExtraction:
    """Read one requested section from a registered, hash-pinned raw HTML capture."""
    _scope(body, capture, section, PAGE_SURFACE)
    _, table = _verified_table(body, binding, basis, section, capture)
    occurrences: list[Occurrence] = []
    for row in table.rows:
        for cell in row.cells:
            period = next(p for p in table.periods if p.index == cell.period_index)
            occurrences.append(
                _occurrence(
                    capture,
                    basis,
                    section,
                    row.label,
                    cell.raw_text,
                    unit=row.unit,
                    native_period=period,
                    anchor=cell.provenance.model_dump(mode="json"),
                    binding=binding,
                    extractor_version=extractor_version,
                    disclosure={"identity_strength": table.identity_strength.value},
                )
            )
    for quarantined in table.quarantined:
        for index, lexeme in enumerate(quarantined.raw_cells):
            occurrences.append(
                _occurrence(
                    capture,
                    basis,
                    section,
                    quarantined.label,
                    lexeme,
                    unit=Unit.UNKNOWN,
                    native_period=None,
                    anchor={
                        "anchor_type": "HTML_TABLE",
                        "table_id": table.table_id,
                        "row_path": f"tr[{quarantined.position}]:{quarantined.label}",
                        "column_index": index,
                        "column_label": None,
                    },
                    binding=binding,
                    extractor_version=extractor_version,
                    disclosure={"quarantined": True, "reason": quarantined.reason},
                )
            )
    reasons = tuple(row.reason for row in table.quarantined)
    return ScreenerExtraction(
        occurrences=tuple(occurrences),
        outcome=ExtractionOutcome.PARTIAL if reasons else ExtractionOutcome.COMPLETE,
        reasons=reasons,
        issuer=binding.symbol,
        basis=basis,
        extraction_context_sha256=_context(capture, binding, basis, section),
    )


def extract_screener_schedule(
    body: bytes,
    *,
    capture: CaptureReference,
    page_body: bytes,
    page_capture: CaptureReference,
    binding: ScreenerIssuerBinding,
    basis: Basis,
    section: Section,
    parent: str,
    metadata_body: bytes | None = None,
    extractor_version: str = EXTRACTOR_VERSION,
) -> ScreenerExtraction:
    """Revalidate a separately pinned raw schedule against its actual page expander.

    Bare schedule JSON declares no issuer/basis. Its binding, basis and exact page capture
    remain explicit supporting provenance; reconciliation never promotes its equivalence tier.
    All lexemes, source nulls and unknown periods survive even when reconciliation is refused.
    """
    _scope(body, capture, section, SCHEDULE_SURFACE)
    _scope(page_body, page_capture, section, PAGE_SURFACE)
    root, table = _verified_table(page_body, binding, basis, section, page_capture)
    parents = schedule_parents(root)
    if (section, parent) not in parents:
        raise ScreenerExtractionError(
            ExtractionOutcome.UNSUPPORTED_SCHEMA,
            "schedule request is absent from this page's own expanders",
        )
    page_rows = [row for row in table.rows if row.schedule_parent == parent]
    if len(page_rows) != 1:
        raise ScreenerExtractionError(
            ExtractionOutcome.UNSUPPORTED_SCHEMA, "schedule has no unique source-bound page parent"
        )
    from fundamentals.ingest.screener_financials_models import schedule_path, schedule_url

    document_id = schedule_path(
        binding.company_id,
        parent=parent,
        section=section,
        basis=ScreenerBasis(basis.value.lower()),
    )
    reasons: list[str] = []
    raw = _unique_json(body)
    try:
        family = read_schedule(
            body,
            section=section,
            parent=parent,
            basis=ScreenerBasis(basis.value.lower()),
            url=schedule_url(
                binding.company_id,
                parent=parent,
                section=section,
                basis=ScreenerBasis(basis.value.lower()),
            ),
            document_id=document_id,
            body_sha256=capture.blob_sha256,
            periods=table.periods,
            page_row=page_rows[0],
            source_id=capture.source_id,
            retrieved_at=capture.first_seen_at,
        )
        rows = family.sub_rows
        reconciliation = family.reconciliation.value
        if family.reconciliation not in (
            ReconciliationStatus.RECONCILED,
            ReconciliationStatus.NOT_APPLICABLE,
        ):
            reasons.append(family.reconciliation_note)
    except ScreenerSessionError as error:
        rows = parse_sub_rows(
            body,
            family=f"{section.value}/{parent}",
            periods=table.periods,
            document_id=document_id,
            body_sha256=capture.blob_sha256,
            source_id=capture.source_id,
            retrieved_at=capture.first_seen_at,
        )
        reconciliation = "refused"
        reasons.append(str(error))
    claim = _metadata_claim(metadata_body, binding, basis, section, parent)
    if claim.get("surface_unverified"):
        reasons.append("retained metadata marks this exact schedule surface unverified")
    occurrences: list[Occurrence] = []
    by_label = {p.label: p for p in table.periods}
    for row in rows:
        values = raw[row.label]
        for label, value in values.items():
            if label in RESERVED_SUB_ROW_KEYS:
                continue
            lexeme = value if isinstance(value, str) or value is None else str(value)
            native_period = by_label.get(label)
            if native_period is None:
                reasons.append(f"schedule period {label!r} is absent from the supporting header")
            unit = Unit.PERCENT if row.percent else Unit.RS_CRORE
            occurrences.append(
                _occurrence(
                    capture,
                    basis,
                    section,
                    row.label,
                    lexeme,
                    unit=unit,
                    native_period=native_period,
                    binding=binding,
                    extractor_version=extractor_version,
                    anchor={
                        "anchor_type": "API_DOCUMENT",
                        "document_id": document_id,
                        "table_key": f"{section.value}/{parent}",
                        "row_label": row.label,
                        "column_label": label,
                        "json_path": [row.label, label],
                    },
                    disclosure={
                        "identity_strength": "configured_url_only",
                        "supporting_page_capture_id": page_capture.capture_id,
                        "supporting_page_sha256": page_capture.blob_sha256,
                        "reconciliation": reconciliation,
                        **claim,
                    },
                    section_name=f"{section.value}/{parent}",
                    precision_supported=isinstance(value, str),
                )
            )
    return ScreenerExtraction(
        occurrences=tuple(occurrences),
        outcome=ExtractionOutcome.PARTIAL if reasons else ExtractionOutcome.COMPLETE,
        reasons=tuple(dict.fromkeys(reasons)),
        issuer=binding.symbol,
        basis=basis,
        extraction_context_sha256=_context(
            capture,
            binding,
            basis,
            section,
            parent=parent,
            page_sha256=page_capture.blob_sha256,
            metadata_sha256=hashlib.sha256(metadata_body).hexdigest()
            if metadata_body is not None
            else None,
        ),
    )


def _scope(body: bytes, capture: CaptureReference, section: Section, surface: str) -> None:
    """Refuse an unregistered surface, another surface or section, or drifted bytes."""
    try:
        surface_authority(capture.source_id, capture.surface)
    except SurfaceNotAuthorisedError as error:
        raise ScreenerExtractionError(ExtractionOutcome.NOT_AUTHORISED, str(error)) from error
    if section not in FAMILY_BY_SECTION:
        raise ScreenerExtractionError(
            ExtractionOutcome.UNSUPPORTED_SCHEMA, "unsupported Screener section"
        )
    if capture.capture_ref_id is None or (capture.source_id, capture.surface) != (
        SOURCE,
        surface,
    ):
        raise ScreenerExtractionError(
            ExtractionOutcome.IDENTITY_REJECTED,
            "capture is unregistered or belongs to another surface",
        )
    if hashlib.sha256(body).hexdigest() != capture.blob_sha256:
        raise ScreenerExtractionError(
            ExtractionOutcome.FAILED, "retained Screener content pin mismatch"
        )


def _verified_table(
    body: bytes,
    binding: ScreenerIssuerBinding,
    basis: Basis,
    section: Section,
    capture: CaptureReference,
) -> tuple[Any, SectionTable]:
    try:
        text = body.decode("utf-8")
        proof, outcome = read_page_evidence(
            text,
            basis_requested=ScreenerBasis(basis.value.lower()),
            topology=binding.topology,
        )
        if proof.company_id != binding.company_id or outcome is not PageOutcome.OK:
            raise ScreenerExtractionError(
                ExtractionOutcome.IDENTITY_REJECTED,
                "raw page does not prove the configured issuer and basis",
            )
        root = parse_document(text)
        # Exchange links are document assertions, not arbitrary URL substrings or directory names.
        links = [urlsplit(str(link)) for link in root.xpath("//a/@href")]
        bse = any(
            link.hostname == "www.bseindia.com"
            and link.path.rstrip("/").endswith("/" + binding.bse_code)
            for link in links
        )
        if not bse:
            raise ScreenerExtractionError(
                ExtractionOutcome.IDENTITY_REJECTED,
                "raw page lacks the pinned exchange-code identity",
            )
        table = read_section(
            root,
            section,
            source_id=capture.source_id,
            file_sha256=capture.blob_sha256,
            retrieved_at=capture.first_seen_at,
        )
        return root, table
    except ScreenerExtractionError:
        raise
    except (ScreenerSessionError, UnicodeDecodeError, ValueError) as error:
        raise ScreenerExtractionError(ExtractionOutcome.PARSE_FAILED, str(error)) from error


def _period(native: Period | None, section: Section, fiscal_end: int) -> PeriodInterval | None:
    if native is None or native.kind is not PeriodKind.DATE or native.period_end is None:
        return None
    end = native.period_end
    if section is Section.BALANCE_SHEET:
        return PeriodInterval.at(end)
    if section is Section.RATIOS:
        return None  # A ratio label does not settle the numerator/denominator temporal role.
    months = 3 if section is Section.QUARTERS else 12
    if end.day != calendar.monthrange(end.year, end.month)[1]:
        return None
    if months == 12 and end.month != fiscal_end:
        return None
    offset = end.year * 12 + end.month - months
    start = date(offset // 12, offset % 12 + 1, 1)
    period = PeriodInterval.duration(start, end)
    return period if period.kind(fiscal_end).value in ("QUARTER", "YEAR") else None


def _occurrence(
    capture: CaptureReference,
    basis: Basis,
    section: Section,
    label: str,
    lexeme: str | None,
    *,
    unit: Unit,
    native_period: Period | None,
    anchor: dict[str, Any],
    binding: ScreenerIssuerBinding,
    extractor_version: str,
    disclosure: dict[str, Any],
    section_name: str | None = None,
    precision_supported: bool = True,
) -> Occurrence:
    value, _ = read_number(lexeme or "")
    # Actual printed decimal places; JSON numeric scalars alone declare no precision.
    printed = (lexeme or "").strip().rstrip("%").replace(",", "")
    declared = len(printed.rsplit(".", 1)[1]) if "." in printed else 0
    precision = (
        PrecisionKind.FINITE
        if value is not None and precision_supported
        else PrecisionKind.UNSUPPORTED
    )
    raw_unit, scale = _UNIT.get(unit, ("unknown", 0))
    period = _period(native_period, section, binding.fiscal_year_end_month)
    location = {
        key: val
        for key, val in anchor.items()
        if key
        not in (
            "retrieved_at",
            "filed_at",
            "published_at",
            "first_seen_at",
            "source_id",
            "file_sha256",
        )
        and val is not None
    }
    return Occurrence(
        occurrence_id=None,
        capture=capture,
        representation=_REPRESENTATION[capture.surface],
        extractor_version=extractor_version,
        native_field=label,
        raw_value_text=lexeme,
        raw_unit=raw_unit,
        raw_scale=scale,
        raw_sign=-1 if value is not None and value < 0 else 1,
        precision_kind=precision,
        declared_precision=declared if precision is PrecisionKind.FINITE else None,
        native_context={
            "schema_identity": _SCHEMA[capture.surface],
            "basis": basis.value,
            "statement_family": FAMILY_BY_SECTION[section].value,
            "label": label,
            "section": section_name or section.value,
            "header_months": 3 if section is Section.QUARTERS else 12,
            "native_period_kind": native_period.kind.value if native_period else "untyped",
            "native_period_label": native_period.label if native_period else None,
            "identity_evidence_ref": binding.identity_evidence_ref,
        },
        period=period,
        missing_state=missing_state(lexeme, value),
        disclosure=disclosure,
        anchor=location,
        anchor_key=input_digest(location),
        knowledge_time=None,
        knowledge_time_status=KnowledgeTimeStatus.UNKNOWN,
        first_seen_at=capture.first_seen_at,
        revision_cause=RevisionCause.ORIGINAL,
    )


def _context(
    capture: CaptureReference,
    binding: ScreenerIssuerBinding,
    basis: Basis,
    section: Section,
    **extra: object,
) -> str:
    return input_digest(
        {
            "surface": capture.surface,
            "capture_sha256": capture.blob_sha256,
            "basis": basis.value,
            "binding": binding.model_dump(mode="json"),
            "section": section.value,
            **extra,
        }
    )


def _metadata_claim(
    body: bytes | None,
    binding: ScreenerIssuerBinding,
    basis: Basis,
    section: Section,
    parent: str,
) -> dict[str, Any]:
    if body is None:
        return {"metadata_verification_unknown": True}
    parsed = _unique_json(body)
    if (parsed.get("company_id"), parsed.get("symbol"), parsed.get("basis")) != (
        binding.company_id,
        binding.symbol,
        basis.value.lower(),
    ):
        raise ScreenerExtractionError(
            ExtractionOutcome.IDENTITY_REJECTED, "retained metadata claims another issuer or basis"
        )
    return {
        "metadata_sha256": hashlib.sha256(body).hexdigest(),
        "claimed_fetched_at": parsed.get("fetched_at"),
        "surface_unverified": f"{section.value}/{parent}"
        in parsed.get("schedule_families_unverified", []),
        "capture_complete_claim": parsed.get("complete"),
        "capture_verified_claim": parsed.get("verified"),
    }


def _unique_json(body: bytes) -> dict[str, Any]:
    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON selector {key!r}")
            result[key] = value
        return result

    try:
        parsed = json.loads(body.decode("utf-8"), object_pairs_hook=unique)
        if not isinstance(parsed, dict):
            raise ValueError("Screener schedule/metadata must be a JSON object")
        return parsed
    except (UnicodeDecodeError, ValueError) as error:
        raise ScreenerExtractionError(ExtractionOutcome.PARSE_FAILED, str(error)) from error
