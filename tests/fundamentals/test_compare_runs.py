"""Runs, manifests, replay and the report CLI over retained Apar originals (D1a Task 9).

Every case runs in its own ``eqos_test_*`` database. Expected values come from the retained
filings (Apar Q2 FY26 revenue from operations 5,715.42 crore in both representations) and
from the run rules; altered inputs are marked copies under ``tmp_path``.
"""

from __future__ import annotations

import threading
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from derived_support import SEGMENT_TOTAL, SEGMENTS, WITHHELD_OTHERS
from evidence_support import (
    BOTH,
    PDF_KIND,
    Q2_QUARTER,
    XBRL_KIND,
    XBRL_ONLY,
    apar_pdf_specs,
    dictionary,
    ingest,
    mapping_set,
    marked_xbrl,
    policy,
)
from psycopg import errors
from retained_support import MarkedEdit, PdfRedaction, apar_original, marked_copy, marked_pdf
from run_support import (
    FY25_Q2_END,
    Q2_END,
    Q2_FY25,
    Q3_END,
    Q3_FY26,
    Q4_END,
    Q4_FY26,
    Runner,
    SpyReader,
    config_copy,
    edit_yaml,
    enum_round_trip,
    failed_pdf_staging,
    forbid_current_reads,
    quarter,
    reseed_basis_status,
    row,
    runner,
)

from fundamentals.api.cli import main
from fundamentals.canon.dictionary import DictionaryRow
from fundamentals.compare.engine_attempts import RunResolutionError
from fundamentals.compare.run import ResultRow, RunStatus, SourceValue, VersionContentDriftError
from fundamentals.compare.run_config import ConfigVersions, extractor_pin
from fundamentals.compare.run_store import STAGE_RESULTS
from fundamentals.contracts.acquisition_outcome import ExtractionOutcome
from fundamentals.contracts.canonical import (
    ApplicabilityStatus,
    Basis,
    Representation,
    StatementFamily,
    ValueIdentity,
)
from fundamentals.contracts.comparison import (
    CorroborationStatus,
    ExtractionStatus,
    PairKind,
    SourceState,
)
from fundamentals.contracts.evidence import AttemptStage, RunMode
from fundamentals.contracts.measurement_key import PeriodInterval
from fundamentals.evidence.first_party_ingest import IngestError
from fundamentals.evidence.mapping import load_mapping_set
from fundamentals.evidence.selection import NOT_EXTRACTED_UNDER_PINS, NOT_INTERPRETED_UNDER_PINS
from fundamentals.pg.identity_seed import SettingKey

__all__ = ["dictionary", "ingest", "mapping_set", "policy", "runner"]

pytestmark = [pytest.mark.pg, pytest.mark.retained]

REVENUE = "revenue_from_operations"
Q2_REVENUE = Decimal("57154200000")
Q3_QUARTER = quarter(date(2025, 10, 1), Q3_END)
Q4_QUARTER = quarter(date(2026, 1, 1), Q4_END)
FY25_Q2_QUARTER = quarter(date(2024, 7, 1), FY25_Q2_END)
X = "pdf-occurrences/test-x"
X_PRIME = "pdf-occurrences/test-x-prime"
REEXTRACT = "xbrl-occurrences/test-reextract"
CORRECTED_REVENUE = MarkedEdit(
    label="corrected-revenue",
    find=b'unitRef="INR">57154200000</in-capmkt:RevenueFromOperations>',
    replace=b'unitRef="INR">57154300000</in-capmkt:RevenueFromOperations>',
)
Q4_NAMESPACE = MarkedEdit(
    label="q4-2025-namespace",
    find=b'xmlns:in-capmkt="http://www.sebi.gov.in/xbrl/2026-01-31/in-capmkt"',
    replace=b'xmlns:in-capmkt="http://www.sebi.gov.in/xbrl/2025-01-31/in-capmkt"',
)
NO_PL_TITLE = PdfRedaction(page=3, row_of="Statement", words=("financial",))
NO_BS_TITLE = PdfRedaction(page=6, row_of="Statement", words=("Liabilities",))


def _pdf_state(
    rows: tuple[ResultRow, ...], canonical_id: str = REVENUE, period: PeriodInterval = Q2_QUARTER
) -> SourceValue:
    """The first-party PDF source value of one reported row."""
    (value,) = [
        item
        for item in row(rows, canonical_id, period).source_values
        if item.representation is Representation.PDF
    ]
    return value


def _families(
    rows: tuple[ResultRow, ...], family: StatementFamily, dictionary_rows: dict[str, DictionaryRow]
) -> list[ResultRow]:
    """Reported rows of one statement family."""
    return [
        item
        for item in rows
        if dictionary_rows[item.key.canonical_id].family is family
        and item.value_identity is ValueIdentity.REPORTED
    ]


# --- atomicity and idempotency (written first) ---------------------------------------------


def test_concurrent_identical_runs_publish_one_run(runner: Runner) -> None:
    """Two threads, default cutoffs, unchanged evidence: one run, no duplicate rows."""
    runner.ingest.run(runner.ingest.intake(BOTH))
    gate = threading.Barrier(2)
    records = []
    failures: list[BaseException] = []

    def go() -> None:
        try:
            request = runner.request()
            gate.wait()
            records.append(runner.execute(request))
        except BaseException as error:  # noqa: BLE001 - surfaced through the assertion
            failures.append(error)

    threads = [threading.Thread(target=go) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert failures == []
    assert {record.run_id for record in records} == {records[0].run_id}
    assert sorted(record.created for record in records) == [False, True]
    counts = runner.run_counts()
    assert counts["runs"] == 1
    assert counts["results"] == len(runner.results(records[0].run_id))


def test_unreachable_database_exits_failure_and_writes_nothing(
    runner: Runner, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A closed loopback port: ``compare run`` exits 5 and the store gains no run."""
    runner.ingest.run(runner.ingest.intake(BOTH))
    for name, value in runner.ingest.pg_db.cli_env().items():
        monkeypatch.setenv(name, value)
    monkeypatch.setenv("EQOS_PG_HOST", "127.0.0.1")
    monkeypatch.setenv("EQOS_PG_PORT", "9")
    monkeypatch.setenv("EQOS_PG_CONNECT_TIMEOUT_S", "1")
    args = ["compare", "run", "--entity", "APARINDS", "--period-end", "2025-09-30"]
    assert main([*args, "--basis", "consolidated"]) == 5
    assert runner.run_counts()["runs"] == 0


def test_mid_publication_failure_leaves_nothing_then_rerun_succeeds(runner: Runner) -> None:
    """A failure after ``results`` are inserted rolls the whole run back."""
    runner.ingest.run(runner.ingest.intake(BOTH))
    request = runner.request()

    def fail_after_results(stage: str) -> None:
        if stage == STAGE_RESULTS:
            raise RuntimeError("injected publication failure")

    with pytest.raises(RuntimeError, match="injected"):
        runner.execute(request, publish_hook=fail_after_results)
    assert set(runner.run_counts().values()) == {0}
    record = runner.execute(request)
    assert record.created and runner.run_counts()["runs"] == 1


# --- replay ---------------------------------------------------------------------------------


def test_replay_reads_by_id_only_and_equals_stored(
    runner: Runner, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Replay over a spy reader equals the stored rows, segment-total traces included."""
    runner.ingest.run(runner.ingest.intake(BOTH))
    record = runner.run()
    stored = runner.results(record.run_id)
    revenue = row(stored, REVENUE, Q2_QUARTER)
    assert {value.value for value in revenue.source_values} == {Q2_REVENUE}
    assert revenue.extraction_status is ExtractionStatus.AGREE
    total = [
        item
        for item in stored
        if item.key.canonical_id == "segment_revenue_members_total"
        and dict(item.key.dimensions.pairs) == SEGMENT_TOTAL
        and item.key.period == Q2_QUARTER
    ][0]
    (xbrl,) = [v for v in total.source_values if v.representation is Representation.XBRL]
    assert xbrl.value == Decimal("60107900000.00") and xbrl.calculation_trace_id is not None
    (traced,) = runner.repository.get_calculation_traces([xbrl.calculation_trace_id])
    (child,) = traced.children
    assert {operand.name for operand in child.trace.operands} == set(SEGMENTS)
    spy = SpyReader(runner.repository)
    forbid_current_reads(monkeypatch)
    assert runner.replay(record.run_id, reader=spy) == stored
    assert spy.calls


def test_withheld_member_run_replays(runner: Runner) -> None:
    """A segment member withheld from the XBRL: the run still replays field by field."""
    marked = marked_xbrl(runner.ingest.tmp_path, WITHHELD_OTHERS)
    runner.ingest.run(runner.ingest.intake(XBRL_ONLY, marked={Representation.XBRL: marked}))
    record = runner.run()
    assert runner.replay(record.run_id) == runner.results(record.run_id)


def test_replay_closure_survives_four_evidence_changes(runner: Runner) -> None:
    """(a) correction, (d) presence change, (b) STANDALONE_ONLY, (c) fiscal year end."""
    ingest = runner.ingest
    original = ingest.run(ingest.intake(BOTH))
    record = runner.run()
    stored = runner.results(record.run_id)
    corrected = marked_xbrl(ingest.tmp_path, CORRECTED_REVENUE)
    ingest.run(
        ingest.intake(BOTH, marked={Representation.XBRL: corrected}),
        supersedes_package_id=original.package_id,
    )
    no_bs = marked_pdf(ingest.tmp_path, "no-bs-title", NO_BS_TITLE)
    ingest.run(ingest.intake({Representation.PDF: PDF_KIND}, marked={Representation.PDF: no_bs}))
    reseed_basis_status(ingest, "STANDALONE_ONLY")
    evidence = runner.repository.settings_as_of(
        ingest.entity_id, SettingKey.FISCAL_YEAR_END_MONTH, runner.now()
    )
    assert evidence is not None
    runner.repository.put_settings_record(
        ingest.entity_id, SettingKey.FISCAL_YEAR_END_MONTH, "12", evidence.evidence_input_id
    )
    fresh = runner.run()
    assert fresh.run_id != record.run_id
    fresh_rows = runner.results(fresh.run_id)
    assert {item.applicability for item in fresh_rows} == {ApplicabilityStatus.NOT_APPLICABLE}
    assert runner.replay(record.run_id) == stored


# --- config and pins ------------------------------------------------------------------------


def test_config_changes_give_new_runs_and_drift_is_refused(runner: Runner, tmp_path: Path) -> None:
    """Dictionary, mapping-set and definition-set versions each give a new run id."""
    runner.ingest.run(runner.ingest.intake(BOTH))
    original = runner.run()
    root = config_copy(tmp_path)
    edit_yaml(root / "dictionary" / "v2" / "metadata.yaml", {"version": "v2"})
    edit_yaml(
        root / "dictionary" / "v2" / "pl.yaml",
        rows_append={"canonical_id": "test_extra_row", "meaning": "Test-only extra P&L row."},
    )
    edit_yaml(root / "mappings" / "v2.yaml", {"version": "v2"})
    edit_yaml(root / "definition_sets" / "v2.yaml", {"version": "v2"})
    ids = {original.run_id}
    for versions in (
        ConfigVersions(dictionary="v2"),
        ConfigVersions(mapping_set="v2"),
        ConfigVersions(definition_set="v2"),
    ):
        request = runner.request(config_root=root, versions=versions)
        record = runner.execute(request, config_root=root)
        assert record.run_id not in ids
        ids.add(record.run_id)
    extra = [r for r in runner.results(max(ids)) if r.key.canonical_id == "test_extra_row"]
    assert extra == []
    dictionary_run = sorted(ids)[1]
    added = [r for r in runner.results(dictionary_run) if r.key.canonical_id == "test_extra_row"]
    assert added and all(r.dictionary_version == "v2" for r in added)
    assert runner.replay(original.run_id) == runner.results(original.run_id)
    edit_yaml(root / "definition_sets" / "v2.yaml", {"records": []}, comment="# changed\n")
    with pytest.raises(VersionContentDriftError):
        runner.run(config_root=root, versions=ConfigVersions(definition_set="v2"))


def test_new_pins_over_an_unchanged_capture(runner: Runner, tmp_path: Path) -> None:
    """Pinned to a mapping set nothing was interpreted under: UNAVAILABLE, INCOMPLETE; after
    re-ingest under it and a new XBRL extractor version the new pins show values."""
    ingest = runner.ingest
    ingest.run(ingest.intake(BOTH))
    original = runner.run()
    root = config_copy(tmp_path)
    edit_yaml(root / "mappings" / "v2.yaml", {"version": "v2"})
    versions = ConfigVersions(mapping_set="v2")
    pins = {Representation.XBRL: extractor_pin(Representation.XBRL, version=REEXTRACT)}
    before = runner.run(config_root=root, versions=versions, extractor_pins=pins)
    revenue = row(runner.results(before.run_id), REVENUE, Q2_QUARTER)
    xbrl = [v for v in revenue.source_values if v.representation is Representation.XBRL][0]
    assert xbrl.state is SourceState.UNAVAILABLE
    assert xbrl.reason in {NOT_INTERPRETED_UNDER_PINS, NOT_EXTRACTED_UNDER_PINS}
    assert before.manifest.status is RunStatus.INCOMPLETE
    remapped = load_mapping_set(root / "mappings", "v2", dictionary=ingest.dictionary)
    ingest.run(
        ingest.intake(XBRL_ONLY),
        mapping_set=remapped,
        extractor_versions={Representation.XBRL: REEXTRACT},
    )
    after = runner.run(config_root=root, versions=versions, extractor_pins=pins)
    revenue = row(runner.results(after.run_id), REVENUE, Q2_QUARTER)
    xbrl = [v for v in revenue.source_values if v.representation is Representation.XBRL][0]
    assert xbrl.state is SourceState.VALUE and xbrl.value == Q2_REVENUE
    assert runner.replay(original.run_id) == runner.results(original.run_id)


# --- failed attempts ------------------------------------------------------------------------


def test_failed_extraction_is_unavailable_and_incomplete(
    runner: Runner, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A PDF whose P&L title is removed: PDF P&L UNAVAILABLE, INCOMPLETE, CLI exit 4."""
    ingest = runner.ingest
    no_pl = marked_pdf(ingest.tmp_path, "no-pl-title", NO_PL_TITLE)
    report = ingest.run(ingest.intake(BOTH, marked={Representation.PDF: no_pl}))
    (failed,) = [
        a
        for a in report.attempts
        if a.representation is Representation.PDF and a.statement_family is StatementFamily.PL
    ]
    assert failed.outcome is ExtractionOutcome.PARSE_FAILED
    record = runner.run()
    stored = runner.results(record.run_id)
    revenue = row(stored, REVENUE, Q2_QUARTER)
    pdf = _pdf_state(stored)
    assert pdf.state is SourceState.UNAVAILABLE and pdf.attempt_id == failed.attempt_id
    assert revenue.extraction_status is ExtractionStatus.UNAVAILABLE
    assert record.manifest.status is RunStatus.INCOMPLETE
    assert runner.replay(record.run_id) == stored
    for name, value in ingest.pg_db.cli_env().items():
        monkeypatch.setenv(name, value)
    args = ["compare", "run", "--entity", "APARINDS", "--period-end", "2025-09-30"]
    assert main([*args, "--basis", "consolidated"]) == 4


def test_failure_without_a_member_decides_the_side(runner: Runner) -> None:
    """(i) package-less and (iii) historical cutoff, (iv) replay; identity hash differs."""
    ingest = runner.ingest
    ingest.run(ingest.intake(XBRL_ONLY))
    between = runner.now()
    before = runner.run()
    with pytest.raises(IngestError):
        ingest.run(failed_pdf_staging(ingest.intake({Representation.PDF: PDF_KIND})))
    (attempt,) = [
        a
        for a in runner.repository.list_attempts(ingest.entity_id, Q2_END)
        if a.stage is AttemptStage.ACQUISITION
    ]
    assert attempt.package_id is None and attempt.capture is None
    assert attempt.attempted_at is not None and attempt.attempted_at > between
    after = runner.run()
    pdf = _pdf_state(runner.results(after.run_id))
    assert pdf.state is SourceState.UNAVAILABLE and pdf.attempt_id == attempt.attempt_id
    assert after.manifest.identity_hash() != before.manifest.identity_hash()
    historical = runner.run(cutoff=between)
    assert _pdf_state(runner.results(historical.run_id)).state is SourceState.NO_VALUE
    for record in (after, historical):
        assert runner.replay(record.run_id) == runner.results(record.run_id)


def test_failed_member_of_a_built_package(runner: Runner) -> None:
    """(ii) the failed PDF attempt carries the package id: UNAVAILABLE, not NO_VALUE."""
    ingest = runner.ingest
    with pytest.raises(IngestError):
        ingest.run(failed_pdf_staging(ingest.intake(BOTH)))
    (attempt,) = [
        a
        for a in runner.repository.list_attempts(ingest.entity_id, Q2_END)
        if a.stage is AttemptStage.ACQUISITION
    ]
    assert attempt.package_id is not None
    record = runner.run()
    pdf = _pdf_state(runner.results(record.run_id))
    assert pdf.state is SourceState.UNAVAILABLE and pdf.attempt_id == attempt.attempt_id
    assert runner.replay(record.run_id) == runner.results(record.run_id)


def test_generations_modes_and_isolation(runner: Runner) -> None:
    """(v) failure → success, (vi) family failure, (vii) modes, (viii) isolation."""
    ingest = runner.ingest
    specs = dict(apar_pdf_specs())
    specs[StatementFamily.PL] = specs[StatementFamily.PL].model_copy(
        update={"title_markers": ("no such statement title",)}
    )
    first = ingest.run(
        ingest.intake(BOTH), pdf_specs=specs, extractor_versions={Representation.PDF: X}
    )
    (failed,) = [
        a
        for a in first.attempts
        if a.representation is Representation.PDF and a.statement_family is StatementFamily.PL
    ]
    between = runner.now()
    ingest.run(ingest.intake(BOTH), extractor_versions={Representation.PDF: X_PRIME})
    pinned_x = {Representation.PDF: extractor_pin(Representation.PDF, version=X)}
    pinned_x_prime = {Representation.PDF: extractor_pin(Representation.PDF, version=X_PRIME)}
    on_x = runner.run(extractor_pins=pinned_x)
    rows_x = runner.results(on_x.run_id)
    assert _pdf_state(rows_x).state is SourceState.UNAVAILABLE
    assert _pdf_state(rows_x).attempt_id == failed.attempt_id
    assets = _pdf_state(rows_x, "total_assets", PeriodInterval.at(Q2_END))
    assert assets.state is SourceState.VALUE
    on_x_prime = runner.run(extractor_pins=pinned_x_prime)
    rows_x_prime = runner.results(on_x_prime.run_id)
    assert _pdf_state(rows_x_prime).value == Q2_REVENUE
    for record in (on_x, on_x_prime):
        assert runner.replay(record.run_id) == runner.results(record.run_id)
    known = runner.run(cutoff=between, extractor_pins=pinned_x_prime)
    known_pdf = _pdf_state(runner.results(known.run_id))
    assert (known_pdf.state, known_pdf.reason) == (
        SourceState.UNAVAILABLE,
        NOT_EXTRACTED_UNDER_PINS,
    )
    retro = runner.run(cutoff=between, mode=RunMode.RETROSPECTIVE, extractor_pins=pinned_x_prime)
    assert _pdf_state(runner.results(retro.run_id)).value == Q2_REVENUE
    for mode in RunMode:
        record = runner.run(cutoff=between, mode=mode, extractor_pins=pinned_x)
        assert _pdf_state(runner.results(record.run_id)).attempt_id == failed.attempt_id
    overall = [
        a
        for a in first.attempts
        if a.representation is Representation.PDF and a.statement_family is None
    ]
    noise = [
        overall[0].model_copy(
            update={
                "attempt_id": None,
                "basis": Basis.STANDALONE,
                "outcome": ExtractionOutcome.PARSE_FAILED,
            }
        ),
        overall[0].model_copy(
            update={
                "attempt_id": None,
                "extractor_version": "pdf-occurrences/unpinned",
                "outcome": ExtractionOutcome.PARSE_FAILED,
            }
        ),
    ]
    runner.repository.put_attempts(noise)
    isolated = runner.run(extractor_pins=pinned_x_prime)
    assert _pdf_state(runner.results(isolated.run_id)).value == Q2_REVENUE


# --- coverage of period kinds ---------------------------------------------------------------


def test_one_member_package_is_one_side_xbrl(runner: Runner) -> None:
    """FY25 Q2 has only an XBRL member: ONE_SIDE_XBRL, COMPLETE."""
    ingest = runner.ingest
    ingest.run(
        ingest.intake({Representation.XBRL: "xbrl-consolidated-comparator"}, Q2_FY25),
        FY25_Q2_END,
    )
    record = runner.run(FY25_Q2_END)
    revenue = row(runner.results(record.run_id), REVENUE, FY25_Q2_QUARTER)
    assert revenue.extraction_status is ExtractionStatus.ONE_SIDE_XBRL
    assert record.manifest.status is RunStatus.COMPLETE


def test_q4_stores_reported_and_derived_with_a_pair(runner: Runner) -> None:
    """FY26 Q4: REPORTED Q4 revenue and DERIVED Q4 = FY − 9M (9M from the Q3 package).

    The Q4 instance is filed under the 2026-01-31 taxonomy, which mapping set v1 does not
    cover (ingest records UNSUPPORTED_SCHEMA), so the test reads a marked copy whose
    in-capmkt namespace is the 2025-01-31 one; every fact is the filing's own.
    FY 229,021,200,000 − 9M 162,993,200,000 = 66,028,000,000; reported Q4 66,028,100,000.
    """
    ingest = runner.ingest
    ingest.run(ingest.intake(XBRL_ONLY, Q3_FY26), Q3_END)
    q4 = marked_copy(apar_original(Q4_FY26, XBRL_KIND), edit=Q4_NAMESPACE, tmp_path=ingest.tmp_path)
    ingest.run(ingest.intake(XBRL_ONLY, Q4_FY26, marked={Representation.XBRL: q4}), Q4_END)
    record = runner.run(Q4_END)
    stored = runner.results(record.run_id)
    reported = row(stored, REVENUE, Q4_QUARTER)
    derived = row(stored, REVENUE, Q4_QUARTER, ValueIdentity.DERIVED)
    assert reported.row_id != derived.row_id
    (xbrl,) = [
        v
        for v in derived.source_values
        if v.representation is Representation.XBRL and v.calculation_trace_id is not None
    ]
    assert xbrl.value == Decimal("66028000000")
    (reported_xbrl,) = [
        v for v in reported.source_values if v.representation is Representation.XBRL
    ]
    assert reported_xbrl.value == Decimal("66028100000")
    (trace,) = runner.repository.get_calculation_traces([xbrl.calculation_trace_id])
    assert [operand.value for operand in trace.trace.operands] == [
        Decimal("229021200000"),
        Decimal("162993200000"),
    ]
    pairs = [p for p in derived.pairs if p.pair_kind is PairKind.REPORTED_VS_DERIVED]
    assert len(pairs) == 1 and pairs[0].difference is not None
    assert runner.replay(record.run_id) == stored


def test_q3_balance_sheet_and_cash_flow_are_not_applicable(runner: Runner) -> None:
    """Q3 files no balance sheet or cash flow: NOT_APPLICABLE with rule ids, never NO_SOURCE."""
    ingest = runner.ingest
    ingest.run(ingest.intake(XBRL_ONLY, Q3_FY26), Q3_END)
    ingest.run(ingest.intake(BOTH))
    rows_by_id = {item.canonical_id: item for item in ingest.dictionary.rows}
    q3 = runner.results(runner.run(Q3_END).run_id)
    q2 = runner.results(runner.run(Q2_END).run_id)
    for family in (StatementFamily.BALANCE_SHEET, StatementFamily.CASH_FLOW):
        q3_rows = _families(q3, family, rows_by_id)
        assert q3_rows
        for item in q3_rows:
            assert item.applicability is ApplicabilityStatus.NOT_APPLICABLE
            assert item.applicability_rule_id
            assert item.corroboration_status is CorroborationStatus.NOT_APPLICABLE
        assert any(
            item.applicability is ApplicabilityStatus.APPLICABLE
            for item in _families(q2, family, rows_by_id)
        )


# --- report and schema ----------------------------------------------------------------------


def test_report_cli_prints_the_run(
    runner: Runner, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """``compare report --run`` prints the run id, the header and the revenue row."""
    runner.ingest.run(runner.ingest.intake(BOTH))
    record = runner.run()
    for name, value in runner.ingest.pg_db.cli_env().items():
        monkeypatch.setenv(name, value)
    capsys.readouterr()
    assert main(["compare", "report", "--run", str(record.run_id)]) == 0
    printed = capsys.readouterr().out
    assert printed.startswith(f"run\t{record.run_id}\n")
    assert "5715.42 crore" in printed
    args = ["compare", "report", "--entity", "APARINDS", "--period-end", "2025-09-30"]
    assert main([*args, "--basis", "consolidated"]) == 0
    assert capsys.readouterr().out.startswith(f"run\t{record.run_id}\n")


def test_resolution_failure_publishes_nothing(runner: Runner) -> None:
    """A period end that is not a fiscal quarter end fails closed before publication."""
    runner.ingest.run(runner.ingest.intake(BOTH))
    with pytest.raises(RunResolutionError):
        runner.run(date(2025, 8, 31))
    assert runner.run_counts()["runs"] == 0


def test_every_enum_value_round_trips_through_its_check(runner: Runner) -> None:
    """Every stored enum value is accepted by its table's CHECK constraint."""
    runner.ingest.run(runner.ingest.intake(BOTH))
    record = runner.run()
    assert enum_round_trip(runner, record.run_id) == []
    with runner.pool.connection() as conn, pytest.raises(errors.CheckViolation):
        conn.execute(
            "INSERT INTO eqos.run_versions (run_id, pin, version, content_sha256) "
            "VALUES (0, 'NOT_AN_ARTIFACT', 'v', 'x')"
        )
