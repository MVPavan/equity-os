"""Exact stored-generation ids returned by first-party ingest (D1b Task 11)."""

from __future__ import annotations

import pytest
from evidence_support import Ingest, dictionary, ingest, mapping_set, policy

from fundamentals.contracts.evidence import InterpretationOrigin

__all__ = ["dictionary", "ingest", "mapping_set", "policy"]

pytestmark = [pytest.mark.pg, pytest.mark.retained]


def test_ingest_report_exposes_exact_generation_ids(ingest: Ingest) -> None:
    """A successful ingest reports the exact stored member generation it produced or reused."""
    report = ingest.run(ingest.intake())
    package = ingest.package(report)
    expected_members: list[dict[str, object]] = []

    for representation, member in sorted(package.members.items(), key=lambda item: item[0].value):
        capture_ref_id = member.capture.capture_ref_id
        assert capture_ref_id is not None
        stored_occurrences = ingest.repository.list_capture_occurrences(capture_ref_id)
        extractor_versions = {occurrence.extractor_version for occurrence in stored_occurrences}
        assert len(extractor_versions) == 1
        (extractor_version,) = extractor_versions
        occurrence_ids = {
            occurrence.occurrence_id
            for occurrence in stored_occurrences
            if occurrence.extractor_version == extractor_version
        }
        assert None not in occurrence_ids
        stored_occurrence_ids = {int(occurrence_id) for occurrence_id in occurrence_ids}
        generation = [
            row
            for row in ingest.repository.list_capture_interpretations(capture_ref_id)
            if row.mapping_set_version == ingest.mapping_set.version
            and row.normalisation_policy_version == ingest.policy.version
            and row.extractor_version == extractor_version
            and row.entity_id == ingest.entity_id
            and row.basis == package.basis
            and row.framework == package.framework
        ]
        direct_ids = {
            row.interpretation_id
            for row in generation
            if row.occurrence_id in stored_occurrence_ids
        }
        exact_generation_ids = {
            row.interpretation_id
            for row in generation
            if row.occurrence_id in stored_occurrence_ids
            or (
                row.origin is InterpretationOrigin.CONSTRUCTED
                and row.operand_interpretation_ids
                and set(row.operand_interpretation_ids) <= direct_ids
            )
        }
        assert None not in direct_ids
        assert None not in exact_generation_ids
        assert stored_occurrence_ids and exact_generation_ids
        expected_members.append(
            {
                "representation": representation.value,
                "source_id": member.capture.source_id,
                "surface": member.capture.surface,
                "capture_ref_id": capture_ref_id,
                "extractor_version": extractor_version,
                "occurrence_ids": sorted(stored_occurrence_ids),
                "interpretation_ids": sorted(int(row_id) for row_id in exact_generation_ids),
            }
        )

    assert report.model_dump(mode="json").get("members") == expected_members
