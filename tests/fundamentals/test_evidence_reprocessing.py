"""Re-processing, re-ingest, shared members and version pins (D1a Task 5).

Stored rows never change: a new extractor or mapping set appends rows under its own triple,
a by-id read returns exactly what it returned before, and a version whose content changed
is refused before anything is written.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import pytest
from evidence_support import (
    PDF_KIND,
    Q2_FY26,
    XBRL_ONLY,
    Ingest,
    dictionary,
    entry_of,
    ingest,
    mapping_set,
    policy,
    replace_entry,
    rows_of,
    temp_mapping,
)
from retained_support import MarkedEdit, apar_original, marked_copy

from fundamentals.canon.dictionary import CanonicalDictionary
from fundamentals.contracts.canonical import Representation
from fundamentals.contracts.evidence import RevisionCause
from fundamentals.contracts.measurement_key import PeriodInterval
from fundamentals.contracts.versioning import VersionContentDriftError
from fundamentals.evidence.first_party_ingest import MAPPING_SET_ARTIFACT
from fundamentals.evidence.mapping import MappingSet

__all__ = ["dictionary", "ingest", "mapping_set", "policy"]

pytestmark = [pytest.mark.pg, pytest.mark.retained]

REEXTRACT = "xbrl-occurrences/test-reextract"
REMAP = "v1-test-remap"


def _remapped(ingest: Ingest, dictionary: CanonicalDictionary) -> MappingSet:
    """Mapping set v1 with one evidence note changed, under its own version."""

    def changed(data: dict[str, Any]) -> None:
        entry = entry_of(data, "capmkt.revenue_from_operations")
        entry["evidence_ref"] = entry["evidence_ref"] + " (re-mapped)"
        replace_entry(data, "capmkt.revenue_from_operations", entry)

    return temp_mapping(ingest.tmp_path, dictionary, changed, version=REMAP)


def test_reprocessing_appends_and_never_rewrites(
    ingest: Ingest, dictionary: CanonicalDictionary
) -> None:
    """A new extractor and mapping set add rows under the new triple; v1 rows stand."""
    first = ingest.run(ingest.intake())
    v1_rows = ingest.interpretations(first)
    v1_ids = [row.interpretation_id for row in v1_rows if row.interpretation_id is not None]
    captures_before = ingest.table_counts()["capture_refs"]
    second = ingest.run(
        ingest.intake(),
        mapping_set=_remapped(ingest, dictionary),
        extractor_versions={Representation.XBRL: REEXTRACT},
    )
    assert ingest.table_counts()["capture_refs"] == captures_before
    assert ingest.repository.get_interpretations(v1_ids) == tuple(
        sorted(v1_rows, key=lambda row: row.interpretation_id or 0)
    )
    xbrl_capture = ingest.capture_id(second, Representation.XBRL)
    new_occurrences = ingest.repository.list_capture_occurrences(xbrl_capture, REEXTRACT)
    assert new_occurrences
    assert {item.revision_cause for item in new_occurrences} == {RevisionCause.PARSER_REEXTRACTION}
    new_rows = [
        row
        for row in ingest.repository.list_capture_interpretations(xbrl_capture)
        if row.mapping_set_version == REMAP
    ]
    assert min(row.recorded_at for row in new_rows) > max(row.recorded_at for row in v1_rows)
    opening = PeriodInterval.at(date(2025, 3, 31))
    (old,) = rows_of(v1_rows, "cf_cash_closing", opening, Representation.XBRL)
    (new,) = rows_of(new_rows, "cf_cash_closing", opening, Representation.XBRL)
    assert new.revision_cause is RevisionCause.PARSER_REEXTRACTION
    assert new.supersedes_interpretation_id == old.interpretation_id
    pdf_rows = [
        row
        for row in ingest.repository.list_capture_interpretations(
            ingest.capture_id(second, Representation.PDF)
        )
        if row.mapping_set_version == REMAP
    ]
    # Same PDF extractor and policy: a mapping-set-only change is ORIGINAL under its triple.
    assert pdf_rows and {row.revision_cause for row in pdf_rows} == {RevisionCause.ORIGINAL}


def test_reprocessing_never_changes_a_by_id_read(
    ingest: Ingest, dictionary: CanonicalDictionary
) -> None:
    """Re-extraction reuses the package and segment members; their statement and member
    evidence read by id — and as of the first ingest — is exactly what it was.
    """
    first = ingest.run(ingest.intake())
    assert first.package_id is not None
    statements = ingest.repository.get_package_statements_of([first.package_id])
    statement_ids = [record.id for record in statements]
    cutoff = ingest.repository.store_clock()
    members = ingest.repository.segment_members_as_of(ingest.entity_id, "segment", cutoff)
    member_ids = [member.id for member in members]
    assert statement_ids and member_ids
    second = ingest.run(
        ingest.intake(),
        mapping_set=_remapped(ingest, dictionary),
        extractor_versions={Representation.XBRL: REEXTRACT},
    )
    assert second.package_id == first.package_id
    xbrl_capture = ingest.capture_id(second, Representation.XBRL)
    assert ingest.repository.list_capture_occurrences(xbrl_capture, REEXTRACT)
    assert ingest.repository.get_package_statements(statement_ids) == tuple(
        sorted(statements, key=lambda record: record.id)
    )
    assert ingest.repository.get_segment_members(member_ids) == tuple(
        sorted(members, key=lambda member: member.id)
    )
    assert ingest.repository.segment_members_as_of(ingest.entity_id, "segment", cutoff) == members


def test_changed_content_under_a_pinned_version_is_refused(
    ingest: Ingest, dictionary: CanonicalDictionary
) -> None:
    """A mapping sign changed under the pinned ``v1`` raises drift and writes nothing."""
    ingest.run(ingest.intake(XBRL_ONLY))
    before = ingest.table_counts()
    assert before["version_pins"] == 2

    def flipped(data: dict[str, Any]) -> None:
        entry = entry_of(data, "capmkt.current_tax")
        replace_entry(data, "capmkt.current_tax", {**entry, "sign": -1})

    drifted = temp_mapping(ingest.tmp_path, dictionary, flipped)
    assert drifted.version == ingest.mapping_set.version
    with pytest.raises(VersionContentDriftError) as raised:
        ingest.run(ingest.intake(XBRL_ONLY), mapping_set=drifted)
    assert raised.value.artifact == MAPPING_SET_ARTIFACT
    assert ingest.table_counts() == before


def test_reingest_writes_nothing(ingest: Ingest) -> None:
    """Every write is idempotent and every generation reused: no table grows."""
    first = ingest.run(ingest.intake())
    before = ingest.table_counts()
    second = ingest.run(ingest.intake())
    assert ingest.table_counts() == before
    assert second.package_id == first.package_id
    assert [a.attempt_id for a in second.attempts] == [a.attempt_id for a in first.attempts]


def test_revision_package_shares_the_unchanged_member(ingest: Ingest) -> None:
    """A revised PDF adds a package and PDF rows; the XBRL member's rows are reused."""
    first = ingest.run(ingest.intake())
    before = ingest.table_counts()
    xbrl_capture = ingest.capture_id(first, Representation.XBRL)
    xbrl_occurrences = len(ingest.repository.list_capture_occurrences(xbrl_capture))
    xbrl_rows = len(ingest.repository.list_capture_interpretations(xbrl_capture))
    revised_pdf = marked_copy(
        apar_original(Q2_FY26, PDF_KIND),
        edit=MarkedEdit(label="revised", find=b"", replace=b"\n%marked revision\n"),
        tmp_path=ingest.tmp_path,
    )
    revision = ingest.run(
        ingest.intake(marked={Representation.PDF: revised_pdf}),
        supersedes_package_id=first.package_id,
    )
    after = ingest.table_counts()
    assert revision.package_id != first.package_id
    assert after["filing_packages"] == before["filing_packages"] + 1
    assert after["capture_refs"] == before["capture_refs"] + 1
    assert ingest.capture_id(revision, Representation.XBRL) == xbrl_capture
    assert len(ingest.repository.list_capture_occurrences(xbrl_capture)) == xbrl_occurrences
    assert len(ingest.repository.list_capture_interpretations(xbrl_capture)) == xbrl_rows
    new_attempts = {a.attempt_id for a in revision.attempts} - {
        a.attempt_id for a in first.attempts
    }
    assert all(
        attempt.representation is Representation.PDF
        for attempt in ingest.repository.get_attempts(sorted(i for i in new_attempts if i))
    )
    revised = ingest.capture_id(revision, Representation.PDF)
    assert ingest.repository.list_capture_interpretations(revised)
