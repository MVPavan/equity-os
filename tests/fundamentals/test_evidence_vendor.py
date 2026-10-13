"""Missing retained inputs cannot impersonate vendor publication or numeric evidence."""

from __future__ import annotations

import importlib
from datetime import date
from pathlib import Path

import pytest

from fundamentals.contracts.acquisition_outcome import ExtractionOutcome, outcome_source_state
from fundamentals.contracts.canonical import Basis, Representation, StatementFamily
from fundamentals.contracts.comparison import SourceState
from fundamentals.contracts.evidence import VendorExtractorPin, VersionPin
from fundamentals.contracts.measurement_key import PeriodInterval
from fundamentals.contracts.observation import AccountingFramework
from fundamentals.contracts.source_catalog import (
    EvidenceRole,
    SourceCatalog,
    SourceClass,
    SourceDescriptor,
    SurfaceAuthority,
)
from fundamentals.evidence.vendor_common import VendorRequest


@pytest.mark.parametrize("vendor", ["tijori", "upstox"])
def test_missing_vendor_input_keeps_exact_request_and_never_claims_publication_absence(
    vendor: str,
) -> None:
    """These constructed authorization inputs test the boundary, not vendor qualification."""
    module = importlib.import_module(f"fundamentals.evidence.vendor_{vendor}")
    representation = Representation.HTML if vendor == "tijori" else Representation.JSON
    surface = "TIJORI_FINANCIALS" if vendor == "tijori" else "income-statement"
    role = EvidenceRole.RECONCILABLE if vendor == "tijori" else EvidenceRole.DIAGNOSTIC_ONLY
    request = VendorRequest(
        source_id=vendor,
        surface=surface,
        representation=representation,
        schema_identity=f"constructed-{vendor}-unavailable",
        entity_id=7,
        period=PeriodInterval.duration(date(2024, 10, 1), date(2024, 12, 31)),
        basis=Basis.CONSOLIDATED,
        framework=AccountingFramework.IND_AS,
        statement_family=StatementFamily.PL,
    )
    catalog = SourceCatalog.of(
        SourceDescriptor(source_id=vendor, source_class=SourceClass.DERIVED, evidence_role=role)
    )
    authority = SurfaceAuthority(
        source_id=vendor,
        surface=surface,
        representation=representation,
        evidence_role=role,
        authority_ref="constructed boundary test authority",
        authority_sha256="a" * 64,
    )
    pin = VendorExtractorPin(
        source_id=vendor, surface=surface, version="draft-test", content_sha256="b" * 64
    )
    generation = module.prepare_unavailable(
        request,
        catalog=catalog,
        authority=authority,
        extractor_pin=pin,
        authority_pin=VersionPin(version="draft-test", content_sha256="c" * 64),
    )
    assert generation.request == request
    assert (
        generation.capture is None and not generation.occurrences and not generation.interpretations
    )
    assert generation.published_config_sha256 is None
    (attempt,) = generation.attempts
    assert (
        attempt.source_id,
        attempt.surface,
        attempt.entity_id,
        attempt.period_end,
        attempt.basis,
    ) == (vendor, surface, 7, date(2024, 12, 31), Basis.CONSOLIDATED)
    assert attempt.framework is request.framework
    assert attempt.statement_family is StatementFamily.PL
    assert attempt.package_id is None and attempt.capture is None
    assert attempt.outcome is ExtractionOutcome.FAILED
    assert outcome_source_state(attempt.outcome) is SourceState.UNAVAILABLE
    assert attempt.input_sha256 == request.identity_sha256()
    assert attempt.attempted_at is None, "the store supplies the actual timestamp on persistence"
    refused = module.prepare_unavailable(
        request,
        catalog=SourceCatalog.of(),
        authority=authority,
        extractor_pin=pin,
        authority_pin=VersionPin(version="draft-test", content_sha256="c" * 64),
    )
    assert refused.attempts[0].outcome is ExtractionOutcome.NOT_AUTHORISED
    assert not refused.occurrences and refused.capture is None
    wrong_source = request.model_copy(update={"source_id": "first-party-looking-undeclared"})
    with pytest.raises(ValueError):
        module.prepare_unavailable(
            wrong_source,
            catalog=catalog,
            authority=authority,
            extractor_pin=pin,
            authority_pin=VersionPin(version="draft-test", content_sha256="c" * 64),
        )
    present = request.model_copy(
        update={
            "retained": {
                "relative_path": Path("constructed-response"),
                "expected_sha256": "d" * 64,
            }
        }
    )
    with pytest.raises(ValueError):
        module.prepare_unavailable(
            present,
            catalog=catalog,
            authority=authority,
            extractor_pin=pin,
            authority_pin=VersionPin(version="draft-test", content_sha256="c" * 64),
        )
