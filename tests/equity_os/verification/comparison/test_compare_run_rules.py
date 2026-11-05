"""Run rules from the D1a phase review, Area C, over retained Apar originals (D1a Task 9).

Each case reproduces one review scenario: condition proofs under the run's pins, formula
context from operand statements, derived extraction with tagging adjustments, source scope,
a one-connection pool, the report's dictionary pin and provenance, configuration failures,
single-entity scope and operational failures. Expected values are the filing's own (Apar Q2
FY26 consolidated XBRL finance costs 1,079,000,000 INR = PDF p3 (e) 107.90 crore); altered
inputs are marked copies under ``tmp_path`` or rows written through the repository.
"""

from __future__ import annotations

import hashlib
from decimal import Decimal
from pathlib import Path

import pytest
from derived_support import scope_formula, xbrl_scope
from evidence_support import (
    BOTH,
    CONFIG,
    Q2_END,
    Q2_QUARTER,
    XBRL_ONLY,
    dictionary,
    ingest,
    mapping_set,
    marked_xbrl,
    policy,
)
from pydantic import ValidationError
from retained_support import MarkedEdit, marked_pdf
from run_support import Q3_END, Q3_FY26, Runner, config_copy, edit_yaml, row, runner

from equity_os.contracts.measurement.canonical import (
    ApplicabilityStatus,
    Basis,
    Representation,
    StatementFamily,
    ValueIdentity,
    ValueKind,
)
from equity_os.contracts.measurement.evidence import (
    AttemptStage,
    FilingFamily,
    Interpretation,
    InterpretationReason,
    InterpretationStatus,
    RevisionCause,
)
from equity_os.contracts.measurement.evidence_tier import EvidenceTier
from equity_os.contracts.measurement.interval import Interval
from equity_os.contracts.measurement.measurement_key import PeriodInterval
from equity_os.contracts.sourcing.acquisition_outcome import ExtractionOutcome
from equity_os.contracts.verification.comparison import ExtractionStatus, SourceState
from equity_os.interface.entry.cli import main
from equity_os.storage.database.pool import open_pool
from equity_os.storage.database.settings import PgRole
from equity_os.verification.comparison.run import (
    RunExitStatus,
    RunScope,
    RunStatus,
    execute_run,
    operational_failures,
)
from equity_os.verification.comparison.run_config import ConfigVersions
from equity_os.verification.comparison.run_models import (
    FIRST_PARTY_SOURCES,
    RunInputDisposition,
    RunInputKind,
)
from equity_os.verification.comparison.run_store import RunStore
from equity_os.verification.comparison.tables import TaggingAdjustment

__all__ = ["dictionary", "ingest", "mapping_set", "policy", "runner"]

REVENUE = "revenue_from_operations"
OPM = "opm_pct"
OPEX = "opex_excl_finance_and_da"
FINANCE = "finance_costs"
# Absent from every observed XBRL instance (dictionary v1 pl.yaml): no pinned interpretation.
CONDITION_ROW = "excise_duty"
CONDITION_ID = "test-no-excise-duty"
OLDER_MAPPING = "test-older-mapping"
OTHER_SURFACE = "BSE_RESULTS_PDF"
XBRL_SURFACE = "NSE_XBRL_INSTANCE"
FINANCE_RECORD = "FC-TEST"
# One crore: the marked XBRL finance costs minus the filed (and PDF) 107.90 crore.
FINANCE_SHIFT = Decimal("10000000")
FINANCE_PLUS_ONE_CRORE = MarkedEdit(
    label="finance-costs-plus-one-crore",
    find=b'<in-capmkt:FinanceCosts contextRef="OneD" decimals="-6" unitRef="INR">'
    b"1079000000</in-capmkt:FinanceCosts>",
    replace=b'<in-capmkt:FinanceCosts contextRef="OneD" decimals="-6" unitRef="INR">'
    b"1089000000</in-capmkt:FinanceCosts>",
)
NO_PL_TITLE_PAGE = 3


def _cli(runner: Runner, monkeypatch: pytest.MonkeyPatch) -> None:
    """Point the in-process CLI at the test database."""
    for name, value in runner.ingest.pg_db.cli_env().items():
        monkeypatch.setenv(name, value)


def _source(rows: object, canonical_id: str, representation: Representation, **where: object):  # type: ignore[no-untyped-def]
    """The first-party source value of one undimensioned row."""
    found = row(rows, canonical_id, **where)  # type: ignore[arg-type]
    (value,) = [
        item
        for item in found.source_values
        if item.representation is representation and item.source_role.value == "FIRST_PARTY"
    ]
    return value


def _xbrl_template(runner: Runner, package_id: int) -> Interpretation:
    """The pinned XBRL revenue interpretation of the Q2 quarter (a row to copy from)."""
    (package,) = runner.repository.get_packages([package_id])
    capture = package.members[Representation.XBRL].capture.capture_ref_id
    assert capture is not None
    (template,) = [
        item
        for item in runner.repository.list_capture_interpretations(capture)
        if item.key is not None
        and item.key.canonical_id == REVENUE
        and item.key.period == Q2_QUARTER
        and not item.key.dimensions.pairs
        and item.status is InterpretationStatus.MAPPED
    ]
    return template


def _condition_interpretation(
    runner: Runner, template: Interpretation, label: str, **update: object
) -> Interpretation:
    """A test interpretation of the condition row on the template's capture, stored."""
    assert template.key is not None
    (interpretation_id,) = runner.repository.reserve_interpretation_ids(1)
    item = template.model_copy(
        update={
            "interpretation_id": interpretation_id,
            "canonical_id": CONDITION_ROW,
            "key": template.key.model_copy(update={"canonical_id": CONDITION_ROW}),
            "input_digest": hashlib.sha256(label.encode()).hexdigest(),
            "mapping_entry_id": f"test.{label}",
            **update,
        }
    )
    runner.repository.put_interpretations([item])
    return item


def _opm_formula_tier(runner: Runner, run_id: int) -> EvidenceTier | None:
    """The stored XBRL OPM trace's own formula tier for the Q2 quarter."""
    rows = runner.results(run_id)
    value = _source(
        rows, OPM, Representation.XBRL, period=Q2_QUARTER, identity=ValueIdentity.DERIVED
    )
    assert value.calculation_trace_id is not None
    (stored,) = runner.repository.get_calculation_traces([value.calculation_trace_id])
    return stored.trace.formula_tier


# --- C1: qualification conditions under the run's pins ------------------------------------------


@pytest.mark.pg
@pytest.mark.retained
def test_condition_proof_reads_only_the_pinned_selection(runner: Runner, tmp_path: Path) -> None:
    """A pinned zero proves the condition; once a pinned INVALID correction supersedes it,
    an older-triple zero must not prove it (review C1)."""
    ingest = runner.ingest
    report = ingest.run(ingest.intake(BOTH))
    root = config_copy(tmp_path)
    scope = xbrl_scope("test-opm-scope", ["CONSOLIDATED"], ["QUARTER"])
    # Constructed qualification metadata tests run pin/condition plumbing only; these
    # synthetic fixtures do not establish the production dictionary's equivalence tier.
    scope["fixture_evidence"] = [
        {
            "capture_id": f"constructed-{index}",
            "capture_sha256": hashlib.sha256(f"constructed-{index}".encode()).hexdigest(),
            "entity_id": index,
            "discriminating": index == 1,
        }
        for index in range(1, 6)
    ]
    scope["sample_rule"] = "constructed five-entity sample for condition-selection plumbing"
    scope["conditions"] = [
        {"condition_id": CONDITION_ID, "canonical_id": CONDITION_ROW, "predicate": "EQUALS_ZERO"}
    ]
    derived = root / "normalisation/dictionary" / "v2" / "derived.yaml"
    edit_yaml(root / "normalisation/dictionary" / "v2" / "metadata.yaml", {"version": "v2"})
    data = __import__("yaml").safe_load(derived.read_text(encoding="utf-8"))
    scope_formula(OPM, scope)(data)
    derived.write_text(__import__("yaml").safe_dump(data, sort_keys=False), encoding="utf-8")
    versions = ConfigVersions(dictionary="v2")
    assert report.package_id is not None
    template = _xbrl_template(runner, report.package_id)
    zero = Interval.exact(Decimal(0))
    pinned_zero = _condition_interpretation(
        runner, template, "pinned-zero", value=Decimal(0), interval=zero
    )
    proven = runner.run(config_root=root, versions=versions)
    assert _opm_formula_tier(runner, proven.run_id) is EvidenceTier.EQUIVALENCE_DEMONSTRATED
    assert any(
        item.kind is RunInputKind.INTERPRETATION
        and item.ref_id == pinned_zero.interpretation_id
        and item.disposition is RunInputDisposition.SELECTED
        for item in proven.manifest.inputs
    )

    _condition_interpretation(
        runner,
        template,
        "pinned-invalid-correction",
        status=InterpretationStatus.INVALID,
        value=None,
        interval=None,
        reason=InterpretationReason.PRECISION_UNSUPPORTED,
        revision_cause=RevisionCause.PARSER_REEXTRACTION,
        supersedes_interpretation_id=pinned_zero.interpretation_id,
    )
    _condition_interpretation(
        runner,
        template,
        "older-triple-zero",
        value=Decimal(0),
        interval=zero,
        mapping_set_version=OLDER_MAPPING,
    )
    record = runner.run(config_root=root, versions=versions)
    assert record.run_id != proven.run_id
    assert _opm_formula_tier(runner, record.run_id) is EvidenceTier.EQUIVALENCE_UNPROVEN
    assert runner.replay(record.run_id, config_root=root) == runner.results(record.run_id)


# --- C2: a statement correction reaches the formulas over it -----------------------------------


@pytest.mark.pg
@pytest.mark.retained
def test_statement_correction_reaches_the_formula_context(runner: Runner) -> None:
    """Q3 files no balance sheet; a later package replacing only the balance sheet makes the
    balance-sheet rows and the formulas over them applicable alike (review C2)."""
    ingest = runner.ingest
    ingest.run(ingest.intake(XBRL_ONLY, Q3_FY26), Q3_END)
    (original,) = runner.repository.list_packages(
        ingest.entity_id, FilingFamily.FINANCIAL_RESULTS, Q3_END
    )
    assert StatementFamily.BALANCE_SHEET not in original.statements_present
    correction = original.model_copy(
        update={
            "package_id": None,
            "supersedes_package_id": original.package_id,
            "replaced_statements": frozenset({StatementFamily.BALANCE_SHEET}),
            "statements_present": frozenset({StatementFamily.BALANCE_SHEET}),
            "knowledge_time": runner.now(),
            "evidence_sha256": hashlib.sha256(b"test-q3-balance-sheet-correction").hexdigest(),
        }
    )
    runner.repository.put_package(correction, statement_evidence={})
    record = runner.run(Q3_END)
    rows = runner.results(record.run_id)
    instant = PeriodInterval.at(Q3_END)
    assert (
        row(rows, "current_assets_total", instant).applicability is ApplicabilityStatus.APPLICABLE
    )
    formula = row(rows, "net_current_assets", instant, ValueIdentity.DERIVED)
    assert formula.applicability is ApplicabilityStatus.APPLICABLE
    assert runner.replay(record.run_id) == rows


# --- C3: derived extraction with operand tagging adjustments ------------------------------------


@pytest.mark.pg
@pytest.mark.retained
def test_operand_tagging_difference_reconciles_the_formula_over_it(
    runner: Runner,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """XBRL finance costs one crore above the PDF, explained by a mapping record: finance costs
    TAGGING_DIFFERENCE, opex TAGGING_DIFFERENCE through a stored adjustment (review C3, C9)."""
    ingest = runner.ingest
    root = config_copy(tmp_path)
    record_yaml = {
        "record_id": FINANCE_RECORD,
        "scope": "MAPPING",
        "scope_ref": "capmkt.finance_costs",
        "canonical_id": FINANCE,
        "operand_name": FINANCE,
        "evidence_ref": "test: marked XBRL copy, finance costs one crore above PDF p3 (e)",
        "explained_amount": str(FINANCE_SHIFT),
        "unit": "CURRENCY_AMOUNT",
    }
    edit_yaml(
        root / "verification/definition_sets" / "v2.yaml",
        {"version": "v2", "records": [record_yaml]},
    )
    marked = marked_xbrl(ingest.tmp_path, FINANCE_PLUS_ONE_CRORE)
    ingest.run(ingest.intake(BOTH, marked={Representation.XBRL: marked}))
    record = runner.run(config_root=root, versions=ConfigVersions(definition_set="v2"))
    rows = runner.results(record.run_id)
    finance = row(rows, FINANCE, Q2_QUARTER)
    assert finance.extraction_status is ExtractionStatus.TAGGING_DIFFERENCE
    opex = row(rows, OPEX, Q2_QUARTER, ValueIdentity.DERIVED)
    assert opex.extraction_status is ExtractionStatus.TAGGING_DIFFERENCE
    (pair,) = opex.pairs
    assert pair.adjustments == (
        TaggingAdjustment(
            operand_name=FINANCE,
            representation=Representation.XBRL,
            direction=-1,
            amount=FINANCE_SHIFT,
            unit=ValueKind.CURRENCY_AMOUNT,
            definition_record_id=FINANCE_RECORD,
        ),
    )
    assert runner.replay(record.run_id, config_root=root) == rows
    _cli(runner, monkeypatch)
    capsys.readouterr()
    args = ["compare", "report", "--run", str(record.run_id), "--config-root", str(root)]
    assert main(args) == RunExitStatus.SUCCESS
    printed = capsys.readouterr().out
    assert f"definition={FINANCE_RECORD}" in printed
    assert f"adjust={FINANCE}:XBRL:-{FINANCE_SHIFT}:{FINANCE_RECORD}" in printed


# --- C4: only requested sources decide a side ---------------------------------------------------


@pytest.mark.pg
@pytest.mark.retained
def test_unrequested_sources_never_decide_a_side(runner: Runner) -> None:
    """A package-less failed PDF acquisition on another surface leaves the PDF side NO_VALUE;
    a run requesting only XBRL never reads the PDF member (review C4)."""
    ingest = runner.ingest
    ingest.run(ingest.intake(XBRL_ONLY))
    (extraction,) = [
        a
        for a in runner.repository.list_attempts(ingest.entity_id, Q2_END)
        if a.stage is AttemptStage.EXTRACTION and a.statement_family is None
    ]
    elsewhere = extraction.model_copy(
        update={
            "attempt_id": None,
            "stage": AttemptStage.ACQUISITION,
            "representation": Representation.PDF,
            "surface": OTHER_SURFACE,
            "extractor_version": "",
            "extraction_context_sha256": None,
            "package_id": None,
            "capture": None,
            "outcome": ExtractionOutcome.FAILED,
        }
    )
    runner.repository.put_attempts([elsewhere])
    record = runner.run()
    pdf = _source(runner.results(record.run_id), REVENUE, Representation.PDF, period=Q2_QUARTER)
    assert (pdf.state, pdf.attempt_id) == (SourceState.NO_VALUE, None)
    assert record.manifest.status is RunStatus.COMPLETE

    ingest.run(ingest.intake(BOTH))
    request = runner.request()
    xbrl_only = request.model_copy(
        update={"scope": request.scope.model_copy(update={"sources": (XBRL_SURFACE,)})}
    )
    rows = runner.results(runner.execute(xbrl_only).run_id)
    pdf = _source(rows, REVENUE, Representation.PDF, period=Q2_QUARTER)
    assert pdf.state is SourceState.NO_VALUE and pdf.interpretation_id is None
    assert _source(rows, REVENUE, Representation.XBRL, period=Q2_QUARTER).value is not None


@pytest.mark.pg
@pytest.mark.retained
def test_package_on_an_excluded_source_never_supersedes_the_requested_source(
    runner: Runner,
) -> None:
    """A PDF-only correction cannot hide the selected XBRL in an XBRL-only run."""
    ingest = runner.ingest
    report = ingest.run(ingest.intake(BOTH))
    assert report.package_id is not None
    (original,) = runner.repository.get_packages([report.package_id])
    correction = original.model_copy(
        update={
            "package_id": None,
            "members": {Representation.PDF: original.members[Representation.PDF]},
            "supersedes_package_id": original.package_id,
            "replaced_statements": frozenset({StatementFamily.PL}),
            "knowledge_time": runner.now(),
            "evidence_sha256": hashlib.sha256(b"test-pdf-only-correction").hexdigest(),
        }
    )
    runner.repository.put_package(correction, statement_evidence={})
    request = runner.request()
    xbrl_only = request.model_copy(
        update={"scope": request.scope.model_copy(update={"sources": (XBRL_SURFACE,)})}
    )
    record = runner.execute(xbrl_only)
    rows = runner.results(record.run_id)
    xbrl = _source(rows, REVENUE, Representation.XBRL, period=Q2_QUARTER)
    assert xbrl.state is SourceState.VALUE
    assert xbrl.value == Decimal("57154200000")
    assert runner.replay(record.run_id) == rows


def test_run_scope_holds_one_entity_and_known_sources() -> None:
    """Row ids carry no entity: two entities are refused, as are unknown or no sources
    (review C7 ruling; C4)."""
    common = {"period_ends": (Q3_END,), "bases": (Basis.CONSOLIDATED,)}
    assert RunScope(entity_ids=(1,), sources=FIRST_PARTY_SOURCES, **common).entity_ids == (1,)
    for entity_ids, sources in (
        ((1, 2), FIRST_PARTY_SOURCES),
        ((), FIRST_PARTY_SOURCES),
        ((1,), ()),
        ((1,), (OTHER_SURFACE,)),
    ):
        with pytest.raises(ValidationError):
            RunScope(entity_ids=entity_ids, sources=sources, **common)


# --- C5: one pooled connection suffices -----------------------------------------------------------


@pytest.mark.pg
@pytest.mark.retained
def test_a_one_connection_pool_executes_a_run(runner: Runner) -> None:
    """Pinning never holds a connection while it takes another (review C5)."""
    ingest = runner.ingest
    ingest.run(ingest.intake(BOTH))
    settings = ingest.pg_db.settings.model_copy(update={"pool_min_size": 1, "pool_max_size": 1})
    with open_pool(settings, PgRole.RUNTIME, dbname=ingest.pg_db.dbname) as pool:
        record = execute_run(runner.request(), pool=pool, config_root=CONFIG)
    assert record.created


# --- C6, C8: configuration refused with exit FAILURE ------------------------------------------


@pytest.mark.pg
@pytest.mark.retained
def test_report_refuses_a_dictionary_that_differs_from_the_pin(
    runner: Runner,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Same dictionary version, other content: the report exits FAILURE (review C6)."""
    runner.ingest.run(runner.ingest.intake(BOTH))
    root = config_copy(tmp_path)
    record = runner.run(config_root=root)
    edit_yaml(
        root / "normalisation/dictionary" / "v1" / "pl.yaml",
        rows_append={"canonical_id": "test_extra_row", "meaning": "Test-only extra P&L row."},
    )
    _cli(runner, monkeypatch)
    args = ["compare", "report", "--run", str(record.run_id)]
    assert main([*args, "--config-root", str(root)]) == RunExitStatus.FAILURE
    assert main([*args, "--config-root", str(CONFIG)]) == RunExitStatus.SUCCESS
    capsys.readouterr()


@pytest.mark.pg
@pytest.mark.parametrize(
    ("relative", "text"),
    [
        pytest.param(
            "verification/comparison_policy/v1.yaml",
            "policy_id: comparison\nversion: v1\nmagnitude_threshold: 0.005\n",
            id="float-threshold",
        ),
        pytest.param(
            "verification/definition_sets/v1.yaml",
            "version: v1\nrecords:\n- record_id: X\n",
            id="incomplete-definition-record",
        ),
        pytest.param(
            "verification/definition_sets/v1.yaml",
            "version: v1\nrecords:\n- record_id: X\n  scope: FILING\n"
            "  scope_ref: not-a-package\n  canonical_id: finance_costs\n"
            "  evidence_ref: test:invalid-reference\n  explained_amount: '1'\n"
            "  unit: CURRENCY_AMOUNT\n",
            id="invalid-filing-definition-reference",
        ),
        pytest.param(
            "verification/comparison_policy/v1.yaml", "policy_id: [unclosed\n", id="malformed-yaml"
        ),
    ],
)
def test_configuration_errors_exit_failure(
    runner: Runner,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    relative: str,
    text: str,
) -> None:
    """A malformed policy, definition set or YAML file exits FAILURE, never a traceback
    (review C8)."""
    assert runner.repository.entity_id("APARINDS") is not None
    root = config_copy(tmp_path)
    (root / relative).write_text(text, encoding="utf-8")
    _cli(runner, monkeypatch)
    args = ["compare", "run", "--entity", "APARINDS", "--period-end", "2025-09-30"]
    assert main([*args, "--basis", "consolidated", "--config-root", str(root)]) == 5
    assert runner.run_counts()["runs"] == 0


# --- C9, C11: provenance, labels and operational failures ---------------------------------------


@pytest.mark.pg
@pytest.mark.retained
def test_failures_and_provenance_are_reported(
    runner: Runner, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A failed PDF P&L read is an operational failure naming its attempt, replayed alike;
    the report labels and anchors every value (review C9, C11)."""
    ingest = runner.ingest
    no_pl = marked_pdf(ingest.tmp_path, "no-pl-title", _no_pl_title())
    report = ingest.run(ingest.intake(BOTH, marked={Representation.PDF: no_pl}))
    (failed,) = [
        a
        for a in report.attempts
        if a.representation is Representation.PDF and a.statement_family is StatementFamily.PL
    ]
    record = runner.run()
    failures = record.manifest.operational_failures
    assert f"PDF\tPARSE_FAILED\tattempt={failed.attempt_id}" in failures
    assert all(item.startswith("PDF\t") for item in failures)
    assert RunStore(runner.pool).read_manifest(record.run_id).operational_failures == failures
    assert operational_failures(runner.replay(record.run_id)) == failures

    rows = runner.results(record.run_id)
    xbrl = _source(rows, REVENUE, Representation.XBRL, period=Q2_QUARTER)
    assert xbrl.interpretation_id is not None
    (interpretation,) = runner.repository.get_interpretations([xbrl.interpretation_id])
    assert interpretation.occurrence_id is not None
    (occurrence,) = runner.repository.get_occurrences([interpretation.occurrence_id])
    _cli(runner, monkeypatch)
    capsys.readouterr()
    assert main(["compare", "report", "--run", str(record.run_id)]) == RunExitStatus.SUCCESS
    printed = capsys.readouterr().out
    assert f"failure\tPDF\tPARSE_FAILED\tattempt={failed.attempt_id}\n" in printed
    anchor = f"capture:{occurrence.capture.capture_ref_id}:{occurrence.anchor_key}"
    assert f"class=OBSERVED\tinterpretation={xbrl.interpretation_id}\tanchor={anchor}" in printed
    assert f"UNAVAILABLE\t-\tINR\tclass=OBSERVED\tattempt={failed.attempt_id}" in printed
    assert "class=COMPUTED\ttrace=" in printed
    assert "\treason=" in printed.split("  pair\t", 1)[1]


def _no_pl_title():  # type: ignore[no-untyped-def]
    """The P&L statement title redaction used by the failed-extraction run test."""
    from test_compare_runs import NO_PL_TITLE

    assert NO_PL_TITLE.page == NO_PL_TITLE_PAGE
    return NO_PL_TITLE
