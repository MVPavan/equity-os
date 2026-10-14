"""Run-level proofs for selection and PDF generation boundaries from the phase review."""

import hashlib
from decimal import Decimal

import pytest
from evidence_support import (
    BOTH,
    PDF_KIND,
    Q2_END,
    Q2_QUARTER,
    XBRL_ONLY,
    apar_pdf_specs,
    dictionary,
    ingest,
    mapping_set,
    marked_xbrl,
    policy,
)
from retained_support import MarkedEdit
from run_support import Runner, row, runner

from fundamentals.compare.run import RunStatus
from fundamentals.compare.run_models import SourceValue
from fundamentals.contracts.acquisition_outcome import ExtractionOutcome
from fundamentals.contracts.canonical import Representation, StatementFamily
from fundamentals.contracts.comparison import SourceState
from fundamentals.contracts.evidence import InterpretationStatus, RevisionCause
from fundamentals.contracts.measurement_key import PeriodInterval

__all__ = ["dictionary", "ingest", "mapping_set", "policy", "runner"]
pytestmark = [pytest.mark.pg, pytest.mark.retained]


def _value(
    runner: Runner, run_id: int, canonical: str, period: PeriodInterval, rep: Representation
) -> SourceValue:
    (value,) = [
        value
        for value in row(runner.results(run_id), canonical, period).source_values
        if value.representation is rep
    ]
    return value


def test_run_sees_a_superseding_interpretation_that_moves_to_another_key(runner: Runner) -> None:
    """Supersession is resolved across the capture before filtering for one measurement."""
    report = runner.ingest.run(runner.ingest.intake(XBRL_ONLY))
    assert report.package_id is not None
    (package,) = runner.repository.get_packages([report.package_id])
    capture = package.members[Representation.XBRL].capture.capture_ref_id
    assert capture is not None
    (original,) = [
        item
        for item in runner.repository.list_capture_interpretations(capture)
        if item.key is not None
        and item.key.canonical_id == "revenue_from_operations"
        and item.key.period == Q2_QUARTER
        and not item.key.dimensions.pairs
    ]
    assert original.key is not None
    (replacement_id,) = runner.repository.reserve_interpretation_ids(1)
    replacement = original.model_copy(
        update={
            "interpretation_id": replacement_id,
            "canonical_id": "excise_duty",
            "key": original.key.model_copy(update={"canonical_id": "excise_duty"}),
            "input_digest": hashlib.sha256(b"test-revenue-key-correction").hexdigest(),
            "supersedes_interpretation_id": original.interpretation_id,
            "revision_cause": RevisionCause.MANUAL_CORRECTION,
        }
    )
    runner.repository.put_interpretations([replacement])
    record = runner.run()
    revenue = _value(
        runner, record.run_id, "revenue_from_operations", Q2_QUARTER, Representation.XBRL
    )
    assert revenue.state is SourceState.NO_VALUE
    corrected = _value(runner, record.run_id, "excise_duty", Q2_QUARTER, Representation.XBRL)
    assert corrected.state is SourceState.VALUE
    assert corrected.value == Decimal("57154200000")
    assert corrected.interpretation_id == replacement_id
    assert runner.replay(record.run_id) == runner.results(record.run_id)


def test_run_keeps_a_keyless_unit_refusal_invalid(runner: Runner) -> None:
    """An evidenced key prefix with an invalid currency remains INVALID in the run."""
    edit = MarkedEdit(
        label="run-iso4217-rebound",
        find=b'xmlns:iso4217="http://www.xbrl.org/2003/iso4217"',
        replace=b'xmlns:iso4217="http://example.com/not-iso4217"',
    )
    source = marked_xbrl(runner.ingest.tmp_path, edit)
    report = runner.ingest.run(runner.ingest.intake(BOTH, marked={Representation.XBRL: source}))
    assert any(
        item.canonical_id == "revenue_from_operations"
        and item.period == Q2_QUARTER
        and item.status is InterpretationStatus.INVALID
        and item.key is None
        for item in runner.ingest.interpretations(report)
    )
    record = runner.run()
    value = _value(
        runner, record.run_id, "revenue_from_operations", Q2_QUARTER, Representation.XBRL
    )
    assert value.state is SourceState.INVALID
    assert value.reason == "UNIT_MISMATCH"
    assert value.interpretation_id is not None
    assert runner.replay(record.run_id) == runner.results(record.run_id)


def test_run_emits_evidenced_dimensions_for_a_keyless_unit_refusal(runner: Runner) -> None:
    """A refused Conductors unit still identifies the disclosed segment measurement."""
    filed = b'<in-capmkt:SegmentRevenue contextRef="OneReportable1D" decimals="-5" unitRef="INR">'
    edit = MarkedEdit(
        label="run-conductors-per-share",
        find=filed,
        replace=filed.replace(b'unitRef="INR"', b'unitRef="INRPerShare"'),
    )
    source = marked_xbrl(runner.ingest.tmp_path, edit)
    runner.ingest.run(runner.ingest.intake(XBRL_ONLY, marked={Representation.XBRL: source}))
    record = runner.run()
    (result,) = [
        result
        for result in runner.results(record.run_id)
        if result.key.canonical_id == "segment_revenue"
        and result.key.period == Q2_QUARTER
        and dict(result.key.dimensions.pairs).get("segment") == "conductors"
    ]
    (value,) = [
        value for value in result.source_values if value.representation is Representation.XBRL
    ]
    assert value.state is SourceState.INVALID
    assert value.reason == "UNIT_MISMATCH"
    assert value.value is None
    assert runner.replay(record.run_id) == runner.results(record.run_id)


@pytest.mark.parametrize("reused", [False, True], ids=["fresh", "reused"])
def test_run_honors_late_package_owned_missing_family_failures(
    runner: Runner, reused: bool
) -> None:
    """Missing PDF families are unavailable even though COMPLETE has an earlier store time."""
    specs = apar_pdf_specs()
    narrow = {StatementFamily.PL: specs[StatementFamily.PL]}
    if reused:
        runner.ingest.run(runner.ingest.intake({Representation.PDF: PDF_KIND}), pdf_specs=narrow)
    report = runner.ingest.run(runner.ingest.intake(BOTH), pdf_specs=narrow)
    (complete,) = [
        attempt
        for attempt in report.attempts
        if attempt.representation is Representation.PDF and attempt.statement_family is None
    ]
    (failed,) = [
        attempt
        for attempt in report.attempts
        if attempt.representation is Representation.PDF
        and attempt.statement_family is StatementFamily.BALANCE_SHEET
        and attempt.outcome is ExtractionOutcome.PARSE_FAILED
    ]
    assert failed.package_id == report.package_id
    assert failed.attempted_at is not None and complete.attempted_at is not None
    assert failed.attempted_at > complete.attempted_at
    record = runner.run()
    value = _value(
        runner, record.run_id, "total_assets", PeriodInterval.at(Q2_END), Representation.PDF
    )
    assert value.state is SourceState.UNAVAILABLE
    assert value.attempt_id == failed.attempt_id
    assert record.manifest.status is RunStatus.INCOMPLETE
    assert runner.replay(record.run_id) == runner.results(record.run_id)


def test_run_refuses_pdf_values_from_incompatible_location_contexts(runner: Runner) -> None:
    """Wide then narrow extraction cannot resurrect the wide context's archived values."""
    specs = apar_pdf_specs()
    runner.ingest.run(runner.ingest.intake(BOTH), pdf_specs=specs)
    cutoff = runner.now()
    narrow = {StatementFamily.PL: specs[StatementFamily.PL]}
    runner.ingest.run(runner.ingest.intake(BOTH), pdf_specs=narrow)
    record = runner.run()
    for canonical, period in (
        ("total_assets", PeriodInterval.at(Q2_END)),
        ("revenue_from_operations", Q2_QUARTER),
    ):
        value = _value(runner, record.run_id, canonical, period, Representation.PDF)
        assert value.state is SourceState.UNAVAILABLE
        assert value.value is None and value.interpretation_id is None
        assert value.reason == "INCOMPATIBLE_EXTRACTION_CONTEXTS"
    assert record.manifest.status is RunStatus.INCOMPLETE
    assert any(
        "INCOMPATIBLE_EXTRACTION_CONTEXTS" in item for item in record.manifest.operational_failures
    )
    assert runner.replay(record.run_id) == runner.results(record.run_id)
    historical = runner.run(cutoff=cutoff)
    prior = _value(
        runner, historical.run_id, "total_assets", PeriodInterval.at(Q2_END), Representation.PDF
    )
    assert prior.state is SourceState.VALUE


def test_run_routes_ambiguous_pdf_owner_candidates_to_invalid(runner: Runner) -> None:
    """Unknown ownership keeps the profit owners row INVALID; the section-scoped OCI row stands."""
    report = runner.ingest.run(runner.ingest.intake(BOTH))
    assert any(
        item.canonical_id == "oci_attributable_owners"
        and item.period == Q2_QUARTER
        and item.status is InterpretationStatus.MAPPED
        and item.value == Decimal("229500000")
        for item in runner.ingest.interpretations(report)
    )
    record = runner.run()
    owners = _value(
        runner, record.run_id, "profit_attributable_owners", Q2_QUARTER, Representation.PDF
    )
    assert owners.state is SourceState.INVALID
    assert owners.reason == "INTERPRETATION_AMBIGUOUS"
    assert owners.value is None
    oci = _value(runner, record.run_id, "oci_attributable_owners", Q2_QUARTER, Representation.PDF)
    # Its section heading is established, so the unestablished owners line never displaces it
    # (stage1_manifest: oci_attributable_owners PDF VALUE 22.95).
    assert oci.state is SourceState.VALUE
    assert oci.value == Decimal("229500000")
    assert runner.replay(record.run_id) == runner.results(record.run_id)
