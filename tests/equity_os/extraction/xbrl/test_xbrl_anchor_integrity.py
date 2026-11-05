"""Duplicate native anchors may never silently collapse differing filed facts."""

import re
from datetime import UTC, datetime

import pytest
from evidence_support import XBRL_ONLY, Ingest, dictionary, ingest, mapping_set, marked_xbrl, policy
from retained_support import MarkedEdit, apar_original

from equity_os.contracts.measurement.canonical import Representation
from equity_os.contracts.measurement.evidence import (
    CaptureReference,
    KnowledgeTimeStatus,
    PackageMember,
)
from equity_os.contracts.sourcing.acquisition_outcome import ExtractionOutcome
from equity_os.extraction.xbrl.xbrl_adapter import occurrences_from_instance, parse_instance
from equity_os.extraction.xbrl.xbrl_parser import XbrlParseError
from equity_os.normalisation.mapping.mapping import MappingSet
from equity_os.storage.records.repository import OccurrenceConflictError

__all__ = ["dictionary", "mapping_set", "ingest", "policy"]
pytestmark = pytest.mark.retained


def _duplicate(mapping_set: MappingSet, *, differing: bool) -> tuple[object, ...]:
    instance = parse_instance(
        apar_original("FY26_Q2", "xbrl-consolidated").read_bytes(), mapping_set=mapping_set
    )
    fact = next(
        item for item in instance.facts if item.is_numeric and item.raw_text == "57154200000"
    )
    first = fact.model_copy(update={"fact_id": "duplicated"})
    second = first.model_copy(
        update={
            "document_order": first.document_order + 1,
            "raw_text": "1" if differing else first.raw_text,
        }
    )
    capture = CaptureReference(
        capture_ref_id=1,
        source_id="nse-indas-xbrl-consolidated",
        surface="NSE_XBRL_INSTANCE",
        request_key="held",
        capture_id="held",
        blob_sha256="a" * 64,
        record_sha256="b" * 64,
        registered_at=datetime.now(UTC),
        first_seen_at=datetime.now(UTC),
    )
    member = PackageMember(
        representation=Representation.XBRL,
        capture=capture,
        knowledge_time=datetime.now(UTC),
        knowledge_time_raw="held",
        knowledge_time_status=KnowledgeTimeStatus.KNOWN,
    )
    return occurrences_from_instance(
        instance.model_copy(update={"facts": (first, second)}),
        capture=capture,
        member=member,
        mapping_set=mapping_set,
    )


def test_differing_duplicate_fact_anchor_is_refused(mapping_set: MappingSet) -> None:
    with pytest.raises(XbrlParseError, match="duplicate"):
        _duplicate(mapping_set, differing=True)


def test_identical_duplicate_fact_anchor_is_emitted_once(mapping_set: MappingSet) -> None:
    assert len(_duplicate(mapping_set, differing=False)) == 1


@pytest.mark.pg
def test_duplicate_anchor_records_one_parse_failed_attempt(ingest: Ingest) -> None:
    body = apar_original("FY26_Q2", "xbrl-consolidated").read_bytes()
    matched = re.search(
        rb'<in-capmkt:RevenueFromOperations\b[^>]*contextRef="OneD"[^>]*>[^<]*</in-capmkt:RevenueFromOperations>',
        body,
    )
    assert matched is not None
    original = matched.group()
    anchored = original.replace(
        b"RevenueFromOperations ", b'RevenueFromOperations id="duplicate" ', 1
    )
    changed = re.sub(rb">[^<]*</", b">1</", anchored)
    marked = marked_xbrl(
        ingest.tmp_path,
        MarkedEdit(label="duplicate-fact-id", find=original, replace=anchored + changed),
    )
    report = ingest.run(ingest.intake(XBRL_ONLY, marked={Representation.XBRL: marked}))
    assert report.package_id is None and report.occurrence_count == 0
    assert (
        len(report.attempts) == 1 and report.attempts[0].outcome is ExtractionOutcome.PARSE_FAILED
    )
    assert "duplicate XBRL anchor" in (report.attempts[0].reason or "")


@pytest.mark.pg
def test_stored_occurrence_reuse_requires_the_entire_payload(ingest: Ingest) -> None:
    report = ingest.run(ingest.intake(XBRL_ONLY))
    occurrences = ingest.repository.list_capture_occurrences(
        ingest.capture_id(report, Representation.XBRL)
    )
    original = next(item for item in occurrences if item.raw_value_text == "57154200000")
    before = ingest.table_counts()
    assert ingest.repository.put_occurrences(
        (original.model_copy(update={"occurrence_id": None}),)
    ) == (original,)
    drifted = original.model_copy(update={"occurrence_id": None, "disclosure": {"different": True}})
    with pytest.raises(OccurrenceConflictError):
        ingest.repository.put_occurrences((drifted,))
    assert ingest.table_counts() == before
