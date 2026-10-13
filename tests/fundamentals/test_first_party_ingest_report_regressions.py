"""Compatibility and branch coverage for first-party ingest generation reports."""

from __future__ import annotations

import pytest
from evidence_support import XBRL_ONLY, Ingest, dictionary, ingest, mapping_set, policy

from fundamentals.contracts.acquisition_outcome import ExtractionOutcome
from fundamentals.contracts.canonical import Representation
from fundamentals.contracts.evidence import AttemptStage
from fundamentals.contracts.source_catalog import BUILTIN_SOURCES
from fundamentals.evidence.first_party_ingest import (
    DEFAULT_EXTRACTOR_VERSIONS,
    IngestReport,
)

__all__ = ["dictionary", "ingest", "mapping_set", "policy"]

pytestmark = [pytest.mark.pg, pytest.mark.retained]

OVERRIDE_XBRL_EXTRACTOR = "xbrl-occurrences/task11-report-override"


def test_legacy_ingest_report_payload_and_constructor_default_members() -> None:
    """The additive member closure does not break the exported legacy report shape."""
    payload = {
        "package_id": None,
        "occurrence_count": 0,
        "interpretation_counts": {},
        "attempts": (),
    }

    direct = IngestReport(**payload)
    validated = IngestReport.model_validate(payload)

    assert direct.members == validated.members == ()
    assert direct.model_dump(mode="json") == {
        **payload,
        "attempts": [],
    }
    assert validated.model_dump(mode="json") == direct.model_dump(mode="json")


def test_reingest_reports_identical_generation_ids(ingest: Ingest) -> None:
    """An unchanged second ingest reports the same exact member generations and adds no rows."""
    first = ingest.run(ingest.intake())
    before = ingest.table_counts()

    second = ingest.run(ingest.intake())

    assert second.members == first.members
    assert [attempt.attempt_id for attempt in second.attempts] == [
        attempt.attempt_id for attempt in first.attempts
    ]
    assert ingest.table_counts() == before


def test_extractor_override_is_reported_from_actual_generation(ingest: Ingest) -> None:
    """A non-default extractor reports only its own stored occurrence and interpretation ids."""
    report = ingest.run(
        ingest.intake(XBRL_ONLY),
        extractor_versions={Representation.XBRL: OVERRIDE_XBRL_EXTRACTOR},
    )

    (member,) = report.members
    assert member.representation is Representation.XBRL
    assert member.extractor_version == OVERRIDE_XBRL_EXTRACTOR
    assert member.extractor_version != DEFAULT_EXTRACTOR_VERSIONS[Representation.XBRL]
    occurrences = ingest.repository.get_occurrences(member.occurrence_ids)
    interpretations = ingest.repository.get_interpretations(member.interpretation_ids)
    assert occurrences and interpretations
    assert all(
        occurrence.capture.capture_ref_id == member.capture_ref_id for occurrence in occurrences
    )
    assert all(occurrence.capture.source_id == member.source_id for occurrence in occurrences)
    assert all(occurrence.capture.surface == member.surface for occurrence in occurrences)
    assert {occurrence.extractor_version for occurrence in occurrences} == {OVERRIDE_XBRL_EXTRACTOR}
    assert all(row.capture_ref_id == member.capture_ref_id for row in interpretations)
    assert {row.extractor_version for row in interpretations} == {OVERRIDE_XBRL_EXTRACTOR}
    assert not ingest.repository.list_capture_occurrences(
        member.capture_ref_id, DEFAULT_EXTRACTOR_VERSIONS[Representation.XBRL]
    )


def test_unauthorised_member_has_attempt_but_no_generation(ingest: Ingest) -> None:
    """A refused PDF contributes its stored attempt while only the complete XBRL is reported."""
    report = ingest.run(ingest.intake(), catalog=BUILTIN_SOURCES)

    (member,) = report.members
    assert member.representation is Representation.XBRL
    refused = [
        attempt for attempt in report.attempts if attempt.representation is Representation.PDF
    ]
    assert len(refused) == 1
    assert refused[0].outcome is ExtractionOutcome.NOT_AUTHORISED
    assert refused[0].stage is AttemptStage.ACQUISITION
    assert refused[0].capture is None
    assert refused[0].attempt_id is not None
    package = ingest.package(report)
    assert set(package.members) == {Representation.XBRL}
    assert member.capture_ref_id == package.members[Representation.XBRL].capture.capture_ref_id
    assert ingest.table_counts()["capture_refs"] == 1
