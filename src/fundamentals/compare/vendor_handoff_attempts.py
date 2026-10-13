"""Stage-aware, source-bound first-party attempt closure for vendor runs.

Failed captured peers need not be successful package members. Preflight compares
the complete immutable source/request/input/context set, without choosing a
latest attempt; replay still reads only the returned manifest identities.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

from fundamentals.api.config import FundamentalsConfig
from fundamentals.compare.run_config import LoadedConfig
from fundamentals.contracts.acquisition_outcome import ExtractionOutcome
from fundamentals.contracts.canonical import Representation
from fundamentals.contracts.evidence import AcquisitionAttempt, AttemptStage, CaptureReference
from fundamentals.contracts.snapshot import canonical_sha256
from fundamentals.contracts.source_catalog import SourceClass
from fundamentals.evidence.capture_intake import NSE_XBRL_SOURCE_ID, SURFACE_OF
from fundamentals.evidence.first_party_context import FirstPartyGenerationContext
from fundamentals.evidence.first_party_extract import (
    pdf_statement_specs_sha256,
    unsupported_schema_context,
)
from fundamentals.evidence.first_party_generation import FirstPartyGenerationHandoff
from fundamentals.evidence.repository import EvidenceRepository
from fundamentals.evidence.vendor_config_files import read_safe
from fundamentals.extract.pdf_statement_pages import specs_from_config

_SYMBOL = re.compile(r"^[A-Z0-9][A-Z0-9_-]*$")
_HASH = re.compile(r"^[0-9a-f]{64}$")
_ACQUISITION_FAILURES = frozenset({ExtractionOutcome.NOT_AUTHORISED, ExtractionOutcome.FAILED})


class FirstPartyAttemptError(ValueError):
    """Attempt scope, source, input, stage or completeness cannot be proven."""


@dataclass(frozen=True)
class _Source:
    source_id: str
    surface: str
    blob_sha256: str | None
    extractor_version: str
    extraction_context_sha256: str | None


def validate_handoff_attempts(
    handoff: FirstPartyGenerationHandoff,
    attempts: tuple[AcquisitionAttempt, ...],
    *,
    context: FirstPartyGenerationContext,
    config: LoadedConfig,
    config_root: Path,
    repository: EvidenceRepository,
) -> tuple[CaptureReference, ...]:
    """Close all attempts and return every actual deciding capture, including failed peers."""
    sources = _sources(handoff, context, config, config_root, repository)
    package_captures = {member.capture_ref_id for member in handoff.members}
    capture_free = {row.attempt_id for row in attempts if row.capture is None}
    if len(handoff.capture_free_attempt_ids) != len(capture_free) or capture_free != set(
        handoff.capture_free_attempt_ids
    ):
        raise FirstPartyAttemptError("capture-free attempt ids differ from the exact stored subset")
    member_ids = {item for member in handoff.members for item in member.attempt_ids}
    peer_ids = {
        row.attempt_id
        for row in attempts
        if row.capture is not None and row.capture.capture_ref_id not in package_captures
    }
    if set(handoff.attempt_ids) != member_ids | capture_free | peer_ids:
        raise FirstPartyAttemptError("closed attempt ids omit or duplicate a deciding source")
    for row in attempts:
        source = sources.get(row.representation)
        if source is None or not _matches(row, handoff, source):
            raise FirstPartyAttemptError("attempt source/input/scope/stage/context differs")
        if row.attempted_at is None:
            raise FirstPartyAttemptError("attempt has no stored database time")
        if row.capture is not None and row.capture.capture_ref_id not in package_captures:
            if (
                row.stage is not AttemptStage.EXTRACTION
                or row.outcome is ExtractionOutcome.COMPLETE
            ):
                raise FirstPartyAttemptError(
                    "a captured peer outside package members must be failed"
                )

    # Scope equality, never a recency choice. Source-derived input/context excludes
    # earlier/later attempts from another parser specification or physical PDF.
    complete = tuple(
        row
        for row in repository.list_attempts(handoff.entity_id, handoff.reporting_period_end)
        if row.representation in sources and _matches(row, handoff, sources[row.representation])
    )
    wanted = {row.attempt_id for row in attempts}
    if wanted != {row.attempt_id for row in complete}:
        raise FirstPartyAttemptError("complete source/input/context attempt ids differ")

    captures = _captures(attempts, repository)
    for capture in captures:
        owned = tuple(
            row
            for row in attempts
            if row.capture is not None and row.capture.capture_ref_id == capture.capture_ref_id
        )
        overall = tuple(
            row
            for row in owned
            if row.stage is AttemptStage.EXTRACTION
            and row.package_id is None
            and row.statement_family is None
        )
        if len(overall) != 1:
            raise FirstPartyAttemptError("captured source requires one exact overall extraction")
        expected = (
            ExtractionOutcome.COMPLETE
            if capture.capture_ref_id in package_captures
            else overall[0].outcome
        )
        if overall[0].outcome is not expected or (
            capture.capture_ref_id not in package_captures
            and expected is ExtractionOutcome.COMPLETE
        ):
            raise FirstPartyAttemptError(
                "overall extraction contradicts package member disposition"
            )
    return captures


def _sources(
    handoff: FirstPartyGenerationHandoff,
    context: FirstPartyGenerationContext,
    config: LoadedConfig,
    config_root: Path,
    repository: EvidenceRepository,
) -> dict[Representation, _Source]:
    symbol = repository.issuer_identifiers(handoff.entity_id).nse_symbol
    if not _SYMBOL.fullmatch(symbol):
        raise FirstPartyAttemptError("issuer has no safe source-configuration convention")
    end = handoff.reporting_period_end
    year = end.year + (end.month > context.fiscal_year_end_month)
    quarter = ((end.month - context.fiscal_year_end_month - 1) % 12) // 3 + 1
    name = f"{symbol.lower()}-fy{year % 100:02d}-q{quarter}.yaml"
    issuer = FundamentalsConfig.model_validate(yaml.safe_load(read_safe(config_root, name)))
    if (issuer.issuer.nse_symbol, issuer.quarter.period_end, issuer.xbrl.symbol) != (
        symbol,
        end,
        symbol,
    ):
        raise FirstPartyAttemptError("source configuration differs from verified issuer/period")
    if issuer.xbrl.source_id != NSE_XBRL_SOURCE_ID:
        raise FirstPartyAttemptError(
            "source configuration does not declare the authorized NSE source"
        )
    assert config.vendor_config is not None
    xbrl_source = config.vendor_config.catalog.describe(issuer.xbrl.source_id)
    if xbrl_source.source_class is not SourceClass.FIRST_PARTY or not xbrl_source.may_reconcile:
        raise FirstPartyAttemptError("configured XBRL source lacks first-party authority")
    xbrl_member = next(
        (member for member in handoff.members if member.representation is Representation.XBRL), None
    )
    if xbrl_member is None:
        raise FirstPartyAttemptError(
            "XBRL physical binding is unproven; accepted retained-intake witness required"
        )
    result = {
        Representation.XBRL: _Source(
            issuer.xbrl.source_id,
            SURFACE_OF[Representation.XBRL].value,
            xbrl_member.blob_sha256,
            config.pinned.extractor_xbrl.version,
            None,
        )
    }
    if issuer.results_pdf.source_class is not SourceClass.FIRST_PARTY:
        raise FirstPartyAttemptError("configured PDF source lacks first-party authority")
    result[Representation.PDF] = _Source(
        issuer.results_pdf.source_id,
        SURFACE_OF[Representation.PDF].value,
        issuer.results_pdf.sha256,
        config.pinned.extractor_pdf.version,
        pdf_statement_specs_sha256(specs_from_config(issuer.pdf_parse)),
    )
    return result


def _matches(
    row: AcquisitionAttempt, handoff: FirstPartyGenerationHandoff, source: _Source
) -> bool:
    if (row.entity_id, row.period_end, row.basis, row.framework, row.source_id, row.surface) != (
        handoff.entity_id,
        handoff.reporting_period_end,
        handoff.basis,
        handoff.framework,
        source.source_id,
        source.surface,
    ) or row.package_id not in (None, handoff.package_id):
        return False
    if not _HASH.fullmatch(row.input_sha256):
        return False
    if source.blob_sha256 is None or row.input_sha256 != source.blob_sha256:
        return False
    if row.stage is AttemptStage.ACQUISITION:
        # This is the immutable first-party acquisition contract, not vendor
        # pinned acquisition: no body, extractor, family or extraction context.
        return (
            row.capture is None
            and row.extractor_version == ""
            and row.extraction_context_sha256 is None
            and row.statement_family is None
            and row.package_id == handoff.package_id
            and row.outcome in _ACQUISITION_FAILURES
            and source.blob_sha256 is not None
        )
    if row.stage is not AttemptStage.EXTRACTION or row.capture is None:
        return False
    if row.extractor_version != source.extractor_version:
        return False
    if (row.capture.source_id, row.capture.surface, row.capture.blob_sha256) != (
        row.source_id,
        row.surface,
        row.input_sha256,
    ):
        return False
    if row.capture.request_key != canonical_sha256(
        {
            "representation": row.representation.value,
            "sha256": row.input_sha256,
        }
    ):
        return False
    expected_context = (
        unsupported_schema_context(handoff.mapping_set_pin.version)
        if row.representation is Representation.XBRL
        and row.outcome is ExtractionOutcome.UNSUPPORTED_SCHEMA
        else source.extraction_context_sha256
    )
    return row.extraction_context_sha256 == expected_context


def _captures(
    attempts: tuple[AcquisitionAttempt, ...], repository: EvidenceRepository
) -> tuple[CaptureReference, ...]:
    ids = sorted(
        {
            row.capture.capture_ref_id
            for row in attempts
            if row.capture is not None and row.capture.capture_ref_id is not None
        }
    )
    found = repository.get_capture_refs(ids)
    if [row.capture_ref_id for row in found] != ids:
        raise FirstPartyAttemptError("deciding capture ids do not reload exactly")
    by_id = {row.capture_ref_id: row for row in found}
    for row in attempts:
        if row.capture is not None and by_id.get(row.capture.capture_ref_id) != row.capture:
            raise FirstPartyAttemptError("deciding attempt capture identity differs by id")
    return found
