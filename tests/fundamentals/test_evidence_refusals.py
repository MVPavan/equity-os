"""First-party ingest refusals over retained Apar and marked copies (D1a Task 5).

A member that names another issuer, period or framework, comes from a source outside the
decision-12 table, or cannot be parsed is refused with one recorded attempt — and a stored
generation is never reused for a request it was not checked against.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from evidence_support import (
    CAPMKT,
    XBRL_ONLY,
    Ingest,
    dictionary,
    ingest,
    mapping_set,
    marked_xbrl,
    policy,
)
from retained_support import (
    APAR_RESULTS_PDF_SOURCE_ID,
    MarkedEdit,
    PdfRedaction,
    apar_original,
    marked_pdf,
)

from fundamentals.contracts.acquisition_outcome import ExtractionOutcome
from fundamentals.contracts.canonical import Basis, Representation
from fundamentals.contracts.evidence import AcquisitionAttempt, AttemptStage
from fundamentals.contracts.observation import AccountingFramework
from fundamentals.contracts.source_catalog import (
    BUILTIN_SOURCES,
    EvidenceRole,
    SourceClass,
    SourceDescriptor,
)
from fundamentals.evidence.capture_intake import NSE_XBRL_SOURCE_ID

__all__ = ["dictionary", "ingest", "mapping_set", "policy"]

pytestmark = [pytest.mark.pg, pytest.mark.retained]

PDF_ONLY = {Representation.PDF: "results"}
WRITTEN_TABLES = ("occurrences", "interpretations", "filing_packages", "package_members")
# The Q2 FY26 XBRL's only framework declaration (DisclosureOfNotesOnFinancialResults-
# ExplanatoryTextBlock@OneD) and the PDF's (page 5, notes).
XBRL_DECLARATION = b"prepared in accordance with Indian Accounting Standard notified"
XBRL_OPENING_INSTANT = (
    b'<xbrli:context id="OneI"><xbrli:entity><xbrli:identifier '
    b'scheme="http://www.sebi.gov.in/in-capmkt/ScripCode">532259</xbrli:identifier>'
    b"</xbrli:entity><xbrli:period><xbrli:instant>2025-09-30<"
)


def _overall(
    report_attempts: tuple[AcquisitionAttempt, ...], representation: Representation
) -> AcquisitionAttempt:
    """The one overall attempt of a member."""
    (attempt,) = [
        a
        for a in report_attempts
        if a.representation is representation and a.statement_family is None
    ]
    return attempt


@pytest.mark.parametrize(
    "edit",
    [
        MarkedEdit(
            label="scrip-context",
            find=b'ScripCode">532259<',
            replace=b'ScripCode">999999<',
            count=43,
        ),
        MarkedEdit(
            label="isin-fact",
            find=b'<in-capmkt:ISIN contextRef="OneD">INE372A01015<',
            replace=b'<in-capmkt:ISIN contextRef="OneD">INE000A01000<',
        ),
    ],
    ids=["scrip-context", "isin-fact"],
)
def test_identity_conflict_rejects_the_member(ingest: Ingest, edit: MarkedEdit) -> None:
    """A member naming another issuer is IDENTITY_REJECTED and writes nothing."""
    before = ingest.table_counts()
    report = ingest.run(
        ingest.intake(XBRL_ONLY, marked={Representation.XBRL: marked_xbrl(ingest.tmp_path, edit)})
    )
    (attempt,) = report.attempts
    assert attempt.outcome is ExtractionOutcome.IDENTITY_REJECTED
    after = ingest.table_counts()
    assert report.package_id is None
    for table in WRITTEN_TABLES:
        assert after[table] == before[table]


@pytest.mark.parametrize(
    "request_change",
    [
        {"basis": Basis.STANDALONE},
        {"period_end": date(2025, 6, 30)},
        {"framework": AccountingFramework.IFRS},
    ],
    ids=["standalone", "other-period", "ifrs"],
)
def test_reused_capture_is_checked_for_each_request(
    ingest: Ingest, request_change: dict[str, Any]
) -> None:
    """After a consolidated Ind AS Q2 ingest, the same capture requested under another
    basis, period or framework is IDENTITY_REJECTED — the stored COMPLETE generation was
    checked for the first request only and is never handed to another.
    """
    first = ingest.run(ingest.intake(XBRL_ONLY))
    assert _overall(first.attempts, Representation.XBRL).outcome is ExtractionOutcome.COMPLETE
    before = ingest.table_counts()
    report = ingest.run(ingest.intake(XBRL_ONLY), **request_change)
    attempt = _overall(report.attempts, Representation.XBRL)
    assert attempt.outcome is ExtractionOutcome.IDENTITY_REJECTED
    assert attempt.attempt_id not in {a.attempt_id for a in first.attempts}
    assert report.package_id is None
    after = ingest.table_counts()
    for table in WRITTEN_TABLES:
        assert after[table] == before[table]
    assert after["capture_refs"] == before["capture_refs"]


@pytest.mark.parametrize("declared", [None, SourceClass.DERIVED], ids=["undeclared", "derived"])
def test_unauthorised_source_is_never_staged(ingest: Ingest, declared: SourceClass | None) -> None:
    """A results PDF the catalog does not declare first-party is NOT_AUTHORISED, unstaged."""
    catalog = BUILTIN_SOURCES
    if declared is not None:
        catalog = catalog.extend(
            SourceDescriptor(
                source_id=APAR_RESULTS_PDF_SOURCE_ID,
                source_class=declared,
                evidence_role=EvidenceRole.DIAGNOSTIC_ONLY,
            )
        )
    report = ingest.run(ingest.intake(), catalog=catalog)
    (refused,) = [a for a in report.attempts if a.representation is Representation.PDF]
    assert refused.outcome is ExtractionOutcome.NOT_AUTHORISED
    assert refused.stage is AttemptStage.ACQUISITION and refused.capture is None
    assert set(ingest.package(report).members) == {Representation.XBRL}
    assert ingest.table_counts()["capture_refs"] == 1


@pytest.mark.parametrize(
    ("representation", "source_id"),
    [
        (Representation.PDF, NSE_XBRL_SOURCE_ID),
        (Representation.PDF, "bse-results-pdf"),
        (Representation.XBRL, "bse-xbrl"),
        (Representation.XBRL, APAR_RESULTS_PDF_SOURCE_ID),
    ],
    ids=["pdf-as-nse-xbrl", "pdf-as-bse-pdf", "xbrl-as-bse-xbrl", "xbrl-as-results-pdf"],
)
def test_first_party_source_of_another_surface_is_not_authorised(
    ingest: Ingest, representation: Representation, source_id: str
) -> None:
    """Only the decision-12 (representation, source) pairs are authorised: a first-party
    source declared for another surface or issuer is NOT_AUTHORISED and never staged.
    """
    intake = ingest.intake()
    bindings = tuple(
        binding.model_copy(update={"source_id": source_id})
        if binding.representation is representation
        else binding
        for binding in intake.bindings
    )
    report = ingest.run(intake.model_copy(update={"bindings": bindings}))
    (refused,) = [a for a in report.attempts if a.representation is representation]
    assert refused.outcome is ExtractionOutcome.NOT_AUTHORISED
    assert refused.stage is AttemptStage.ACQUISITION and refused.capture is None
    assert ingest.table_counts()["capture_refs"] == 1


def test_unknown_namespace_is_unsupported_schema(ingest: Ingest) -> None:
    """A re-declared namespace is UNSUPPORTED_SCHEMA with no occurrences or interpretations."""
    edit = MarkedEdit(
        label="namespace",
        find=f'xmlns:in-capmkt="{CAPMKT}"'.encode(),
        replace=b'xmlns:in-capmkt="http://www.sebi.gov.in/xbrl/2099-01-31/in-capmkt"',
    )
    report = ingest.run(
        ingest.intake(XBRL_ONLY, marked={Representation.XBRL: marked_xbrl(ingest.tmp_path, edit)})
    )
    (attempt,) = report.attempts
    assert attempt.outcome is ExtractionOutcome.UNSUPPORTED_SCHEMA
    counts = ingest.table_counts()
    assert counts["occurrences"] == counts["interpretations"] == 0


def _truncated_pdf(tmp_path: Path) -> Path:
    """The retained PDF's first 2 KiB: a header with no page tree."""
    target = tmp_path / "truncated-results.pdf"
    target.write_bytes(apar_original("FY26_Q2", "results").read_bytes()[:2048])
    return target


def _garbage_pdf(tmp_path: Path) -> Path:
    """Bytes that are not a PDF at all."""
    target = tmp_path / "garbage-results.pdf"
    target.write_bytes(b"this is not a portable document\n" * 64)
    return target


def _invalid_date_xbrl(tmp_path: Path) -> Path:
    """The XBRL with the period-end instant context dated 31 September."""
    edit = MarkedEdit(
        label="invalid-context-date",
        find=XBRL_OPENING_INSTANT,
        replace=XBRL_OPENING_INSTANT.replace(b"2025-09-30", b"2025-09-31"),
    )
    return marked_xbrl(tmp_path, edit)


@pytest.mark.parametrize(
    ("representation", "build"),
    [
        (Representation.XBRL, _invalid_date_xbrl),
        (Representation.PDF, _garbage_pdf),
        (Representation.PDF, _truncated_pdf),
    ],
    ids=["xbrl-invalid-context-date", "pdf-garbage", "pdf-truncated"],
)
def test_parser_failure_is_one_parse_failed_attempt(
    ingest: Ingest, representation: Representation, build: Callable[[Path], Path]
) -> None:
    """A member the parser cannot read records exactly one overall PARSE_FAILED attempt
    and no occurrences, instead of escaping the ingest as an exception.
    """
    path = build(ingest.tmp_path)
    members = XBRL_ONLY if representation is Representation.XBRL else PDF_ONLY
    report = ingest.run(ingest.intake(members, marked={representation: path}))
    (attempt,) = report.attempts
    assert attempt.stage is AttemptStage.EXTRACTION and attempt.statement_family is None
    assert attempt.outcome is ExtractionOutcome.PARSE_FAILED
    assert report.package_id is None
    assert ingest.table_counts()["occurrences"] == 0


def test_framework_must_be_declared_by_the_capture(ingest: Ingest) -> None:
    """The requested framework is verified against the capture's own declaration: where it
    is found is recorded; a capture declaring none is IDENTITY_REJECTED.
    """
    report = ingest.run(ingest.intake())
    xbrl = _overall(report.attempts, Representation.XBRL)
    pdf = _overall(report.attempts, Representation.PDF)
    assert xbrl.outcome is pdf.outcome is ExtractionOutcome.COMPLETE
    assert "DisclosureOfNotesOnFinancialResultsExplanatoryTextBlock" in (xbrl.reason or "")
    assert "page 5" in (pdf.reason or "")
    undeclared_xbrl = marked_xbrl(
        ingest.tmp_path,
        MarkedEdit(
            label="no-framework-declaration",
            find=XBRL_DECLARATION,
            replace=b"prepared under the standards notified",
        ),
    )
    undeclared_pdf = marked_pdf(
        ingest.tmp_path,
        "no-framework-declaration",
        PdfRedaction(page=5, row_of="Indian", words=("Indian",)),
    )
    marked = ingest.run(
        ingest.intake(
            marked={Representation.XBRL: undeclared_xbrl, Representation.PDF: undeclared_pdf}
        )
    )
    for representation in (Representation.XBRL, Representation.PDF):
        attempt = _overall(marked.attempts, representation)
        assert attempt.outcome is ExtractionOutcome.IDENTITY_REJECTED
    assert marked.package_id is None
